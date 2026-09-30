"""The integration's own brand images, and Home Assistant serving them."""

from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from PIL import Image
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.xiaomi_vacuum_map.const import DOMAIN

BRAND = Path(__file__).parent.parent / "custom_components" / DOMAIN / "brand"

# Every image home-assistant/brands specifies, with the bounds on its shortest
# side: icons are square at exactly that size, logos may be any width.
IMAGES = {
    "icon.png": (256, 256),
    "icon@2x.png": (512, 512),
    "logo.png": (128, 256),
    "logo@2x.png": (256, 512),
    "dark_icon.png": (256, 256),
    "dark_icon@2x.png": (512, 512),
    "dark_logo.png": (128, 256),
    "dark_logo@2x.png": (256, 512),
}


@pytest.mark.parametrize(("image", "shortest_side"), IMAGES.items())
def test_image_follows_the_brands_rules(
    image: str, shortest_side: tuple[int, int]
) -> None:
    """Each image is a trimmed, transparent PNG of the size the rules set."""
    with Image.open(BRAND / image) as png:
        assert png.format == "PNG"
        width, height = png.size
        low, high = shortest_side
        assert low <= min(width, height) <= high
        if image.removeprefix("dark_").startswith("icon"):
            assert width == height
        rgba = png.convert("RGBA")
        assert rgba.getbbox() == (0, 0, width, height), "not trimmed"
        assert rgba.getextrema()[3][0] == 0, "no transparent pixels"


@pytest.mark.parametrize("image", IMAGES)
async def test_home_assistant_serves_image(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, image: str
) -> None:
    """Home Assistant serves each image from brand/, not a fallback."""
    assert await async_setup_component(hass, "brands", {})
    client = await hass_client()

    response = await client.get(f"/api/brands/integration/{DOMAIN}/{image}")

    assert response.status == 200
    assert await response.read() == (BRAND / image).read_bytes()
