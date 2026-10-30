"""Renewing the Xiaomi cloud session with its passToken rather than signing in again."""

import datetime
from dataclasses import asdict
from http.cookies import SimpleCookie
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.robot_vacuum_map.connector import (
    XiaomiCloudMapExtractorConnector,
)
from custom_components.robot_vacuum_map.connector.utils.exceptions import (
    FailedLoginException,
)
from custom_components.robot_vacuum_map.connector.xiaomi_cloud.connector import (
    XiaomiCloudConnector,
    XiaomiCloudConnectorConfig,
    XiaomiCloudSessionData,
)

PASS_TOKEN = "p4ss-token"
STS_URL = "https://sts.api.io.mi.com/sts?nonce=n&clientSign=c"
RENEWAL = (
    '&&&START&&&{"code": 0, "ssecurity": "new-ssecurity", "userId": 42,'
    f' "cUserId": "c-42", "location": "{STS_URL}"}}'
)


def response(
    status: int = 200, text: str = "", cookies: dict[str, str] | None = None
) -> MagicMock:
    jar = SimpleCookie()
    for key, value in (cookies or {}).items():
        jar[key] = value
    if "userId" in jar:
        jar["userId"]["max-age"] = "2592000"
    return MagicMock(status=status, text=AsyncMock(return_value=text), cookies=jar)


def connector_answering(*responses: MagicMock) -> XiaomiCloudConnector:
    """A cloud connector whose expired session keeps a passToken."""
    connector = XiaomiCloudConnector(MagicMock())
    connector.pass_token = PASS_TOKEN
    cookie_jar = MagicMock()
    cookie_jar.__iter__.side_effect = lambda: iter([])
    connector._session_data = XiaomiCloudSessionData(
        MagicMock(cookie_jar=cookie_jar),
        {},
        userId="42",
        serviceToken="old-token",
        ssecurity="old-ssecurity",
        expiration=datetime.datetime.now(),
    )
    connector._session_data.session.get = AsyncMock(side_effect=responses)
    return connector


async def test_renews_the_session_without_a_password() -> None:
    connector = connector_answering(
        response(text=RENEWAL, cookies={"userId": "42"}),
        response(cookies={"serviceToken": "new-token"}),
    )

    assert await connector.login_with_pass_token()

    first, second = connector._session_data.session.get.await_args_list
    assert first.kwargs["cookies"]["passToken"] == PASS_TOKEN
    assert second.args == (STS_URL,)
    assert connector._session_data.serviceToken == "new-token"
    assert connector._session_data.ssecurity == "new-ssecurity"
    assert connector._session_data.cUserId == "c-42"
    assert connector.is_authenticated()


@pytest.mark.parametrize(
    "responses",
    [
        (response(text='&&&START&&&{"code": 70016}'),),
        (response(status=401, text="{}"),),
        (response(text=RENEWAL), response(status=200)),
    ],
    ids=["refused", "unauthorized", "no serviceToken"],
)
async def test_leaves_the_session_alone_when_xiaomi_refuses(
    responses: tuple[MagicMock, ...],
) -> None:
    connector = connector_answering(*responses)

    assert not await connector.login_with_pass_token()

    assert connector._session_data.serviceToken == "old-token"
    assert connector._session_data.ssecurity == "old-ssecurity"


async def test_asks_nothing_without_a_passToken() -> None:
    connector = connector_answering()
    connector.pass_token = None

    assert not await connector.login_with_pass_token()

    connector._session_data.session.get.assert_not_awaited()


async def test_keeps_the_passToken_with_the_stored_session() -> None:
    connector = connector_answering()

    stored = asdict(connector.to_config())
    stored["expiration"] = stored["expiration"].isoformat()
    restored = await XiaomiCloudConnector.from_config(
        XiaomiCloudConnectorConfig.from_dict(stored), MagicMock()
    )

    assert restored.pass_token == PASS_TOKEN
    assert PASS_TOKEN not in repr(connector.to_config())


def test_loads_a_session_stored_before_the_passToken_was_kept() -> None:
    stored = asdict(connector_answering().to_config())
    stored.pop("pass_token")
    stored["expiration"] = stored["expiration"].isoformat()

    assert XiaomiCloudConnectorConfig.from_dict(stored).pass_token is None


def with_cloud(renews: bool, **config: Any) -> XiaomiCloudMapExtractorConnector:
    """A connector whose session has expired, set up to download a map."""
    saver = AsyncMock()
    connector = XiaomiCloudMapExtractorConnector(
        MagicMock(), MagicMock(**config), None, saver
    )
    connector._cloud_connector = MagicMock(
        is_authenticated=MagicMock(return_value=False),
        login_with_pass_token=AsyncMock(return_value=renews),
        login_with_credentials=AsyncMock(),
    )
    connector._status = MagicMock()
    connector._vacuum_connector = MagicMock(
        get_map=AsyncMock(return_value=(MagicMock(), b"map"))
    )
    connector._draw = AsyncMock()
    return connector


async def test_renews_an_expired_session_before_signing_in_again() -> None:
    connector = with_cloud(renews=True)

    await connector._update()

    connector._cloud_connector.login_with_credentials.assert_not_awaited()
    connector._session_saver.assert_awaited_once_with(
        connector._cloud_connector.to_config()
    )


async def test_signs_in_again_and_keeps_the_session_when_renewing_fails() -> None:
    connector = with_cloud(renews=False, username="user", password="password")
    connector._cloud_connector.is_authenticated.side_effect = [False, True]

    await connector._update()

    connector._cloud_connector.login_with_credentials.assert_awaited_once_with(
        "user", "password"
    )
    connector._session_saver.assert_awaited_once()


async def test_asks_for_reauthentication_when_neither_works() -> None:
    connector = with_cloud(renews=False, username=None, password=None)

    with pytest.raises(FailedLoginException):
        await connector._update()

    connector._session_saver.assert_not_awaited()


async def test_renews_once_when_the_cloud_turns_a_valid_token_down() -> None:
    connector = with_cloud(renews=True)
    connector._cloud_connector.is_authenticated.return_value = True
    connector._vacuum_connector.get_map.side_effect = [
        FailedLoginException(),
        (MagicMock(), b"map"),
    ]

    await connector._update()

    assert connector._vacuum_connector.get_map.await_count == 2
    connector._cloud_connector.login_with_pass_token.assert_awaited_once()
