#
# Copyright Tristen Georgiou 2023
#
import re

from tasos.apiauth.config import get_apiauth_settings, PASSWORD_REGEX, PASSWORD_HELP


def test_get_apiauth_settings() -> None:
    # NOTE: the environment variables are set using pytest-env and are found in the pyproject.toml file
    settings = get_apiauth_settings()
    assert settings.secret_key == "somesecretkey"
    assert settings.algorithm == "HS256"
    assert settings.access_token_expire_minutes == 15
    assert settings.database_url == "sqlite+aiosqlite://?check_same_thread=false"
    assert settings.password_regex == re.compile(PASSWORD_REGEX)
    assert settings.password_help == PASSWORD_HELP
