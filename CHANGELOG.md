# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Removed

- Phone vibration: buttons no longer buzz and game rumble no longer vibrates the phone, on any device.

## [0.1.0] - 2026-10-02

First public version.

### Added

- Phone controller page with the full Xbox 360 layout: two analog sticks, 8-way D-pad, A/B/X/Y with enlarged touch areas, bumpers, triggers, Back/Guide/Start, and stick clicks by double-tap.
- One virtual Xbox 360 controller per phone through ViGEmBus, up to 4 players.
- Reconnect handling: slots are held for 30 seconds, matched by browser id or IP, and buttons are released when a phone drops.
- Controller names, set on the phone or from the test page.
- Test page showing what phones send next to what Windows reports, with a live log and a Stop button.
- Host page with a large QR code.
- Rumble passed through to Android phones.
- Windows setup script (driver install included), run script and desktop shortcut.
