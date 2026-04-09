"""Samsung Frame TV Art Mode switch entity."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
    CONF_TOKEN,
    STATE_ON,
    STATE_OFF,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er

from pysmartthings import Attribute, Capability, Command

from .api.art import SamsungTVAsyncArt
from .const import (
    AUTH_METHOD_OAUTH,
    AUTH_METHOD_ST_ENTRY,
    CONF_API_KEY,
    CONF_AUTH_METHOD,
    CONF_DEVICE_ID,
    CONF_OAUTH_TOKEN,
    CONF_WS_NAME,
    DATA_ART_API,
    DATA_CFG,
    DEFAULT_PORT,
    DOMAIN,
    WS_PREFIX,
)
from . import async_get_samsungtv_api_key

# SmartThings component
COMPONENT_MAIN = "main"

_LOGGER = logging.getLogger(__name__)

# Time to wait for TV to be ready after WOL
TV_STARTUP_DELAY = 8  # seconds


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Samsung Frame Art Mode switch from config entry."""
    config = hass.data[DOMAIN][entry.entry_id][DATA_CFG]
    host = config[CONF_HOST]
    port = config.get(CONF_PORT, DEFAULT_PORT)
    token = config.get(CONF_TOKEN)
    ws_name = config.get(CONF_WS_NAME, "HomeAssistant")

    # Get device name from config or entry title, fallback to host
    device_name = config.get(CONF_NAME) or entry.title or host

    # Get SmartThings config - use async_get_samsungtv_api_key for OAuth support
    api_key = config.get(CONF_API_KEY)
    device_id = config.get(CONF_DEVICE_ID)
    auth_method = config.get(CONF_AUTH_METHOD)

    # For OAuth, get token from oauth_token if api_key is not available
    if auth_method == AUTH_METHOD_OAUTH and not api_key:
        oauth_token = config.get(CONF_OAUTH_TOKEN)
        if oauth_token and isinstance(oauth_token, dict):
            api_key = oauth_token.get("access_token")
            _LOGGER.debug("Power switch using OAuth token")

    session = async_get_clientsession(hass)

    entities = []

    # Create Power Switch if SmartThings is configured
    if api_key and device_id:
        try:
            entities.append(
                SamsungTVPowerSwitch(
                    hass=hass,
                    entry=entry,
                    device_id=device_id,
                    device_name=device_name,
                    session=session,
                )
            )
            _LOGGER.info("Power switch (SmartThings) created for %s", device_name)
        except Exception as ex:
            _LOGGER.warning("Could not setup Power switch via SmartThings: %s", ex)
    else:
        _LOGGER.debug("SmartThings not configured, Power switch not created")

    # Create Art Mode switch if Frame TV is supported (each platform gets its own API instance)
    frame_tv_supported = hass.data[DOMAIN][entry.entry_id].get(DATA_ART_API, False)

    if frame_tv_supported:
        art_api = SamsungTVAsyncArt(
            host=host,
            port=port,
            token=token,
            session=session,
            timeout=5,
            name=f"{WS_PREFIX} {ws_name} Art Switch",
        )
        entities.append(
            FrameArtModeSwitch(
                hass,
                entry,
                art_api,
                device_name,
                host,
                st_api_key=api_key,
                st_device_id=device_id,
                session=session,
            )
        )
        _LOGGER.info("Frame Art Mode switch created for %s", device_name)
    else:
        _LOGGER.debug("Frame TV art mode not supported on %s", host)

    # Create the switch entities
    if entities:
        async_add_entities(entities)


class FrameArtModeSwitch(SwitchEntity):
    """Switch to control Samsung Frame TV Art Mode."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_has_entity_name = True
    _attr_name = "Art Mode"
    _attr_icon = "mdi:palette"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        art_api: SamsungTVAsyncArt,
        device_name: str,
        host: str,
        st_api_key: str | None = None,
        st_device_id: str | None = None,
        session=None,
    ) -> None:
        """Initialize the Art Mode switch."""
        self._hass = hass
        self._entry = entry
        self._art_api = art_api
        self._device_name = device_name
        self._host = host
        self._st_api_key = st_api_key
        self._st_device_id = st_device_id
        self._session = session
        self._attr_unique_id = f"{entry.entry_id}_art_mode_switch"
        self._attr_is_on = None
        self._available = True
        self._updating = False
        self._media_player_entity_id: str | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info to link this entity to the TV device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._device_name,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def is_on(self) -> bool | None:
        """Return True if Art Mode is on."""
        return self._attr_is_on

    def _get_media_player_entity_id(self) -> str | None:
        """Get the media_player entity_id for this TV."""
        if self._media_player_entity_id:
            return self._media_player_entity_id

        # Find media_player entity for this config entry using the correct API
        entity_registry = er.async_get(self._hass)
        for entity in entity_registry.entities.values():
            if (
                entity.config_entry_id == self._entry.entry_id
                and entity.domain == "media_player"
            ):
                self._media_player_entity_id = entity.entity_id
                return entity.entity_id

        return None

    async def _is_tv_on(self) -> bool:
        """Check if TV is currently on."""
        entity_id = self._get_media_player_entity_id()
        if not entity_id:
            return False

        state = self._hass.states.get(entity_id)
        if state is None:
            return False

        # TV is "on" if state is not off/unavailable
        return state.state not in (STATE_OFF, "unavailable", "unknown")

    async def _turn_on_tv(self) -> bool:
        """Turn on the TV using media_player service."""
        entity_id = self._get_media_player_entity_id()
        if not entity_id:
            _LOGGER.warning(
                "Could not find media_player entity for %s", self._device_name
            )
            return False

        _LOGGER.info("Turning on TV %s before activating Art Mode", entity_id)

        try:
            await self._hass.services.async_call(
                "media_player",
                "turn_on",
                {"entity_id": entity_id},
                blocking=True,
            )
            return True
        except Exception as ex:
            _LOGGER.error("Failed to turn on TV: %s", ex)
            return False

    async def _wait_for_tv_ready(self, max_wait: int = 15) -> bool:
        """Wait for TV to be ready after turning on."""
        _LOGGER.debug("Waiting for TV to be ready (max %ds)...", max_wait)

        for i in range(max_wait):
            await asyncio.sleep(1)

            # Try to connect to Art API
            try:
                async with asyncio.timeout(3):
                    is_supported = await self._art_api.supported()
                    if is_supported:
                        _LOGGER.debug("TV ready after %d seconds", i + 1)
                        return True
            except Exception:
                pass

            _LOGGER.debug("TV not ready yet, waiting... (%d/%d)", i + 1, max_wait)

        _LOGGER.warning("TV did not become ready within %d seconds", max_wait)
        return False

    def _is_tv_playing_content(self) -> bool:
        """Check if TV is actively playing content (not idle/art mode)."""
        entity_id = self._get_media_player_entity_id()
        if not entity_id:
            return False
        state = self._hass.states.get(entity_id)
        if state is None:
            return False
        return state.state in ("playing", "paused")

    async def _st_set_artmode(self, mode: bool) -> bool:
        """Set art mode via SmartThings API (fallback for 2024+ Frame TVs).

        Uses the execute command API with custom art mode capability.
        """
        if not self._st_api_key or not self._st_device_id or not self._session:
            _LOGGER.warning(
                "SmartThings art mode: missing api_key=%s, device_id=%s, session=%s",
                bool(self._st_api_key),
                bool(self._st_device_id),
                bool(self._session),
            )
            return False

        from . import async_get_samsungtv_api_key

        api_key = await async_get_samsungtv_api_key(self._hass, self._entry)
        if not api_key:
            api_key = self._st_api_key

        url = f"https://api.smartthings.com/v1/devices/{self._st_device_id}/commands"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Try multiple capability names used by different Frame TV generations
        if mode:
            # Turn art mode ON
            capabilities = [
                ("samsungvd.ambient", "setAmbientOn", []),  # 2024+ Frame TVs
                ("samsungvd.artMode", "setArtMode", ["on"]),  # Older Frame TVs
                ("custom.artMode", "setArtMode", ["on"]),  # Legacy
            ]
        else:
            # Turn art mode OFF — switch back to normal TV
            capabilities = [
                ("switch", "on", []),  # Wake from art/ambient mode
                ("samsungvd.artMode", "setArtMode", ["off"]),
                ("custom.artMode", "setArtMode", ["off"]),
            ]

        for cap, cmd, args in capabilities:
            payload = {
                "commands": [
                    {
                        "component": "main",
                        "capability": cap,
                        "command": cmd,
                    }
                ]
            }
            if args:
                payload["commands"][0]["arguments"] = args
            try:
                async with asyncio.timeout(10):
                    async with self._session.post(
                        url, headers=headers, json=payload
                    ) as resp:
                        if resp.status == 200:
                            result = await resp.json()
                            _LOGGER.info(
                                "Art Mode %s via SmartThings (%s): %s",
                                "ON" if mode else "OFF",
                                cap,
                                result,
                            )
                            return True
                        elif resp.status == 422:
                            # Capability not supported, try next
                            _LOGGER.debug(
                                "SmartThings capability %s not supported", cap
                            )
                            continue
                        else:
                            body = await resp.text()
                            _LOGGER.warning(
                                "SmartThings art mode command failed (%d): %s",
                                resp.status,
                                body,
                            )
            except Exception as ex:
                _LOGGER.warning("SmartThings art mode error with %s: %s", cap, ex)

        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn Art Mode on."""
        _LOGGER.debug("Turning Art Mode ON for %s", self._device_name)

        # Guard: do not switch to Art Mode if TV is actively playing content
        if self._is_tv_playing_content():
            _LOGGER.info(
                "Art Mode activation blocked: TV is playing content on %s",
                self._device_name,
            )
            self._hass.bus.async_fire(
                f"{DOMAIN}_art_mode_blocked",
                {"entity_id": self.entity_id, "reason": "playback_active"},
            )
            return

        # Check if TV is on
        tv_is_on = await self._is_tv_on()

        if not tv_is_on:
            _LOGGER.info("TV is off, turning it on first...")

            # Turn on TV
            if not await self._turn_on_tv():
                _LOGGER.error("Failed to turn on TV, cannot activate Art Mode")
                return

            # Wait for TV to be ready
            if not await self._wait_for_tv_ready(max_wait=20):
                _LOGGER.warning(
                    "TV may not be fully ready, attempting Art Mode anyway..."
                )

            # Additional delay for TV to stabilize
            await asyncio.sleep(2)

        # Try SmartThings API first (most reliable for 2024+ Frame TVs)
        if self._st_api_key and self._st_device_id:
            _LOGGER.info("Art Mode: trying SmartThings API for %s", self._device_name)
            if await self._st_set_artmode(True):
                self._attr_is_on = True
                self._available = True
                self.async_write_ha_state()
                _LOGGER.info(
                    "Art Mode turned ON via SmartThings for %s", self._device_name
                )
                return

            _LOGGER.info("SmartThings art mode failed, trying local WebSocket...")

        # Fallback: local WebSocket art API
        try:
            async with asyncio.timeout(15):
                _LOGGER.info(
                    "Art Mode: trying local WebSocket API for %s",
                    self._device_name,
                )
                result = await self._art_api.set_artmode(True)
                if result:
                    self._attr_is_on = True
                    self._available = True
                    self.async_write_ha_state()
                    _LOGGER.info(
                        "Art Mode turned ON via local API for %s", self._device_name
                    )
                    return
                _LOGGER.warning("Local art API returned no confirmation")
        except asyncio.TimeoutError:
            _LOGGER.warning("Local art API timed out")
        except Exception as ex:
            _LOGGER.warning("Local art API error: %s", type(ex).__name__)
            self._attr_is_on = True
            self._available = True
            self.async_write_ha_state()
            _LOGGER.info("Art Mode turned ON via SmartThings for %s", self._device_name)
            return

        _LOGGER.error(
            "Failed to turn Art Mode ON for %s via all methods", self._device_name
        )
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn Art Mode off (switch to normal TV mode)."""
        _LOGGER.debug("Turning Art Mode OFF for %s", self._device_name)

        # Check if TV is on
        tv_is_on = await self._is_tv_on()

        if not tv_is_on:
            _LOGGER.debug("TV is already off, Art Mode is already off")
            self._attr_is_on = False
            self.async_write_ha_state()
            return

        # Try SmartThings API first
        if self._st_api_key and self._st_device_id:
            _LOGGER.info(
                "Art Mode OFF: trying SmartThings API for %s", self._device_name
            )
            if await self._st_set_artmode(False):
                self._attr_is_on = False
                self._available = True
                self.async_write_ha_state()
                _LOGGER.info(
                    "Art Mode turned OFF via SmartThings for %s", self._device_name
                )
                return

        # Fallback: local WebSocket
        try:
            async with asyncio.timeout(15):
                result = await self._art_api.set_artmode(False)
                if result:
                    self._attr_is_on = False
                    self._available = True
                    self.async_write_ha_state()
                    _LOGGER.info(
                        "Art Mode turned OFF via local API for %s", self._device_name
                    )
                    return
        except (asyncio.TimeoutError, Exception) as ex:
            _LOGGER.warning("Local art API OFF failed: %s", ex)

        _LOGGER.warning("Failed to turn Art Mode OFF for %s", self._device_name)

    async def async_update(self) -> None:
        """Update the Art Mode state."""
        if self._updating:
            return

        self._updating = True
        try:
            # FIRST: Check if TV is powered off
            tv_is_on = await self._is_tv_on()

            if not tv_is_on:
                # TV is off, Art Mode must be off too
                _LOGGER.debug("TV is off, setting Art Mode to off")
                self._attr_is_on = False
                self._available = True
                return

            # TV is on, get actual Art Mode status
            async with asyncio.timeout(8):
                art_mode = await self._art_api.get_artmode()
                if art_mode is not None:
                    self._attr_is_on = art_mode == "on"
                    self._available = True
                    _LOGGER.debug("Art Mode state updated: %s", self._attr_is_on)
                else:
                    _LOGGER.debug("Could not get Art Mode state")
        except asyncio.TimeoutError:
            _LOGGER.debug("Timeout updating Art Mode state")
            # Don't mark as unavailable on timeout - TV might be off
        except Exception as ex:
            _LOGGER.debug("Error updating Art Mode state: %s", ex)
        finally:
            self._updating = False

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""
        # Schedule initial state update
        self.hass.async_create_background_task(
            self.async_update(),
            f"frame_art_switch_initial_update_{self._entry.entry_id}",
        )


class SamsungTVPowerSwitch(SwitchEntity):
    """Switch for turning Samsung TV on/off via SmartThings API."""

    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_has_entity_name = True
    _attr_translation_key = "power"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_name: str,
        session,  # aiohttp session
    ) -> None:
        """Initialize the power switch."""
        self.hass = hass
        self._entry = entry
        self._session = session
        self._device_id = device_id
        self._device_name = device_name
        self._attr_unique_id = f"{entry.entry_id}_power"
        self._attr_is_on = False
        self._available = True

        # Command pending tracking to prevent state flicker
        self._last_command_time: float | None = None
        self._last_command_state: bool | None = None

    async def _get_st_client(self):
        """Get SmartThings client with current token from config entry.

        This ensures the client always uses the latest token after OAuth refresh.
        """
        from pysmartthings import SmartThings

        # Get current token from entry data (may have been refreshed by media_player)
        api_key = await async_get_samsungtv_api_key(self.hass, self._entry)

        if not api_key:
            # Fallback to direct config
            config = self.hass.data[DOMAIN][self._entry.entry_id][DATA_CFG]
            api_key = config.get(CONF_API_KEY)
            if not api_key:
                oauth_token = config.get(CONF_OAUTH_TOKEN)
                if oauth_token and isinstance(oauth_token, dict):
                    api_key = oauth_token.get("access_token")

        if not api_key:
            _LOGGER.warning("No SmartThings API key available for power switch")
            return None

        st_client = SmartThings(session=self._session)
        st_client.authenticate(api_key)
        return st_client

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._device_name,
            manufacturer="Samsung",
            model="Smart TV",
        )

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return "Power"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._available

    @property
    def icon(self) -> str:
        """Return the icon."""
        return "mdi:power" if self._attr_is_on else "mdi:power-off"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the TV on via SmartThings API."""
        try:
            st_client = await self._get_st_client()
            if not st_client:
                _LOGGER.error("Cannot turn on TV: SmartThings client not available")
                return

            # Use Command.ON constant (uppercase), not Command(...)
            await st_client.execute_device_command(
                self._device_id, Capability.SWITCH, Command.ON, COMPONENT_MAIN
            )

            # Track command to prevent state flicker
            self._last_command_time = time.time()
            self._last_command_state = True

            # Set state immediately for responsive UI
            self._attr_is_on = True
            self._available = True
            self.async_write_ha_state()
            _LOGGER.debug("Power switch turned on via SmartThings")

            # Wait longer for SmartThings Cloud to update
            await asyncio.sleep(5)
            await self.async_update()

        except Exception as ex:
            _LOGGER.error("Error turning on TV via SmartThings: %s", ex)
            self._available = False
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the TV off via SmartThings API."""
        try:
            st_client = await self._get_st_client()
            if not st_client:
                _LOGGER.error("Cannot turn off TV: SmartThings client not available")
                return

            # Use Command.OFF constant (uppercase), not Command(...)
            await st_client.execute_device_command(
                self._device_id, Capability.SWITCH, Command.OFF, COMPONENT_MAIN
            )

            # Track command to prevent state flicker
            self._last_command_time = time.time()
            self._last_command_state = False

            # Set state immediately for responsive UI
            self._attr_is_on = False
            self._available = True
            self.async_write_ha_state()
            _LOGGER.debug("Power switch turned off via SmartThings")

            # Wait longer for SmartThings Cloud to update
            await asyncio.sleep(5)
            await self.async_update()

        except Exception as ex:
            _LOGGER.error("Error turning off TV via SmartThings: %s", ex)
            self._available = False
            self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the switch state from SmartThings."""
        try:
            st_client = await self._get_st_client()
            if not st_client:
                self._available = False
                return

            components = await st_client.get_device_status(self._device_id)

            if (
                "main" in components
                and "switch" in components["main"]
                and "switch" in components["main"]["switch"]
            ):
                switch_status = components["main"]["switch"]["switch"]
                new_state = switch_status.value == "on"

                # Check if we recently sent a command
                if (
                    self._last_command_time is not None
                    and self._last_command_state is not None
                ):
                    time_since_command = time.time() - self._last_command_time

                    # If less than 10 seconds since command and state contradicts expected state
                    if (
                        time_since_command < 10
                        and new_state != self._last_command_state
                    ):
                        _LOGGER.debug(
                            "Power switch: Ignoring contradictory update from SmartThings "
                            "(expected: %s, received: %s, time since command: %.1fs)",
                            self._last_command_state,
                            new_state,
                            time_since_command,
                        )
                        # Keep the command state, don't update
                        return

                    # If more than 10 seconds, clear command tracking
                    if time_since_command >= 10:
                        self._last_command_time = None
                        self._last_command_state = None

                # Update state
                self._attr_is_on = new_state
                self._available = True
                _LOGGER.debug(
                    "Power switch state updated from SmartThings: %s",
                    self._attr_is_on,
                )
            else:
                _LOGGER.debug(
                    "Switch capability not available for %s", self._device_name
                )
                self._available = False
        except Exception as ex:
            _LOGGER.warning(
                "Error updating power switch state from SmartThings: %s", ex
            )
            self._available = False

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""
        # Schedule initial state update
        self.hass.async_create_background_task(
            self.async_update(),
            f"power_switch_initial_update_{self._entry.entry_id}",
        )
