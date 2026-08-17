import json
import tempfile
import unittest
from pathlib import Path

from forge.code_auditor import audit_agent_code
from forge.schemas import AgentBlueprint, TestCase


def _blueprint() -> AgentBlueprint:
    return AgentBlueprint(
        name="Valid Test Agent",
        slug="valid-test-agent",
        purpose="Vérifier l’audit de code.",
        system_instructions="Répondre avec précision.",
        tests=[TestCase(name="smoke", input="ping", expected_behavior="pong", critical=True)],
    )


def _write_valid(root: Path) -> None:
    (root / "agent.py").write_text(
        "import json\n\n"
        "def self_test():\n"
        "    print(json.dumps({'ok': True}))\n"
        "    return 0\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(self_test() if '--self-test' in __import__('sys').argv else 0)\n",
        encoding="utf-8",
    )
    (root / "smoke_test.py").write_text("assert __import__('agent').self_test() == 0\n", encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps(_blueprint().model_dump()), encoding="utf-8")
    (root / "README.md").write_text("# Valid Test Agent\n", encoding="utf-8")
    (root / "requirements.txt").write_text("pytest==8.3.3\n", encoding="utf-8")
    (root / "requirements-release.txt").write_text("pyinstaller==6.10.0\npytest==8.3.3\n", encoding="utf-8")
    for name in ("installer.iss", "build_release.ps1", "build_release.bat", "RELEASE_WINDOWS.md", "install_from_link.ps1", "release-manifest.json", "CLIENT_README.md", "CLIENT_MESSAGE_TEMPLATE.md"):
        (root / name).write_text("# test\n", encoding="utf-8")
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_valid.py").write_text(
        "import unittest\n\nclass ValidTest(unittest.TestCase):\n    def test_truth(self):\n        self.assertTrue(True)\n",
        encoding="utf-8",
    )


class CodeAuditorTests(unittest.TestCase):
    def test_valid_agent_passes_and_runs_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid(root)
            report = audit_agent_code(root, _blueprint())
        self.assertEqual(report.verdict, "PASSED")
        self.assertIn("python_compile", report.executed_checks)
        self.assertIn("unit_tests", report.executed_checks)
        self.assertIn("self_test", report.executed_checks)
        self.assertIn("smoke_test", report.executed_checks)
        self.assertFalse(report.blocking_findings)

    def test_broken_agent_is_blocked_with_structured_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "agent.py").write_text(
                "import definitely_missing_module\n"
                "import subprocess\n"
                "API_KEY = 'sk-1234567890abcdef'\n"
                "def broken(:\n    pass\n",
                encoding="utf-8",
            )
            (root / "requirements.txt").write_text("pywin32\n", encoding="utf-8")
            report = audit_agent_code(root, _blueprint(), run_tests=False)
        self.assertEqual(report.verdict, "BLOCKED")
        diagnostics = " ".join(f.diagnostic for f in report.findings)
        self.assertIn("Syntaxe Python invalide", diagnostics)
        self.assertTrue(any(f.blocking for f in report.findings))
        self.assertTrue(all(f.file and f.diagnostic and f.proposed_fix for f in report.findings))

    def test_missing_tests_block_release_even_when_python_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_valid(root)
            for path in (root / "tests").glob("*.py"):
                path.unlink()
            report = audit_agent_code(root, _blueprint(), run_tests=False)
        self.assertEqual(report.verdict, "BLOCKED")
        self.assertTrue(any("Aucun test" in f.diagnostic for f in report.findings))


if __name__ == "__main__":
    unittest.main()

