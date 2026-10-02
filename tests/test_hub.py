import time

import pytest

from seidr_pad.hub import Hub
from seidr_pad.pads import FakePad
from seidr_pad.protocol import NEUTRAL

PHONE_IP = "192.168.1.20"


class FakeSocket:
    def __init__(self, close_code=1001):
        self.closed = False
        self.close_code = close_code
        self.sent = []

    async def send_json(self, obj):
        self.sent.append(obj)

    async def send_str(self, data):
        self.sent.append(data)


@pytest.fixture
def hub():
    return Hub(FakePad, "test", out=lambda line: None)


async def connect(hub, client_id, ip=PHONE_IP):
    player, note = await hub.claim(client_id, ip)
    if player is not None:
        player.ws = FakeSocket()
        player.ip = ip
    return player, note


async def test_new_phones_get_consecutive_slots(hub):
    slots = [(await connect(hub, f"phone{i}", f"192.168.1.{i}"))[0].slot for i in range(1, 5)]
    assert slots == [1, 2, 3, 4]


async def test_fifth_phone_is_turned_away(hub):
    for i in range(1, 5):
        await connect(hub, f"phone{i}", f"192.168.1.{i}")
    player, note = await connect(hub, "phone5", "192.168.1.5")
    assert player is None and note == "full"


async def test_same_client_id_rejoins_its_slot(hub):
    first, _ = await connect(hub, "abc")
    again, note = await hub.claim("abc", PHONE_IP)
    assert again is first and note == "rejoined"


async def test_same_ip_with_new_storage_keeps_the_slot(hub):
    safari, _ = await connect(hub, "safari-id")
    home_screen_app, note = await hub.claim("home-screen-id", PHONE_IP)
    assert home_screen_app is safari
    assert note.startswith("same phone")
    assert safari.client_id == "home-screen-id"


async def test_loopback_clients_are_not_merged_by_ip(hub):
    a, _ = await connect(hub, "tab1", "127.0.0.1")
    b, _ = await connect(hub, "tab2", "127.0.0.1")
    assert a.slot != b.slot


async def test_release_lets_go_of_every_button(hub):
    player, _ = await connect(hub, "abc")
    hub.apply(player, (0x1000, 255, 0, 100, 100, 0, 0))
    assert player.pad.state != NEUTRAL
    hub.release(player, player.ws)
    assert player.pad.state == NEUTRAL
    assert not player.connected


async def test_release_from_a_replaced_connection_is_ignored(hub):
    player, _ = await connect(hub, "abc")
    old_ws = player.ws
    player.ws = FakeSocket()  # a newer tab took over
    hub.release(player, old_ws)
    assert player.connected


async def test_slot_is_freed_after_the_grace_period(hub):
    player, _ = await connect(hub, "abc")
    hub.release(player, player.ws)
    now = time.monotonic()
    hub.tick(now + hub.grace_s - 1)
    assert 1 in hub.players
    hub.tick(now + hub.grace_s + 1)
    assert 1 not in hub.players
    assert player.pad.closed


async def test_tick_resends_state_to_connected_pads(hub):
    player, _ = await connect(hub, "abc")
    hub.apply(player, (0x1000, 0, 0, 0, 0, 0, 0))
    player.pad.state = NEUTRAL  # pretend the driver dropped the update
    hub.tick(time.monotonic())
    assert player.pad.state == (0x1000, 0, 0, 0, 0, 0, 0)


async def test_rename_cleans_the_name_and_tells_the_phone(hub):
    player, _ = await connect(hub, "abc")
    hub.rename(player, "  Sam\n", by="in a test")
    assert player.name == "Sam"
    assert player.label == "P1 (Sam)"


async def test_status_lists_every_slot(hub):
    await connect(hub, "abc")
    status = hub.status()
    assert [s["slot"] for s in status] == [1, 2, 3, 4]
    assert status[0]["connected"] and not status[1]["connected"]


async def test_failed_pad_creation_reports_an_error():
    def broken(slot):
        raise RuntimeError("driver not ready")

    hub = Hub(broken, "test", out=lambda line: None)
    hub._make_pad = _no_retry(hub)  # skip the retry delays
    player, note = await hub.claim("abc", PHONE_IP)
    assert player is None and note == "error"


def _no_retry(hub):
    async def make_pad(slot):
        try:
            return hub.pad_factory(slot)
        except Exception:
            return None
    return make_pad
