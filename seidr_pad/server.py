"""The web server: phone page, WebSocket endpoints, and the PC-side pages."""

from __future__ import annotations

import asyncio
import io
import json
import os
from importlib import resources

import qrcode
import qrcode.image.svg
from aiohttp import WSMsgType, web

from .device import describe_device
from .hub import LOOPBACK, Hub
from .protocol import CLIENT_ID_MAX, clean_name, parse_state

HUB = web.AppKey("hub", Hub)
PHONE_URL = web.AppKey("phone_url", str)
_HOUSEKEEPING = web.AppKey("housekeeping", asyncio.Task)

STATIC = resources.files(__package__) / "static"


def _is_local(request: web.Request) -> bool:
    return request.remote in LOOPBACK


async def phone_socket(request: web.Request) -> web.WebSocketResponse:
    """One phone. Messages: hello, s (state), ping, setname."""
    hub = request.app[HUB]
    ip = request.remote
    ws = web.WebSocketResponse(heartbeat=3)
    await ws.prepare(request)
    player = None
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            data = json.loads(msg.data)
            if "s" in data and player is not None:
                hub.apply(player, parse_state(data["s"]))
            elif "ping" in data:
                if player is not None and isinstance(data.get("lat"), (int, float)):
                    player.latency = round(data["lat"])
                await ws.send_json({"pong": data["ping"]})
            elif "setname" in data and player is not None:
                hub.rename(player, data["setname"], "on the phone")
            elif "hello" in data:
                player = await _hello(request, ws, data)
                if player is None:
                    break
    except (ValueError, TypeError, KeyError) as e:
        hub.log(f"Bad message from {ip}, dropping connection: {e}")
    finally:
        if player is not None:
            hub.release(player, ws)
    return ws


async def _hello(request: web.Request, ws: web.WebSocketResponse, data: dict):
    hub = request.app[HUB]
    ip = request.remote
    device = describe_device(request.headers.get("User-Agent", ""), bool(data.get("standalone")))
    player, note = await hub.claim(str(data["hello"])[:CLIENT_ID_MAX], ip)
    if player is None:
        if note == "full":
            hub.log(f"Turned away {device} at {ip}: all {hub.max_players} slots taken")
            await ws.send_json({"full": True})
        else:
            hub.log(f"Could not create a controller for {device} at {ip}; it will retry")
        return None

    old = player.ws
    player.ws = ws
    player.ip = ip
    player.device = device
    player.released_at = None
    if data.get("name"):  # the phone remembers its name between game nights
        player.name = clean_name(data["name"])
    hub.log(f"{player.label} connected ({note}): {device} at {ip}")
    if old is not None and not old.closed:
        hub.log(f"{player.label}: closing its older connection")
        await old.send_json({"replaced": True})  # stops it reconnecting and stealing the slot back
        await old.close()
    await ws.send_json({"slot": player.slot, "led": player.xinput_index, "name": player.name})
    hub.broadcast_players()
    return player


async def monitor_socket(request: web.Request) -> web.WebSocketResponse:
    """The /test page: receives live state and logs; can rename players from this PC."""
    hub = request.app[HUB]
    ws = web.WebSocketResponse(heartbeat=10)
    await ws.prepare(request)
    hub.monitors.add(ws)
    await ws.send_json({"t": "hello", "mode": hub.mode, "url": request.app[PHONE_URL],
                        "players": hub.status()})
    local = _is_local(request)
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT or not local:
                continue
            try:
                data = json.loads(msg.data)
                player = hub.players.get(int(data.get("slot", 0)))
            except (ValueError, TypeError, AttributeError):
                continue
            if data.get("t") == "rename" and player is not None:
                hub.rename(player, data.get("name"), "from the test page")
    finally:
        hub.monitors.discard(ws)
    return ws


async def stop(request: web.Request) -> web.Response:
    """The Stop button on /test. Only accepted from this PC, never from phones."""
    if not _is_local(request):
        raise web.HTTPForbidden(text="Only the PC running the server can stop it.")
    hub = request.app[HUB]
    hub.log("Stop pressed on the test page, shutting down")

    async def shutdown():
        await asyncio.sleep(0.3)  # let the response go out first
        hub.close_all()
        os._exit(0)

    asyncio.ensure_future(shutdown())
    return web.json_response({"ok": True})


async def status(request: web.Request) -> web.Response:
    return web.json_response({"url": request.app[PHONE_URL], "players": request.app[HUB].status()})


async def qr_code(request: web.Request) -> web.Response:
    img = qrcode.make(request.app[PHONE_URL], image_factory=qrcode.image.svg.SvgPathImage, box_size=20)
    buf = io.BytesIO()
    img.save(buf)
    return web.Response(body=buf.getvalue(), content_type="image/svg+xml")


def _page(name: str):
    async def handler(request: web.Request) -> web.Response:
        return web.Response(text=(STATIC / name).read_text(encoding="utf-8"), content_type="text/html")
    return handler


@web.middleware
async def no_cache(request: web.Request, handler):
    # Phones (iPhone Home Screen apps especially) otherwise keep running old copies after an update.
    resp = await handler(request)
    if not isinstance(resp, web.WebSocketResponse):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


async def _start_housekeeping(app: web.Application) -> None:
    app[HUB].loop = asyncio.get_running_loop()
    app[_HOUSEKEEPING] = asyncio.create_task(app[HUB].run())


async def _cleanup(app: web.Application) -> None:
    app[_HOUSEKEEPING].cancel()
    app[HUB].close_all()


def create_app(hub: Hub, phone_url: str) -> web.Application:
    app = web.Application(middlewares=[no_cache])
    app[HUB] = hub
    app[PHONE_URL] = phone_url
    app.router.add_get("/", _page("index.html"))
    app.router.add_get("/host", _page("host.html"))
    app.router.add_get("/test", _page("test.html"))
    app.router.add_get("/ws", phone_socket)
    app.router.add_get("/ws/monitor", monitor_socket)
    app.router.add_get("/api/status", status)
    app.router.add_post("/api/stop", stop)
    app.router.add_get("/qr.svg", qr_code)
    app.router.add_static("/static/", str(STATIC))
    app.on_startup.append(_start_housekeeping)
    app.on_cleanup.append(_cleanup)
    return app
