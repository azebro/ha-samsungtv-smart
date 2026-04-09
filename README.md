# Samsung TV Smart - Frame Art Edition

[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/eflye/ha-samsungtv-smart?style=for-the-badge)](https://github.com/eflye/ha-samsungtv-smart/releases)
[![Validate with HACS](https://img.shields.io/github/actions/workflow/status/eflye/ha-samsungtv-smart/validate.yaml?style=for-the-badge&label=HACS%20Validation&logo=data:image/svg%2Bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0Ij48cGF0aCBmaWxsPSIjZmZmIiBkPSJNMTIgMkM2LjQ4IDIgMiA2LjQ4IDIgMTJzNC40OCAxMCAxMCAxMCAxMC00LjQ4IDEwLTEwUzE3LjUyIDIgMTIgMnptLTIgMTVsLTUtNSAxLjQxLTEuNDFMMTAgMTQuMTdsNy41OS03LjU5TDE5IDhsLTkgOXoiLz48L3N2Zz4=)](https://github.com/eflye/ha-samsungtv-smart/actions/workflows/validate.yaml)
[![Validate with Hassfest](https://img.shields.io/github/actions/workflow/status/eflye/ha-samsungtv-smart/hassfest.yaml?style=for-the-badge&label=Hassfest&logo=home-assistant)](https://github.com/eflye/ha-samsungtv-smart/actions/workflows/hassfest.yaml)
[![Linting](https://img.shields.io/github/actions/workflow/status/eflye/ha-samsungtv-smart/linting.yaml?style=for-the-badge&label=Linting)](https://github.com/eflye/ha-samsungtv-smart/actions/workflows/linting.yaml)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=eflye&repository=ha-samsungtv-smart&category=integration)

📺 Home Assistant integration for Samsung Smart TVs with **enhanced Frame TV Art Mode support**, **presence-aware automation entities**, and **OAuth2 authentication**.

This is a fork of [ollo69/ha-samsungtv-smart](https://github.com/ollo69/ha-samsungtv-smart) with significant improvements for Samsung Frame TV users.

---

## ✨ What's New in v7.0.0

### 🏠 Presence-Aware Art Mode (NEW)

Automatically control Art Mode based on room occupancy:

- **Presence-Aware Binary Sensor** - `binary_sensor.<tv_name>_presence_aware` tracks whether the TV should show art based on a configured presence sensor
- **Configurable Off Delay** - Set a timeout (0-120 minutes) before the sensor turns off after presence is lost
- **Playback Guard** - Art Mode switch prevents activation while the TV is actively playing or paused, protecting your viewing experience
- **Guard Events** - `samsungtv_smart_art_mode_blocked` event fires when Art Mode activation is blocked, enabling notification automations

### 💡 Illuminance-Based Art Brightness (NEW)

Automatically adjust art brightness to match ambient light:

- **Art Brightness Number Entity** - `number.<tv_name>_art_brightness` for manual brightness control (0-100%)
- **Recommended Brightness Sensor** - `sensor.<tv_name>_recommended_art_brightness` computes optimal brightness from a lux sensor using a logarithmic curve
- **Configurable Thresholds** - Set min/max lux and brightness values in the integration options
- **30-Second Debounce** - Prevents flooding the TV with rapid brightness changes when lux fluctuates

### 🔄 HA 2026.3 Modernization (NEW)

- **`asyncio.timeout`** - Replaced deprecated `async_timeout` with stdlib `asyncio.timeout`
- **`entry.runtime_data`** - Migrated from `hass.data[DOMAIN]` dict to typed `runtime_data` dataclass
- **Centralized Art API** - Single `art_api` instance created in `__init__.py`, eliminating race conditions across platforms
- **Minimum HA version bumped to 2026.3**

### 🔐 OAuth2 Authentication

The original integration uses Personal Access Tokens (PAT) that expire after a few months, requiring manual renewal. This fork implements **full OAuth2 authentication** with:

- **Automatic token refresh** - Tokens are refreshed 5 minutes before expiration
- **Race condition protection** - Global lock prevents concurrent refresh attempts
- **24-hour token validity** - SmartThings OAuth tokens last 24 hours with automatic renewal
- **No more manual PAT renewal** - Set it and forget it!

### 🖼️ Enhanced Frame TV Art Mode

Complete control over your Samsung Frame TV's Art Mode:

- **Art Mode Switch** - Dedicated switch entity with retry logic and playback guard
- **Frame Art Sensor** - Real-time artwork tracking with thumbnail support
- **Slideshow Automation** - Configure automatic artwork rotation
- **Matte Control** - Change frame styles and colors
- **Thumbnail Management** - Download and cache artwork thumbnails locally
- **Orphan Cleanup** - Automatically remove thumbnails for deleted favorites

### 🔧 Technical Improvements

- **WebSocket Auto-Reconnection** - Automatically reconnects when TV closes connection
- **pysmartthings v6.0+ Compatibility** - Updated for latest SmartThings library
- **Improved Error Handling** - Better logging and retry mechanisms
- **SmartThings Illuminance Sensor** - Ambient light sensor support
- **Brightness Intensity Sensor** - Art Mode brightness tracking

---

## 📋 Requirements

- Samsung Smart TV (2016+ models)
- Samsung Frame TV (for Art Mode and brightness features)
- Home Assistant 2026.3 or newer
- SmartThings account linked to your TV
- **For OAuth2**: SmartThings Developer Account (free)

---

## 🚀 Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=eflye&repository=ha-samsungtv-smart&category=integration)

1. Open HACS in Home Assistant
2. Go to **Integrations**
3. Search for "Samsung TV Smart" and install
4. Restart Home Assistant

**Alternative (Custom Repository):**

If the integration is not yet in the HACS default list:

1. Open HACS → **Integrations** → three dots menu → **Custom repositories**
2. Add: `https://github.com/eflye/ha-samsungtv-smart`
3. Category: **Integration**
4. Click **Add**, then search and install
5. Restart Home Assistant

### Manual Installation

1. Download the latest release from GitHub
2. Copy the `samsungtv_smart` folder to `/config/custom_components/`
3. Restart Home Assistant

---

## 🔐 OAuth2 Setup (Recommended)

OAuth2 provides automatic token refresh, eliminating the need for manual PAT renewal.

### Step 1: Create SmartThings OAuth Application

1. Go to [SmartThings Developer Workspace](https://smartthings.developer.samsung.com/workspace)
2. Sign in with your Samsung account
3. Click **New Project** → **Device Integration** → **SmartThings Cloud Connector**
4. Name your project (e.g., "Home Assistant Integration")
5. Go to **Develop** → **Registration** → **App Registration**
6. Click **Create New**

### Step 2: Configure OAuth Settings

In the App Registration form:

| Field | Value |
|-------|-------|
| **App Name** | Home Assistant Samsung TV |
| **App Type** | Automation App |
| **OAuth Scope** | `r:devices:*` and `x:devices:*` |
| **Redirect URI** | `https://my.home-assistant.io/redirect/oauth` |

7. Click **Save** and note your:
   - **Client ID** (OAuth Client Id)
   - **Client Secret** (OAuth Client Secret)

> ⚠️ **Important**: Use the "OAuth Client Id", NOT the "App Id"!

### Step 3: Configure Home Assistant

Add your credentials to Home Assistant:

**Option A: Via UI**
1. Go to **Settings** → **Devices & Services** → **Application Credentials**
2. Click **Add Credentials**
3. Select **Samsung TV Smart**
4. Enter your Client ID and Client Secret

**Option B: Via configuration.yaml**
```yaml
# configuration.yaml
application_credentials:
  - platform: samsungtv_smart
    client_id: "YOUR_CLIENT_ID"
    client_secret: "YOUR_CLIENT_SECRET"
```

### Step 4: Add Integration with OAuth

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration** → **Samsung TV Smart**
3. Select **SmartThings OAuth** as authentication method
4. Complete the OAuth flow in your browser
5. Your TV should now appear with OAuth authentication

---

## 🖼️ Frame TV Art Mode Features

### Entities Created

| Entity | Type | Description |
|--------|------|-------------|
| `media_player.samsung_*` | Media Player | Main TV control with art mode attributes |
| `switch.samsung_*_frame_art_mode` | Switch | Toggle Art Mode on/off (with playback guard) |
| `sensor.samsung_*_frame_art` | Sensor | Current artwork info and thumbnail |
| `sensor.samsung_*_illuminance` | Sensor | Ambient light level |
| `sensor.samsung_*_brightness_intensity` | Sensor | Art Mode brightness |
| `sensor.samsung_*_recommended_art_brightness` | Sensor | Computed brightness from lux (requires illuminance sensor config) |
| `number.samsung_*_art_brightness` | Number | Art brightness control 0-100% (requires illuminance sensor config + Frame TV) |
| `binary_sensor.samsung_*_presence_aware` | Binary Sensor | Presence-aware state with configurable off delay (requires presence sensor config) |

### Available Services

#### Basic Art Mode Control

```yaml
# Get Art Mode status
service: samsungtv_smart.art_get_artmode
target:
  entity_id: media_player.samsung_frame

# Turn Art Mode on/off
service: samsungtv_smart.art_set_artmode
target:
  entity_id: media_player.samsung_frame
data:
  enabled: true
```

#### Artwork Selection

```yaml
# Select specific artwork
service: samsungtv_smart.art_select_image
target:
  entity_id: media_player.samsung_frame
data:
  content_id: "SAM-S1234567"

# Get available artworks
service: samsungtv_smart.art_available
target:
  entity_id: media_player.samsung_frame
data:
  category_id: "MY-C0004"  # Optional: filter by category
```

#### Matte (Frame) Control

```yaml
# Change matte style and color
service: samsungtv_smart.art_change_matte
target:
  entity_id: media_player.samsung_frame
data:
  matte_type: "shadowbox"
  matte_color: "neutral"

# Available matte types:
# none, modernthin, modern, modernwide, flexible, shadowbox, panoramic, triptych, mix, squares

# Available colors (varies by matte type):
# neutral, antique, warm, polar, sand, seafoam, sage, burgandy, navy, apricot, byzantine, lavender, redorange, ink, peach
```

#### Slideshow & Auto-Rotation

```yaml
# Configure slideshow
service: samsungtv_smart.art_set_slideshow
target:
  entity_id: media_player.samsung_frame
data:
  duration: "15min"  # 1min, 5min, 10min, 15min, 30min, 1hour, 2hour, 4hour, 8hour
  shuffle: true
  category_id: 4  # 2=Personal, 4=Favorites

# Configure auto-rotation (similar to slideshow)
service: samsungtv_smart.art_set_auto_rotation
target:
  entity_id: media_player.samsung_frame
data:
  duration: "1hour"
  shuffle: true
  category_id: 4
```

#### Brightness Control

```yaml
# Set Art Mode brightness (0-100)
service: samsungtv_smart.art_set_brightness
target:
  entity_id: media_player.samsung_frame
data:
  brightness: 50

# Get current brightness
service: samsungtv_smart.art_get_brightness
target:
  entity_id: media_player.samsung_frame
```

#### Thumbnail Management

```yaml
# Download single thumbnail
service: samsungtv_smart.art_get_thumbnail
target:
  entity_id: media_player.samsung_frame
data:
  content_id: "SAM-S1234567"
  save_to_file: true

# Batch download with orphan cleanup
service: samsungtv_smart.art_get_thumbnails_batch
target:
  entity_id: media_player.samsung_frame
data:
  favorites_only: true
  cleanup_orphans: true  # Remove thumbnails for deleted favorites
  force_download: false  # Skip existing files
```

#### Favorites Management

```yaml
# Add/remove from favorites
service: samsungtv_smart.art_set_favourite
target:
  entity_id: media_player.samsung_frame
data:
  content_id: "SAM-S1234567"
  favourite: true
```

---

## 📂 Thumbnail Storage

Thumbnails are saved to organized directories:

```
/config/www/frame_art/
├── current.jpg          # Currently displayed artwork
├── personal/            # User-uploaded images (MY_F*)
│   ├── MY_F0001.jpg
│   └── MY_F0002.jpg
├── store/               # Samsung Art Store (SAM-S*)
│   ├── SAM-S1234567.jpg
│   └── SAM-S7654321.jpg
└── other/               # Other content types
```

Access thumbnails via:
- Current: `/local/frame_art/current.jpg`
- Store: `/local/frame_art/store/SAM-S1234567.jpg`
- Personal: `/local/frame_art/personal/MY_F0001.jpg`

---

## 🤖 Automation Examples

### Presence-Based Art Mode

```yaml
alias: "Frame Art: Art Mode on Presence"
triggers:
  - trigger: state
    entity_id: binary_sensor.living_room_tv_presence_aware
    to: "on"
actions:
  - action: switch.turn_on
    target:
      entity_id: switch.samsung_frame_frame_art_mode
mode: single
```

### Auto-Off When No Presence

```yaml
alias: "Frame Art: TV Off When Empty"
triggers:
  - trigger: state
    entity_id: binary_sensor.living_room_tv_presence_aware
    to: "off"
conditions:
  - condition: state
    entity_id: switch.samsung_frame_frame_art_mode
    state: "on"
actions:
  - action: media_player.turn_off
    target:
      entity_id: media_player.samsung_frame
mode: single
```

### Auto Art Brightness from Ambient Light

```yaml
alias: "Frame Art: Auto Brightness"
triggers:
  - trigger: state
    entity_id: sensor.samsung_frame_recommended_art_brightness
conditions:
  - condition: state
    entity_id: switch.samsung_frame_frame_art_mode
    state: "on"
actions:
  - action: number.set_value
    target:
      entity_id: number.samsung_frame_art_brightness
    data:
      value: "{{ trigger.to_state.state }}"
mode: single
```

### Weekend Art Slideshow

```yaml
alias: "Frame Art: Weekend Slideshow"
triggers:
  - trigger: time
    at: "09:00:00"
conditions:
  - condition: time
    weekday:
      - sat
      - sun
actions:
  - action: samsungtv_smart.art_set_slideshow
    target:
      entity_id: media_player.samsung_frame
    data:
      duration: "15min"
      shuffle: true
      category_id: 4
mode: single
```

### Sync Favorites Thumbnails

```yaml
alias: "Frame Art: Sync Favorites"
triggers:
  - trigger: time_pattern
    hours: "/6"  # Every 6 hours
actions:
  - action: samsungtv_smart.art_get_thumbnails_batch
    target:
      entity_id: media_player.samsung_frame
    data:
      favorites_only: true
      cleanup_orphans: true
  - delay:
      seconds: 2
  - action: homeassistant.update_entity
    target:
      entity_id: sensor.store  # Folder sensor for gallery card
mode: single
```

### Sync Matte Selection from TV

When matte is changed on the TV, update input_select helpers:

```yaml
alias: "Frame Art: Sync Matte from TV"
triggers:
  - trigger: state
    entity_id: sensor.samsung_frame_frame_art
    attribute: current_matte_id
actions:
  - variables:
      matte_id: >-
        {{ state_attr('sensor.samsung_frame_frame_art', 'current_matte_id') |
        default('none', true) | lower }}
      matte_type: |
        {% if matte_id in ['none', '', None] or '_' not in matte_id %}
          none
        {% else %}
          {{ matte_id.split('_')[0] | lower }}
        {% endif %}
      matte_color: |
        {% if matte_id in ['none', '', None] or '_' not in matte_id %}
          {{ states('input_select.frame_matte_color') }}
        {% else %}
          {{ matte_id.split('_')[1] | lower }}
        {% endif %}
  - action: input_select.select_option
    target:
      entity_id: input_select.frame_matte_type
    data:
      option: "{{ matte_type | trim }}"
  - action: input_select.select_option
    target:
      entity_id: input_select.frame_matte_color
    data:
      option: "{{ matte_color | trim }}"
mode: queued
```

### Art Mode at Night

```yaml
alias: "Frame Art: Night Mode"
triggers:
  - trigger: time
    at: "22:00:00"
conditions:
  - condition: state
    entity_id: media_player.samsung_frame
    state: "on"
actions:
  - action: switch.turn_on
    target:
      entity_id: switch.samsung_frame_frame_art_mode
  - action: samsungtv_smart.art_set_brightness
    target:
      entity_id: media_player.samsung_frame
    data:
      brightness: 20
mode: single
```

---

## 🖼️ Custom Folder Gallery Card

Display your Frame TV artwork collection in a Lovelace gallery.

### Installation

1. Copy `folder-gallery-card.js` to `/config/www/community/folder-gallery-card/`
2. Add to Lovelace resources:
   ```yaml
   resources:
     - url: /local/community/folder-gallery-card/folder-gallery-card.js
       type: module
   ```

### Configuration

1. First, create a folder sensor to monitor your thumbnails:

```yaml
# configuration.yaml
sensor:
  - platform: folder
    folder: /config/www/frame_art/store
    filter: "*.jpg"
    scan_interval: 30
```

2. Add the card to your dashboard:

```yaml
type: custom:folder-gallery-card
title: Frame TV Favorites
folder_sensor: sensor.store
folder: /local/frame_art/store
columns: 4
image_height: 160px
aspect_ratio: "1"
tap_action: lightbox
hold_action:
  service: samsungtv_smart.art_select_image
  target:
    entity_id: media_player.samsung_frame
  data:
    content_id: "{{content_id}}"
```

### Card Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `title` | string | - | Card title |
| `folder_sensor` | string | - | Folder sensor entity ID |
| `folder` | string | - | Base folder path (e.g., `/local/frame_art/store`) |
| `columns` | number | 4 | Number of columns |
| `image_height` | string | `150px` | Image height |
| `aspect_ratio` | string | - | Aspect ratio (e.g., "1" for square, "16/9") |
| `gap` | string | `8px` | Gap between images |
| `border_radius` | string | `8px` | Image border radius |
| `tap_action` | string | - | Action on tap: `lightbox`, `action`, `more-info` |
| `hold_action` | object | - | Service call on hold |

### Template Variables

Use these in your action data:
- `{{content_id}}` - Artwork content ID (extracted from filename)
- `{{filename}}` - Full filename
- `{{image_path}}` - Full image path
- `{{name}}` - Artwork name

---

## 🐛 Troubleshooting

### OAuth Token Refresh Issues

If you see "Invalid refresh token" errors:

1. Check that only one instance is refreshing tokens (global lock should prevent this)
2. Verify your Client ID and Secret are correct
3. Try reconfiguring the integration with OAuth

### Art Mode Commands Fail

If Art Mode commands fail silently:

1. Enable debug logging:
   ```yaml
   logger:
     logs:
       custom_components.samsungtv_smart: debug
       custom_components.samsungtv_smart.api.art: debug
   ```

2. Check for WebSocket disconnection in logs
3. The integration now auto-reconnects, but a restart may help

### Thumbnails Not Downloading

1. Ensure TV is in Art Mode or on
2. Check if content is DRM-protected (Samsung Art Store items may have restrictions)
3. Look for timeout errors in logs

### Gallery Card Not Updating

After removing favorites:
1. Call `art_get_thumbnails_batch` with `cleanup_orphans: true`
2. Wait 2 seconds
3. Call `homeassistant.update_entity` on your folder sensor

---

## 🔧 Debug Logging

```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.samsungtv_smart: debug
    custom_components.samsungtv_smart.api.art: debug
    custom_components.samsungtv_smart.api.smartthings: debug
    custom_components.samsungtv_smart.switch: debug
    custom_components.samsungtv_smart.sensor: debug
```

---

## 📝 Changelog

### v7.0.0 (Presence & Brightness Edition)

#### Presence-Aware Art Mode
- ✨ New `binary_sensor.<tv_name>_presence_aware` entity with configurable off delay
- ✨ Playback guard on Art Mode switch prevents interrupting active viewing
- ✨ `samsungtv_smart_art_mode_blocked` event for guard notifications
- ✨ Options flow step for presence & illuminance sensor configuration

#### Illuminance-Based Art Brightness
- ✨ New `number.<tv_name>_art_brightness` entity (0-100%)
- ✨ New `sensor.<tv_name>_recommended_art_brightness` with logarithmic lux mapping
- ✨ Configurable min/max lux thresholds and brightness range
- ✨ 30-second debounce prevents rapid brightness changes

#### HA 2026.3 Modernization
- 🔧 Replaced `async_timeout` with `asyncio.timeout` (stdlib)
- 🔧 Migrated to `entry.runtime_data` dataclass pattern
- 🔧 Centralized `art_api` creation in `__init__.py` (eliminates race conditions)
- 🔧 Fixed `get_brightness()` dict return type parsing
- 🔧 Fixed duplicate brightness conversion formula
- 🔧 Bumped minimum HA version to 2026.3

### v0.9.0 (Frame Art Edition)

#### OAuth2 Authentication
- ✨ Full OAuth2 support with automatic token refresh
- ✨ Global lock prevents race conditions during token refresh
- ✨ Token propagation via callback to all components
- ✨ Fallback mechanism for legacy PAT authentication

#### Frame TV Art Mode
- ✨ New `switch.samsung_*_frame_art_mode` entity with retry logic
- ✨ New `sensor.samsung_*_frame_art` with artwork tracking
- ✨ Thumbnail download and caching to local storage
- ✨ Batch thumbnail download with `cleanup_orphans` option
- ✨ Slideshow and auto-rotation configuration
- ✨ Matte (frame) style and color control
- ✨ Photo filter support
- ✨ Brightness control (0-100 scale)

#### Technical Improvements
- 🔧 WebSocket auto-reconnection when TV closes connection
- 🔧 pysmartthings v6.0+ compatibility (Capability.switch → string constants)
- 🔧 SmartThings illuminance sensor support
- 🔧 Brightness intensity sensor
- 🔧 Improved error handling and logging
- 🔧 Exponential backoff for failed operations

---

## 🙏 Credits

- [ollo69](https://github.com/ollo69) - Original ha-samsungtv-smart integration
- [NickWaterton](https://github.com/NickWaterton) - samsung-tv-ws-api reference
- Samsung SmartThings - API documentation

---

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
