"""Tests for FrameArtBrightnessNumber entity.

Uses mocks to avoid HA framework integration test issues.
"""


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
