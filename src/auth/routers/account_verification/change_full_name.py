from typing import Annotated
from src.database.models import users
from src.auth.utils.logging import logging
from fastapi import APIRouter, status, Depends
from src.auth.utils.validator import check_fullname
from src.auth.schema.response import ResponseDefault
from src.auth.utils.jwt.general import get_current_user
from src.database.connection import database_connection
from src.auth.utils.request_format import ChangeUserFullName
from src.auth.utils.database.general import local_time
from src.auth.routers.exceptions import (
    DatabaseError,
    EntityForceInputSameDataError,
    ServiceError,
    FinanceTrackerApiError,
)

router = APIRouter(tags=["account-verification"], prefix="/change")


async def change_full_name_endpoint(
    schema: ChangeUserFullName, current_user: Annotated[dict, Depends(get_current_user)]
) -> ResponseDefault:
    response = ResponseDefault()
    validated_full_name = await check_fullname(value=schema.full_name)

    try:
        if current_user.full_name == validated_full_name:
            raise EntityForceInputSameDataError(
                detail="Cannot change name into same name."
            )

        async with database_connection().connect() as session:
            try:
                query = (
                    users.update()
                    .where(users.c.user_uuid == current_user.user_uuid)
                    .values(updated_at=local_time(), full_name=validated_full_name)
                )

                await session.execute(query)
                await session.commit()
                logging.info("Success changed user full name.")
            except FinanceTrackerApiError as FE:
                raise FE
            except Exception as E:
                logging.error(f"Error while change user full name: {E}.")
                await session.rollback()
                raise DatabaseError(detail=f"Database error: {E}.")
            finally:
                await session.close()

        response.success = True
        response.message = "User successfully changed full name."

    except FinanceTrackerApiError as FTE:
        raise FTE

    except Exception as E:
        raise ServiceError(detail=f"Service error: {E}.", name="Finance Tracker")

    return response


router.add_api_route(
    methods=["PATCH"],
    path="/full-name",
    endpoint=change_full_name_endpoint,
    status_code=status.HTTP_200_OK,
    summary="Change user pin endpoint.",
)
