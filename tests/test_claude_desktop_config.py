import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


class ClaudeDesktopConfigTests(unittest.TestCase):
    def load_module(self):
        import importlib
        import sys

        sys.path.insert(0, str(ROOT))
        sys.modules.pop("backend.claude_desktop_config", None)
        return importlib.import_module("backend.claude_desktop_config")

    def make_config(self, module, root: Path):
        primary = root / "Claude"
        third_party = root / "Claude-3p"
        executable = root / "AnthropicClaude" / "claude.exe"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"")
        patches = mock.patch.dict(
            os.environ,
            {
                "CONFIGPILOT_CLAUDE_PRIMARY_DATA_DIR": str(primary),
                "CONFIGPILOT_CLAUDE_DATA_DIR": str(third_party),
                "CONFIGPILOT_CLAUDE_EXECUTABLE": str(executable),
            },
        )
        patches.start()
        self.addCleanup(patches.stop)
        return module.ClaudeDesktopConfig(), primary, third_party

    @staticmethod
    def write_json(path: Path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def test_reload_reads_active_profile_without_exposing_api_key(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_id = "47d9f41b-7b52-46e3-ac29-f64626682da3"
            third_party = root / "Claude-3p"
            self.write_json(
                third_party / "developer_settings.json", {"allowDevTools": True}
            )
            self.write_json(
                third_party / "claude_desktop_config.json",
                {"deploymentMode": "3p", "preferences": {"sidebarMode": "default"}},
            )
            self.write_json(
                third_party / "configLibrary" / "_meta.json",
                {
                    "appliedId": profile_id,
                    "entries": [{"id": profile_id, "name": "Gateway"}],
                },
            )
            self.write_json(
                third_party / "configLibrary" / f"{profile_id}.json",
                {
                    "inferenceProvider": "gateway",
                    "inferenceGatewayBaseUrl": "https://gateway.example.com",
                    "inferenceGatewayApiKey": "secret-value",
                    "inferenceGatewayAuthScheme": "x-api-key",
                    "inferenceModels": ["model-a", {"name": "model-b"}],
                    "inferenceCustomHeaders": {"X-Tenant": "demo"},
                },
            )

            config, _, _ = self.make_config(module, root)

            self.assertTrue(config.installed)
            self.assertTrue(config.developerModeEnabled)
            self.assertTrue(config.thirdPartyEnabled)
            self.assertEqual(config.endpoint, "https://gateway.example.com")
            self.assertEqual(config.authScheme, "x-api-key")
            self.assertEqual(config.modelsText, "model-a\nmodel-b")
            self.assertTrue(config.hasApiKey)
            self.assertEqual(config.headerCount, 1)
            self.assertEqual(config.profileName, "Gateway")
            self.assertNotIn("secret-value", vars(config).values())

    def test_apply_creates_profile_enables_developer_mode_and_preserves_settings(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, primary, third_party = self.make_config(module, root)
            self.write_json(
                primary / "developer_settings.json", {"useMacMenuBarHelper": True}
            )
            self.write_json(
                third_party / "claude_desktop_config.json",
                {"preferences": {"sidebarMode": "default"}},
            )
            config.reload()

            notices = []
            config.notify.connect(lambda level, title, message: notices.append((level, title, message)))
            config.applyConfig(
                {
                    "endpoint": "https://gateway.example.com/v1",
                    "authScheme": "bearer",
                    "modelsText": "model-a\nmodel-b\nmodel-a",
                    "apiKey": "new-secret",
                    "headersText": '{"X-Tenant": "demo"}',
                }
            )

            meta = json.loads(
                (third_party / "configLibrary" / "_meta.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(meta["entries"]), 1)
            self.assertEqual(meta["entries"][0]["name"], "ConfigPilot")
            profile_path = (
                third_party / "configLibrary" / f"{meta['appliedId']}.json"
            )
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(profile["inferenceProvider"], "gateway")
            self.assertEqual(profile["inferenceCredentialKind"], "static")
            self.assertEqual(
                profile["inferenceGatewayBaseUrl"], "https://gateway.example.com/v1"
            )
            self.assertEqual(profile["inferenceGatewayAuthScheme"], "bearer")
            self.assertEqual(profile["inferenceGatewayApiKey"], "new-secret")
            self.assertEqual(profile["inferenceModels"], ["model-a", "model-b"])
            self.assertEqual(profile["inferenceCustomHeaders"], {"X-Tenant": "demo"})

            primary_settings = json.loads(
                (primary / "developer_settings.json").read_text(encoding="utf-8")
            )
            third_party_settings = json.loads(
                (third_party / "developer_settings.json").read_text(encoding="utf-8")
            )
            desktop_config = json.loads(
                (third_party / "claude_desktop_config.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(primary_settings["allowDevTools"])
            self.assertTrue(primary_settings["useMacMenuBarHelper"])
            self.assertTrue(third_party_settings["allowDevTools"])
            self.assertEqual(desktop_config["deploymentMode"], "3p")
            self.assertEqual(
                desktop_config["preferences"], {"sidebarMode": "default"}
            )
            self.assertTrue(
                (third_party / "claude_desktop_config.json.bak").is_file()
            )
            self.assertEqual(notices[-1][0], 1)

    def test_sensitive_fields_are_preserved_until_explicitly_cleared(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile_id = "47d9f41b-7b52-46e3-ac29-f64626682da3"
            third_party = root / "Claude-3p"
            self.write_json(
                third_party / "configLibrary" / "_meta.json",
                {
                    "appliedId": profile_id,
                    "entries": [{"id": profile_id, "name": "Gateway"}],
                },
            )
            profile_path = third_party / "configLibrary" / f"{profile_id}.json"
            self.write_json(
                profile_path,
                {
                    "inferenceProvider": "gateway",
                    "inferenceGatewayBaseUrl": "https://old.example.com",
                    "inferenceGatewayApiKey": "old-secret",
                    "inferenceCustomHeaders": {"X-Secret": "keep-me"},
                },
            )
            config, _, _ = self.make_config(module, root)

            config.applyConfig(
                {
                    "endpoint": "https://new.example.com",
                    "authScheme": "bearer",
                    "modelsText": "",
                    "apiKey": "",
                    "headersText": "",
                }
            )
            preserved = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(preserved["inferenceGatewayApiKey"], "old-secret")
            self.assertEqual(
                preserved["inferenceCustomHeaders"], {"X-Secret": "keep-me"}
            )

            config.applyConfig(
                {
                    "endpoint": "https://new.example.com",
                    "authScheme": "x-api-key",
                    "modelsText": "",
                    "clearApiKey": True,
                    "clearHeaders": True,
                }
            )
            cleared = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertNotIn("inferenceGatewayApiKey", cleared)
            self.assertNotIn("inferenceCustomHeaders", cleared)
            self.assertNotIn("inferenceGatewayHeaders", cleared)

    def test_individual_mode_toggles_preserve_gateway_profile_and_settings(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, primary, third_party = self.make_config(module, root)
            self.write_json(
                primary / "developer_settings.json", {"useMacMenuBarHelper": True}
            )
            self.write_json(
                third_party / "claude_desktop_config.json",
                {"preferences": {"sidebarMode": "default"}},
            )
            config.reload()
            config.applyConfig(
                {
                    "endpoint": "https://gateway.example.com",
                    "authScheme": "bearer",
                    "modelsText": "model-a",
                    "apiKey": "keep-secret",
                }
            )

            meta = json.loads(
                (third_party / "configLibrary" / "_meta.json").read_text(
                    encoding="utf-8"
                )
            )
            profile_path = (
                third_party / "configLibrary" / f"{meta['appliedId']}.json"
            )
            original_profile = profile_path.read_text(encoding="utf-8")

            config.setDeveloperModeEnabled(False)
            config.setThirdPartyEnabled(False)

            primary_settings = json.loads(
                (primary / "developer_settings.json").read_text(encoding="utf-8")
            )
            third_party_settings = json.loads(
                (third_party / "developer_settings.json").read_text(
                    encoding="utf-8"
                )
            )
            desktop_config = json.loads(
                (third_party / "claude_desktop_config.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(primary_settings["allowDevTools"])
            self.assertTrue(primary_settings["useMacMenuBarHelper"])
            self.assertFalse(third_party_settings["allowDevTools"])
            self.assertEqual(desktop_config["deploymentMode"], "1p")
            self.assertEqual(
                desktop_config["preferences"], {"sidebarMode": "default"}
            )
            self.assertEqual(profile_path.read_text(encoding="utf-8"), original_profile)
            self.assertFalse(config.developerModeEnabled)
            self.assertFalse(config.thirdPartyEnabled)

            config.setDeveloperModeEnabled(True)
            config.setThirdPartyEnabled(True)

            self.assertTrue(config.developerModeEnabled)
            self.assertTrue(config.thirdPartyEnabled)
            self.assertEqual(profile_path.read_text(encoding="utf-8"), original_profile)

    def test_gateway_toggle_requires_a_saved_gateway_profile(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, _, third_party = self.make_config(module, root)
            notices = []
            config.notify.connect(
                lambda level, title, message: notices.append((level, title, message))
            )

            config.setThirdPartyEnabled(True)

            self.assertFalse(
                (third_party / "claude_desktop_config.json").exists()
            )
            self.assertFalse(config.thirdPartyEnabled)
            self.assertEqual(notices[-1][0], 2)
            self.assertIn("尚未保存 Gateway 配置", notices[-1][2])

    def test_invalid_input_does_not_create_configuration(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, _, third_party = self.make_config(module, root)
            notices = []
            config.notify.connect(lambda level, title, message: notices.append((level, title, message)))

            config.applyConfig(
                {
                    "endpoint": "not-a-url",
                    "authScheme": "auto",
                    "modelsText": "model-a",
                    "headersText": "[]",
                }
            )

            self.assertFalse((third_party / "configLibrary").exists())
            self.assertEqual(notices[-1][0], 2)
            self.assertIn("Gateway endpoint", notices[-1][2])

    def test_invalid_existing_meta_is_not_overwritten(self):
        module = self.load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            third_party = root / "Claude-3p"
            meta_path = third_party / "configLibrary" / "_meta.json"
            self.write_json(
                meta_path,
                {"appliedId": "broken", "entries": [{"id": "broken"}]},
            )
            original = meta_path.read_text(encoding="utf-8")
            config, _, _ = self.make_config(module, root)
            notices = []
            config.notify.connect(
                lambda level, title, message: notices.append((level, title, message))
            )

            config.applyConfig(
                {
                    "endpoint": "https://gateway.example.com",
                    "authScheme": "bearer",
                    "modelsText": "model-a",
                }
            )

            self.assertEqual(meta_path.read_text(encoding="utf-8"), original)
            self.assertEqual(notices[-1][0], 2)
            self.assertIn("无效配置条目", notices[-1][2])


if __name__ == "__main__":
    unittest.main()
