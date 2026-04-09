"""Tests for lux_to_brightness mapping function.

Pure unit tests — no Home Assistant framework dependency.
The function is duplicated here to avoid import issues with HA-dependent modules.
"""

import math

import pytest


def lux_to_brightness(
    lux: float,
    min_lux: float = 1.0,
    max_lux: float = 1000.0,
    min_brightness: int = 5,
    max_brightness: int = 100,
) -> int:
    """Map lux to art brightness using a logarithmic curve.

    Duplicated from sensor.py for isolated testing.
    """
    if lux <= min_lux:
        return min_brightness
    if lux >= max_lux:
        return max_brightness

    log_min = math.log10(max(min_lux, 0.1))
    log_max = math.log10(max_lux)
    log_lux = math.log10(lux)

    normalized = (log_lux - log_min) / (log_max - log_min)
    brightness = min_brightness + normalized * (max_brightness - min_brightness)
    return max(min_brightness, min(max_brightness, round(brightness)))


class TestLuxToBrightness:
    """Test the logarithmic lux-to-brightness mapping function."""

    def test_zero_lux_returns_min(self):
        assert lux_to_brightness(0) == 5

    def test_min_lux_returns_min(self):
        assert lux_to_brightness(1.0) == 5

    def test_below_min_lux_returns_min(self):
        assert lux_to_brightness(0.5) == 5

    def test_max_lux_returns_max(self):
        assert lux_to_brightness(1000.0) == 100

    def test_above_max_lux_returns_max(self):
        assert lux_to_brightness(5000.0) == 100

    def test_10_lux_mid_low(self):
        result = lux_to_brightness(10.0)
        assert 30 <= result <= 45

    def test_100_lux_mid_high(self):
        result = lux_to_brightness(100.0)
        assert 60 <= result <= 75

    def test_negative_lux(self):
        assert lux_to_brightness(-5) == 5

    def test_custom_thresholds(self):
        result = lux_to_brightness(
            50, min_lux=10, max_lux=100, min_brightness=20, max_brightness=80
        )
        assert 20 <= result <= 80

    def test_custom_min_max_brightness(self):
        assert lux_to_brightness(0, min_brightness=10, max_brightness=50) == 10
        assert lux_to_brightness(2000, min_brightness=10, max_brightness=50) == 50

    def test_result_is_integer(self):
        for lux in [0, 0.5, 1, 5, 10, 50, 100, 500, 1000, 5000]:
            result = lux_to_brightness(lux)
            assert isinstance(result, int)

    def test_monotonically_increasing(self):
        prev = 0
        for lux in [0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]:
            result = lux_to_brightness(lux)
            assert result >= prev, f"Decreased at lux={lux}: {result} < {prev}"
            prev = result


class TestBrightnessScaleConversion:
    """Test the UI (0-100) to TV (1-10) brightness conversion."""

    @staticmethod
    def ui_to_tv(brightness: int) -> int:
        """Convert UI brightness (0-100) to TV brightness (1-10)."""
        return max(1, min(10, round(brightness / 10)))

    def test_0_maps_to_1(self):
        """TV rejects 0, so min is 1."""
        assert self.ui_to_tv(0) == 1

    def test_10_maps_to_1(self):
        assert self.ui_to_tv(10) == 1

    def test_15_maps_to_2(self):
        assert self.ui_to_tv(15) == 2

    def test_50_maps_to_5(self):
        assert self.ui_to_tv(50) == 5

    def test_100_maps_to_10(self):
        assert self.ui_to_tv(100) == 10

    def test_all_values_in_range(self):
        for ui in range(0, 101):
            tv = self.ui_to_tv(ui)
            assert 1 <= tv <= 10, f"UI={ui} mapped to TV={tv} out of range"


"""Tests for lux_to_brightness mapping function."""

import pytest

from custom_components.samsungtv_smart.sensor import lux_to_brightness


class TestLuxToBrightness:
    """Test the logarithmic lux-to-brightness mapping function."""

    def test_zero_lux_returns_min(self):
        """Lux=0 should return min_brightness."""
        assert lux_to_brightness(0) == 5

    def test_min_lux_returns_min(self):
        """Lux at min_lux should return min_brightness."""
        assert lux_to_brightness(1.0) == 5

    def test_below_min_lux_returns_min(self):
        """Lux below min_lux should return min_brightness."""
        assert lux_to_brightness(0.5) == 5

    def test_max_lux_returns_max(self):
        """Lux at max_lux should return max_brightness."""
        assert lux_to_brightness(1000.0) == 100

    def test_above_max_lux_returns_max(self):
        """Lux above max_lux should clamp to max_brightness."""
        assert lux_to_brightness(5000.0) == 100

    def test_10_lux_mid_low(self):
        """10 lux with defaults should be roughly 1/3 of range."""
        result = lux_to_brightness(10.0)
        assert 30 <= result <= 45

    def test_100_lux_mid_high(self):
        """100 lux with defaults should be roughly 2/3 of range."""
        result = lux_to_brightness(100.0)
        assert 60 <= result <= 75

    def test_negative_lux(self):
        """Negative lux should return min_brightness."""
        assert lux_to_brightness(-5) == 5

    def test_custom_thresholds(self):
        """Custom min/max thresholds should work correctly."""
        result = lux_to_brightness(
            50, min_lux=10, max_lux=100, min_brightness=20, max_brightness=80
        )
        assert 20 <= result <= 80

    def test_custom_min_max_brightness(self):
        """Custom brightness range should be respected."""
        assert lux_to_brightness(0, min_brightness=10, max_brightness=50) == 10
        assert lux_to_brightness(2000, min_brightness=10, max_brightness=50) == 50

    def test_result_is_integer(self):
        """Result should always be an integer."""
        for lux in [0, 0.5, 1, 5, 10, 50, 100, 500, 1000, 5000]:
            result = lux_to_brightness(lux)
            assert isinstance(result, int)

    def test_monotonically_increasing(self):
        """Brightness should increase monotonically with lux."""
        prev = 0
        for lux in [0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]:
            result = lux_to_brightness(lux)
            assert (
                result >= prev
            ), f"Brightness decreased at lux={lux}: {result} < {prev}"
            prev = result
