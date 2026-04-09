# Implementation Plan: Modernization & New Presence-Aware Features

**Version**: 7.0.0
**Target HA Minimum**: 2026.3
**Current HA Minimum**: 2025.6
**Date**: 2026-04-09

---

## Table of Contents

1. [Overview](#1-overview)
2. [Phase 1: HA Modernization](#2-phase-1-ha-modernization)
3. [Phase 2a: Presence-Based Art Mode Switching](#3-phase-2a-presence-based-art-mode-switching)
4. [Phase 2b: Illuminance-Based Art Brightness Control](#4-phase-2b-illuminance-based-art-brightness-control)
5. [Phase 2c: No-Presence Auto-Off](#5-phase-2c-no-presence-auto-off)
6. [Phase 3: New Entities](#6-phase-3-new-entities)
7. [Configuration Schema](#7-configuration-schema)
8. [Safety Guards](#8-safety-guards)
9. [File Change Summary](#9-file-change-summary)
10. [Testing Strategy](#10-testing-strategy)
11. [Migration Notes](#11-migration-notes)

---

## 1. Overview

### Goals

1. **Modernize** the integration to comply with HA 2026.3 APIs and deprecation removals.
2. **Add presence-aware Art Mode** — when a presence sensor detects occupancy, the TV switches to Art Mode (configurable via integration options; user writes HA automations calling exposed entities & services).
3. **Add illuminance-based brightness** — when a lux sensor is configured, the integration exposes a `number` entity and internal logic to map lux values to art brightness via a logarithmic curve.
4. **Auto-off on no presence** — when Art Mode is active and no presence is detected for X minutes, the TV turns off completely.

### Design Decisions (Per User Input)

| Decision | Choice |
|---|---|
| Automation logic location | **Option B** — integration exposes entities and services; user writes HA automations. Integration includes guards to prevent disrupting active playback. |
| Brightness mapping | **Logarithmic curve** — better matches human perception. |
| No-presence auto-off scope | **Art Mode only** — only triggers when TV is in Art Mode, never interrupts active viewing. |
| New entities | **Yes** — new `binary_sensor` for presence-aware state tracking. |
| HA minimum version | **Bump to 2026.3**. |

---

## 2. Phase 1: HA Modernization

Bring the codebase up to HA 2026.3 standards before adding features.

### 2.1 Replace `async_timeout` with `asyncio.timeout`

`async_timeout` is deprecated in favor of the stdlib `asyncio.timeout()` (available since Python 3.11, required by HA 2025.x+).

**Files to change:**

| File | Current | Replacement |
|---|---|---|
| `__init__.py` L14, L622, L730, L757 | `import async_timeout` / `async with async_timeout.timeout(N)` | Remove import, use `async with asyncio.timeout(N)` |
| `media_player.py` L17, L1171 | Same pattern | Same replacement |
| `api/upnp.py` L8, L47 | Same pattern | Same replacement |

**Steps:**

1. Remove `import async_timeout` from all three files.
2. Add `import asyncio` if not already present (it is already present in `__init__.py` and `media_player.py`; add to `upnp.py`).
3. Replace every `async with async_timeout.timeout(X):` with `async with asyncio.timeout(X):`.
4. Remove `async_timeout` from `requirements.txt` and `manifest.json` requirements (it is not listed — it was a transitive dependency, so no action needed on those files).

### 2.2 Bump Minimum HA Version

**Files to change:**

- `const.py` — change `MIN_HA_MAJ_VER = 2025` / `MIN_HA_MIN_VER = 6` → `MIN_HA_MAJ_VER = 2026` / `MIN_HA_MIN_VER = 3`
- `const.py` — `__min_ha_version__` will auto-compute to `"2026.3.0"`.
- `manifest.json` — update `"version": "7.0.0"` (major bump for breaking min-version change).
- `requirements.txt` — update `homeassistant==2026.3.0` (or latest 2026.3.x).

### 2.3 Add Local Brand Images (New HA 2026.3 Feature)

HA 2026.3 supports local brand images for custom integrations.

**Steps:**

1. Create directory `custom_components/samsungtv_smart/brand/`.
2. Add `icon.png` and `logo.png` files with appropriate Samsung TV Smart branding.
3. No manifest changes required — HA discovers the `brand/` folder automatically.

### 2.4 OAuth2 Error Handling Modernization

HA 2026.3 introduces new OAuth token exceptions: `OAuth2TokenRequestTransientError`, `OAuth2TokenRequestReauthError`, `OAuth2TokenRequestError`.

**Files to change:**

- `__init__.py` — in `async_get_samsungtv_api_key()`, wrap `implementation.async_refresh_token()` calls to catch new exception types instead of bare `Exception`.
- `media_player.py` — in `_do_oauth_refresh()`, same pattern.

**Steps:**

1. Import `OAuth2TokenRequestReauthError`, `OAuth2TokenRequestTransientError` from `homeassistant.helpers.config_entry_oauth2_flow`.
2. Replace generic `except Exception` around token refresh with specific catches:
   - `OAuth2TokenRequestReauthError` → trigger reauth flow via `ConfigEntryAuthFailed`.
   - `OAuth2TokenRequestTransientError` → log warning, retry later.
   - `OAuth2TokenRequestError` → log error, use stale token.

### 2.5 Use `entry.runtime_data` Pattern

Current code stores integration data in `hass.data[DOMAIN][entry.entry_id]` (dict-based). The modern HA pattern uses typed `entry.runtime_data`. **This refactor is mandatory in Phase 1** — all Phase 2 code will be written against the new pattern.

**Steps:**

1. Define a `dataclass` in `__init__.py`:

   ```python
   from dataclasses import dataclass, field

   @dataclass
   class SamsungTVRuntimeData:
       """Runtime data for a Samsung TV Smart config entry."""
       cfg: dict
       options: dict
       cfg_yaml: dict = field(default_factory=dict)
       art_api: SamsungTVAsyncArt | None = None
   ```

2. Create a type alias:

   ```python
   type SamsungTVConfigEntry = ConfigEntry[SamsungTVRuntimeData]
   ```

3. In `async_setup_entry`, store data on `entry.runtime_data` instead of `hass.data[DOMAIN][entry_id]`.
4. Update all consumers (`media_player.py`, `sensor.py`, `switch.py`, `remote.py`, `diagnostics.py`) to read from `entry.runtime_data`.
5. Keep `hass.data[DOMAIN]` only for global data (logo paths).

> **Note**: This is a significant refactor touching ~20 call sites across 6 files but must be done in Phase 1 so all Phase 2 code uses the new pattern consistently.

### 2.6 Centralize `art_api` Creation in `__init__.py`

**Problem (review finding C3):** Currently `sensor.py` and `switch.py` both independently check for and create `SamsungTVAsyncArt` instances. Since `async_forward_entry_setups` runs platforms concurrently, two platforms can race to create separate WebSocket connections, leaking one.

**Fix:** Create `art_api` exactly once in `async_setup_entry` in `__init__.py`, before forwarding to platforms.

```python
async def async_setup_entry(hass, entry):
    # ... existing setup ...

    # Create Art API once for all platforms
    art_api = None
    session = async_get_clientsession(hass)
    host = config[CONF_HOST]
    port = config.get(CONF_PORT, DEFAULT_PORT)
    token = config.get(CONF_TOKEN)
    ws_name = config.get(CONF_WS_NAME, "HomeAssistant")

    try:
        async with asyncio.timeout(5):
            art_api_candidate = SamsungTVAsyncArt(
                host=host, port=port, token=token,
                session=session, timeout=5,
                name=f"{WS_PREFIX} {ws_name} Art",
            )
            if await art_api_candidate.supported():
                art_api = art_api_candidate
    except (asyncio.TimeoutError, Exception):
        pass  # Not a Frame TV or TV is off

    # Store in runtime_data
    entry.runtime_data = SamsungTVRuntimeData(
        cfg=config, options=entry.options.copy(),
        art_api=art_api,
    )

    await hass.config_entries.async_forward_entry_setups(entry, SAMSMART_PLATFORM)
```

All platform files (`sensor.py`, `switch.py`, `number.py`) consume `entry.runtime_data.art_api` — they never create their own instance. Remove all `art_api` creation logic from `sensor.py` and `switch.py`.

### 2.7 Remove `async_timeout` Dependency from `requirements.txt`

`async_timeout` is no longer imported anywhere after 2.1. Verify it is not listed in `requirements.txt` or `manifest.json` `requirements`. Currently it is not, as it was a transitive dependency of `homeassistant`. No action required.

### 2.8 Fix Existing `get_brightness()` Return Type Bug

**Problem (review finding C1):** `art_api.get_brightness()` returns a `dict | None` (e.g., `{"value": "5"}`), not an `int`. The existing `media_player.py` line ~2797 does `result * 10` on this dict, which crashes. The existing `async_art_set_brightness` at line ~2780 also has two competing conversion formulas — the first is computed then immediately overwritten.

**Fix in Phase 1** (before new entities rely on it):

1. In `media_player.py` `async_art_get_brightness()`, parse the dict:
   ```python
   result = await self._art_api.get_brightness()
   if result and isinstance(result, dict):
       tv_val = int(result.get("value", 0))
       return {"brightness_tv": tv_val, "brightness_ui": tv_val * 10}
   ```
2. In `media_player.py` `async_art_set_brightness()`, remove the duplicate conversion formula — keep only:
   ```python
   tv_brightness = max(1, min(10, round(brightness / 10)))
   ```
   Note: minimum is `1`, not `0` — the TV API does not accept brightness 0.

---

## 3. Phase 2a: Presence-Based Art Mode Switching

### Architecture

The integration does **not** embed automation logic. Instead, it:

1. Exposes a **config option** to select a presence sensor entity (e.g., `binary_sensor.living_room_presence`).
2. Creates a **`binary_sensor` entity** (`binary_sensor.<tv_name>_presence_aware`) that tracks whether the TV should be in Art Mode based on presence state.
3. Exposes the existing `switch.<tv_name>_art_mode` entity for toggling Art Mode.
4. **Guards** in the Art Mode switch prevent enabling Art Mode if the TV is actively playing content.

The user then writes a simple HA automation:

```yaml
automation:
  - alias: "TV Art Mode on presence"
    trigger:
      - platform: state
        entity_id: binary_sensor.living_room_tv_presence_aware
        to: "on"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.living_room_tv_art_mode
```

### Config Options to Add

| Option Key | Type | Default | Description |
|---|---|---|---|
| `presence_sensor` | `entity_id` (binary_sensor) | `None` | Presence sensor entity to monitor. |

### Implementation Steps

#### 3.1 Add Config Constants

**File**: `const.py`

```python
CONF_PRESENCE_SENSOR = "presence_sensor"
```

#### 3.2 Add Options Flow Entry

**File**: `config_flow.py`

In the `OptionsFlowHandler`, add `CONF_PRESENCE_SENSOR` to the main options form with an `EntitySelector` filtered to `binary_sensor` domain.

```python
vol.Optional(
    CONF_PRESENCE_SENSOR,
    description={"suggested_value": options.get(CONF_PRESENCE_SENSOR)},
): EntitySelector(EntitySelectorConfig(domain="binary_sensor")),
```

#### 3.3 Add Strings/Translations

**File**: `strings.json` only (HA auto-generates `translations/en.json` from `strings.json`)

Add translation keys for the new option:

```json
"presence_sensor": {
  "name": "Presence Sensor",
  "description": "Binary sensor entity for room presence detection. Used to trigger Art Mode and auto-off."
}
```

#### 3.4 Add Guards to Art Mode Switch

**File**: `switch.py` — `FrameArtModeSwitch.async_turn_on()`

Before enabling Art Mode, check if the TV is actively playing content:

```python
async def async_turn_on(self, **kwargs: Any) -> None:
    """Turn Art Mode on."""
    # Guard: do not switch to Art Mode if TV is actively playing
    if await self._is_tv_playing_content():
        _LOGGER.info(
            "Art Mode not activated: TV is currently playing content on %s",
            self._device_name,
        )
        return
    # ... existing logic
```

The `_is_tv_playing_content()` method checks the media_player state:

```python
async def _is_tv_playing_content(self) -> bool:
    """Check if TV is actively playing content (not idle/art mode)."""
    entity_id = self._get_media_player_entity_id()
    if not entity_id:
        return False
    state = self.hass.states.get(entity_id)
    if state is None:
        return False
    # Consider "playing" or "paused" as active content
    return state.state in ("playing", "paused")
```

---

## 4. Phase 2b: Illuminance-Based Art Brightness Control

### Architecture

The integration:

1. Exposes a **config option** to select an illuminance sensor entity (e.g., `sensor.living_room_lux`).
2. Exposes config options for **min/max lux thresholds** and min/max brightness values.
3. Creates a **`number` entity** (`number.<tv_name>_art_brightness`) that represents the current art mode brightness (0–100) and can be set manually.
4. Creates a **`sensor` entity** (`sensor.<tv_name>_recommended_art_brightness`) that outputs the computed recommended brightness based on current lux reading and the logarithmic mapping.
5. The user writes an automation to apply the recommended brightness:

```yaml
automation:
  - alias: "Auto art brightness"
    trigger:
      - platform: state
        entity_id: sensor.living_room_tv_recommended_art_brightness
    condition:
      - condition: state
        entity_id: switch.living_room_tv_art_mode
        state: "on"
    action:
      - service: number.set_value
        target:
          entity_id: number.living_room_tv_art_brightness
        data:
          value: "{{ trigger.to_state.state }}"
```

### Logarithmic Brightness Mapping

The mapping function converts lux to brightness (0–100) using a logarithmic curve:

```python
import math

def lux_to_brightness(
    lux: float,
    min_lux: float = 1.0,
    max_lux: float = 1000.0,
    min_brightness: int = 5,
    max_brightness: int = 100,
) -> int:
    """Map lux to brightness using logarithmic curve.

    Uses log10 for perceptual linearity:
    - 1 lux   → min_brightness (dark room)
    - 10 lux  → ~33% brightness
    - 100 lux → ~67% brightness
    - 1000 lux → max_brightness (bright room)
    """
    if lux <= min_lux:
        return min_brightness
    if lux >= max_lux:
        return max_brightness

    # Normalize to 0-1 range using log scale
    log_min = math.log10(max(min_lux, 0.1))
    log_max = math.log10(max_lux)
    log_lux = math.log10(lux)

    normalized = (log_lux - log_min) / (log_max - log_min)
    brightness = min_brightness + normalized * (max_brightness - min_brightness)
    return max(min_brightness, min(max_brightness, round(brightness)))
```

### Config Options to Add

| Option Key | Type | Default | Description |
|---|---|---|---|
| `illuminance_sensor` | `entity_id` (sensor) | `None` | Illuminance sensor entity (must report `lx`). |
| `brightness_min_lux` | `int` | `1` | Lux value that maps to minimum brightness. |
| `brightness_max_lux` | `int` | `1000` | Lux value that maps to maximum brightness. |
| `brightness_min` | `int` | `5` | Minimum art brightness (0–100). |
| `brightness_max` | `int` | `100` | Maximum art brightness (0–100). |

### Implementation Steps

#### 4.1 Add Config Constants

**File**: `const.py`

```python
CONF_ILLUMINANCE_SENSOR = "illuminance_sensor"
CONF_BRIGHTNESS_MIN_LUX = "brightness_min_lux"
CONF_BRIGHTNESS_MAX_LUX = "brightness_max_lux"
CONF_BRIGHTNESS_MIN = "brightness_min"
CONF_BRIGHTNESS_MAX = "brightness_max"
```

#### 4.2 Add Options Flow Entries

**File**: `config_flow.py`

Add presence and illuminance options as a **new menu step** `async_step_presence_art` (review finding M3 — can’t conditionally show/hide fields within a single HA form step). This fits the existing advanced options menu architecture.

```python
async def async_step_presence_art(self, user_input=None):
    """Handle presence & art mode options."""
    errors = {}
    if user_input is not None:
        # Validate min < max (review finding Q4)
        min_lux = user_input.get(CONF_BRIGHTNESS_MIN_LUX, 1)
        max_lux = user_input.get(CONF_BRIGHTNESS_MAX_LUX, 1000)
        min_br = user_input.get(CONF_BRIGHTNESS_MIN, 5)
        max_br = user_input.get(CONF_BRIGHTNESS_MAX, 100)
        if min_lux >= max_lux:
            errors[CONF_BRIGHTNESS_MAX_LUX] = "min_gte_max"
        elif min_br >= max_br:
            errors[CONF_BRIGHTNESS_MAX] = "min_gte_max"
        else:
            self._std_options.update(user_input)
            return await self.async_step_menu()

    data_schema = vol.Schema({
        vol.Optional(
            CONF_PRESENCE_SENSOR,
            description={"suggested_value": options.get(CONF_PRESENCE_SENSOR)},
        ): EntitySelector(EntitySelectorConfig(domain="binary_sensor")),
        vol.Optional(
            CONF_NO_PRESENCE_OFF_DELAY,
            default=options.get(CONF_NO_PRESENCE_OFF_DELAY, 10),
        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=120)),
        vol.Optional(
            CONF_ILLUMINANCE_SENSOR,
            description={"suggested_value": options.get(CONF_ILLUMINANCE_SENSOR)},
        ): EntitySelector(EntitySelectorConfig(
            domain="sensor",
            device_class=SensorDeviceClass.ILLUMINANCE,
        )),
        vol.Optional(
            CONF_BRIGHTNESS_MIN_LUX,
            default=options.get(CONF_BRIGHTNESS_MIN_LUX, 1),
        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=10000)),
        vol.Optional(
            CONF_BRIGHTNESS_MAX_LUX,
            default=options.get(CONF_BRIGHTNESS_MAX_LUX, 1000),
        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100000)),
        vol.Optional(
            CONF_BRIGHTNESS_MIN,
            default=options.get(CONF_BRIGHTNESS_MIN, 5),
        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional(
            CONF_BRIGHTNESS_MAX,
            default=options.get(CONF_BRIGHTNESS_MAX, 100),
        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
    })
    return self.async_show_form(
        step_id="presence_art",
        data_schema=data_schema,
        errors=errors,
    )
```

Add `"presence_art"` to the `menu_options` list in `async_step_menu()`.

**Validation (review finding Q4):** Cross-field validation ensures `min_lux < max_lux` and `min_brightness < max_brightness`. If violated, the form redisplays with an error.

#### 4.3 Add `number` Platform

**New file**: `custom_components/samsungtv_smart/number.py`

Create a `NumberEntity` for art brightness control. **Must include `async_update` for polling** (review finding M2 — without it, the entity is stale after restart or external TV changes).

```python
class FrameArtBrightnessNumber(SamsungTVEntity, NumberEntity):
    """Number entity for controlling Frame TV art brightness."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"
    _attr_has_entity_name = True
    _attr_name = "Art Brightness"
    _attr_icon = "mdi:brightness-6"

    # Poll every 60 seconds to sync with external changes
    _attr_should_poll = True
    SCAN_INTERVAL = timedelta(seconds=60)

    async def async_set_native_value(self, value: float) -> None:
        """Set art brightness via the Art API."""
        brightness = int(value)
        # Convert 0-100 to TV's 1-10 scale (min 1, TV rejects 0)
        tv_brightness = max(1, min(10, round(brightness / 10)))
        await self._art_api.set_brightness(tv_brightness)
        self._attr_native_value = brightness

    async def async_update(self) -> None:
        """Read current brightness from TV."""
        try:
            result = await self._art_api.get_brightness()
            if result and isinstance(result, dict):
                tv_val = int(result.get("value", 0))
                self._attr_native_value = tv_val * 10  # convert 1-10 to 0-100
        except Exception:
            pass  # TV may be off
```

**Key decisions:**
- Extends `SamsungTVEntity` for correct device linkage (review finding M5).
- Uses `max(1, ...)` consistently (review finding m1 — TV API rejects brightness 0).
- Parses `get_brightness()` dict response correctly (review finding C1).
- Includes `async_update` with 60s poll interval for state synchronization.

#### 4.4 Add Recommended Brightness Sensor

**File**: `sensor.py` (extend existing file)

Add a `SensorEntity` that computes recommended brightness from the configured illuminance sensor. **Must debounce updates** (review finding M4 — lux sensors can update every 1–5 seconds, which would flood the TV with API calls).

The `lux_to_brightness()` function lives in `sensor.py` alongside its only consumer (review finding m3 — no need for a separate `utils.py` for a single function).

```python
class FrameArtRecommendedBrightnessSensor(SamsungTVEntity, SensorEntity):
    """Sensor showing recommended art brightness based on ambient light."""

    _attr_has_entity_name = True
    _attr_name = "Recommended Art Brightness"
    _attr_icon = "mdi:brightness-auto"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = False

    def __init__(self, config, entry_id, illuminance_entity_id, lux_config):
        super().__init__(config, entry_id)
        self._illuminance_entity_id = illuminance_entity_id
        self._lux_config = lux_config
        self._debounce_unsub = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to illuminance sensor state changes."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                self._illuminance_entity_id,
                self._illuminance_changed,
            )
        )

    @callback
    def _illuminance_changed(self, event) -> None:
        """Handle illuminance state change with debounce."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return

        try:
            lux = float(new_state.state)
        except (ValueError, TypeError):
            return

        new_brightness = lux_to_brightness(lux, **self._lux_config)

        # Only write state when computed value actually changes
        if new_brightness == self._attr_native_value:
            return

        # Debounce: wait 30s for lux to stabilize before updating
        if self._debounce_unsub:
            self._debounce_unsub()
        self._debounce_unsub = async_call_later(
            self.hass, 30, partial(self._apply_brightness, new_brightness)
        )

    @callback
    def _apply_brightness(self, brightness, _now) -> None:
        """Apply debounced brightness value."""
        self._debounce_unsub = None
        self._attr_native_value = brightness
        self.async_write_ha_state()
```

**Debounce strategy** (two layers):
1. Only fire when the **integer brightness result changes** (log curve rounds, so many small lux changes produce the same int).
2. 30-second `async_call_later` delay — cancelled/restarted on each new update, so only the final stabilized reading fires.

**Entity inheritance**: extends `SamsungTVEntity` for correct device grouping (review finding M5).

#### 4.5 Register New Platform

**File**: `__init__.py`

Add `Platform.NUMBER` to `SAMSMART_PLATFORM`:

```python
SAMSMART_PLATFORM = [
    Platform.SENSOR,
    Platform.MEDIA_PLAYER,
    Platform.REMOTE,
    Platform.SWITCH,
    Platform.NUMBER,
]
```

**File**: `manifest.json` — no change needed; HA discovers platforms from the module.

---

## 5. Phase 2c: No-Presence Auto-Off

### Architecture

The integration:

1. Exposes a **config option** for `no_presence_off_delay` (minutes).
2. This feature **requires** `presence_sensor` to also be configured.
3. This uses the **same** `binary_sensor.<tv_name>_presence_aware` entity from Phase 2a — it turns `off` after the configured delay once presence is lost.
4. The user writes an automation:

```yaml
automation:
  - alias: "TV off after no presence"
    trigger:
      - platform: state
        entity_id: binary_sensor.living_room_tv_presence_aware
        to: "off"
    condition:
      - condition: state
        entity_id: switch.living_room_tv_art_mode
        state: "on"
    action:
      - service: media_player.turn_off
        target:
          entity_id: media_player.living_room_tv
```

> **Note (review finding C2):** There is only ONE binary_sensor entity (`_presence_aware`). It is `on` when presence is detected, and transitions to `off` after the configured delay. Both the Art Mode activation automation and the auto-off automation use this same entity with different trigger values (`to: "on"` vs `to: "off"`).

### Guards

The `media_player.turn_off` service already handles the TV power-off. The integration adds an extra safety attribute `art_mode_active` to the binary_sensor output, but the **automation condition** is the primary guard — it only fires when Art Mode is active.

If the TV is playing content (not in Art Mode), the automation condition blocks execution.

### Config Options to Add

| Option Key | Type | Default | Description |
|---|---|---|---|
| `no_presence_off_delay` | `int` (minutes) | `10` | Minutes of no presence before the binary_sensor turns off. Set 0 to disable. |

### Implementation Steps

#### 5.1 Add Config Constant

**File**: `const.py`

```python
CONF_NO_PRESENCE_OFF_DELAY = "no_presence_off_delay"
```

#### 5.2 Add Options Flow Entry

**File**: `config_flow.py`

Add the delay input to the options form, only visible when `presence_sensor` is configured:

```python
vol.Optional(
    CONF_NO_PRESENCE_OFF_DELAY,
    default=options.get(CONF_NO_PRESENCE_OFF_DELAY, 10),
): vol.All(vol.Coerce(int), vol.Range(min=0, max=120)),
```

#### 5.3 Add Strings/Translations

Add translation keys for the new option.

---

## 6. Phase 3: New Entities

### 6.1 Binary Sensor: Presence Aware

**New file**: `custom_components/samsungtv_smart/binary_sensor.py`

This is the **single** presence-related entity (review finding C2 resolved). It handles both "presence detected → trigger art mode" and "presence lost + delay → trigger auto-off".

```python
class FrameTVPresenceAwareSensor(SamsungTVEntity, BinarySensorEntity):
    """Binary sensor that indicates if presence is detected and TV should show art."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_has_entity_name = True
    _attr_name = "Presence Aware"
    _attr_should_poll = False

    def __init__(self, config, entry_id, presence_entity_id, no_presence_delay):
        super().__init__(config, entry_id)
        self._attr_unique_id = f"{entry_id}_presence_aware"
        self._presence_entity_id = presence_entity_id
        self._no_presence_delay = no_presence_delay  # minutes
        self._timeout_unsub = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to presence sensor changes."""
        # Listen to config changes to update delay at runtime (M1/Q6)
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
            self._attr_is_on = None  # unavailable
        else:
            self._attr_is_on = False

    @callback
    def _update_config(self, _=None) -> None:
        """Update delay from config options (Q6 fix)."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry:
            self._no_presence_delay = entry.options.get(
                CONF_NO_PRESENCE_OFF_DELAY, 10
            )

    @callback
    def _presence_changed(self, event) -> None:
        """Handle presence state change."""
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        # Handle unavailable/unknown presence sensor (Q1 decision: treat as no-presence)
        if new_state.state in ("unavailable", "unknown"):
            _LOGGER.warning(
                "Presence sensor %s is %s — treating as no presence",
                self._presence_entity_id, new_state.state,
            )
            # Start timeout as if presence lost
            if self._attr_is_on:
                if self._no_presence_delay > 0:
                    if self._timeout_unsub:
                        self._timeout_unsub()
                    self._timeout_unsub = async_call_later(
                        self.hass,
                        self._no_presence_delay * 60,
                        self._timeout_expired,
                    )
                else:
                    self._attr_is_on = False
                    self.async_write_ha_state()
            return

        if new_state.state == "on":
            # Cancel any pending timeout
            if self._timeout_unsub:
                self._timeout_unsub()
                self._timeout_unsub = None
            self._attr_is_on = True
            self.async_write_ha_state()
        else:
            # Start timeout countdown
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
```

**Key design decisions:**
- Extends `SamsungTVEntity` for correct device linkage (review finding M5).
- Single entity for both presence-on and presence-timeout (review finding C2).
- Listens to `SIGNAL_CONFIG_ENTITY` to update `no_presence_delay` at runtime without reload (review finding Q6).
- When presence sensor goes `unavailable`/`unknown`, **treats as no-presence** and starts the timeout countdown (Q1 decision — failsafe to eventually turn off TV and save power). Logs a warning.
- Sets initial state from current presence sensor value on `async_added_to_hass`.

**Extra attributes** to expose via `extra_state_attributes`:

- `art_mode_active` — reflects current Art Mode state (from TV).
- `tv_playing` — reflects whether the TV is actively playing content.

These allow advanced automations to condition on playback state.

### 6.2 Register Platform

**File**: `__init__.py`

Add `Platform.BINARY_SENSOR` to `SAMSMART_PLATFORM`.

---

## 7. Configuration Schema

### Options Flow — Full Updated Schema

Presence & illuminance options are in a **separate menu step** (`async_step_presence_art`) accessible from the advanced options menu (review finding M3):

```
┌─ Standard Options (async_step_init) ─────────────────┐
│  Logo Option            [dropdown]                    │
│  Use Local Logo         [toggle]                      │
│  App Load Method        [dropdown]                    │
│  ST Status Info         [toggle]  (if SmartThings)    │
│  ST Channel Info        [toggle]  (if SmartThings)    │
│  Show Channel Number    [toggle]                      │
│  Power On Method        [dropdown] (if SmartThings)   │
│  [Show Advanced Options] [toggle]                     │
└───────────────────────────────────────────────────────┘

┌─ Advanced Menu (async_step_menu) ────────────────────┐
│  > Source List                                        │
│  > App List                                           │
│  > Channel List                                       │
│  > Sync Entities                                      │
│  > Presence & Art Mode    ← NEW                       │
│  > Standard Options                                   │
│  > Advanced Options                                   │
│  > Save & Exit                                        │
└───────────────────────────────────────────────────────┘

┌─ Presence & Art Mode (async_step_presence_art) ──────┐
│  Presence Sensor        [entity selector]             │
│  No-Presence Off Delay  [number] minutes              │
│  Illuminance Sensor     [entity selector]             │
│  Min Lux Threshold      [number]                      │
│  Max Lux Threshold      [number]                      │
│  Min Brightness         [number]                      │
│  Max Brightness         [number]                      │
└───────────────────────────────────────────────────────┘
```

### Entity Creation on Options Change (Review Finding M1)

The current `_update_listener` only updates options dict in memory. When a user adds a `presence_sensor` or `illuminance_sensor` in options, the new binary_sensor/number platform `async_setup_entry` has already run (with no sensor configured).

**Fix:** In `_update_listener`, detect when presence/illuminance sensor options are added or removed, and reload the entry:

```python
async def _update_listener(hass, entry):
    """Update when config_entry options update."""
    old_options = hass.data[DOMAIN].get(f"{entry.entry_id}_prev_opts", {})
    new_options = entry.options

    # Check if sensor configs changed (requires entity re-creation)
    sensor_keys = {CONF_PRESENCE_SENSOR, CONF_ILLUMINANCE_SENSOR}
    old_sensors = {k: old_options.get(k) for k in sensor_keys}
    new_sensors = {k: new_options.get(k) for k in sensor_keys}

    hass.data[DOMAIN][f"{entry.entry_id}_prev_opts"] = new_options.copy()

    if old_sensors != new_sensors:
        # Sensor config changed — reload to create/remove entities
        await hass.config_entries.async_reload(entry.entry_id)
    else:
        # Normal options update — signal entities to refresh config
        entry.runtime_data.options = new_options.copy()
        async_dispatcher_send(hass, SIGNAL_CONFIG_ENTITY)
```

### Non-Frame TV Handling (Review Finding Q5)

New platforms (`binary_sensor.py`, `number.py`) must handle non-Frame TVs gracefully:

```python
async def async_setup_entry(hass, entry, async_add_entities):
    art_api = entry.runtime_data.art_api  # may be None for non-Frame TVs
    options = entry.runtime_data.options
    config = entry.runtime_data.cfg

    entities = []

    # Only create presence sensor if configured
    presence_sensor = options.get(CONF_PRESENCE_SENSOR)
    if presence_sensor:
        entities.append(FrameTVPresenceAwareSensor(...))

    # Only create brightness entities if illuminance sensor configured AND TV is Frame
    illuminance_sensor = options.get(CONF_ILLUMINANCE_SENSOR)
    if illuminance_sensor and art_api:
        entities.append(FrameArtBrightnessNumber(...))
        entities.append(FrameArtRecommendedBrightnessSensor(...))

    if entities:
        async_add_entities(entities)
```

Non-Frame TVs: `art_api` is `None`, so brightness entities are never created. Presence sensor works for any TV (it doesn't depend on Frame TV support).

---

## 8. Safety Guards

### 8.1 Playback Protection

**Where**: `switch.py` (`FrameArtModeSwitch.async_turn_on`)

**Logic**: Before activating Art Mode, check the linked `media_player` entity state. If the state is `playing` or `paused`, log an info message and return without switching. This prevents an automation from interrupting active TV viewing.

```python
ACTIVE_PLAYBACK_STATES = {"playing", "paused"}

async def async_turn_on(self, **kwargs):
    mp_state = self.hass.states.get(self._get_media_player_entity_id())
    if mp_state and mp_state.state in ACTIVE_PLAYBACK_STATES:
        _LOGGER.info("Art Mode activation blocked: TV is playing content")
        # Fire event so automations can react (Q2 decision)
        self.hass.bus.async_fire(
            f"{DOMAIN}_art_mode_blocked",
            {"entity_id": self.entity_id, "reason": "playback_active"},
        )
        return
    # ... existing Art Mode activation logic
```

The `samsungtv_smart_art_mode_blocked` event lets advanced users create automations that react to guard blocks (e.g., send a notification).

### 8.2 Turn-Off Protection

**Where**: User automations (documented in README)

The auto-off automation should **always** include a condition checking `switch.art_mode` is `on`. If the TV is actively being watched (Art Mode switch is off, TV is in normal mode), the automation does not fire.

### 8.3 State Consistency

**Where**: `binary_sensor.py`

The `FrameTVPresenceAwareSensor` exposes `extra_state_attributes` with `art_mode_active` and `tv_playing` boolean flags, read from the linked media_player entity. This allows users to add granular conditions to their automations.

---

## 9. File Change Summary

| File | Action | Description |
|---|---|---|
| `const.py` | **Modify** | Bump HA version, add new `CONF_*` constants |
| `manifest.json` | **Modify** | Bump version to `7.0.0` |
| `__init__.py` | **Modify** | Replace `async_timeout`, refactor to `runtime_data`, centralize `art_api` creation, add `Platform.NUMBER` and `Platform.BINARY_SENSOR`, fix `_update_listener` for entity reload |
| `media_player.py` | **Modify** | Replace `async_timeout`, fix `get_brightness()` dict parsing (C1), fix duplicate brightness conversion (m5) |
| `api/upnp.py` | **Modify** | Replace `async_timeout` |
| `config_flow.py` | **Modify** | Add `async_step_presence_art` menu step with cross-field validation |
| `switch.py` | **Modify** | Add playback guard to `FrameArtModeSwitch.async_turn_on`, remove `art_api` creation (moved to `__init__.py`) |
| `sensor.py` | **Modify** | Add `FrameArtRecommendedBrightnessSensor` with debounce, add `lux_to_brightness()` function, remove `art_api` creation (moved to `__init__.py`) |
| `binary_sensor.py` | **Create** | New `FrameTVPresenceAwareSensor` entity with timeout and unavailable handling |
| `number.py` | **Create** | New `FrameArtBrightnessNumber` entity with polling |
| `strings.json` | **Modify** | Add translation keys for new options and entities |
| `services.yaml` | **No change** | Existing art services are sufficient |
| `requirements.txt` | **Modify** | Update `homeassistant` version |
| `brand/icon.png` | **Create** | Local brand icon |
| `brand/logo.png` | **Create** | Local brand logo |

### New Files

1. `custom_components/samsungtv_smart/binary_sensor.py` (~120 lines)
2. `custom_components/samsungtv_smart/number.py` (~100 lines)
3. `custom_components/samsungtv_smart/brand/icon.png`
4. `custom_components/samsungtv_smart/brand/logo.png`

---

## 10. Testing Strategy

### Unit Tests to Add

| Test File | Coverage |
|---|---|
| `tests/test_binary_sensor.py` | Presence sensor tracking, timeout logic, state attributes |
| `tests/test_number.py` | Brightness set/get, lux-to-brightness mapping function |
| `tests/test_switch_guards.py` | Playback protection guard in Art Mode switch |
| `tests/test_brightness_mapping.py` | Logarithmic mapping function — edge cases (0 lux, max lux, boundary values) |
| `tests/test_config_flow_options.py` | New options rendered correctly, validation of thresholds |

### Key Test Cases

1. **Brightness mapping**:
   - `lux=0` returns `min_brightness`
   - `lux=1` returns `min_brightness` (default min_lux=1)
   - `lux=10` returns approximately 38 (with defaults)
   - `lux=100` returns approximately 68 (with defaults)
   - `lux=1000` returns `max_brightness`
   - `lux=5000` returns `max_brightness` (clamped)
   - Custom thresholds work correctly

2. **Playback guard**:
   - TV state `playing` → Art Mode switch rejects `turn_on`
   - TV state `paused` → Art Mode switch rejects `turn_on`
   - TV state `idle` → Art Mode switch allows `turn_on`
   - TV state `off` → Art Mode switch allows `turn_on` (will power on first)

3. **Presence timeout**:
   - Presence `on` → `binary_sensor` is `on`
   - Presence `off` → delay starts, sensor stays `on` during delay
   - Delay expires → sensor becomes `off`
   - Presence `on` during delay → delay cancelled, sensor stays `on`
   - Delay = 0 → sensor turns `off` immediately
   - Presence sensor `unavailable` → treated as no-presence, starts timeout
   - Presence sensor `unknown` → same behavior as `unavailable`

4. **Options validation (Q4)**:
   - `min_lux >= max_lux` → form shows error, rejects submission
   - `min_brightness >= max_brightness` → form shows error, rejects submission
   - Valid ranges → accepted

5. **Options change reload (M1)**:
   - Adding `presence_sensor` in options → triggers entry reload → binary_sensor entity created
   - Removing `presence_sensor` in options → triggers entry reload → binary_sensor entity removed
   - Changing non-sensor options → no reload, signal dispatched

6. **Non-Frame TV (Q5)**:
   - TV without Frame support → `art_api` is `None` → no brightness entities created, no errors
   - Presence sensor still works on non-Frame TVs

7. **Number entity brightness (C1/M2)**:
   - `get_brightness()` returns `{"value": "5"}` → entity shows 50
   - `get_brightness()` returns `None` → entity state unchanged
   - `set_native_value(50)` → calls `art_api.set_brightness(5)`
   - After HA restart → entity polls and recovers current brightness

---

## 11. Migration Notes

### For Users Upgrading from v6.x to v7.0

1. **Minimum HA version increases to 2026.3.** Users on older HA versions must upgrade HA first.
2. **No breaking config changes.** All new options default to disabled (`None` / `0`). Existing configs continue to work as-is.
3. **New entities are auto-created** but only when the corresponding sensor is configured in options. No entity bloat for users who don't configure presence/illuminance sensors.
4. **`async_timeout` removed** — this is transparent to users; only relevant if forking the code.

### For Developers

1. All `async_timeout` usage must use `asyncio.timeout()` going forward.
2. New features follow the entity-exposure pattern — do not embed automation logic in the integration.
3. The logarithmic brightness mapping function (`lux_to_brightness`) lives in `sensor.py` alongside its only consumer.
4. The `binary_sensor` platform file uses `async_track_state_change_event` from `homeassistant.helpers.event` for efficient state tracking.
5. The `number` platform entity uses the Art API's `set_brightness(value)` which accepts 1–10 range (not 0–10); the entity converts from its 0–100 user-facing range.
6. All new entities extend `SamsungTVEntity` for correct device grouping.
7. `__init__.py` stores a **boolean flag** `DATA_ART_API` indicating Frame TV support. Each platform creates its own `SamsungTVAsyncArt` WebSocket instance to avoid concurrent WebSocket errors.
8. `art_api.get_brightness()` returns a `dict` (e.g., `{"value": "5"}`), not an `int`. Always parse: `int(result.get("value", 0))`.
9. Only edit `strings.json` for translations — HA auto-generates `translations/en.json`.
10. When presence/illuminance sensor options change, `_update_listener` triggers `async_reload` to re-create entities.
11. Art Mode activation on 2024+ Frame TVs requires **SmartThings `samsungvd.ambient`/`setAmbientOn`** — the local WebSocket art channel does not respond until art mode is already active. See Section 12 for full details.

---

## Implementation Order

```
Phase 1 (Modernization)     ← Do first, PR separately
  ├── 2.1 Replace async_timeout
  ├── 2.2 Bump min HA version
  ├── 2.3 Add brand images
  ├── 2.4 OAuth error handling
  ├── 2.5 runtime_data refactor (MANDATORY — Phase 2 depends on it)
  ├── 2.6 Centralize art_api creation in __init__.py
  ├── 2.7 Verify async_timeout dependency removal
  └── 2.8 Fix existing get_brightness() return type bug

Phase 2 (Features)          ← Second PR
  ├── const.py additions
  ├── config_flow.py: async_step_presence_art menu step
  ├── strings.json translations
  ├── __init__.py: register platforms, fix _update_listener for reload
  ├── binary_sensor.py (presence + timeout + unavailable handling)
  ├── number.py (art brightness with polling)
  ├── sensor.py (recommended brightness with debounce)
  └── switch.py (playback guard)

Phase 3 (Tests + Docs)      ← Third PR
  ├── All test files
  ├── README updates with example automations
  └── Example automations in docs/
```

---

## 12. Samsung 2024+ Frame TV Art Mode Architecture

### Discovery: Local WebSocket Art Channel Limitations

Testing with a **QE75LS03DAUXXU (VD-FRAME-2024)** revealed critical differences in how 2024 Frame TVs handle the art mode WebSocket channel compared to older models.

#### Connection Behavior

- The TV **accepts WebSocket connections** on port 8002 (SSL with token) to `com.samsung.art-app`
- The TV sends `ms.channel.clientConnect` events confirming the connection
- **However, the TV does NOT respond to any `art_app_request` events** when the art app is not running
- All requests (`get_artmode_status`, `set_artmode_status`, `get_current_artwork`, etc.) timeout with no response
- The art app only runs when the TV is **already in Art Mode** — creating a chicken-and-egg problem

#### What Works and What Doesn't

| Method | 2022 Frame TV | 2024 Frame TV | Notes |
|---|---|---|---|
| Local WS `set_artmode_status` | Works | Does NOT respond | Art app not running unless already in art mode |
| Local WS `get_artmode_status` | Works | Only works **while in Art Mode** | Returns `{"value": "on"}` once art mode is active |
| Local WS `get_current_artwork` | Works | Only works **while in Art Mode** | Returns artwork details once active |
| Local WS `get_brightness` | Works | Only works **while in Art Mode** | Returns brightness dict |
| SmartThings `samsungvd.ambient`/`setAmbientOn` | Not tested | **Works** | Activates art mode reliably |
| SmartThings `switch`/`on` | Works | Works | Wakes TV from standby |

#### Root Cause

Samsung 2024 Frame TVs moved art mode activation behind the SmartThings cloud API. The `com.samsung.art-app` WebSocket channel no longer has an active listener on the TV side unless the art app is already loaded. This is likely related to a CEC regression where HDMI-CEC power-off sends the TV fully off instead of into Art Mode (documented in Samsung Community forums).

#### The `samsungvd.ambient` Capability

2024 Frame TVs expose art mode via the SmartThings `samsungvd.ambient` capability (not `samsungvd.artMode` or `custom.artMode`):

```json
{
  "id": "samsungvd.ambient",
  "commands": {
    "setAmbientOn": {
      "arguments": []
    },
    "sendData": {
      "arguments": [{"name": "data", "type": "object"}]
    }
  }
}
```

The SmartThings phone app uses this same capability. The command requires **no arguments**:

```json
{
  "commands": [{
    "component": "main",
    "capability": "samsungvd.ambient",
    "command": "setAmbientOn"
  }]
}
```

Response: `{"results": [{"status": "COMPLETED"}]}`

#### Verified Behavior After Activation

Once Art Mode is activated via SmartThings, the local WebSocket art channel **comes alive immediately**:

1. TV sends `ms.channel.clientConnect` with `"isHost": true` (the art app connected)
2. TV sends `ms.channel.ready`
3. TV sends `d2d_service_message` with `"event": "art_mode_changed", "status": "on"`
4. All subsequent local WebSocket art requests work normally:
   - `get_artmode_status` → responds with `{"value": "on"}`
   - `get_current_artwork` → responds with artwork details
   - `get_content_list` → full art library
   - `get_thumbnail_list` → thumbnail data over socket
   - `get_slideshow_status` → slideshow settings

### Implemented Art Mode Control Strategy

```
async_turn_on():
  1. Check playback guard (reject if TV is playing/paused)
  2. Check if TV is on (turn on via WOL/SmartThings if needed)
  3. Try SmartThings API first:
     └── POST samsungvd.ambient/setAmbientOn (2024+ Frame TVs)
     └── POST samsungvd.artMode/setArtMode "on" (older Frame TVs)
     └── POST custom.artMode/setArtMode "on" (legacy)
  4. Fallback: Local WebSocket art API
     └── set_artmode_status "on" (works on older models)

async_turn_off():
  1. Try SmartThings API first:
     └── POST switch/on (wakes TV from art mode to normal)
     └── POST samsungvd.artMode/setArtMode "off"
     └── POST custom.artMode/setArtMode "off"
  2. Fallback: Local WebSocket art API
     └── set_artmode_status "off"
```

### WebSocket Connection Management

Each platform (`sensor.py`, `switch.py`, `number.py`) creates its **own** `SamsungTVAsyncArt` WebSocket instance. This avoids the "Concurrent call to receive() is not allowed" error that occurs when sharing a single aiohttp WebSocket across concurrent coroutines.

The `__init__.py` only stores a **boolean flag** (`DATA_ART_API = True/False`) indicating Frame TV support, determined by a one-time HTTP REST check to `http://<TV_IP>:8001/api/v2/` during setup.

### Required OAuth/PAT Scopes

The following SmartThings scopes are required for full art mode control:

- `r:devices:*` — Read device status
- `x:devices:*` — Execute device commands (including `setAmbientOn`)
- `w:devices:*` — Update device properties

No additional scopes beyond the standard `r:devices:*` and `x:devices:*` are needed for art mode.

### Known Samsung Community Issues (2024 Models)

1. **CEC Art Mode Regression** — HDMI-CEC power-off sends TV fully off instead of into Art Mode (firmware bug, previously fixed in 2022 models)
2. **WebSocket Connection Saturation** — Samsung TVs have strict limits (~5) on simultaneous WebSocket connections. If too many are opened without closing, the SmartThings service becomes unresponsive
3. **`frameTVArtModePi` Workaround** — A community project that brute-forces art mode by repeatedly sending `KEY_POWER` until the TV enters art mode; works but is unreliable
