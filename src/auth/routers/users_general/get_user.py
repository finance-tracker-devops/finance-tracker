from fastapi import APIRouter, status
from src.auth.utils.jwt.general import get_user
from src.auth.utils.validator import check_phone_number
from src.auth.schema.response import ResponseDefault, UniqueID
from src.auth.routers.exceptions import (
    EntityDoesNotExistError,
    ServiceError,
    FinanceTrackerApiError,
)

router = APIRouter(tags=["users-general"], prefix="/users")


async def get_user_endpoint(phone_number: str) -> ResponseDefault:
    response = ResponseDefault()
    try:
        validated_phone_number = await check_phone_number(phone_number=phone_number)
        account = await get_user(phone_number=validated_phone_number)

        if not account:
            raise EntityDoesNotExistError(detail="User not found.")

        if not account.verified_phone_number:
            response.success = True
            response.message = "User should validate phone number first."
            response.data = UniqueID(unique_id=str(account.user_uuid))

            return response

        response.success = True
        response.message = "User found."
        response.data = UniqueID(unique_id=str(account.user_uuid))

    except FinanceTrackerApiError as FTE:
        raise FTE

    except Exception as e:
        raise ServiceError(detail=f"Service error: {e}.", name="Finance Tracker")

    return response


router.add_api_route(
    methods=["GET"],
    path="/get-user",
    response_model=ResponseDefault,
    endpoint=get_user_endpoint,
    status_code=status.HTTP_200_OK,
    summary="Get unique id user.",
)
