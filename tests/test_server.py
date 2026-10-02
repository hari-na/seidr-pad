import pytest

from seidr_pad.hub import Hub
from seidr_pad.pads import FakePad
from seidr_pad.server import create_app

URL = "http://192.168.1.9:8777/"


@pytest.fixture
async def setup(aiohttp_client):
    hub = Hub(FakePad, "test", out=lambda line: None)
    client = await aiohttp_client(create_app(hub, URL))
    return hub, client


async def join(client, client_id="phone1", **extra):
    ws = await client.ws_connect("/ws")
    await ws.send_json({"hello": client_id, **extra})
    while True:  # skip rumble/LED feedback, wait for the join reply
        msg = await ws.receive_json()
        if "slot" in msg or "full" in msg:
            return ws, msg


async def test_phone_joins_and_drives_its_pad(setup):
    hub, client = setup
    ws, reply = await join(client)
    assert reply["slot"] == 1
    await ws.send_json({"s": [0x1000, 255, 0, 1000, -1000, 0, 0]})
    await ws.send_json({"ping": 1})  # round trip so the state has been handled
    assert (await ws.receive_json()) == {"pong": 1}
    assert hub.players[1].pad.state == (0x1000, 255, 0, 1000, -1000, 0, 0)
    await ws.close()


async def test_phone_name_from_hello_is_kept(setup):
    hub, client = setup
    ws, reply = await join(client, name="Sam")
    assert reply["name"] == "Sam"
    assert hub.players[1].name == "Sam"
    await ws.close()


async def test_malformed_state_drops_the_connection_and_releases_buttons(setup):
    hub, client = setup
    ws, _ = await join(client)
    await ws.send_json({"s": [0x1000, 0, 0, 0, 0, 0, 0]})
    await ws.send_json({"s": "garbage"})
    msg = await ws.receive()
    assert msg.type.name in ("CLOSE", "CLOSED")
    assert hub.players[1].pad.state == (0, 0, 0, 0, 0, 0, 0)


async def test_second_tab_takes_over_and_the_first_is_told(setup):
    hub, client = setup
    first, _ = await join(client, "same-id")
    second, reply = await join(client, "same-id")
    assert reply["slot"] == 1
    told = []
    async for msg in first:  # ends when the server closes the old connection
        told.append(msg.json())
    assert {"replaced": True} in told
    await second.close()


async def test_full_game_turns_phones_away(setup):
    hub, client = setup
    sockets = [(await join(client, f"phone{i}"))[0] for i in range(4)]
    _, reply = await join(client, "phone5")
    assert reply == {"full": True}
    for ws in sockets:
        await ws.close()


async def test_monitor_sees_state_and_can_rename(setup):
    hub, client = setup
    phone, _ = await join(client)
    monitor = await client.ws_connect("/ws/monitor")
    hello = await monitor.receive_json()
    assert hello["t"] == "hello" and hello["url"] == URL

    await phone.send_json({"s": [0x2000, 0, 0, 0, 0, 0, 0]})
    while True:
        msg = await monitor.receive_json()
        if msg["t"] == "state":
            break
    assert msg == {"t": "state", "slot": 1, "s": [0x2000, 0, 0, 0, 0, 0, 0]}

    await monitor.send_json({"t": "rename", "slot": 1, "name": "Sam"})
    while True:  # the phone is told its new name
        msg = await phone.receive_json()
        if "name" in msg:
            break
    assert msg == {"name": "Sam"}
    await phone.close()
    await monitor.close()


async def test_status_endpoint(setup):
    _, client = setup
    resp = await client.get("/api/status")
    data = await resp.json()
    assert data["url"] == URL
    assert len(data["players"]) == 4


@pytest.mark.parametrize("path", ["/", "/host", "/test", "/static/pad.js", "/qr.svg"])
async def test_pages_are_served_uncached(setup, path):
    _, client = setup
    resp = await client.get(path)
    assert resp.status == 200
    assert resp.headers["Cache-Control"] == "no-cache"
