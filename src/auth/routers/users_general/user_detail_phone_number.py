from typing import Annotated
from fastapi import APIRouter, status, Depends
from src.auth.schema.response import ResponseDefault
from src.auth.utils.jwt.general import get_current_user
from src.auth.routers.exceptions import ServiceError, FinanceTrackerApiError

router = APIRouter(tags=["users-general"], prefix="/users")


async def user_detail_phone_number_endpoint(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ResponseDefault:
    response = ResponseDefault()
    try:
        response.success = True
        response.message = (
            f"Extracting account {current_user.full_name} phone number info."
        )
        response.data = current_user.to_detail_user_phone_number().dict()
    except FinanceTrackerApiError as FTE:
        raise FTE
    except Exception as E:
        raise ServiceError(detail=f"Service error: {E}.", name="Finance Tracker")
    return response


router.add_api_route(
    methods=["GET"],
    path="/detail/phone-number",
    response_model=ResponseDefault,
    endpoint=user_detail_phone_number_endpoint,
    status_code=status.HTTP_200_OK,
    summary="Retrieve current authenticated users phone number information.",
)
