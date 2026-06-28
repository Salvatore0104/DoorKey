import pytest

from hr6107.state import CallState, TerminalState


def test_happy_path_state_machine():
    state = TerminalState()
    state.ring()
    state.transition(CallState.CONNECTING)
    state.transition(CallState.ACTIVE)
    state.transition(CallState.ENDING)
    state.transition(CallState.IDLE)
    assert state.call_state == CallState.IDLE
    assert state.call_count == 1


def test_invalid_state_transition_is_rejected():
    state = TerminalState()
    with pytest.raises(ValueError, match="invalid transition"):
        state.transition(CallState.ACTIVE)

