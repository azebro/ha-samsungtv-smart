"""Samsung Frame TV Art Brightness number entity."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.art import SamsungTVAsyncArt
from .const import (
    CONF_ILLUMINANCE_SENSOR,
    DATA_ART_API,
    DATA_CFG,
    DATA_OPTIONS,
    DOMAIN,
)
from .entity import SamsungTVEntity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Samsung TV number entities from config entry."""
    frame_tv_supported = hass.data[DOMAIN][entry.entry_id].get(DATA_ART_API, False)
    options = hass.data[DOMAIN][entry.entry_id][DATA_OPTIONS]
    config = hass.data[DOMAIN][entry.entry_id][DATA_CFG]

    entities: list[NumberEntity] = []

    # Only create brightness entity if illuminance sensor configured AND Frame TV
    illuminance_sensor = options.get(CONF_ILLUMINANCE_SENSOR)
    if illuminance_sensor and frame_tv_supported:
        from homeassistant.helpers.aiohttp_client import async_get_clientsession
        from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
        from .const import DEFAULT_PORT, WS_PREFIX, CONF_WS_NAME

        host = config[CONF_HOST]
        port = config.get(CONF_PORT, DEFAULT_PORT)
        token = config.get(CONF_TOKEN)
        ws_name = config.get(CONF_WS_NAME, "HomeAssistant")
        session = async_get_clientsession(hass)

        art_api = SamsungTVAsyncArt(
            host=host,
            port=port,
            token=token,
            session=session,
            timeout=5,
            name=f"{WS_PREFIX} {ws_name} Art Number",
        )
        entities.append(
            FrameArtBrightnessNumber(
                config=config,
                entry_id=entry.entry_id,
                art_api=art_api,
            )
        )

    if entities:
        async_add_entities(entities, update_before_add=True)


class FrameArtBrightnessNumber(SamsungTVEntity, NumberEntity):
    """Number entity for controlling Frame TV art brightness."""

    _attr_native_min_value = 10
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"
    _attr_has_entity_name = True
    _attr_name = "Art Brightness"
    _attr_icon = "mdi:brightness-6"
    _attr_should_poll = True

    def __init__(
        self,
        config: dict[str, Any],
        entry_id: str,
        art_api: SamsungTVAsyncArt,
    ) -> None:
        """Initialize the brightness number entity."""
        super().__init__(config, entry_id)
        self._attr_unique_id = f"{entry_id}_art_brightness"
        self._art_api = art_api

    async def async_set_native_value(self, value: float) -> None:
        """Set art brightness via the Art API."""
        brightness = int(value)
        # Convert 0-100 to TV's 1-10 scale (min 1, TV rejects 0)
        tv_brightness = max(1, min(10, round(brightness / 10)))
        _LOGGER.debug(
            "Setting art brightness: %d (UI) -> %d (TV)", brightness, tv_brightness
        )
        await self._art_api.set_brightness(tv_brightness)
        self._attr_native_value = float(brightness)

    async def async_update(self) -> None:
        """Read current brightness from TV."""
        try:
            async with asyncio.timeout(8):
                result = await self._art_api.get_brightness()
                if result and isinstance(result, dict):
                    tv_val = int(result.get("value", 0))
                    self._attr_native_value = float(tv_val * 10)
                    _LOGGER.debug(
                        "Art brightness updated: TV=%d, UI=%d", tv_val, tv_val * 10
                    )
        except TimeoutError:
            _LOGGER.debug("Timeout reading art brightness")
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Could not read art brightness (TV may be off)")
