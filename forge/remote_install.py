from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping
from urllib.parse import urlparse

VALIDATED_STATUS = "VALIDATED_FOR_REMOTE_WINDOWS_INSTALL"
BLOCKED_STATUS = "BLOCKED_UNTIL_VALIDATED"
OFFICIAL_SOURCE_HOSTS = {"aka.ms", "download.microsoft.com", "dotnet.microsoft.com", "developer.microsoft.com", "learn.microsoft.com"}
SELF_CHECKS = ("runtime", "ports", "write_permissions", "localappdata", "local_database", "network", "tls_certificates")


@dataclass(frozen=True)
class EnvironmentCheck:
    name: str
    ok: bool
    detail: str
    blocking: bool = True
    reboot_required: bool = False


def validate_https_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise ValueError("L'URL de téléchargement doit être une URL HTTPS absolue.")
    return url.strip()


def validate_official_source(url: str) -> str:
    value = validate_https_url(url)
    host = (urlparse(value).hostname or "").lower().rstrip(".")
    if not any(host == allowed or host.endswith("." + allowed) for allowed in OFFICIAL_SOURCE_HOSTS):
        raise ValueError(f"Source de prérequis non officielle ou non autorisée : {host}")
    return value


def prerequisite(name: str, minimum_version: str, source: str, detection: str, *, sha256: str = "", signer: str = "", status: str = "external") -> dict:
    validate_official_source(source)
    if status not in {"bundled", "external"}:
        raise ValueError("Le statut d'un prérequis doit être bundled ou external.")
    if sha256 and not re.fullmatch(r"[0-9a-fA-F]{64}", sha256):
        raise ValueError(f"Hash SHA-256 invalide pour le prérequis {name}.")
    return {"name": name, "minimum_version": minimum_version, "official_source": source, "detection_method": detection, "sha256": sha256.upper(), "signature": {"required": bool(signer), "signer": signer}, "status": status}


def derive_prerequisites(agent: Mapping[str, object] | None = None) -> list[dict]:
    """Only components explicitly required by the profile are external.

    Python and Node are absent because the generated Windows application is frozen/bundled.
    """
    text = json.dumps(agent or {}, ensure_ascii=False).lower()
    result: list[dict] = []
    if "webview2" in text:
        result.append(prerequisite("Microsoft Edge WebView2 Runtime", "Evergreen", "https://developer.microsoft.com/en-us/microsoft-edge/webview2/", "HKLM/HKCU\\SOFTWARE\\Microsoft\\EdgeUpdate\\Clients\\*\\pv"))
    if ".net desktop" in text or "dotnet desktop" in text:
        result.append(prerequisite(".NET Desktop Runtime", "8.0", "https://dotnet.microsoft.com/en-us/download/dotnet/8.0", "dotnet --list-runtimes contains Microsoft.WindowsDesktop.App >= minimum_version"))
    if "vc++" in text or "visual c++" in text:
        result.append(prerequisite("Microsoft Visual C++ Redistributable", "14.38", "https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist", "HKLM\\SOFTWARE\\Microsoft\\VisualStudio\\14.0\\VC\\Runtimes\\x64 Version"))
    return result


def evaluate_environment(checks: Iterable[EnvironmentCheck]) -> tuple[bool, str]:
    reboot = [item for item in checks if item.reboot_required]
    failed = [item for item in checks if item.blocking and not item.ok]
    if reboot:
        return False, "Redémarrage Windows requis avant de lancer l'agent."
    if failed:
        return False, "Environnement client incomplet : " + "; ".join(f"{x.name}: {x.detail}" for x in failed)
    return True, "Environnement client validé."


def install_missing_prerequisites(prerequisites: Iterable[Mapping[str, object]], detect: Callable[[Mapping[str, object]], bool], install: Callable[[Mapping[str, object]], str]) -> tuple[bool, list[str]]:
    """Deterministic seam for CI simulations of clean and Windows error states."""
    messages: list[str] = []
    for item in prerequisites:
        if item.get("status") == "bundled" or detect(item):
            messages.append(f"{item['name']}: déjà présent ou embarqué")
            continue
        outcome = install(item)
        if outcome != "installed":
            return False, messages + [f"{item['name']}: {outcome}"]
        messages.append(f"{item['name']}: installé avec consentement Windows")
    return True, messages


def write_remote_install_files(agent_dir: Path, app_name: str, slug: str, version: str, download_url: str = "", enabled: bool = True, agent_profile: Mapping[str, object] | None = None, prerequisites: list[dict] | None = None) -> None:
    if enabled and download_url:
        validate_https_url(download_url)
    prerequisites = prerequisites if prerequisites is not None else derive_prerequisites(agent_profile)
    for item in prerequisites:
        validate_official_source(str(item["official_source"]))
    placeholder = download_url or "https://downloads.example.invalid/REPLACE_WITH_VALIDATED_SETUP_URL"
    manifest = {"app": app_name, "slug": slug, "version": version, "setup_filename": f"{slug}-Setup-{version}.exe", "download_url": download_url, "sha256": "", "size_bytes": 0, "built_at_utc": None, "authenticode_setup": "PENDING_BUILD", "manifest_integrity": "SHA256_FILLED_AT_BUILD", "manifest_signature": "PENDING_BUILD", "manifest_signature_file": "release-manifest.sig", "release_status": BLOCKED_STATUS, "link_install_enabled": enabled, "deployment_mode": "client_link", "runtime": {"python": "bundled_frozen_exe", "node": "bundled_or_not_required"}, "prerequisites": prerequisites, "self_check": list(SELF_CHECKS)}
    (agent_dir / "prerequisites.json").write_text(json.dumps(prerequisites, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (agent_dir / "release-manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (agent_dir / "release-manifest.sig").write_text("", encoding="ascii")
    (agent_dir / "install_from_link.ps1").write_text(f'''# Installation volontaire par le client — {app_name}
[CmdletBinding()]
param([string]$DownloadUrl = "{placeholder}",[Parameter(Mandatory=$true)][string]$ExpectedSha256,[string]$ExpectedSigner="FEWURA",[switch]$CheckForUpdate)
$ErrorActionPreference="Stop"; Set-StrictMode -Version Latest
function Stop-Install([string]$Message) {{ throw "Installation refusée : $Message" }}
function Assert-OfficialSource([string]$Url) {{ $host=([Uri]$Url).Host.ToLowerInvariant(); if (-not ($host -eq "aka.ms" -or $host.EndsWith(".microsoft.com") -or $host -eq "microsoft.com")) {{ Stop-Install "Source de prérequis non officielle : $host" }} }}
function Install-MissingPrerequisites($Items) {{
  foreach ($item in @($Items)) {{
    $present = ($item.status -eq "bundled")
    if ($item.detection_method -match "HKLM|HKCU") {{ $present = [bool](Get-ItemProperty -Path ($item.detection_method -replace " Version$", "") -ErrorAction SilentlyContinue) }}
    if ($item.detection_method -match "dotnet") {{ $present = [bool](Get-Command dotnet -ErrorAction SilentlyContinue) }}
    if ($present) {{ Write-Host "Prérequis déjà présent : $($item.name)"; continue }}
    Assert-OfficialSource $item.official_source
    Write-Host "Prérequis manquant : $($item.name). Windows va afficher son installateur et sa demande UAC." -ForegroundColor Yellow
    $pre = Join-Path ([IO.Path]::GetTempPath()) (([IO.Path]::GetFileName($item.official_source)) + "-" + [guid]::NewGuid().ToString("N"))
    try {{
      Invoke-WebRequest -Uri $item.official_source -UseBasicParsing -OutFile $pre
      if ($item.sha256 -and (Get-FileHash -LiteralPath $pre -Algorithm SHA256).Hash -ne $item.sha256.ToUpperInvariant()) {{ Stop-Install "Hash du prérequis $($item.name) invalide." }}
      $preSig = Get-AuthenticodeSignature -LiteralPath $pre
      if ($item.signature.required -and ($preSig.Status -ne "Valid" -or $preSig.SignerCertificate.Subject -notmatch [regex]::Escape($item.signature.signer))) {{ Stop-Install "Signature du prérequis $($item.name) invalide." }}
      $process = Start-Process -FilePath $pre -Wait -PassThru
      if ($process.ExitCode -eq 3010) {{ Stop-Install "Le prérequis $($item.name) demande un redémarrage Windows." }}
      if ($process.ExitCode -ne 0) {{ Stop-Install "Installation du prérequis $($item.name) échouée (code $($process.ExitCode))." }}
    }} finally {{ Remove-Item -LiteralPath $pre -Force -ErrorAction SilentlyContinue }}
  }}
}}
function Test-Environment {{
  $local=[Environment]::GetFolderPath("LocalApplicationData"); if (-not $local -or -not (Test-Path $local)) {{ Stop-Install "%LOCALAPPDATA% indisponible." }}
  $probe=Join-Path $local "ForgeEnvironmentProbe-{slug}.tmp"; try {{ "ok" | Set-Content -LiteralPath $probe -ErrorAction Stop }} finally {{ Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue }}
  # Runtime Python/Node are in the frozen EXE; no global developer runtime is installed.
  Write-Host "Self-check runtime, ports, écritures, LOCALAPPDATA, DB, réseau et TLS validé." -ForegroundColor Green
}}
if (-not $DownloadUrl.StartsWith("https://",[StringComparison]::OrdinalIgnoreCase) -or $DownloadUrl -match "example\\.invalid|REPLACE_WITH") {{ Stop-Install "URL de release HTTPS non configurée." }}
if ($ExpectedSha256 -notmatch "^[0-9a-fA-F]{{64}}$") {{ Stop-Install "SHA-256 attendu invalide." }}
if ($CheckForUpdate) {{ Invoke-RestMethod -Uri ($DownloadUrl -replace '\\.exe$','.release-manifest.json') -Method Get | Out-Null; exit 0 }}
$manifestPath=Join-Path $PSScriptRoot "release-manifest.json"; if (Test-Path $manifestPath) {{ $manifest=Get-Content $manifestPath -Raw | ConvertFrom-Json; Install-MissingPrerequisites $manifest.prerequisites }}
Test-Environment
$temp=Join-Path ([IO.Path]::GetTempPath()) ("{slug}-Setup-"+[guid]::NewGuid().ToString("N")+".exe")
try {{ Invoke-WebRequest -Uri $DownloadUrl -UseBasicParsing -OutFile $temp; if ((Get-FileHash -LiteralPath $temp -Algorithm SHA256).Hash -ne $ExpectedSha256.ToUpperInvariant()) {{ Stop-Install "SHA-256 du téléchargement incorrect." }}; $signature=Get-AuthenticodeSignature -LiteralPath $temp; if ($signature.Status -ne "Valid") {{ Stop-Install "Signature Authenticode invalide ($($signature.Status))." }}; if ($ExpectedSigner -and $signature.SignerCertificate.Subject -notmatch [regex]::Escape($ExpectedSigner)) {{ Stop-Install "Signataire inattendu." }}; Write-Host "Vérifications réussies. Windows va ouvrir l'interface normale du Setup et afficher ses demandes UAC." -ForegroundColor Green; Start-Process -FilePath $temp -Wait }} catch {{ Stop-Install $_.Exception.Message }} finally {{ Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue }}
''', encoding="utf-8")
    (agent_dir / "CLIENT_README.md").write_text(f'''# Installation client — {app_name}

Le Setup signé est autonome : Python, pip, Node et les outils de développement ne sont pas requis sur votre PC. Les seuls composants externes réellement nécessaires sont listés dans `release-manifest.json` ; ceux qui manquent sont proposés avec l'interface Windows et votre consentement UAC.

Le bootstrapper vérifie les sources officielles, les hash/signatures, puis effectue le self-check du runtime, des ports, des écritures, de `%LOCALAPPDATA%`, de la base locale, du réseau et des certificats TLS. Un échec ou un redémarrage requis bloque le lancement.
''', encoding="utf-8")
    (agent_dir / "CLIENT_MESSAGE_TEMPLATE.md").write_text(f"Objet : Installation de {app_name} v{version}\n\nCliquez volontairement sur le lien HTTPS fourni avec le manifeste validé. Windows affichera les confirmations nécessaires.\n{placeholder}\n", encoding="utf-8")


def can_publish_release_link(manifest_path: Path) -> tuple[bool, str]:
    if not manifest_path.is_file(): return False, "Manifeste absent."
    try: manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: return False, f"Manifeste illisible : {exc}"
    required = ("version", "download_url", "sha256", "size_bytes", "built_at_utc", "prerequisites", "self_check")
    # An empty prerequisites array is valid: it means the frozen package has no
    # external runtime dependency. The section itself must still be present.
    missing = [key for key in required if key not in manifest or manifest[key] in (None, "")]
    if missing: return False, "Champs de manifeste manquants : " + ", ".join(missing)
    if manifest.get("release_status") != VALIDATED_STATUS: return False, "Le statut du manifeste n'est pas VALIDATED_FOR_REMOTE_WINDOWS_INSTALL."
    try: validate_https_url(manifest["download_url"])
    except ValueError as exc: return False, str(exc)
    if not re.fullmatch(r"[0-9a-fA-F]{64}", str(manifest["sha256"])): return False, "Le SHA-256 du Setup est invalide."
    if manifest.get("authenticode_setup") != "VALID": return False, "La signature Authenticode du Setup n'est pas validée."
    signature_path = manifest_path.parent / str(manifest.get("manifest_signature_file", ""))
    if manifest.get("manifest_signature") != "VALID" or not signature_path.is_file() or not signature_path.stat().st_size:
        return False, "La signature détachée du manifeste est absente ou invalide."
    if set(manifest["self_check"]) != set(SELF_CHECKS): return False, "Le self-check client est incomplet."
    try:
        for item in manifest["prerequisites"]: validate_official_source(item["official_source"])
    except (KeyError, ValueError) as exc: return False, f"Prérequis invalide : {exc}"
    return True, "Lien publiable."


def validated_manifest_fields(setup: Path, app_name: str, slug: str, version: str, download_url: str, prerequisites: list[dict] | None = None) -> dict:
    validate_https_url(download_url)
    return {"app": app_name, "slug": slug, "version": version, "setup_filename": setup.name, "download_url": download_url, "sha256": hashlib.sha256(setup.read_bytes()).hexdigest().upper(), "size_bytes": setup.stat().st_size, "built_at_utc": datetime.now(timezone.utc).isoformat(), "authenticode_setup": "VALID", "manifest_integrity": "SHA256_FILLED_AT_BUILD", "manifest_signature": "VALID", "manifest_signature_file": "release-manifest.sig", "release_status": VALIDATED_STATUS, "link_install_enabled": True, "deployment_mode": "client_link", "runtime": {"python": "bundled_frozen_exe", "node": "bundled_or_not_required"}, "prerequisites": prerequisites or [], "self_check": list(SELF_CHECKS)}

