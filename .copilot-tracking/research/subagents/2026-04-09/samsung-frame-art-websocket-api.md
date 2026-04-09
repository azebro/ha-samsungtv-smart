# Samsung Frame TV Art Mode WebSocket API Research

## Research Topics

1. Correct WebSocket endpoint and connection flow for the art channel (com.samsung.art-app)
2. What events the TV sends back: ms.channel.connect vs ms.channel.ready — which indicates readiness on 2024-2026 models?
3. Correct request/response format for: get_artmode_status, set_artmode_status, get_brightness, set_brightness
4. Whether the TV echoes back request_id in responses or uses separate event names
5. Any changes in the Samsung TV WebSocket API for 2024+ Frame TV models
6. Whether d2d_service_message event is still used or if there's a new format

## Sources

- Local codebase: custom_components/samsungtv_smart/api/art.py
- https://github.com/NickWaterton/samsung-tv-ws-api (Nick Waterton's fork)
- https://github.com/xchwarze/samsung-tv-ws-api (original library)
- https://github.com/ollo69/ha-samsungtv-smart/issues

## Findings

_In progress..._
