"""Controller backends: what one phone's input is sent to.

``XboxPad`` creates a real virtual Xbox 360 controller through the ViGEmBus
driver. ``FakePad`` creates nothing and only remembers the last state, for
testing phones without the driver and for the unit tests.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from .protocol import NEUTRAL, State

# callback(large_motor, small_motor, led_number); called from a driver thread.
FeedbackCallback = Callable[[int, int, int], None]


class Pad(Protocol):
    def apply(self, *state: int) -> None: ...
    def neutral(self) -> None: ...
    def on_feedback(self, callback: FeedbackCallback) -> None: ...
    def close(self) -> None: ...


class FakePad:
    """Stand-in used with --fake, when the driver is missing, and in tests."""

    def __init__(self, slot: int):
        self.slot = slot
        self.state: State = NEUTRAL
        self.closed = False
        self.feedback: FeedbackCallback | None = None

    def apply(self, *state: int) -> None:
        self.state = tuple(state)

    def neutral(self) -> None:
        self.state = NEUTRAL

    def on_feedback(self, callback: FeedbackCallback) -> None:
        self.feedback = callback

    def close(self) -> None:
        self.closed = True


class XboxPad:
    """One virtual Xbox 360 controller."""

    def __init__(self, slot: int):
        import vgamepad  # imported lazily: importing it connects to the driver

        self.slot = slot
        self.pad = vgamepad.VX360Gamepad()

    def apply(self, b: int, lt: int, rt: int, lx: int, ly: int, rx: int, ry: int) -> None:
        r = self.pad.report
        r.wButtons = b
        r.bLeftTrigger = lt
        r.bRightTrigger = rt
        r.sThumbLX, r.sThumbLY = lx, ly
        r.sThumbRX, r.sThumbRY = rx, ry
        self.pad.update()

    def neutral(self) -> None:
        self.apply(*NEUTRAL)

    def on_feedback(self, callback: FeedbackCallback) -> None:
        # vgamepad checks the parameter names, so they must match exactly.
        def notification(client, target, large_motor, small_motor, led_number, user_data):
            callback(large_motor, small_motor, led_number)

        self.pad.register_notification(notification)

    def close(self) -> None:
        try:
            self.neutral()
            self.pad.unregister_notification()
        except Exception:
            pass
        del self.pad  # vgamepad unplugs the device when the object is freed


def select_backend(fake: bool, out: Callable[[str], None] = print):
    """Pick the pad factory to use. Returns ``(factory, mode_description)``.

    Falls back to ``FakePad`` if the driver can't be reached, so phones can
    still be tested.
    """
    if fake:
        return FakePad, "TEST MODE (--fake): no controllers are created"
    try:
        import vgamepad
    except Exception as e:
        out(f"\nCould not reach the ViGEmBus driver ({e}).")
        out("Install it with scripts\\setup.bat (or the ViGEmBusSetup .msi), then reboot.")
        out("Starting in test mode instead: no controllers are created.\n")
        return FakePad, "TEST MODE (driver missing): no controllers are created"

    # Self-test: plug in one controller and unplug it again. This also absorbs
    # the slow first attach right after a driver install.
    for attempt in range(1, 6):
        try:
            pad = vgamepad.VX360Gamepad()
            del pad
            out("Driver check: OK, virtual controllers can be created.")
            break
        except Exception as e:
            out(f"Driver check attempt {attempt}/5 failed: {e or type(e).__name__}")
            time.sleep(attempt)
    else:
        out("Driver check failed. Try rebooting; controllers may not work.")
    return XboxPad, "virtual Xbox 360 controllers"
