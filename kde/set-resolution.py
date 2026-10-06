#!/usr/bin/python3
"""Apply a bounded client mode to HEADLESS-1 at application start, not resume."""

import json
import os
import subprocess


def mode(env: dict[str, str]) -> tuple[int, int, int]:
    values = tuple(
        int(env.get(key, default))
        for key, default in (
            ("SUNSHINE_CLIENT_WIDTH", "1920"),
            ("SUNSHINE_CLIENT_HEIGHT", "1080"),
            ("SUNSHINE_CLIENT_FPS", "60"),
        )
    )
    width, height, fps = values
    if not (320 <= width <= 7680 and 240 <= height <= 7680 and 24 <= fps <= 240):
        raise ValueError("Client mode must be 320–7680 x 240–7680 at 24–240 Hz")
    return width - width % 2, height - height % 2, fps


if __name__ == "__main__":
    w, h, fps = mode(os.environ)
    reply = json.loads(
        subprocess.check_output(
            ["swaymsg", "-r", "output", "HEADLESS-1", "mode", f"{w}x{h}@{fps}Hz"],
            text=True,
        )
    )
    if not all(item.get("success") for item in reply):
        raise SystemExit(f"Sway rejected mode: {reply}")
