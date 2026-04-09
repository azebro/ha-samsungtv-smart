"""Samsung TV Presence Aware binary sensor."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from .const import (
    CONF_NO_PRESENCE_OFF_DELAY,
    CONF_PRESENCE_SENSOR,
    DATA_CFG,
    DATA_OPTIONS,
    DOMAIN,
    SIGNAL_CONFIG_ENTITY,
)
from .entity import SamsungTVEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Samsung TV binary sensors from config entry."""
    config = hass.data[DOMAIN][entry.entry_id][DATA_CFG]
    options = hass.data[DOMAIN][entry.entry_id][DATA_OPTIONS]

    entities: list[BinarySensorEntity] = []

    presence_sensor = options.get(CONF_PRESENCE_SENSOR)
    if presence_sensor:
        no_presence_delay = options.get(CONF_NO_PRESENCE_OFF_DELAY, 10)
        entities.append(
            FrameTVPresenceAwareSensor(
                config=config,
                entry_id=entry.entry_id,
                presence_entity_id=presence_sensor,
                no_presence_delay=no_presence_delay,
            )
        )

    if entities:
        async_add_entities(entities)


class FrameTVPresenceAwareSensor(SamsungTVEntity, BinarySensorEntity):
    """Binary sensor indicating presence-aware state for Art Mode automation."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_has_entity_name = True
    _attr_name = "Presence Aware"
    _attr_should_poll = False

    def __init__(
        self,
        config: dict[str, Any],
        entry_id: str,
        presence_entity_id: str,
        no_presence_delay: int,
    ) -> None:
        """Initialize the presence aware sensor."""
        super().__init__(config, entry_id)
        self._attr_unique_id = f"{entry_id}_presence_aware"
        self._entry_id = entry_id
        self._presence_entity_id = presence_entity_id
        self._no_presence_delay = no_presence_delay
        self._timeout_unsub: callback | None = None
        self._media_player_entity_id: str | None = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to presence sensor changes and config updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_CONFIG_ENTITY, self._update_config
            )
        )
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                self._presence_entity_id,
                self._presence_changed,
            )
        )
        # Set initial state from current presence sensor value
        current = self.hass.states.get(self._presence_entity_id)
        if current and current.state == "on":
            self._attr_is_on = True
        elif current and current.state in ("unavailable", "unknown"):
            self._attr_is_on = None
        else:
            self._attr_is_on = False

    async def async_will_remove_from_hass(self) -> None:
        """Cancel pending timeout on removal."""
        if self._timeout_unsub:
            self._timeout_unsub()
            self._timeout_unsub = None

    @callback
    def _update_config(self, _: Any = None) -> None:
        """Update delay from config options on signal."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry:
            self._no_presence_delay = entry.options.get(CONF_NO_PRESENCE_OFF_DELAY, 10)

    @callback
    def _presence_changed(self, event) -> None:
        """Handle presence state change."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        # Q1 decision: treat unavailable/unknown as no-presence (failsafe)
        if new_state.state in ("unavailable", "unknown"):
            _LOGGER.warning(
                "Presence sensor %s is %s — treating as no presence",
                self._presence_entity_id,
                new_state.state,
            )
            self._start_timeout()
            return

        if new_state.state == "on":
            if self._timeout_unsub:
                self._timeout_unsub()
                self._timeout_unsub = None
            self._attr_is_on = True
            self.async_write_ha_state()
        else:
            self._start_timeout()

    def _start_timeout(self) -> None:
        """Start or restart the no-presence timeout."""
        if self._timeout_unsub:
            self._timeout_unsub()
            self._timeout_unsub = None

        if self._no_presence_delay > 0:
            self._timeout_unsub = async_call_later(
                self.hass,
                self._no_presence_delay * 60,
                self._timeout_expired,
            )
        else:
            self._attr_is_on = False
            self.async_write_ha_state()

    @callback
    def _timeout_expired(self, _now) -> None:
        """Called when no-presence timeout expires."""
        self._timeout_unsub = None
        self._attr_is_on = False
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose art mode and playback status for automation conditions."""
        attrs: dict[str, Any] = {}
        if not self._media_player_entity_id:
            from homeassistant.helpers import entity_registry as er

            entity_reg = er.async_get(self.hass)
            for entity in entity_reg.entities.values():
                if (
                    entity.config_entry_id == self._entry_id
                    and entity.domain == "media_player"
                ):
                    self._media_player_entity_id = entity.entity_id
                    break
        if self._media_player_entity_id:
            mp_state = self.hass.states.get(self._media_player_entity_id)
            if mp_state:
                attrs["tv_playing"] = mp_state.state in ("playing", "paused")
                art_mode = mp_state.attributes.get("art_mode_status")
                attrs["art_mode_active"] = art_mode == "on" if art_mode else False
        return attrs
