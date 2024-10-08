from typing import Annotated
from src.auth.utils.logging import logging
from fastapi import APIRouter, status, Depends
from src.auth.schema.response import ResponseDefault
from src.auth.utils.request_format import CreateSpend
from src.auth.utils.jwt.general import get_current_user
from src.database.connection import database_connection
from src.database.models import money_spends, money_spend_schemas
from src.auth.utils.database.general import filter_month_year_category, local_time
from src.auth.routers.exceptions import (
    ServiceError,
    DatabaseError,
    FinanceTrackerApiError,
)

router = APIRouter(tags=["money-spends"])


async def create_spend(
    schema: CreateSpend, current_user: Annotated[dict, Depends(get_current_user)]
) -> ResponseDefault:
    """
    Create a money spend data with all the information:

    - **spend_day**: This refers to the specific calendar date (e.g., 1, 2 ... 31) when the schema was created or applies to.
    - **spend_month**: This refers to the specific calendar month (e.g., January, February) when the schema was created or applies to.
    - **spend_year**: This represents the calendar year (e.g., 2023, 2024) associated with the schema.
    - **category**: This identifies the type of expense or area the schema pertains to. Examples of categories could be "Rent," "Groceries," "Transportation," or any other relevant groupings you define.
    - **description**: A description or note about the spending.
    - **amount**: The amount of money spent.
    """

    response = ResponseDefault()

    is_available = await filter_month_year_category(
        user_uuid=current_user.user_uuid,
        month=schema.spend_month,
        year=schema.spend_year,
        category=schema.category,
    )

    try:
        logging.info("Endpoint create spend money.")
        async with database_connection().connect() as session:
            try:
                if is_available is False:
                    try:
                        logging.info(
                            f"Inserting data into table {money_spends.name} and {money_spend_schemas.name}"
                        )

                        create_spend = money_spends.insert().values(
                            created_at=local_time(),
                            updated_at=None,
                            user_uuid=current_user.user_uuid,
                            spend_day=schema.spend_day,
                            spend_month=schema.spend_month,
                            spend_year=schema.spend_year,
                            category=schema.category,
                            description=schema.description,
                            amount=schema.amount,
                        )
                        create_category = money_spend_schemas.insert().values(
                            created_at=local_time(),
                            updated_at=None,
                            user_uuid=current_user.user_uuid,
                            month=schema.spend_month,
                            year=schema.spend_year,
                            category=schema.category,
                            budget=0,
                        )
                        await session.execute(create_spend)
                        await session.execute(create_category)
                        await session.commit()
                        logging.info("Created new spend money and schema.")
                        response.message = "Created new spend money and schema data."
                        response.success = True
                    except Exception as E:
                        logging.error(
                            f"Error during creating new spend money and schema: {E}."
                        )
                        await session.rollback()
                        raise DatabaseError(detail=f"Database error: {E}.")
                else:
                    try:
                        logging.info(
                            f"Only inserting data into table {money_spends.name}"
                        )
                        create_spend = money_spends.insert().values(
                            created_at=local_time(),
                            updated_at=None,
                            user_uuid=current_user.user_uuid,
                            spend_day=schema.spend_day,
                            spend_month=schema.spend_month,
                            spend_year=schema.spend_year,
                            category=schema.category,
                            description=schema.description,
                            amount=schema.amount,
                        )
                        await session.execute(create_spend)
                        await session.commit()
                        logging.info("Created new spend money.")
                        response.message = "Created new spend money."
                        response.success = True
                    except Exception as E:
                        logging.error(f"Error during creating new spend money: {E}.")
                        await session.rollback()
                        raise DatabaseError(detail=f"Database error: {E}.")
            except Exception as E:
                logging.error(
                    f"Error during creating spend money or with adding money schema: {E}."
                )
                await session.rollback()
                raise DatabaseError(
                    detail=f"Database error during creating spend money or with adding money schema: {E}."
                )
            finally:
                await session.close()
    except FinanceTrackerApiError as FTE:
        raise FTE

    except Exception as E:
        raise ServiceError(detail=f"Service error: {E}.", name="Finance Tracker")

    return response


router.add_api_route(
    methods=["POST"],
    path="/create-spend",
    response_model=ResponseDefault,
    endpoint=create_spend,
    status_code=status.HTTP_201_CREATED,
    summary="Create daily spend record.",
)
