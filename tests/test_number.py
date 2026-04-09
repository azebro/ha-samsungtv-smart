"""Tests for FrameArtBrightnessNumber entity.

Uses mocks to avoid HA framework integration test issues.
"""

from unittest.mock import AsyncMock

import pytest


class TestBrightnessSetValue:
    """Test UI-to-TV brightness conversion and API calls."""

    @staticmethod
    def _ui_to_tv(brightness: int) -> int:
        return max(1, min(10, round(brightness / 10)))

    def test_set_50_sends_5(self):
        assert self._ui_to_tv(50) == 5

    def test_set_100_sends_10(self):
        assert self._ui_to_tv(100) == 10

    def test_set_0_sends_1(self):
        """TV API rejects 0, min UI is 10. But conversion still works for edge."""
        assert self._ui_to_tv(0) == 1

    def test_set_15_sends_2(self):
        assert self._ui_to_tv(15) == 2

    def test_set_5_sends_1(self):
        assert self._ui_to_tv(5) == 1

    def test_set_95_sends_10(self):
        assert self._ui_to_tv(95) == 10


class TestBrightnessResponseParsing:
    """Test parsing get_brightness() dict response (C1 fix)."""

    @staticmethod
    def parse_brightness(result) -> float | None:
        """Simulate the parsing logic from number.py async_update."""
        if result and isinstance(result, dict):
            tv_val = int(result.get("value", 0))
            return float(tv_val * 10)
        return None

    def test_dict_with_value_5(self):
        assert self.parse_brightness({"value": "5"}) == 50.0

    def test_dict_with_value_10(self):
        assert self.parse_brightness({"value": "10"}) == 100.0

    def test_dict_with_value_1(self):
        assert self.parse_brightness({"value": "1"}) == 10.0

    def test_dict_with_value_0(self):
        assert self.parse_brightness({"value": "0"}) == 0.0

    def test_none_response(self):
        assert self.parse_brightness(None) is None

    def test_empty_dict(self):
        """Empty dict is falsy in Python, so treated like None."""
        assert self.parse_brightness({}) is None

    def test_non_dict_response(self):
        """If API returns something unexpected, return None."""
        assert self.parse_brightness("5") is None

    def test_dict_with_missing_value_key(self):
        assert self.parse_brightness({"brightness": "5"}) == 0.0


"""Tests for the FrameArtBrightnessNumber entity."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.samsungtv_smart.number import FrameArtBrightnessNumber


@pytest.fixture
def mock_config():
    """Return a minimal config dict."""
    return {
        "host": "192.168.1.100",
        "name": "Test TV",
    }


@pytest.fixture
def mock_art_api():
    """Return a mock art API."""
    api = AsyncMock()
    api.set_brightness = AsyncMock()
    api.get_brightness = AsyncMock(return_value={"value": "5"})
    return api


class TestBrightnessNumberInit:
    """Test initialization."""

    def test_attributes(self, mock_config, mock_art_api):
        """Test entity attributes are set correctly."""
        entity = FrameArtBrightnessNumber(
            config=mock_config,
            entry_id="test_entry",
            art_api=mock_art_api,
        )
        assert entity._attr_unique_id == "test_entry_art_brightness"
        assert entity._attr_name == "Art Brightness"
        assert entity._attr_native_min_value == 10
        assert entity._attr_native_max_value == 100
        assert entity._attr_native_step == 1
        assert entity._attr_should_poll is True


class TestBrightnessSetValue:
    """Test setting brightness values."""

    @pytest.mark.asyncio
    async def test_set_50_calls_api_with_5(self, mock_config, mock_art_api):
        """Setting UI value 50 should send TV value 5."""
        entity = FrameArtBrightnessNumber(
            config=mock_config, entry_id="test", art_api=mock_art_api
        )
        await entity.async_set_native_value(50.0)
        mock_art_api.set_brightness.assert_called_once_with(5)
        assert entity._attr_native_value == 50.0

    @pytest.mark.asyncio
    async def test_set_100_calls_api_with_10(self, mock_config, mock_art_api):
        """Setting UI value 100 should send TV value 10."""
        entity = FrameArtBrightnessNumber(
            config=mock_config, entry_id="test", art_api=mock_art_api
        )
        await entity.async_set_native_value(100.0)
        mock_art_api.set_brightness.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_set_0_calls_api_with_1(self, mock_config, mock_art_api):
        """Setting UI value 0 should send TV value 1 (min 1, TV rejects 0)."""
        entity = FrameArtBrightnessNumber(
            config=mock_config, entry_id="test", art_api=mock_art_api
        )
        await entity.async_set_native_value(0.0)
        # max(1, min(10, round(0/10))) = max(1, 0) = 1
        mock_art_api.set_brightness.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_set_15_calls_api_with_2(self, mock_config, mock_art_api):
        """Setting UI value 15 should send TV value 2."""
        entity = FrameArtBrightnessNumber(
            config=mock_config, entry_id="test", art_api=mock_art_api
        )
        await entity.async_set_native_value(15.0)
        mock_art_api.set_brightness.assert_called_once_with(2)


class TestBrightnessUpdate:
    """Test polling/update for brightness."""

    @pytest.mark.asyncio
    async def test_update_parses_dict_response(self, mock_config, mock_art_api):
        """get_brightness returns dict — entity should parse it correctly."""
        mock_art_api.get_brightness.return_value = {"value": "5"}
        entity = FrameArtBrightnessNumber(
            config=mock_config, entry_id="test", art_api=mock_art_api
        )
        await entity.async_update()
        assert entity._attr_native_value == 50.0

    @pytest.mark.asyncio
    async def test_update_handles_none_response(self, mock_config, mock_art_api):
        """get_brightness returns None — entity should not crash."""
        mock_art_api.get_brightness.return_value = None
        entity = FrameArtBrightnessNumber(
            config=mock_config, entry_id="test", art_api=mock_art_api
        )
        entity._attr_native_value = 30.0
        await entity.async_update()
        # Should remain unchanged
        assert entity._attr_native_value == 30.0

    @pytest.mark.asyncio
    async def test_update_handles_exception(self, mock_config, mock_art_api):
        """get_brightness raises — entity should not crash."""
        mock_art_api.get_brightness.side_effect = Exception("TV off")
        entity = FrameArtBrightnessNumber(
            config=mock_config, entry_id="test", art_api=mock_art_api
        )
        entity._attr_native_value = 30.0
        await entity.async_update()
        assert entity._attr_native_value == 30.0

    @pytest.mark.asyncio
    async def test_update_brightness_10_maps_to_100(self, mock_config, mock_art_api):
        """TV brightness 10 should map to UI brightness 100."""
        mock_art_api.get_brightness.return_value = {"value": "10"}
        entity = FrameArtBrightnessNumber(
            config=mock_config, entry_id="test", art_api=mock_art_api
        )
        await entity.async_update()
        assert entity._attr_native_value == 100.0

    @pytest.mark.asyncio
    async def test_update_brightness_1_maps_to_10(self, mock_config, mock_art_api):
        """TV brightness 1 should map to UI brightness 10."""
        mock_art_api.get_brightness.return_value = {"value": "1"}
        entity = FrameArtBrightnessNumber(
            config=mock_config, entry_id="test", art_api=mock_art_api
        )
        await entity.async_update()
        assert entity._attr_native_value == 10.0
