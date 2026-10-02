"""Player slots: which phone drives which virtual controller.

The hub hands out up to ``max_players`` slots. A phone keeps its slot across
reconnects for ``grace_s`` seconds, recognized by the id it stores in the
browser or, failing that, by its IP address (Safari and an iPhone Home Screen
app don't share storage). The hub also feeds the /test page monitors.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable

from .pads import Pad
from .protocol import NEUTRAL, State, buttons_text, clean_name

LOOPBACK = ("127.0.0.1", "::1")

CLOSE_REASONS = {
    1000: "page closed",
    1001: "page closed or app switched",
    1006: "connection lost (Wi-Fi drop or phone locked)",
}


class Player:
    def __init__(self, slot: int, client_id: str, pad: Pad):
        self.slot = slot
        self.client_id = client_id
        self.pad = pad
        self.ws = None  # the phone's WebSocket while connected
        self.ip: str | None = None
        self.device = ""
        self.name = ""
        self.released_at: float | None = None  # set while disconnected, inside the grace period
        self.xinput_index: int | None = None  # which controller number Windows gave it
        self.rumble = (0, 0)
        self.state: State = NEUTRAL
        self.msgs = 0
        self.latency: int | None = None

    @property
    def label(self) -> str:
        return f"P{self.slot} ({self.name})" if self.name else f"P{self.slot}"

    @property
    def connected(self) -> bool:
        return self.ws is not None

    def info(self) -> dict:
        return {
            "slot": self.slot, "name": self.name,
            "connected": self.connected, "held": not self.connected,
            "device": self.device, "ip": self.ip, "xinput": self.xinput_index,
            "latency": self.latency, "state": self.state,
        }


class Hub:
    def __init__(self, pad_factory: Callable[[int], Pad], mode: str, *, verbose: bool = False,
                 max_players: int = 4, grace_s: float = 30, stats_every_s: float = 10,
                 out: Callable[[str], None] = print):
        self.pad_factory = pad_factory
        self.mode = mode
        self.verbose = verbose
        self.max_players = max_players
        self.grace_s = grace_s
        self.stats_every_s = stats_every_s
        self.out = out
        self.players: dict[int, Player] = {}
        self.monitors: set = set()  # WebSockets of open /test pages
        self.loop: asyncio.AbstractEventLoop | None = None
        self._claim_lock = asyncio.Lock()
        self._last_stats = time.monotonic()

    # ---- logging and /test page updates ----------------------------------

    def log(self, msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')}  {msg}"
        self.out(line)
        self.broadcast({"t": "log", "msg": line})

    def broadcast(self, obj: dict) -> None:
        if not self.monitors:
            return
        data = json.dumps(obj)
        for ws in list(self.monitors):
            if not ws.closed:
                asyncio.ensure_future(ws.send_str(data))

    def broadcast_players(self) -> None:
        self.broadcast({"t": "players", "players": self.status()})

    def status(self) -> list[dict]:
        out = []
        for slot in range(1, self.max_players + 1):
            p = self.players.get(slot)
            out.append(p.info() if p else {"slot": slot, "connected": False, "held": False})
        return out

    # ---- slots -------------------------------------------------------------

    async def claim(self, client_id: str, ip: str) -> tuple[Player | None, str]:
        """Find this phone's slot or give it a new one.

        Returns ``(player, note)``; player is None when the note is "full" or "error".
        """
        if self.loop is None:
            self.loop = asyncio.get_running_loop()
        async with self._claim_lock:  # creating a pad awaits; don't hand one slot out twice
            return await self._claim(client_id, ip)

    async def _claim(self, client_id: str, ip: str) -> tuple[Player | None, str]:
        for p in self.players.values():
            if p.client_id == client_id:
                return p, "rejoined"
        # Same phone, different browser storage: treat a known IP as the same
        # device. Skipped for the PC itself so local tests can open several
        # tabs as separate players.
        if ip not in LOOPBACK:
            for p in self.players.values():
                if p.ip == ip:
                    p.client_id = client_id
                    return p, "same phone, new browser tab or app"
        for slot in range(1, self.max_players + 1):
            if slot not in self.players:
                pad = await self._make_pad(slot)
                if pad is None:
                    return None, "error"
                p = Player(slot, client_id, pad)
                pad.on_feedback(lambda big, small, led, p=p:
                                self.loop.call_soon_threadsafe(self.feedback, p, big, small, led))
                self.players[slot] = p
                return p, "new player"
        return None, "full"

    async def _make_pad(self, slot: int) -> Pad | None:
        # The very first controller after a driver install can take a moment to attach.
        for attempt in range(1, 6):
            try:
                return self.pad_factory(slot)
            except Exception as e:
                self.log(f"  creating controller for P{slot} failed (attempt {attempt}/5): {e or type(e).__name__}")
                await asyncio.sleep(0.5 * attempt)
        return None

    def release(self, p: Player, ws) -> None:
        """A phone's connection closed: let go of every button and hold the slot."""
        if p.ws is not ws:
            return  # a newer connection already took this slot over
        p.ws = None
        p.pad.neutral()
        p.state = NEUTRAL
        p.released_at = time.monotonic()
        reason = CLOSE_REASONS.get(ws.close_code, f"closed (code {ws.close_code})")
        self.log(f"{p.label} disconnected: {reason}. Buttons released, slot held {self.grace_s:.0f}s")
        self.broadcast_players()

    # ---- input and feedback ------------------------------------------------

    def apply(self, p: Player, state: State) -> None:
        p.pad.apply(*state)
        p.msgs += 1
        if state == p.state:
            return
        if self.verbose and state[:3] != p.state[:3]:
            self.log(f"{p.label}: buttons {buttons_text(state[0])}  LT {state[1]}  RT {state[2]}")
        p.state = state
        self.broadcast({"t": "state", "slot": p.slot, "s": state})

    def rename(self, p: Player, name, by: str) -> None:
        name = clean_name(name)
        if name == p.name:
            return
        old = p.label
        p.name = name
        self.log(f"{old} renamed to {name or '(no name)'} {by}")
        if p.ws is not None and not p.ws.closed:
            asyncio.ensure_future(p.ws.send_json({"name": name}))
        self.broadcast_players()

    def feedback(self, p: Player, big: int, small: int, led: int) -> None:
        """Rumble and player-LED updates from the game, via the driver."""
        if led != p.xinput_index:
            self.log(f"{p.label}: Windows assigned it controller #{led + 1}")
        if self.verbose and (big, small) != p.rumble:
            self.log(f"{p.label}: rumble large={big} small={small}")
        p.xinput_index = led
        p.rumble = (big, small)
        if p.ws is not None and not p.ws.closed:
            asyncio.ensure_future(p.ws.send_json({"r": [big, small], "led": led}))
        self.broadcast_players()

    # ---- housekeeping ------------------------------------------------------

    def tick(self, now: float) -> None:
        """Called about once a second."""
        self.broadcast_players()  # keeps latency on /test fresh
        for slot, p in list(self.players.items()):
            if p.connected:
                # Reports sent while Windows is still plugging in a new
                # controller are dropped, so re-send the current state.
                p.pad.apply(*p.state)
            elif p.released_at is not None and now - p.released_at > self.grace_s:
                p.pad.close()
                del self.players[slot]
                self.log(f"{p.label} slot freed, its virtual controller was unplugged")
                self.broadcast_players()
        if now - self._last_stats >= self.stats_every_s:
            self._log_stats(now - self._last_stats)
            self._last_stats = now

    def _log_stats(self, elapsed: float) -> None:
        parts = []
        for p in self.players.values():
            if p.connected:
                lat = f"{p.latency} ms" if p.latency is not None else "? ms"
                parts.append(f"{p.label} {p.msgs / elapsed:.0f} msg/s {lat}")
            p.msgs = 0
        if parts:
            self.log("stats: " + " | ".join(parts))

    async def run(self) -> None:
        while True:
            await asyncio.sleep(1)
            self.tick(time.monotonic())

    def close_all(self) -> None:
        for p in self.players.values():
            p.pad.close()
