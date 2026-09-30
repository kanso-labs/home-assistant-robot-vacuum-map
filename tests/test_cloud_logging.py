"""The cloud connector's debug log, which people paste into public issues."""

import datetime
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.xiaomi_vacuum_map.connector.xiaomi_cloud.connector import (
    XiaomiCloudConnector,
    XiaomiCloudConnectorConfig,
    XiaomiCloudSessionData,
)
from custom_components.xiaomi_vacuum_map.connector.xiaomi_cloud.utils import (
    REDACTED,
    redacted,
    without_query,
)

SSECURITY = "s3cr3t-ssecurity"
SERVICE_TOKEN = "t0k3n-service"
PASS_TOKEN = "p4ss-token"
PASSWORD = "hunter2-password"
NONCE = "n0nce-value"
CLIENT_SIGN = "cl1ent-sign"
SECRETS = (SSECURITY, SERVICE_TOKEN, PASS_TOKEN, PASSWORD, NONCE, CLIENT_SIGN)

STS_URL = f"https://sts.api.io.mi.com/sts?nonce={NONCE}&clientSign={CLIENT_SIGN}"
LOGIN_RESPONSE = (
    '&&&START&&&{"code": 0, "desc": "ok", '
    f'"ssecurity": "{SSECURITY}", "passToken": "{PASS_TOKEN}", '
    f'"userId": 42, "cUserId": "c-42", "location": "{STS_URL}"}}'
)


def assert_no_secrets(text: str) -> None:
    for secret in SECRETS:
        assert secret not in text


def test_keeps_the_secrets_out_of_the_session_repr() -> None:
    session = XiaomiCloudSessionData(
        MagicMock(), {}, ssecurity=SSECURITY, serviceToken=SERVICE_TOKEN
    )

    assert_no_secrets(repr(session))


def test_keeps_the_secrets_out_of_the_connector_config_repr() -> None:
    config = XiaomiCloudConnectorConfig(
        username="user@example.com",
        password=PASSWORD,
        server="de",
        user_id="42",
        c_user_id="c-42",
        service_token=SERVICE_TOKEN,
        expiration=None,
        ssecurity=SSECURITY,
        device_id="abcdef",
    )

    assert_no_secrets(repr(config))


def test_logs_the_authentication_check_without_the_session(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The check runs on every refresh, so it must not print the session."""
    session = XiaomiCloudSessionData(
        MagicMock(),
        {},
        ssecurity=SSECURITY,
        serviceToken=SERVICE_TOKEN,
        # Naive, as the connector restores a stored session's expiry.
        expiration=datetime.datetime.fromisoformat("9999-12-31T00:00:00"),
    )

    with caplog.at_level(logging.DEBUG):
        assert session.is_authenticated()

    assert "Authentication check" in caplog.text
    assert_no_secrets(caplog.text)


async def test_logs_a_credentials_login_without_its_secrets(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Step 2 answers with the session's secrets, and step 3 follows a signed URL."""
    connector = XiaomiCloudConnector(MagicMock())
    connector._username = "user@example.com"
    connector._password = PASSWORD
    connector._session_data = XiaomiCloudSessionData(MagicMock(), {})

    step_2 = MagicMock(status=200)
    step_2.text = AsyncMock(return_value=LOGIN_RESPONSE)
    step_2.cookies.get.return_value.get.return_value = "3600"
    connector._session_data.post = AsyncMock(return_value=step_2)

    step_3 = MagicMock(status=200)
    step_3.text = AsyncMock(return_value="ok")
    step_3.cookies.__contains__.return_value = True
    step_3.cookies.get.return_value.value = SERVICE_TOKEN
    connector._session_data.get = AsyncMock(return_value=step_3)

    with caplog.at_level(logging.DEBUG):
        location = await connector._login_with_credentials_step_2("sign")
        await connector._login_with_credentials_step_3(location)

    assert connector._session_data.serviceToken == SERVICE_TOKEN
    assert "step 2 content" in caplog.text
    assert_no_secrets(caplog.text)


def test_masks_the_secrets_of_a_login_response() -> None:
    """Everything else stays readable, to debug a login by."""
    assert redacted(LOGIN_RESPONSE) == {
        "code": 0,
        "desc": "ok",
        "ssecurity": REDACTED,
        "passToken": REDACTED,
        "userId": 42,
        "cUserId": "c-42",
        "location": REDACTED,
    }


def test_logs_a_page_only_by_its_length() -> None:
    assert redacted(f"<html>{SERVICE_TOKEN}</html>") == "<26 characters>"


def test_logs_a_url_without_its_query() -> None:
    assert without_query(STS_URL) == "https://sts.api.io.mi.com/sts"
