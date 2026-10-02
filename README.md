# seidr-pad

*Seiðr: the old Norse craft of moving what you cannot touch.*

Four friends, one couch, zero controllers. Their phones will do.

## Features

- **Up to 4 players:** each phone becomes its own virtual Xbox 360 controller through the [ViGEmBus](https://github.com/nefarius/ViGEmBus) driver, so any PC game that supports Xbox controllers works.
- **No app:** scan a QR code and the browser becomes the controller. Works in Safari and Chrome on iPhone and Android, over Wi-Fi.
- **Full Xbox 360 layout:** two analog sticks, D-pad with diagonals, A/B/X/Y, bumpers, triggers, Back/Guide/Start and stick clicks (double-tap a stick).
- **Reconnects cleanly:** a phone that drops off Wi-Fi gets its player slot back, and its buttons are released so nobody's character keeps running.
- **Controller names:** each player can name their controller, and the name follows them between game nights.
- **Live test page:** on the PC, see what each phone sends next to what Windows actually reports.

## Requirements

- Windows 10 or 11 (x64)
- [Python 3.10 or newer](https://www.python.org/downloads/)
- Phones on the same Wi-Fi network as the PC

## Install

```bat
git clone https://github.com/hari-na/seidr-pad.git
cd seidr-pad
scripts\setup.bat
```

`setup.bat` creates a Python environment, installs seidr-pad, installs the ViGEmBus driver (approve the Windows prompt; restart if asked) and offers to create a desktop shortcut.

## Play

1. Start seidr-pad from the **Seidr Pad** desktop shortcut. It starts the server and opens the test page. (Or run `scripts\run.bat` to keep the log in a console window.)
2. The first time, Windows asks to let Python through the firewall. Allow it on **Private networks**.
3. Each player scans the QR code with their phone camera and taps **Tap to start**. The big QR code is at `http://localhost:8777/host`.
4. Start the game. It sees one Xbox controller per phone.

Connect the phones before launching the game: some games only look for controllers at startup.

### Controls

- **Sticks:** touch anywhere in the stick area. The stick centers where your thumb lands.
- **Stick click (L3/R3):** double-tap the stick and hold.
- **A/B/X/Y:** each button's touch area is larger than the drawn circle, and you can roll your thumb between them.
- **Name:** tap "tap to name" under your player number.

### Phone tips

- **iPhone:** Safari can't hide its toolbars. For full screen, tap Share, then **Add to Home Screen**, and open Seidr Pad from there.
- **Android:** full screen and landscape lock turn on when you tap Start.
- Set the phone's auto-lock to a few minutes so it doesn't sleep during cutscenes.

## Test page

Open `http://localhost:8777/test` on the PC:

- **Sent by phones:** what each phone is pressing, plus its device, IP, latency and update rate. Click a name to rename that player.
- **Seen by Windows:** what the virtual controllers report, read back through the browser's Gamepad API. If both halves match, the game gets the same input. Browsers only reveal controllers after a button press while the page is in front.
- **Server log**, and a **Stop server** button.

## Command line

```
seidr-pad [--port 8777] [--fake] [-v]
```

| Option | |
|---|---|
| `--port` | Port to serve on (default 8777) |
| `--fake` | Don't create controllers; for testing phones without the driver |
| `-v` | Also log every button press and the game's rumble requests |

## Troubleshooting

- **Phones can't load the page:** they must be on the same Wi-Fi as the PC (not a guest network), the PC's network profile must be **Private**, and Python must be allowed through the firewall.
- **"TEST MODE (driver missing)":** ViGEmBus isn't installed, or the PC needs a restart. Run `scripts\setup.bat` again.
- **The game ignores the controllers:** connect the phones first, then start the game.
- **Two players from one phone:** shouldn't happen; phones are matched by IP as well as browser storage. If it does, please open an issue with the server log.

## Security

seidr-pad is meant for a trusted home network. Anyone on the same Wi-Fi can open the page and take a free controller slot. There's no password. Don't run it on public or shared Wi-Fi. Stopping the server and renaming players from the test page only work from the PC itself.

## How it works

```
Phone browser (touch gamepad page)
   |  WebSocket over Wi-Fi: full controller state on every change
seidr-pad server (Python, aiohttp)
   |  one virtual controller per phone, via vgamepad
ViGEmBus driver  ->  virtual Xbox 360 controllers  ->  game
```

Phones send their whole state each time, not individual presses, so a lost message can't leave a button stuck. The server also resends each controller's state every second, because Windows drops updates sent while it's still plugging in a new controller.

### Project layout

```
seidr_pad/
  cli.py        command line entry point
  server.py     web server and WebSocket endpoints
  hub.py        player slots, reconnects, logging
  pads.py       controller backends (ViGEm and a fake one for testing)
  protocol.py   message format and validation
  device.py     User-Agent to "iPhone Safari" style labels
  launcher.py   desktop shortcut: start the server, open the test page
  static/       phone page, test page, host page
scripts/        Windows setup, run and shortcut scripts
tests/          pytest suite
```

## Development

```bat
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\pytest
.venv\Scripts\ruff check .
```

`seidr-pad --fake` runs without the driver, and on any OS. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Credits

- [ViGEmBus](https://github.com/nefarius/ViGEmBus) by Nefarius Software Solutions, the driver that makes virtual controllers possible. It's no longer actively developed but works on Windows 10 and 11.
- [vgamepad](https://github.com/yannbouteiller/vgamepad), the Python bindings for ViGEm, which also ships the driver installer.

Xbox is a trademark of Microsoft. seidr-pad is not affiliated with or endorsed by Microsoft.

## License

[MIT](LICENSE)
