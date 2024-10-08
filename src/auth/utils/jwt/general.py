from typing import Annotated
from pydantic import EmailStr
from datetime import timedelta
from jose import JWTError, jwt
from uuid_extensions import uuid7
from sqlalchemy import and_, select
from src.database.models import users
from sqlalchemy.engine.row import Row
from passlib.context import CryptContext
from src.auth.utils.logging import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from src.database.connection import database_connection
from src.auth.utils.validator import check_pin, check_uuid
from src.auth.utils.database.general import (
    local_time,
    is_access_token_blacklisted,
)
from src.auth.utils.request_format import (
    TokenData,
    UserInDB,
    DetailUserFullName,
    DetailUserPhoneNumber,
    DetailUserEmail,
)
from src.secret import (
    ACCESS_TOKEN_SECRET_KEY,
    ACCESS_TOKEN_ALGORITHM,
    REFRESH_TOKEN_SECRET_KEY,
)

password_content = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


async def verify_pin(pin: str, hashed_pin: str) -> str:
    return password_content.verify(pin, hashed_pin)


async def get_password_hash(password: str) -> str:
    return password_content.hash(password)


async def get_user(
    phone_number: str = None, unique_id: str = None, email: EmailStr = None
) -> UserInDB | None:
    try:
        async with database_connection().connect() as session:
            try:
                filters = []

                if phone_number:
                    filters.append(users.c.phone_number == phone_number)
                if unique_id:
                    filters.append(users.c.user_uuid == unique_id)
                if email:
                    filters.append(users.c.email == email)

                if not filters:
                    logging.error("No valid filter provided.")

                query = select(users).where(and_(*filters))
                result = await session.execute(query)
                checked = result.fetchone()
                if checked:
                    logging.info("User found.")
                    user_data = UserInDB(
                        user_uuid=str(checked.user_uuid),
                        created_at=checked.created_at,
                        updated_at=checked.updated_at,
                        full_name=checked.full_name,
                        email=checked.email,
                        phone_number=checked.phone_number,
                        pin=checked.pin,
                        verified_email=checked.verified_email,
                        verified_phone_number=checked.verified_phone_number,
                    )
                    return user_data

                logging.warning("User not found.")
            except Exception as E:
                logging.error(f"Error during get_user: {E}.")
                await session.rollback()
            finally:
                await session.close()
    except Exception as E:
        logging.error(f"Error after get_user: {E}.")
    return None


async def authenticate_user(user_uuid: uuid7, pin: str) -> Row | None:
    await check_uuid(unique_id=user_uuid)
    await check_pin(pin=pin)

    try:
        users = await get_user(unique_id=user_uuid)
        if not users:
            logging.error("Authentication failed, users not found.")
            return None
        if not await verify_pin(pin=pin, hashed_pin=users.pin):
            logging.error(
                f"Authentication failed, invalid pin for users {users.full_name}."
            )
            return None
    except Exception as E:
        logging.error(f"Error after authenticate_user: {E}.")
        return None
    return users


async def create_access_token(data: dict, access_token_expires: timedelta) -> str:
    to_encode = data.copy()
    expires = local_time() + access_token_expires
    to_encode.update({"exp": expires})
    encoded_access_token = jwt.encode(claims=to_encode, key=ACCESS_TOKEN_SECRET_KEY)
    return encoded_access_token


async def create_refresh_token(data: dict, refresh_token_expires: timedelta) -> str:
    to_encode = data.copy()
    expires = local_time() + refresh_token_expires
    to_encode.update({"exp": expires})
    encoded_refresh_token = jwt.encode(claims=to_encode, key=REFRESH_TOKEN_SECRET_KEY)
    return encoded_refresh_token


async def get_access_token(access_token: str = Depends(oauth2_scheme)) -> str:
    return access_token


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> DetailUserFullName | DetailUserPhoneNumber | DetailUserEmail | None:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "bearer"},
    )

    blacklisted_access_token = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session expired. Please perform re login.",
        headers={"WWW-Authenticate": "bearer"},
    )

    try:
        validate_access_token = await is_access_token_blacklisted(access_token=token)

        if validate_access_token is True:
            raise blacklisted_access_token

        payload = jwt.decode(
            token=token,
            key=ACCESS_TOKEN_SECRET_KEY,
            algorithms=[ACCESS_TOKEN_ALGORITHM],
        )

        user_uuid = payload.get("sub")

        token_data = TokenData(user_uuid=user_uuid)
        users = await get_user(unique_id=token_data.user_uuid)

        if user_uuid is None or users is None:
            raise credentials_exception
    except JWTError as e:
        logging.error(f"JWTError: {e}")
        raise credentials_exception
    return users


async def verify_email_status(token: Annotated[str, Depends(oauth2_scheme)]) -> bool:
    already_verified = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="User email already verified.",
    )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "bearer"},
    )

    try:
        payload = jwt.decode(
            token=token,
            key=ACCESS_TOKEN_SECRET_KEY,
            algorithms=[ACCESS_TOKEN_ALGORITHM],
        )

        user_uuid = payload.get("sub")

        token_data = TokenData(user_uuid=user_uuid)
        users = await get_user(unique_id=token_data.user_uuid)
        email_status = users.verified_email

        if email_status:
            raise already_verified
    except JWTError as e:
        logging.error(f"JWTError: {e}")
        raise credentials_exception
    return email_status
