# Sunshine in an independent Sway session

Fork of [daaaaan/sunshine-headless-sway](https://github.com/daaaaan/sunshine-headless-sway), with a KDE/NVIDIA profile that runs streaming applications in their own Sway, Xwayland, D-Bus and audio session under the current Linux user.

The local KDE desktop keeps its physical displays, keyboard, mouse and audio. Sunshine captures `HEADLESS-1` with `wlr` and encodes with NVENC. The profile reuses existing Moonlight pairing and migrates the known KWin virtual-output game wrappers.

## KDE profile

Requirements: Sway, Sunshine with wlr-screencopy support, NVIDIA drivers, PipeWire (including its PulseAudio module), WirePlumber with the `policy` profile, `pactl`, Python with `dbus-python`, KDE configuration tools, `dbus-run-session`, Foot, Quickshell (tested with 0.3.1), and Dolphin. The user must already have access to input devices, `/dev/uinput`, and the GPU render node. The installer checks dependencies and does not install packages or change group membership.

```sh
python kde/install.py install
python kde/install.py activate
```

`install` generates a separate profile from `~/.config/sunshine/{sunshine.conf,apps.json}`. It preserves those original files and keeps using their state/certificate files, so existing Moonlight pairing remains available. Generated configuration lives in `~/.config/sunshine-headless/`; runtime scripts live in `~/.local/share/sunshine-headless/`.

`activate` records the previous service states, disables the old Sunshine and KWin virtual-output services, masks the packaged Sunshine service against competing autostart, and enables `sunshine-headless.service`. Close any active stream/game first. Rollback has been tested locally:

```sh
python kde/install.py rollback
```

To update: edit the repository source (or original Sunshine app definitions), rerun `install`, then restart `sunshine-headless.service`. Generated profile files are overwritten by `install`; do not edit deployed copies as the source of truth.

## Usage

Connect to the same host from Moonlight. `DefaultDesktop` shows the independent Sway session with a terminal. The original Genshin and Zenless Zone Zero entries are migrated when their known `sunshine-virtual-output` wrappers are present. `Terminal (Sway)` is also added.

- Super+B: show/hide the top panel and Dock over a fullscreen window.
- Super+Enter: terminal (explicitly uses Bash, independent of Foot's configured shell).
- Super+F: toggle fullscreen; Super+Space: toggle floating.
- Super+Shift+Q: close the focused window.
- Super+1/2: switch workspace; Super+Shift+1/2: move a window.

Application-start prep commands apply the client's width, height and frame rate to `HEADLESS-1`. Dimensions are bounded and rounded down to even pixels. A resume of an existing Moonlight session may not rerun prep commands; quit the Moonlight app session before changing its requested mode. Existing games do not automatically rebuild their render resolution on resume.

Applications must start in the private environment. For manual commands:

```sh
~/.local/share/sunshine-headless/session.py exec swaymsg -t get_outputs
~/.local/share/sunshine-headless/session.py exec foot /bin/bash
```

The gamescope wrapper reads Sway's actual output mode and changes only gamescope display options, preserving everything after `--`. Existing launcher instances must be closed before launching them remotely. Home directories, game files and application configuration are still shared. Steam and other single-instance applications may need a dedicated Linux user if local and remote instances must run simultaneously.

## Top panel and window Dock

The private Sway session starts the Quickshell configuration in `kde/quickshell/`.
The top panel shows workspaces, the active window, display size, private audio
volume and the clock. Click volume to mute; scroll over it to adjust volume.
The bottom Dock opens terminals/files and lists each running window separately.
Click a window to activate it, including windows on other workspaces; scroll the
Dock when the window list overflows. The focused window has a teal indicator.

Both panels hide automatically while an application is fullscreen. Super+B
reveals them above the game, and switching windows clears that temporary reveal.
Switching away from a fullscreen window temporarily leaves fullscreen so Sway
can focus sibling windows; returning to that window restores fullscreen.
Panels reserve space for ordinary windows and never take keyboard focus. Window
and workspace data come from the private Wayland/Sway connections, while audio
controls use its private PipeWire instance. Bundled fallback icons work without
a host icon theme. Notifications, a full app menu and a system tray are not included.

Edit the repository QML files, then run `python kde/install.py install`.
Quickshell live-reloads deployed QML. For Sway binding/autostart changes, run
`~/.local/share/sunshine-headless/session.py exec swaymsg reload`; this keeps
running applications alive. The `--no-duplicate` flag prevents multiple panels.

## Isolation and lifecycle

One systemd user service supervises Sway, Sunshine, a private PipeWire server and WirePlumber's policy-only profile. All streaming sockets live under `/run/user/<uid>/sunshine-headless`. A dedicated D-Bus session prevents desktop service activation from borrowing the host bus. Sway publishes its actual `WAYLAND_DISPLAY`, `DISPLAY`, and IPC socket; the service never guesses display numbers or imports its environment into the shared user service manager.

KWin's own `Enabled` settings disable only Sunshine's known `0xbeef:0xdead` keyboard/mouse/touch/pen devices. Existing devices are updated through D-Bus, and persistent settings cover recreation. The exact previous key values are restored when the service stops. Sway disables physical inputs and allows the matching virtual inputs. No udev properties are removed, and no root access is needed when device access is already configured.

Gamepads accessed directly through evdev are **not isolated** between applications of the same user. This profile is desktop isolation, not a security sandbox. HDR is not enabled or validated. The Sway headless output and hardware encoders still share the GPU with KDE.

The private audio graph exposes only a virtual stereo sink. Sunshine can change its private default sink without changing KDE's default output. WirePlumber uses separate state and its policy-only profile, so it does not discover physical audio hardware. There is no delayed host-sink restoration workaround.

Stopping/restarting the service ends its applications. Ordinary Moonlight disconnection leaves the session available, subject to Sunshine's per-app lifecycle. With user lingering enabled and input/render permissions available, the service can run independently of graphical login; a full logout/reboot cycle still needs validation on the target host.

## Diagnostics and checks

```sh
systemctl --user status sunshine-headless
journalctl --user -u sunshine-headless -n 100
~/.local/share/sunshine-headless/session.py exec pactl list short sinks
python -m unittest discover -s tests -v
uvx ruff check kde tests kde/gamescope
sh -n kde/launch-game.sh
```

For multiple GPUs, set `WLR_RENDER_DRM_DEVICE` in `~/.local/share/sunshine-headless/settings.json` to a stable `/dev/dri/by-path/*-render` path. The installer only auto-selects a GPU when exactly one render-node symlink exists.

See [local validation](docs/VALIDATION.md) for tested behavior and remaining client checks. The original generic installer and templates are retained for reference; their [upstream guide](docs/UPSTREAM.md) describes a different deployment. Do not combine the two installers.
