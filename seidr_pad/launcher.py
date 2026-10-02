"""Desktop-shortcut entry point: start the server if it isn't running, then open the test page.

Run with pythonw (no console of its own). The server gets its own minimized
console window, so its log is still there if needed.
"""

from __future__ import annotations

import ctypes
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

from .cli import DEFAULT_PORT

TEST_URL = f"http://localhost:{DEFAULT_PORT}/test"
STARTUP_TIMEOUT_S = 20  # the driver self-test can take a few seconds


def running() -> bool:
    try:
        # 127.0.0.1, not localhost: Windows takes ~2s to refuse the IPv6 attempt.
        with urllib.request.urlopen(f"http://127.0.0.1:{DEFAULT_PORT}/api/status", timeout=1):
            return True
    except OSError:
        return False


def start_server() -> None:
    python = Path(sys.executable).with_name("python.exe")  # console python, not pythonw
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 7  # SW_SHOWMINNOACTIVE: minimized, doesn't steal focus
    subprocess.Popen([str(python), "-m", "seidr_pad", "-v"],
                     startupinfo=si, creationflags=subprocess.CREATE_NEW_CONSOLE)


def main() -> None:
    if not running():
        start_server()
        deadline = time.time() + STARTUP_TIMEOUT_S
        while not running():
            if time.time() > deadline:
                ctypes.windll.user32.MessageBoxW(
                    None, "The server didn't start. Run scripts\\run.bat to see the error.", "seidr-pad", 0x10)
                sys.exit(1)
            time.sleep(0.3)
    webbrowser.open(TEST_URL)


if __name__ == "__main__":
    main()
