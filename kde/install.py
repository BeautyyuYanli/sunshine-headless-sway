#!/usr/bin/python3
"""Generate an isolated KDE profile without overwriting Sunshine's original config.

install is repeatable; activate records service state once and performs cutover.
rollback restores service state and KWin input settings. Pairing/certificates stay
in the original Sunshine directory and must never be copied into this repository.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

SOURCE = Path(__file__).resolve().parent
HOME = Path.home()
DEST = HOME / ".local/share/sunshine-headless"
CONF = HOME / ".config/sunshine-headless"
ORIGINAL = HOME / ".config/sunshine"
UNITS = HOME / ".config/systemd/user"
STATE = HOME / ".local/state/sunshine-headless"
OLD_UNITS = (
    "app-dev.lizardbyte.app.Sunshine.service",
    "sunshine1.service",
    "sunshine-virtual-output.service",
)


def systemctl(*args, check=True):
    return subprocess.run(
        ["systemctl", "--user", *args], check=check, text=True, capture_output=True
    )


def configuration(source: str, overrides: dict[str, object]) -> str:
    """Preserve unknown settings/comments, replacing each managed option once."""
    lines = []
    for line in source.splitlines():
        match = re.match(r"\s*([a-zA-Z_][a-zA-Z_0-9]*)\s*=", line)
        if not match or match[1] not in overrides:
            lines.append(line)
    return (
        "\n".join(lines)
        + "\n\n"
        + "\n".join(f"{key} = {value}" for key, value in overrides.items())
        + "\n"
    )


def migrate_apps(source: dict, dest: Path) -> dict:
    """Replace only the known KWin helpers; preserve other app definitions."""
    apps = json.loads(json.dumps(source))
    root = str(dest)
    for app in apps.get("apps", []):
        prep = app.setdefault("prep-cmd", [])
        prep[:] = [
            entry
            for entry in prep
            if not any(
                marker in entry.get("do", "")
                for marker in (
                    "sunshine-virtual-output/adapt.py",
                    "sunshine-headless/set-resolution.py",
                )
            )
        ]
        prep.insert(0, {"do": f'"{root}/set-resolution.py"', "undo": ""})
        detached = app.get("detached", [])
        for index, command in enumerate(detached):
            for old, game in (
                ("launch-genshin.sh", "genshin"),
                ("launch-zzz.sh", "zzz"),
            ):
                if command.endswith("/sunshine-virtual-output/" + old):
                    detached[index] = f'"{root}/launch-game.sh" {game}'
    if not any(app.get("name") == "Terminal (Sway)" for app in apps.get("apps", [])):
        apps.setdefault("apps", []).append(
            {
                "name": "Terminal (Sway)",
                "cmd": "foot /bin/bash",
                "prep-cmd": [{"do": f'"{root}/set-resolution.py"', "undo": ""}],
            }
        )
    return apps


def install():
    dependencies = (
        "sway",
        "sunshine",
        "pipewire",
        "wireplumber",
        "pactl",
        "dbus-run-session",
        "kwriteconfig6",
        "kreadconfig6",
        "foot",
        "quickshell",
        "dolphin",
    )
    missing = [name for name in dependencies if not shutil.which(name)]
    if missing:
        raise SystemExit(f"Install missing dependencies first: {', '.join(missing)}")
    import dbus  # noqa: F401  # validate runtime dependency before writes

    if not os.access("/dev/uinput", os.W_OK):
        raise SystemExit("The current user needs write access to /dev/uinput")
    for path in (DEST, CONF, UNITS, STATE, DEST / "bin"):
        path.mkdir(parents=True, exist_ok=True)
    for name in (
        "session.py",
        "input-isolation.py",
        "set-resolution.py",
        "launch-game.sh",
        "sway.conf",
        "pipewire.conf",
    ):
        shutil.copy2(SOURCE / name, DEST / name)
    shutil.copytree(SOURCE / "quickshell", DEST / "quickshell", dirs_exist_ok=True)
    shutil.copy2(SOURCE / "gamescope", DEST / "bin/gamescope")
    shutil.copy2(
        SOURCE / "sunshine-headless.service", UNITS / "sunshine-headless.service"
    )
    original = (ORIGINAL / "sunshine.conf").read_text()
    overrides = {
        "capture": "wlr",
        "encoder": "nvenc",
        "output_name": "HEADLESS-1",
        "audio_sink": "sink-sunshine-stereo",
        "virtual_sink": "sink-sunshine-stereo",
        "file_apps": CONF / "apps.json",
        "file_state": ORIGINAL / "sunshine_state.json",
        "credentials_file": ORIGINAL / "sunshine_state.json",
        "pkey": ORIGINAL / "credentials/cakey.pem",
        "cert": ORIGINAL / "credentials/cacert.pem",
        "log_path": CONF / "sunshine.log",
        "min_log_level": "info",
    }
    (CONF / "sunshine.conf").write_text(configuration(original, overrides))
    apps = migrate_apps(json.loads((ORIGINAL / "apps.json").read_text()), DEST)
    (CONF / "apps.json").write_text(
        json.dumps(apps, ensure_ascii=False, indent=2) + "\n"
    )
    # Keep a stable device path across boots; only auto-select an unambiguous GPU.
    render_nodes = list(Path("/dev/dri/by-path").glob("*-render"))
    if len(render_nodes) == 1 and not (DEST / "settings.json").exists():
        (DEST / "settings.json").write_text(
            json.dumps({"WLR_RENDER_DRM_DEVICE": str(render_nodes[0])}) + "\n"
        )
    systemctl("daemon-reload")
    print(f"Generated {CONF} and {DEST}; run activate to switch services.")


def activate():
    if not (DEST / "session.py").exists():
        raise SystemExit("Run install first")
    manifest = STATE / "previous-services.json"
    if not manifest.exists():
        previous = {
            unit: {
                "enabled": systemctl("is-enabled", unit, check=False).stdout.strip(),
                "active": systemctl("is-active", unit, check=False).stdout.strip()
                == "active",
            }
            for unit in OLD_UNITS
        }
        manifest.write_text(json.dumps(previous, indent=2) + "\n")
    try:
        for unit in OLD_UNITS:
            systemctl("disable", "--now", unit, check=False)
        # Block packaged desktop autostart from competing for Sunshine's ports.
        systemctl("mask", OLD_UNITS[0])
        systemctl("enable", "--now", "sunshine-headless.service")
    except Exception:
        rollback()
        raise
    print("Started sunshine-headless.service. Inspect its journal and test Moonlight.")


def rollback():
    systemctl("disable", "--now", "sunshine-headless.service", check=False)
    subprocess.run([str(DEST / "input-isolation.py"), "restore"], check=True)
    manifest = STATE / "previous-services.json"
    if not manifest.exists():
        return
    previous = json.loads(manifest.read_text())
    for unit, status in previous.items():
        if unit == OLD_UNITS[0] and status["enabled"] != "masked":
            systemctl("unmask", unit)
        if status["enabled"] in ("enabled", "enabled-runtime"):
            args = ["enable", unit]
            if status["enabled"] == "enabled-runtime":
                args.insert(1, "--runtime")
            systemctl(*args)
    for unit, status in reversed(list(previous.items())):
        if status["active"]:
            systemctl("start", unit)
    manifest.unlink()
    print("Restored previous Sunshine services and KWin input settings.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "activate", "rollback"))
    args = parser.parse_args()
    {"install": install, "activate": activate, "rollback": rollback}[args.action]()
