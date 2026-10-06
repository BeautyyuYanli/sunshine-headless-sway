"""Regression coverage for migration preservation and untrusted client arguments."""

import copy
import importlib.machinery
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(ROOT / path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


installer = load("installer", "kde/install.py")
session = load("session", "kde/session.py")
resolution = load("resolution", "kde/set-resolution.py")
gamescope = load("gamescope", "kde/gamescope")


class MigrationTests(unittest.TestCase):
    def test_config_preserves_unmanaged_options_and_replaces_duplicates(self):
        source = "# custom\ncapture = kwin\n  capture=wlr\nbitrate=45000\n"
        rendered = installer.configuration(
            source, {"capture": "wlr", "encoder": "nvenc"}
        )
        self.assertEqual(rendered.count("capture"), 1)
        self.assertIn("bitrate=45000", rendered)
        self.assertIn("# custom", rendered)
        self.assertIn("capture = wlr", rendered)

    def test_apps_preserve_user_commands_and_migrate_known_helpers(self):
        source = {
            "env": {"CUSTOM": "keep"},
            "apps": [
                {
                    "name": "game",
                    "image-path": "cover.png",
                    "detached": [
                        "/home/test/.local/share/sunshine-virtual-output/launch-genshin.sh"
                    ],
                    "prep-cmd": [
                        {
                            "do": "/home/test/.local/share/sunshine-virtual-output/adapt.py",
                            "undo": "",
                        },
                        {"do": "custom-prep", "undo": "custom-undo"},
                    ],
                }
            ],
        }
        before = copy.deepcopy(source)
        result = installer.migrate_apps(
            source, Path("/home/test/.local/share/sunshine-headless")
        )
        self.assertEqual(source, before)
        self.assertEqual(result["env"], source["env"])
        self.assertEqual(result["apps"][0]["image-path"], "cover.png")
        self.assertIn("custom-prep", str(result))
        self.assertIn("custom-undo", str(result))
        self.assertNotIn("sunshine-virtual-output", str(result))
        self.assertEqual(
            installer.migrate_apps(
                result, Path("/home/test/.local/share/sunshine-headless")
            ),
            result,
        )


class SessionTests(unittest.TestCase):
    def test_published_display_replaces_host_without_host_authentication(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.json"
            path.write_text(
                json.dumps(
                    {
                        "DISPLAY": ":2",
                        "WAYLAND_DISPLAY": "wayland-1",
                        "PULSE_SERVER": "unix:/private/pulse/native",
                    }
                )
            )
            with patch.object(session, "ENV_FILE", path):
                result = session.session_env(
                    {
                        "DISPLAY": ":1",
                        "XAUTHORITY": "/host/auth",
                        "SESSION_MANAGER": "host",
                        "CUSTOM": "keep",
                    }
                )
        self.assertEqual(result["DISPLAY"], ":2")
        self.assertEqual(result["CUSTOM"], "keep")
        self.assertNotIn("XAUTHORITY", result)
        self.assertNotIn("SESSION_MANAGER", result)


class ModeTests(unittest.TestCase):
    def test_default_and_even_client_dimensions(self):
        self.assertEqual(resolution.mode({}), (1920, 1080, 60))
        self.assertEqual(
            resolution.mode(
                {
                    "SUNSHINE_CLIENT_WIDTH": "2245",
                    "SUNSHINE_CLIENT_HEIGHT": "1009",
                    "SUNSHINE_CLIENT_FPS": "120",
                }
            ),
            (2244, 1008, 120),
        )

    def test_invalid_client_dimensions_never_reach_sway(self):
        for value in ("0", "999999", "1920; exec touch /tmp/injected", "NaN"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolution.mode({"SUNSHINE_CLIENT_WIDTH": value})

    def test_gamescope_changes_display_options_but_preserves_game_arguments(self):
        tail = ["--", "wine", "game.exe", "-w", "42", "--output-width=99"]
        result = gamescope.rewrite(
            ["-w800", "-H", "600", "--nested-refresh=30", "--fullscreen"] + tail,
            2244,
            1008,
            120,
        )
        self.assertEqual(result[result.index("--") :], tail)
        self.assertIn("--fullscreen", result)
        self.assertNotIn("-w800", result)
        self.assertEqual(result[result.index("--nested-width") + 1], "2244")
        self.assertEqual(result[result.index("--nested-refresh") + 1], "120")


if __name__ == "__main__":
    unittest.main()
