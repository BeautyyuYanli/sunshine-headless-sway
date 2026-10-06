#!/usr/bin/python3
"""Supervise a private Sway/audio/Sunshine process tree; never import its env globally.

The Sway exec hook publishes its real sockets (including its own Xwayland DISPLAY).
All children share a private D-Bus and runtime directory, but retain the user's
home/configuration. This is desktop isolation, not a security sandbox.
"""

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME = Path(f"/run/user/{os.getuid()}/sunshine-headless")
ENV_FILE = RUNTIME / "session.json"
KEYS = (
    "WAYLAND_DISPLAY",
    "DISPLAY",
    "SWAYSOCK",
    "DBUS_SESSION_BUS_ADDRESS",
    "XDG_RUNTIME_DIR",
    "XDG_CURRENT_DESKTOP",
    "XDG_SESSION_TYPE",
    "PULSE_SERVER",
    "PULSE_RUNTIME_PATH",
    "PULSE_SINK",
    "PIPEWIRE_RUNTIME_DIR",
    "PIPEWIRE_REMOTE",
)


def publish():
    data = {key: os.environ[key] for key in KEYS if key in os.environ}
    pending = ENV_FILE.with_suffix(".tmp")
    pending.write_text(json.dumps(data))
    pending.replace(ENV_FILE)


def session_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Use published sockets, dropping host X11 authentication/session metadata."""
    result = dict(os.environ if base is None else base)
    for key in (
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "SWAYSOCK",
        "SESSION_MANAGER",
        "XAUTHORITY",
        "XDG_SESSION_ID",
        "XDG_SEAT",
        "XDG_VTNR",
    ):
        result.pop(key, None)
    result.update(json.loads(ENV_FILE.read_text()))
    return result


def wait_ready(predicate, children, label):
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        if any(child.poll() is not None for child in children):
            raise RuntimeError(f"A session component exited while waiting for {label}")
        if predicate():
            return
        time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for {label}")


def run():
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    ENV_FILE.unlink(missing_ok=True)
    env = dict(os.environ)
    for key in (
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "SWAYSOCK",
        "SESSION_MANAGER",
        "XAUTHORITY",
        "XDG_SESSION_ID",
        "XDG_SEAT",
        "XDG_VTNR",
    ):
        env.pop(key, None)
    env.update(
        XDG_RUNTIME_DIR=str(RUNTIME),
        PIPEWIRE_RUNTIME_DIR=str(RUNTIME),
        PIPEWIRE_REMOTE="pipewire-0",
        PULSE_RUNTIME_PATH=str(RUNTIME / "pulse"),
        PULSE_SERVER=f"unix:{RUNTIME}/pulse/native",
        PULSE_SINK="sink-sunshine-stereo",
        XDG_CURRENT_DESKTOP="sway",
        XDG_SESSION_TYPE="wayland",
        WLR_BACKENDS="headless,libinput",
        WLR_LIBINPUT_NO_DEVICES="1",
        LIBSEAT_BACKEND="noop",
        WLR_RENDERER="gles2",
    )
    # Optional per-machine GPU selection, without guessing render node numbering.
    settings = ROOT / "settings.json"
    if settings.exists():
        env.update(json.loads(settings.read_text()))
    children = []

    def stop(_signum, _frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        children.append(
            subprocess.Popen(["pipewire", "-c", str(ROOT / "pipewire.conf")], env=env)
        )
        wait_ready(lambda: (RUNTIME / "pipewire-0").exists(), children, "PipeWire")
        wp_env = dict(
            env,
            XDG_STATE_HOME=str(Path.home() / ".local/state/sunshine-headless/audio"),
        )
        children.append(
            subprocess.Popen(["wireplumber", "--profile=policy"], env=wp_env)
        )

        def audio_ready():
            result = subprocess.run(
                ["pactl", "list", "short", "sinks"],
                env=env,
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            return result.returncode == 0 and "sink-sunshine-stereo" in result.stdout

        wait_ready(audio_ready, children, "private audio sink")
        children.append(
            subprocess.Popen(
                ["sway", "--unsupported-gpu", "-c", str(ROOT / "sway.conf")], env=env
            )
        )
        wait_ready(ENV_FILE.exists, children, "Sway environment")
        actual_env = session_env(env)
        children.append(
            subprocess.Popen(
                [
                    "sunshine",
                    str(Path.home() / ".config/sunshine-headless/sunshine.conf"),
                ],
                env=actual_env,
            )
        )
        print("Private Sway, audio and Sunshine started", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        raise RuntimeError(
            "A session component exited; restarting the complete session"
        )
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        ENV_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    action = sys.argv[1]
    if action == "publish":
        publish()
    elif action == "run":
        run()
    elif action == "exec":
        os.execvpe(sys.argv[2], sys.argv[2:], session_env())
    else:
        raise SystemExit("Usage: session.py run|publish|exec COMMAND [ARGS...]")
