import pytest

from seidr_pad.protocol import NAME_MAX, NEUTRAL, buttons_text, clean_name, parse_state


def test_parse_state_passes_valid_values_through():
    assert parse_state([0x1000, 255, 0, 100, -100, 32767, -32768]) == (0x1000, 255, 0, 100, -100, 32767, -32768)


def test_parse_state_clamps_out_of_range_values():
    assert parse_state([0, 999, -5, 99999, -99999, 0, 0]) == (0, 255, 0, 32767, -32768, 0, 0)


def test_parse_state_drops_the_unused_button_bit():
    assert parse_state([0xFFFF, 0, 0, 0, 0, 0, 0])[0] == 0xF7FF


def test_parse_state_accepts_floats():
    assert parse_state([1.0, 0, 0, 0.9, 0, 0, 0]) == (1, 0, 0, 0, 0, 0, 0)


@pytest.mark.parametrize("bad", ["garbage", [1, 2, 3], [0, 0, 0, 0, 0, 0, "x"], None, 5])
def test_parse_state_rejects_malformed_input(bad):
    with pytest.raises((ValueError, TypeError)):
        parse_state(bad)


def test_clean_name_trims_and_strips_control_characters():
    assert clean_name("  Sam\n\t\x00 ") == "Sam"


def test_clean_name_truncates():
    assert clean_name("x" * 50) == "x" * NAME_MAX


def test_clean_name_handles_empty_values():
    assert clean_name(None) == ""
    assert clean_name("") == ""


def test_buttons_text():
    assert buttons_text(0x1000 | 0x0100) == "LB+A"
    assert buttons_text(0) == "-"
    assert NEUTRAL == (0, 0, 0, 0, 0, 0, 0)
