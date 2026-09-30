"""What a diagnostics download carries about the vacuum."""

from custom_components.robot_vacuum_map.connector.model import (
    XiaomiCloudMapExtractorData,
)


def test_carries_what_the_vacuum_reported_when_the_map_did_not_parse() -> None:
    """The vacuum's own data survives a map that failed to parse."""
    data = XiaomiCloudMapExtractorData(
        additional_vacuum_data={"miot_properties": {"2-1": 4}}
    )

    assert data.as_dict()["additional_vacuum_data"] == {"miot_properties": {"2-1": 4}}
