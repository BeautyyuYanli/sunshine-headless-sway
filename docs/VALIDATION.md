# Local validation — 2026-10-07

Host: Arch Linux, KDE Plasma, Sway 1.12, wlroots 0.20.2, Sunshine 2026.516.143833, NVIDIA RTX 3090 Ti, PipeWire 1.6.9.

Passed:

- Headless Sway using GLES2 and the NVIDIA render node, while KDE remains running.
- Sunshine wlr selection of `HEADLESS-1` and H.264/HEVC NVENC encoder initialization.
- Separate Sway Xwayland display and private Wayland/runtime/D-Bus environment; KDE service-manager environment retained its original display values.
- Live KWin input properties: all three present Sunshine keyboard/mouse devices disabled. Sway: those same devices enabled; all enumerated physical inputs disabled.
- Output changes from 1920x1080 at 60 Hz to 2244x1008 at 120 Hz; gamescope dry run uses the latter dimensions/rate.
- A real Foot window rendered and captured with grim on the headless output.
- A four-second 440 Hz PCM signal played into the private sink and recorded from its monitor (587520 recorded samples, peak amplitude 12000). KDE's default sink was unchanged. Recording uses a short latency to avoid terminating before the recording buffer flushes.
- Rollback restored the previous Sunshine/KWin virtual-output services and re-enabled Sunshine input in KWin; reactivation successfully started the isolated stack again.
- Six unit tests for preserving configuration/app data, idempotent app migration, client mode validation gamescope argument boundaries and removal of host session metadata.
- Python lint/format checks, shell syntax and systemd unit validation.

Not yet validated:

- An actual Moonlight client streaming session, including user-perceived latency, keyboard/mouse interaction and audio over the network.
- End-to-end Genshin/ZZZ gameplay. Launch entries were migrated and gamescope mode selection checked without starting or updating a game.
- Touch/pen clients, controllers, HDR, logout and full reboot. Gamepads read directly through evdev are outside this profile's isolation guarantee.
