# Contributing

Thanks for helping. Bug reports, phone compatibility reports and pull requests are all welcome.

## Setup

```bat
git clone https://github.com/hari-na/seidr-pad.git
cd seidr-pad
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
```

On macOS or Linux, use `.venv/bin/...` instead. The server runs in `--fake` mode there, which is enough for work on the phone page, the test page and the server logic.

## Running

```bat
.venv\Scripts\seidr-pad -v          :: real controllers (Windows + ViGEmBus)
.venv\Scripts\seidr-pad --fake -v   :: no driver needed
```

Open `http://localhost:8777/test` to watch input, and open the phone page from a phone on the same Wi-Fi. A desktop browser works too: shrink the window to landscape phone size.

## Checks

Run both before opening a pull request. CI runs them on Windows and Linux.

```bat
.venv\Scripts\pytest
.venv\Scripts\ruff check .
```

## Guidelines

- **Keep the phone page dependency-free.** It's plain HTML, CSS and JavaScript served as-is. No build step.
- **Anything a phone sends is untrusted.** Validate it on the server (see `protocol.py`), and put names and device strings into pages with `textContent`, never `innerHTML`.
- **PC-only actions** (stop, rename others) must check that the request comes from the PC itself.
- **Tests:** new server or hub behavior gets a test. `FakePad` stands in for the driver.
- **Commits:** small and focused, with [Conventional Commits](https://www.conventionalcommits.org/) messages (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`, `ci:`).

## Reporting a bug

Please include the phone model and browser, Windows version, the game, and the server log around the problem (`scripts\run.bat` shows it, or the test page's log panel).
