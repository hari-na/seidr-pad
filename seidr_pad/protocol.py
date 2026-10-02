"""The phone-to-server message format and its validation.

A phone sends its whole controller state on every change as a 7-item array:
``[buttons, left_trigger, right_trigger, left_x, left_y, right_x, right_y]``.
Buttons are XUSB bits (the same bits a real Xbox 360 controller reports),
triggers are 0..255 and stick axes are -32768..32767 with up positive.
Sending the full state, not deltas, means a lost message can't leave a
button stuck down.
"""

from __future__ import annotations

State = tuple[int, int, int, int, int, int, int]

NEUTRAL: State = (0, 0, 0, 0, 0, 0, 0)

BUTTON_NAMES = {
    0x0001: "Up", 0x0002: "Down", 0x0004: "Left", 0x0008: "Right",
    0x0010: "Start", 0x0020: "Back", 0x0040: "LS", 0x0080: "RS",
    0x0100: "LB", 0x0200: "RB", 0x0400: "Guide",
    0x1000: "A", 0x2000: "B", 0x4000: "X", 0x8000: "Y",
}
VALID_BUTTON_MASK = 0xF7FF  # every XUSB button bit except the unused 0x0800

NAME_MAX = 16
CLIENT_ID_MAX = 64


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def parse_state(raw) -> State:
    """Validate a state array from a phone and clamp it to XUSB ranges.

    Raises ValueError or TypeError for anything that isn't 7 numbers.
    """
    b, lt, rt, lx, ly, rx, ry = (int(v) for v in raw)
    return (
        b & VALID_BUTTON_MASK,
        _clamp(lt, 0, 255), _clamp(rt, 0, 255),
        _clamp(lx, -32768, 32767), _clamp(ly, -32768, 32767),
        _clamp(rx, -32768, 32767), _clamp(ry, -32768, 32767),
    )


def clean_name(raw) -> str:
    """Player names come from phones: keep printable characters, trimmed and short."""
    name = "".join(ch for ch in str(raw or "") if ch.isprintable()).strip()
    return name[:NAME_MAX]


def buttons_text(buttons: int) -> str:
    """Human-readable button list for logs, e.g. ``A+LB``."""
    return "+".join(name for bit, name in BUTTON_NAMES.items() if buttons & bit) or "-"
