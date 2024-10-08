from pytz import timezone
from datetime import datetime
from typing import Annotated
from src.auth.utils.logging import logging
from fastapi import APIRouter, status, Depends
from src.auth.utils.validator import check_otp
from src.auth.schema.response import ResponseDefault
from src.auth.utils.jwt.general import get_current_user
from src.auth.utils.request_format import OTPVerification
from src.auth.routers.exceptions import (
    ServiceError,
    FinanceTrackerApiError,
    EntityAlreadyVerifiedError,
    MandatoryInputError,
    EntityDoesNotExistError,
    InvalidOperationError,
)
from src.auth.utils.database.general import (
    extract_data_otp,
    update_verify_email_status,
)

router = APIRouter(tags=["account-verification"], prefix="/verify")


async def verify_email_endpoint(
    schema: OTPVerification,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ResponseDefault:
    response = ResponseDefault()

    try:
        initials_account = await extract_data_otp(user_uuid=current_user.user_uuid)
        now_utc = datetime.now(timezone("UTC"))

        if not initials_account:
            logging.info("OTP data not found.")
            raise EntityDoesNotExistError(detail="Data not found.")

        if not current_user.email:
            logging.info("User is not input email yet.")
            raise MandatoryInputError(detail="User should add email first.")

        if current_user.verified_email:
            logging.info("User email already verified.")
            raise EntityAlreadyVerifiedError(detail="User email already verified.")

        await check_otp(otp=schema.otp)

        if now_utc > initials_account.blacklisted_at:
            raise InvalidOperationError(detail="OTP already expired.")

        if initials_account.otp_number != schema.otp:
            raise InvalidOperationError(detail="Invalid OTP code.")

        if (
            now_utc < initials_account.blacklisted_at
            and initials_account.otp_number == schema.otp
        ):
            await update_verify_email_status(user_uuid=current_user.user_uuid)

            response.success = True
            response.message = "User email verified."

    except FinanceTrackerApiError as FTE:
        raise FTE

    except Exception as E:
        raise ServiceError(detail=f"Service error: {E}.", name="Finance Tracker")

    return response


router.add_api_route(
    methods=["POST"],
    path="/email",
    endpoint=verify_email_endpoint,
    response_model=ResponseDefault,
    status_code=status.HTTP_200_OK,
    summary="User email verification.",
)
