from __future__ import annotations

import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .schemas import AgentBlueprint, CodeAuditReport, CodeFinding


_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"\bsk-[A-Za-z0-9]{12,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
_DANGEROUS_DEPENDENCIES = {"pypiwin32", "pywin32", "pip", "setuptools"}
_WINDOWS_PATH = re.compile(r"(?:[A-Za-z]:\\|\\\\|%[^%]+%\\|os\.getenv\(['\"](?:APPDATA|LOCALAPPDATA|PROGRAMFILES))")
_NETWORK_CALLS = {"urlopen", "urlretrieve", "request", "get", "post", "put", "delete", "connect"}
_SUBPROCESS_CALLS = {"run", "Popen", "call", "check_call", "check_output"}


@dataclass(frozen=True)
class _Issue:
    severity: str
    file: str
    line: int | None
    diagnostic: str
    proposed_fix: str
    blocking: bool

    def model(self) -> CodeFinding:
        return CodeFinding(
            severity=self.severity,
            file=self.file,
            line=self.line,
            diagnostic=self.diagnostic,
            proposed_fix=self.proposed_fix,
            blocking=self.blocking,
        )


def _issue(severity: str, path: Path, root: Path, diagnostic: str, fix: str, line: int | None = None, blocking: bool = False) -> _Issue:
    return _Issue(severity, str(path.relative_to(root)).replace("\\", "/"), line, diagnostic, fix, blocking)


def _declared_dependencies(path: Path) -> set[str]:
    result: set[str] = set()
    if not path.exists():
        return result
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        name = re.split(r"[<>=!~;\s]", line, maxsplit=1)[0]
        result.add(name.lower().replace("-", "_"))
    return result


def _module_is_available(name: str, root: Path, declared: set[str]) -> bool:
    top = name.split(".", 1)[0]
    if top in sys.stdlib_module_names or top in {"__future__"}:
        return True
    if top in {item.split("_")[0] for item in declared}:
        return True
    if (root / (top + ".py")).exists() or (root / top / "__init__.py").exists():
        return True
    return importlib.util.find_spec(top) is not None


def _scan_ast(path: Path, root: Path, declared: set[str]) -> list[_Issue]:
    issues: list[_Issue] = []
    try:
        with tokenize.open(path) as source_file:
            source = source_file.read()
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError, tokenize.TokenError) as exc:
        line = getattr(exc, "lineno", None)
        issues.append(_issue("critical", path, root, f"Syntaxe Python invalide : {exc}", "Corriger la syntaxe avant toute release.", line, True))
        return issues

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        else:
            names = []
        for name in names:
            if not _module_is_available(name, root, declared):
                issues.append(_issue("critical", path, root, f"Import potentiellement cassé ou dépendance absente : {name}", "Ajouter la dépendance correctement épinglée ou corriger l’import.", node.lineno, True))
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                issues.append(_issue("warning", path, root, "Exception nue qui masque des erreurs inattendues.", "Capturer une exception précise et journaliser le contexte.", node.lineno))
            elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
                issues.append(_issue("warning", path, root, "Capture globale de Exception.", "Capturer les exceptions attendues et traiter les erreurs explicitement.", node.lineno))
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name) and node.exc.func.id == "NotImplementedError":
            issues.append(_issue("error", path, root, "Fonction explicitement non implémentée.", "Implémenter le chemin utilisé ou le retirer du package livré.", node.lineno, True))
        if isinstance(node, ast.Call):
            func_name = node.func.attr if isinstance(node.func, ast.Attribute) else (node.func.id if isinstance(node.func, ast.Name) else "")
            owner = node.func.value.id if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) else ""
            if owner == "subprocess" or func_name in _SUBPROCESS_CALLS:
                issues.append(_issue("warning", path, root, "Exécution de processus détectée.", "Limiter les commandes à une allowlist, utiliser une liste d’arguments et conserver un contrôle humain si l’action est sensible.", node.lineno))
            if owner in {"requests", "httpx", "urllib", "aiohttp", "socket"} or func_name in _NETWORK_CALLS:
                issues.append(_issue("warning", path, root, "Accès réseau détecté.", "Limiter les domaines, définir des timeouts et documenter l’autorisation réseau.", node.lineno))
            if owner in {"sqlite3", "sqlalchemy", "psycopg", "mysql", "pymysql"} or func_name in {"connect", "execute", "executemany"}:
                issues.append(_issue("info", path, root, "Accès base de données détecté.", "Utiliser des requêtes paramétrées, une base située hors de Program Files et des tests d’intégrité.", node.lineno))
            if func_name in {"open", "write_text", "write_bytes", "unlink", "remove", "rmtree"}:
                issues.append(_issue("info", path, root, "Accès au système de fichiers détecté.", "Valider les chemins, éviter les suppressions implicites et stocker les données utilisateur dans LOCALAPPDATA.", node.lineno))
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if _WINDOWS_PATH.search(node.value) and "LOCALAPPDATA" not in node.value.upper():
                issues.append(_issue("warning", path, root, "Chemin Windows fragile ou codé en dur détecté.", "Utiliser pathlib et une base dérivée de LOCALAPPDATA plutôt qu’un chemin absolu.", node.lineno))
    return issues


def _scan_text(path: Path, root: Path) -> list[_Issue]:
    issues: list[_Issue] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        for pattern in _SECRET_PATTERNS:
            if pattern.search(line) and "example" not in path.name.lower() and "votre" not in line.lower():
                issues.append(_issue("critical", path, root, "Secret potentiel détecté dans le code ou la configuration.", "Supprimer la valeur, utiliser une variable d’environnement et ne jamais committer le secret.", lineno, True))
                break
        if "--trusted-host" in line or re.search(r"(?:https?|git\+https?)://", line) and path.name.startswith("requirements"):
            issues.append(_issue("error", path, root, "Dépendance installée depuis une source non verrouillée ou non standard.", "Utiliser un index de confiance et une version/empreinte verrouillée.", lineno, True))
    return issues


def _scan_dependencies(root: Path, issues: list[_Issue]) -> None:
    for path in root.glob("requirements*.txt"):
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            name = re.split(r"[<>=!~;\s]", line, maxsplit=1)[0].lower()
            if not re.search(r"(?:==|===|@)", line):
                issues.append(_issue("warning", path, root, f"Dépendance non épinglée : {name}.", "Épingler une version testée, idéalement avec hash dans un lockfile.", lineno))
            if name in _DANGEROUS_DEPENDENCIES:
                issues.append(_issue("error", path, root, f"Dépendance sensible ou inutile en runtime : {name}.", "Retirer cette dépendance ou justifier explicitement son usage et la verrouiller.", lineno, True))


def _run_command(command: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str]:
    try:
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)
        return result.returncode, (result.stdout + result.stderr)[-4000:]
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def audit_agent_code(agent_dir: Path, blueprint: AgentBlueprint | None = None, run_tests: bool = True) -> CodeAuditReport:
    """Audit an agent package without executing its application logic."""
    root = Path(agent_dir).resolve()
    issues: list[_Issue] = []
    if not root.is_dir():
        return CodeAuditReport(verdict="BLOCKED", findings=[CodeFinding(severity="critical", file=str(root), diagnostic="Package agent introuvable.", proposed_fix="Créer le package avant audit.", blocking=True)], executed_checks=[])

    expected = {"agent.py", "manifest.json", "README.md", "requirements.txt", "tests"}
    if blueprint is not None:
        expected.update({"requirements-release.txt", "installer.iss", "build_release.ps1", "build_release.bat", "RELEASE_WINDOWS.md", "install_from_link.ps1", "release-manifest.json", "CLIENT_README.md", "CLIENT_MESSAGE_TEMPLATE.md"})
    for name in sorted(expected):
        if not (root / name).exists():
            issues.append(_issue("critical", root / name, root, f"Fichier ou répertoire attendu absent : {name}", "Générer le fichier requis avant matérialisation.", blocking=True))

    tests_dir = root / "tests"
    test_files = list(tests_dir.glob("test_*.py")) + list(tests_dir.glob("*_test.py")) if tests_dir.is_dir() else []
    if not test_files:
        issues.append(_issue("critical", tests_dir, root, "Aucun test automatisé détecté.", "Ajouter au moins un test de comportement et un test critique déclaré.", blocking=True))
    if blueprint is not None and (not blueprint.tests or not any(test.critical for test in blueprint.tests)):
        issues.append(_issue("critical", root / "manifest.json", root, "Le blueprint ne contient pas de test critique.", "Déclarer au moins un test critique exécutable.", blocking=True))

    declared = _declared_dependencies(root / "requirements.txt") | _declared_dependencies(root / "requirements-release.txt")
    python_files = list(root.rglob("*.py"))
    for path in python_files:
        if any(part in {".venv", "build", "dist", "release"} for part in path.parts):
            continue
        issues.extend(_scan_ast(path, root, declared))
        issues.extend(_scan_text(path, root))
    for path in root.rglob("*.txt"):
        if path.name.startswith("requirements"):
            issues.extend(_scan_text(path, root))
    config_suffixes = {".json", ".env", ".ini", ".cfg", ".toml", ".yaml", ".yml"}
    for path in root.rglob("*"):
        if path.is_file() and (path.suffix.lower() in config_suffixes or path.name.startswith(".env")):
            issues.extend(_scan_text(path, root))
    _scan_dependencies(root, issues)

    executed = ["python_ast_syntax_imports", "expected_files", "tests_declared_and_present", "secrets_and_dependencies", "filesystem_db_subprocess_network_scan"]
    if python_files:
        code, output = _run_command([sys.executable, "-m", "compileall", "-q", "."], root)
        executed.append("python_compile")
        if code:
            issues.append(_issue("critical", root, root, f"Compilation Python échouée : {output}", "Corriger les erreurs de compilation.", blocking=True))
    if run_tests and test_files:
        if importlib.util.find_spec("pytest") is not None:
            command = [sys.executable, "-m", "pytest", "-q"]
        else:
            command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"]
        code, output = _run_command(command, root)
        executed.append("unit_tests")
        if code:
            issues.append(_issue("critical", root / "tests", root, f"Tests automatisés échoués : {output}", "Corriger les tests et relancer l’audit.", blocking=True))
    if (root / "agent.py").exists():
        code, output = _run_command([sys.executable, "agent.py", "--self-test"], root)
        executed.append("self_test")
        if code:
            issues.append(_issue("critical", root / "agent.py", root, f"Self-test échoué : {output}", "Corriger le self-test de l’agent.", blocking=True))
        smoke = root / "smoke_test.py"
        if smoke.exists():
            code, output = _run_command([sys.executable, str(smoke)], root)
            executed.append("smoke_test")
            if code:
                issues.append(_issue("critical", smoke, root, f"Smoke-test échoué : {output}", "Corriger le parcours principal de l’agent.", blocking=True))

    findings = [item.model() for item in issues]
    blocking = [item for item in findings if item.blocking or item.severity == "critical"]
    score = max(0, 100 - sum(35 if item.severity == "critical" else 15 if item.severity == "error" else 3 for item in findings))
    return CodeAuditReport(score=score, verdict="BLOCKED" if blocking else "PASSED", findings=findings, executed_checks=executed)

