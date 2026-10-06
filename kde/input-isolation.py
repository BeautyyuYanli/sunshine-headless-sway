#!/usr/bin/python3
"""Disable only Sunshine passthrough devices in KWin, leaving libinput tags intact.

KConfig edits use KDE's configuration tools. Save the exact prior key values for
ExecStopPost/rollback. Known names are configured before Sunshine creates devices,
so hotplug does not depend on a polling watcher. Does not isolate evdev gamepads.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import dbus

NAMES = (
    "Keyboard passthrough",
    "Mouse passthrough",
    "Mouse passthrough (absolute)",
    "Touch passthrough",
    "Pen passthrough",
)
STATE = Path.home() / ".local/state/sunshine-headless/input.json"
INTERFACE = "org.kde.KWin.InputDevice"
ABSENT = "__sunshine_absent__"


def config_args(name):
    return [
        "--file",
        "kcminputrc",
        "--group",
        "Libinput",
        "--group",
        "48879",
        "--group",
        "57005",
        "--group",
        name,
        "--key",
        "Enabled",
    ]


def host_bus():
    address = os.environ.get(
        "HOST_DBUS_SESSION_BUS_ADDRESS", f"unix:path=/run/user/{os.getuid()}/bus"
    )
    return dbus.bus.BusConnection(address)


def live_devices(bus):
    if not bus.name_has_owner("org.kde.KWin"):
        return []
    manager = dbus.Interface(
        bus.get_object("org.kde.KWin", "/org/kde/KWin/InputDevice"),
        "org.freedesktop.DBus.Properties",
    )
    devices = []
    for name in manager.Get("org.kde.KWin.InputDeviceManager", "devicesSysNames"):
        try:
            prop = dbus.Interface(
                bus.get_object("org.kde.KWin", f"/org/kde/KWin/InputDevice/{name}"),
                "org.freedesktop.DBus.Properties",
            )
            info = prop.GetAll(INTERFACE)
            if (
                info["vendor"] == 48879
                and info["product"] == 57005
                and info["name"] in NAMES
            ):
                devices.append((str(info["name"]), prop))
        except dbus.exceptions.DBusException as exc:
            # A device may disappear during enumeration; other errors must surface.
            if exc.get_dbus_name() not in (
                "org.freedesktop.DBus.Error.UnknownObject",
                "org.freedesktop.DBus.Error.UnknownInterface",
            ):
                raise
    return devices


def reload_config(bus):
    message = dbus.lowlevel.SignalMessage(
        "/KGlobalSettings", "org.kde.KGlobalSettings", "notifyChange"
    )
    message.append(dbus.Int32(3), dbus.Int32(0), signature="ii")
    bus.send_message(message)
    bus.flush()


def main(action):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    bus = host_bus()
    if action == "disable":
        if not STATE.exists():
            saved = {
                name: subprocess.check_output(
                    ["kreadconfig6", *config_args(name), "--default", ABSENT], text=True
                ).strip()
                for name in NAMES
            }
            STATE.write_text(json.dumps(saved))
        for name in NAMES:
            subprocess.run(
                ["kwriteconfig6", *config_args(name), "--type", "bool", "false"],
                check=True,
            )
        reload_config(bus)
        for name, prop in live_devices(bus):
            prop.Set(INTERFACE, "enabled", dbus.Boolean(False))
            if prop.Get(INTERFACE, "enabled"):
                raise RuntimeError(f"KWin still accepts {name}")
    elif action == "restore":
        if not STATE.exists():
            return
        saved = json.loads(STATE.read_text())
        for name, prop in live_devices(bus):
            prop.Set(INTERFACE, "enabled", dbus.Boolean(saved[name] != "false"))
        for name, value in saved.items():
            args = ["--delete"] if value == ABSENT else ["--type", "bool", value]
            subprocess.run(["kwriteconfig6", *config_args(name), *args], check=True)
        reload_config(bus)
        STATE.unlink()
    else:
        raise SystemExit("Usage: input-isolation.py disable|restore")


if __name__ == "__main__":
    main(sys.argv[1])
