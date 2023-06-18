#
# Copyright Tristen Georgiou 2023
#
import pytest

from tasos.apiauth.model import Password, ChangePassword


@pytest.fixture
def valid_registrations() -> list[dict[str, str]]:
    return [
        {
            "password": "Abcdef123!",
            "password_confirm": "Abcdef123!",
        },
        {
            "password": "1%TasosSoftware",
            "password_confirm": "1%TasosSoftware",
        },
    ]


@pytest.fixture
def invalid_passwords() -> list[dict[str, str]]:
    return [
        {
            "password": "invalid",  # too short
            "password_confirm": "invalid",
        },
        {
            "password": "Abcdef123!" + "a" * 50,  # too long
            "password_confirm": "Abcdef123!" + "a" * 50,
        },
        {
            "password": "abcdef123!",  # no uppercase
            "password_confirm": "abcdef123!",
        },
        {
            "password": "ABCDEF123!",  # no lowercase
            "password_confirm": "ABCDEF123!",
        },
        {
            "password": "Abcdefghi!",  # no number
            "password_confirm": "Abcdefghi!",
        },
        {
            "password": "Abcdef123",  # no special character
            "password_confirm": "Abcdef123",
        },
    ]


def test_password_validation(
    valid_registrations: list[dict[str, str]], invalid_passwords: list[dict[str, str]]
) -> None:
    for data in valid_registrations:
        reg = Password.parse_obj(data)

        assert reg.password.get_secret_value() == data["password"]
        assert reg.password_confirm.get_secret_value() == data["password_confirm"]

    for data in invalid_passwords:
        with pytest.raises(ValueError, match="Password must be between 8 and 50 characters"):
            Password.parse_obj(data)

    # test passwords don't match
    with pytest.raises(ValueError, match="Passwords do not match"):
        Password.parse_obj(
            {
                "password": "Abcdef123!",
                "password_confirm": "no match!",
            }
        )


def test_new_password_same_as_old() -> None:
    with pytest.raises(ValueError, match="You cannot use your current password as your new password"):
        ChangePassword.parse_obj(
            {
                "current_password": "Abcdef123!",
                "password": "Abcdef123!",
                "password_confirm": "Abcdef123!",
            }
        )
