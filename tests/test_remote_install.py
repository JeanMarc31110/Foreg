import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from forge.remote_install import (
    EnvironmentCheck,
    SELF_CHECKS,
    VALIDATED_STATUS,
    can_publish_release_link,
    derive_prerequisites,
    evaluate_environment,
    install_missing_prerequisites,
    validate_https_url,
    write_remote_install_files,
)


class RemoteInstallTests(unittest.TestCase):
    def test_generated_client_contract_is_consent_based(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_remote_install_files(root, "Test Agent", "test-agent", "1.2.3", "https://cdn.example.test/test.exe")
            bootstrapper = (root / "install_from_link.ps1").read_text(encoding="utf-8")
            self.assertIn("Invoke-WebRequest", bootstrapper)
            self.assertIn("Get-FileHash", bootstrapper)
            self.assertIn("Get-AuthenticodeSignature", bootstrapper)
            self.assertIn("Start-Process -FilePath $temp -Wait", bootstrapper)
            self.assertIn("[switch]$CheckForUpdate", bootstrapper)
            self.assertIn("if ($CheckForUpdate)", bootstrapper)
            for forbidden in ("/S", "/VERYSILENT", "/SUPPRESSMSGBOXES", "Invoke-Command", "Start-Job"):
                self.assertNotIn(forbidden, bootstrapper)
            manifest = json.loads((root / "release-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["deployment_mode"], "client_link")
            self.assertTrue(manifest["link_install_enabled"])
            self.assertEqual(manifest["release_status"], "BLOCKED_UNTIL_VALIDATED")
            self.assertEqual(manifest["runtime"]["python"], "bundled_frozen_exe")
            self.assertEqual(manifest["self_check"], list(SELF_CHECKS))
            self.assertTrue((root / "prerequisites.json").exists())

    def test_invalid_url_and_unvalidated_manifest_are_refused(self):
        with self.assertRaises(ValueError):
            validate_https_url("http://cdn.example.test/setup.exe")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_remote_install_files(root, "Test Agent", "test-agent", "1.0.0", agent_profile={"purpose": "WebView2"})
            allowed, reason = can_publish_release_link(root / "release-manifest.json")
            self.assertFalse(allowed)
            self.assertIn("manquants", reason.lower())

    def test_bootstrapper_parses_on_windows_powershell_when_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_remote_install_files(root, "Test Agent", "test-agent", "1.0.0")
            if not shutil_which("pwsh"):
                self.skipTest("PowerShell Core indisponible dans cet environnement")
            env = os.environ.copy()
            env["FORGE_BOOTSTRAPPER"] = str(root / "install_from_link.ps1")
            result = subprocess.run(
                ["pwsh", "-NoProfile", "-NonInteractive", "-Command", "[scriptblock]::Create((Get-Content -LiteralPath $env:FORGE_BOOTSTRAPPER -Raw)) | Out-Null"],
                env=env, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_validated_manifest_is_publishable_only_with_real_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "release-manifest.json"
            manifest_path.write_text(json.dumps({
                "version": "1.0.0", "download_url": "https://cdn.example.test/setup.exe",
                "sha256": "A" * 64, "size_bytes": 123, "built_at_utc": "2026-08-17T00:00:00+00:00",
                "release_status": VALIDATED_STATUS, "authenticode_setup": "VALID",
                "prerequisites": [], "self_check": list(SELF_CHECKS),
                "manifest_signature": "VALID", "manifest_signature_file": "release-manifest.sig",
            }), encoding="utf-8")
            (manifest_path.parent / "release-manifest.sig").write_text("detached-signature", encoding="ascii")
            allowed, reason = can_publish_release_link(manifest_path)
            self.assertTrue(allowed)
            self.assertEqual(reason, "Lien publiable.")

            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            data["sha256"] = "not-a-hash"
            manifest_path.write_text(json.dumps(data), encoding="utf-8")
            allowed, _ = can_publish_release_link(manifest_path)
            self.assertFalse(allowed)

    def test_prerequisites_are_derived_only_when_explicitly_required(self):
        self.assertEqual(derive_prerequisites({"purpose": "local SQLite agent"}), [])
        items = derive_prerequisites({"purpose": "Uses WebView2 and Visual C++"})
        self.assertEqual({item["name"] for item in items}, {"Microsoft Edge WebView2 Runtime", "Microsoft Visual C++ Redistributable"})
        self.assertTrue(all(item["official_source"].startswith("https://") for item in items))

    def test_generated_bootstrapper_contains_visible_prerequisite_install_and_self_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_remote_install_files(root, "Web Agent", "web-agent", "1.0.0", agent_profile={"purpose": "WebView2"})
            script = (root / "install_from_link.ps1").read_text(encoding="utf-8")
            self.assertIn("Install-MissingPrerequisites", script)
            self.assertIn("Start-Process -FilePath $pre -Wait -PassThru", script)
            self.assertIn("Get-AuthenticodeSignature", script)
            for marker in ("RUNTIME", "PORTS", "LOCALAPPDATA", "DB", "TLS"):
                self.assertIn(marker, script.upper())

    def test_clean_machine_and_present_prerequisite(self):
        item = {"name": "Runtime", "status": "external"}
        ok, messages = install_missing_prerequisites([item], lambda _: False, lambda _: "installed")
        self.assertTrue(ok)
        self.assertIn("consentement Windows", messages[0])
        ok, _ = install_missing_prerequisites([item], lambda _: True, lambda _: "error")
        self.assertTrue(ok)

    def test_invalid_download_hash_reboot_access_denied_and_busy_port_block(self):
        item = {"name": "Runtime", "status": "external"}
        for outcome in ("hash_invalid", "reboot_required", "access_denied", "port_occupied"):
            ok, messages = install_missing_prerequisites([item], lambda _: False, lambda _: outcome)
            self.assertFalse(ok, outcome)
            self.assertIn(outcome, messages[-1])
        ok, reason = evaluate_environment([
            EnvironmentCheck("port 8765", False, "déjà occupé"),
            EnvironmentCheck("TLS", True, "ok"),
        ])
        self.assertFalse(ok)
        self.assertIn("port 8765", reason)
        ok, reason = evaluate_environment([EnvironmentCheck("runtime", True, "ok", reboot_required=True)])
        self.assertFalse(ok)
        self.assertIn("Redémarrage", reason)


if __name__ == "__main__":
    unittest.main()


def shutil_which(command: str) -> str | None:
    import shutil
    return shutil.which(command)

