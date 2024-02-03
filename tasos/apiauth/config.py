#
# Copyright Tristen Georgiou 2023
#
import re
from functools import cache
from typing import Pattern
from pydantic_settings import BaseSettings, SettingsConfigDict

# defaults
PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,50}$"
PASSWORD_HELP = (
    "Password must be between 8 and 50 characters long and contain at least one uppercase letter, one lowercase letter,"
    " one number and one special character from @$!%*?&"
)
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


class ApiAuthSettings(BaseSettings):
    """
    The settings for the API Auth module - all should be defined as environment variables
    """

    secret_key: str  #: generate with `openssl rand -hex 32`
    algorithm: str  #: e.g. HS256
    access_token_expire_minutes: int  #: expiry time of this token, in minutes
    database_url: str  #: Async DB engine e.g. dialect+driver://username:password@host:port/database[?key=value..]
    password_regex: Pattern[str] = re.compile(PASSWORD_REGEX)  #: regex for password strength
    password_help: str = PASSWORD_HELP  #: help text for password strength
    datetime_fmt: str = DATETIME_FMT  #: datetime format for the API
    model_config = SettingsConfigDict(env_prefix="apiauth_", env_file=".env", env_file_encoding="utf-8")


@cache
def get_apiauth_settings() -> ApiAuthSettings:
    return ApiAuthSettings()
