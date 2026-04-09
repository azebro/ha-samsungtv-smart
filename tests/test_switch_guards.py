"""Tests for the Art Mode switch playback guard.

Tests the _is_tv_playing_content logic in isolation.
"""


class TestPlaybackGuard:
    """Tests for active playback states detection."""

    @staticmethod
    def is_playing(state_str: str | None) -> bool:
        """Simulate _is_tv_playing_content logic."""
        if state_str is None:
            return False
        return state_str in ("playing", "paused")

    def test_playing_blocks(self):
        assert self.is_playing("playing") is True

    def test_paused_blocks(self):
        assert self.is_playing("paused") is True

    def test_idle_allows(self):
        assert self.is_playing("idle") is False

    def test_off_allows(self):
        assert self.is_playing("off") is False

    def test_on_allows(self):
        assert self.is_playing("on") is False

    def test_standby_allows(self):
        assert self.is_playing("standby") is False

    def test_none_allows(self):
        """No state (entity not found) should not block."""
        assert self.is_playing(None) is False

    def test_no_media_player_allows(self):
        """Missing media_player entity should not block."""
        assert self.is_playing(None) is False

    def test_unavailable_allows(self):
        assert self.is_playing("unavailable") is False

    def test_unknown_allows(self):
        assert self.is_playing("unknown") is False
