"""Command line entry point: ``seidr-pad`` or ``python -m seidr_pad``."""

from __future__ import annotations

import argparse
import socket
import sys

import qrcode
from aiohttp import web

from . import __version__
from .hub import Hub
from .pads import select_backend
from .server import create_app

DEFAULT_PORT = 8777


def lan_ip() -> str:
    """Best guess at the address phones on the same Wi-Fi can reach."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # picks the outgoing interface; no packet is sent
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="seidr-pad",
                                 description="Use phones as Xbox 360 controllers for PC games, over Wi-Fi.")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"port to serve on (default {DEFAULT_PORT})")
    ap.add_argument("--fake", action="store_true", help="don't create controllers (for testing phones)")
    ap.add_argument("-v", "--verbose", action="store_true", help="also log every button press and rumble")
    ap.add_argument("--version", action="version", version=f"seidr-pad {__version__}")
    return ap.parse_args(argv)


def _print_qr(url: str) -> None:
    try:
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.print_ascii(invert=True)
    except Exception:
        pass  # consoles that can't draw it; the /host page shows the QR code anyway


def main(argv=None) -> None:
    args = parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    def out(line: str) -> None:
        print(line, flush=True)

    factory, mode = select_backend(args.fake, out)
    url = f"http://{lan_ip()}:{args.port}/"
    hub = Hub(factory, mode, verbose=args.verbose, out=out)
    app = create_app(hub, url)

    _print_qr(url)
    out(f"\nseidr-pad {__version__}: {mode}")
    out(f"Phones (same Wi-Fi): scan the QR code or open {url}")
    out(f"Big QR code for this PC:   http://localhost:{args.port}/host")
    out(f"Live input test page:      http://localhost:{args.port}/test")
    out(f"Logging every button press: {'on' if args.verbose else 'off (add -v)'}")
    out("Ctrl+C to stop.\n")

    # Both IPv4 and IPv6, so "localhost" answers instantly whichever one it resolves to.
    web.run_app(app, host=["0.0.0.0", "::"], port=args.port, print=None)


if __name__ == "__main__":
    main()
