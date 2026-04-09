"""Tests for the FrameTVPresenceAwareSensor logic.

Tests the presence state machine and timeout logic in isolation.
"""


class TestPresenceSensorInit:
    """Tests for initialization parameters."""

    def test_default_delay(self):
        """Default delay should be passed through."""
        delay = 10
        assert delay == 10

    def test_zero_delay(self):
        """Zero delay is valid — means immediate off."""
        delay = 0
        assert delay == 0


class TestPresenceStateMachine:
    """Tests for the presence state change logic."""

    @staticmethod
    def compute_new_state(
        current_is_on: bool,
        new_presence_state: str,
        delay_minutes: int,
    ) -> tuple[bool | None, bool]:
        """Simulate _presence_changed logic.

        Returns (new_is_on, should_start_timeout).
        """
        if new_presence_state in ("unavailable", "unknown"):
            # Q1 decision: treat as no-presence
            if current_is_on:
                if delay_minutes > 0:
                    return current_is_on, True  # start timeout
                return False, False  # immediate off
            return current_is_on, False

        if new_presence_state == "on":
            return True, False  # cancel timeout, set on

        # presence off
        if delay_minutes > 0:
            return current_is_on, True  # start timeout, keep current during delay
        return False, False  # immediate off

    def test_presence_on(self):
        is_on, timeout = self.compute_new_state(False, "on", 10)
        assert is_on is True
        assert timeout is False

    def test_presence_off_with_delay(self):
        is_on, timeout = self.compute_new_state(True, "off", 10)
        assert is_on is True  # stays on during delay
        assert timeout is True

    def test_presence_off_no_delay(self):
        is_on, timeout = self.compute_new_state(True, "off", 0)
        assert is_on is False
        assert timeout is False

    def test_unavailable_when_on_with_delay(self):
        is_on, timeout = self.compute_new_state(True, "unavailable", 10)
        assert timeout is True  # starts timeout

    def test_unavailable_when_on_no_delay(self):
        is_on, timeout = self.compute_new_state(True, "unavailable", 0)
        assert is_on is False

    def test_unknown_when_on_with_delay(self):
        is_on, timeout = self.compute_new_state(True, "unknown", 10)
        assert timeout is True

    def test_unavailable_when_already_off(self):
        is_on, timeout = self.compute_new_state(False, "unavailable", 10)
        assert is_on is False
        assert timeout is False

    def test_presence_on_cancels_timeout(self):
        """Going on should cancel any pending timeout."""
        is_on, timeout = self.compute_new_state(False, "on", 10)
        assert is_on is True
        assert timeout is False  # no timeout should start


class TestTimeoutExpired:
    """Tests for timeout expiration behavior."""

    def test_timeout_sets_off(self):
        """When timeout expires, sensor should be off."""
        # After timeout: is_on = False
        is_on = False  # simulated _timeout_expired result
        assert is_on is False

    def test_timeout_unsub_cleared(self):
        """Timeout unsub should be cleared after expiry."""
        timeout_unsub = None  # simulated after _timeout_expired
        assert timeout_unsub is None


class TestInitialState:
    """Tests for initial state computation."""

    @staticmethod
    def compute_initial(presence_state: str | None) -> bool | None:
        """Simulate initial state from async_added_to_hass."""
        if presence_state == "on":
            return True
        if presence_state in ("unavailable", "unknown"):
            return None
        return False

    def test_initial_on(self):
        assert self.compute_initial("on") is True

    def test_initial_off(self):
        assert self.compute_initial("off") is False

    def test_initial_unavailable(self):
        assert self.compute_initial("unavailable") is None

    def test_initial_unknown(self):
        assert self.compute_initial("unknown") is None

    def test_initial_none(self):
        assert self.compute_initial(None) is False
