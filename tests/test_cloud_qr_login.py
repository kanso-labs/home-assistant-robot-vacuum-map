"""The link the QR login offers beside its code, for signing in on the same device."""

from unittest.mock import AsyncMock, MagicMock

from yarl import URL

from custom_components.robot_vacuum_map.connector.xiaomi_cloud.connector import (
    XiaomiCloudConnector,
)

LOGIN_URL = "https://account.xiaomi.com/longPolling/login?ticket=abc"
SERVICE_LOGIN = (
    "https://account.xiaomi.com/pass/serviceLogin?sid=xiaomiio&_json=true"
    "&callback=https%3A%2F%2Fsts.api.io.mi.com%2Fsts&followup=https%3A%2F%2Ffollow"
)


def connector_redirecting_to(location: str | None) -> XiaomiCloudConnector:
    """A connector whose session answers loginUrl with this redirect."""
    connector = XiaomiCloudConnector(MagicMock())
    headers = {} if location is None else {"Location": location}
    connector._session_data = MagicMock(
        get=AsyncMock(return_value=MagicMock(status=302, headers=headers))
    )
    return connector


async def test_offers_the_sign_in_page_without_the_json_flag() -> None:
    """With _json=true a signed-out browser gets JSON instead of a sign-in form."""
    connector = connector_redirecting_to(SERVICE_LOGIN)

    link = URL(await connector._browser_login_url(LOGIN_URL))

    assert "_json" not in link.query
    assert link.path == "/pass/serviceLogin"
    assert link.query["sid"] == "xiaomiio"
    assert link.query["callback"] == "https://sts.api.io.mi.com/sts"
    assert link.query["followup"] == "https://follow"
    connector._session_data.get.assert_awaited_once_with(
        LOGIN_URL, allow_redirects=False
    )


async def test_keeps_the_link_it_cannot_improve() -> None:
    """No redirect, a redirect without the flag, or a failure keep loginUrl."""
    for connector in (
        connector_redirecting_to(None),
        connector_redirecting_to("https://account.xiaomi.com/pass/serviceLogin?a=1"),
    ):
        assert await connector._browser_login_url(LOGIN_URL) == LOGIN_URL

    failing = connector_redirecting_to(SERVICE_LOGIN)
    failing._session_data.get.side_effect = OSError("offline")
    assert await failing._browser_login_url(LOGIN_URL) == LOGIN_URL
