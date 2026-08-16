from __future__ import annotations

from pathlib import Path


def write_windows_release_files(agent_dir: Path, app_name: str, slug: str, version: str) -> None:
    """Generate a fail-closed Windows client release pipeline for a generated agent."""

    (agent_dir / "requirements-release.txt").write_text(
        "pyinstaller>=6.10.0\npytest>=8.0.0\n",
        encoding="utf-8",
    )

    installer = f'''#define MyAppName "{app_name}"
#define MyAppVersion "{version}"
#define MyAppPublisher "FEWURA"
#define MyAppExeName "{slug}.exe"

[Setup]
AppId={{{{{slug}-fewura-agent}}}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
DefaultDirName={{localappdata}}\\Programs\\{{#MyAppName}}
DefaultGroupName={{#MyAppName}}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=release
OutputBaseFilename={slug}-Setup-{version}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={{app}}\\{{#MyAppExeName}}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "dist\\{slug}.exe"; DestDir: "{{app}}"; Flags: ignoreversion

[Icons]
Name: "{{autoprograms}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"
Name: "{{autodesktop}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked

[Run]
Filename: "{{app}}\\{{#MyAppExeName}}"; Description: "Lancer {{#MyAppName}}"; Flags: nowait postinstall skipifsilent
'''
    (agent_dir / "installer.iss").write_text(installer, encoding="utf-8")

    powershell = f'''$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$AppName = "{app_name}"
$Slug = "{slug}"
$Version = "{version}"
$Python = Join-Path $Root ".venv\\Scripts\\python.exe"
$Exe = Join-Path $Root "dist\\$Slug.exe"
$ReleaseDir = Join-Path $Root "release"
$Setup = Join-Path $ReleaseDir "$Slug-Setup-$Version.exe"

function Fail([string]$Message) {{
    Write-Host "RELEASE BLOQUEE: $Message" -ForegroundColor Red
    exit 1
}}

function Find-SignTool {{
    if ($env:SIGNTOOL_PATH -and (Test-Path $env:SIGNTOOL_PATH)) {{ return $env:SIGNTOOL_PATH }}
    $kits = Get-ChildItem "${{env:ProgramFiles(x86)}}\\Windows Kits\\10\\bin" -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
        Where-Object {{ $_.FullName -match '\\x64\\signtool.exe$' }} |
        Sort-Object FullName -Descending
    if ($kits) {{ return $kits[0].FullName }}
    Fail "signtool.exe introuvable. Installez le Windows SDK ou définissez SIGNTOOL_PATH."
}}

function Find-InnoCompiler {{
    if ($env:ISCC_PATH -and (Test-Path $env:ISCC_PATH)) {{ return $env:ISCC_PATH }}
    $candidates = @(
        "$env:ProgramFiles\\Inno Setup 6\\ISCC.exe",
        "${{env:ProgramFiles(x86)}}\\Inno Setup 6\\ISCC.exe"
    )
    foreach ($candidate in $candidates) {{ if (Test-Path $candidate) {{ return $candidate }} }}
    Fail "Inno Setup 6 introuvable. Installez-le ou définissez ISCC_PATH."
}}

function Sign-File([string]$Path) {{
    $SignTool = Find-SignTool
    if ($env:CODE_SIGN_CERT_SHA1) {{
        & $SignTool sign /sha1 $env:CODE_SIGN_CERT_SHA1 /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $Path
    }} elseif ($env:CODE_SIGN_PFX_PATH) {{
        if (-not (Test-Path $env:CODE_SIGN_PFX_PATH)) {{ Fail "CODE_SIGN_PFX_PATH ne pointe vers aucun fichier." }}
        if (-not $env:CODE_SIGN_PFX_PASSWORD) {{ Fail "CODE_SIGN_PFX_PASSWORD manque." }}
        & $SignTool sign /f $env:CODE_SIGN_PFX_PATH /p $env:CODE_SIGN_PFX_PASSWORD /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 $Path
    }} else {{
        Fail "Aucun certificat de signature. Définissez CODE_SIGN_CERT_SHA1 ou CODE_SIGN_PFX_PATH."
    }}
    if ($LASTEXITCODE -ne 0) {{ Fail "Échec de signature: $Path" }}
}}

function Verify-Signature([string]$Path) {{
    $sig = Get-AuthenticodeSignature -FilePath $Path
    if ($sig.Status -ne "Valid") {{ Fail "Signature Authenticode invalide pour $Path (status=$($sig.Status))." }}
}}

Write-Host "[1/10] Préparation d'un environnement de build propre..."
Remove-Item -Recurse -Force build, dist, release -ErrorAction SilentlyContinue
if (Test-Path ".venv") {{ Remove-Item -Recurse -Force ".venv" }}
py -3 -m venv .venv
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt -r requirements-release.txt
if ($LASTEXITCODE -ne 0) {{ Fail "Installation des dépendances impossible." }}

Write-Host "[2/10] Compilation et tests source complets..."
$testFiles = @(Get-ChildItem -Path $Root -Recurse -File -Include 'test_*.py','*_test.py' | Where-Object {{ $_.FullName -notmatch '\\(.venv|build|dist|release)\\' }})
if ($testFiles.Count -eq 0) {{ Fail "Aucun test automatisé trouvé. FORGE interdit une release client sans tests." }}
& $Python -m compileall -q agent.py
if ($LASTEXITCODE -ne 0) {{ Fail "Compilation Python source échouée." }}
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) {{ Fail "Au moins un test source ou métier échoue." }}

Write-Host "[3/10] Self-test de la version source..."
& $Python agent.py --self-test
if ($LASTEXITCODE -ne 0) {{ Fail "Le self-test source a échoué." }}

Write-Host "[4/10] Construction du vrai EXE Windows..."
& $Python -m PyInstaller --noconfirm --clean --onefile --name $Slug agent.py
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Exe)) {{ Fail "PyInstaller n'a pas produit l'EXE." }}

Write-Host "[5/10] Test du vrai EXE compilé..."
& $Exe --self-test
if ($LASTEXITCODE -ne 0) {{ Fail "Le vrai EXE a échoué au self-test." }}

Write-Host "[6/10] Signature et vérification de l'EXE..."
Sign-File $Exe
Verify-Signature $Exe

Write-Host "[7/10] Construction du Setup Inno Setup..."
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
$ISCC = Find-InnoCompiler
& $ISCC "installer.iss"
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $Setup)) {{ Fail "Le Setup n'a pas été construit." }}

Write-Host "[8/10] Signature et vérification du Setup..."
Sign-File $Setup
Verify-Signature $Setup

Write-Host "[9/10] Installation réelle dans un répertoire Windows vierge..."
$TestDir = Join-Path $env:TEMP ("FewuraReleaseTest-" + [guid]::NewGuid().ToString("N"))
if (Test-Path $TestDir) {{ Remove-Item -Recurse -Force $TestDir }}
New-Item -ItemType Directory -Force -Path $TestDir | Out-Null
& $Setup /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR="$TestDir"
if ($LASTEXITCODE -ne 0) {{ Fail "Installation silencieuse de test échouée." }}
$InstalledExe = Join-Path $TestDir "$Slug.exe"
if (-not (Test-Path $InstalledExe)) {{ Fail "L'EXE installé est introuvable." }}
Verify-Signature $InstalledExe
& $InstalledExe --self-test
if ($LASTEXITCODE -ne 0) {{ Fail "L'application réellement installée a échoué au self-test." }}
$Uninstaller = Join-Path $TestDir "unins000.exe"
if (-not (Test-Path $Uninstaller)) {{ Fail "Désinstalleur absent : installation client incomplète." }}
& $Uninstaller /VERYSILENT /SUPPRESSMSGBOXES /NORESTART | Out-Null
Start-Sleep -Milliseconds 500
if (Test-Path $InstalledExe) {{ Fail "La désinstallation de test n'a pas retiré l'exécutable installé." }}
Remove-Item -Recurse -Force $TestDir -ErrorAction SilentlyContinue

Write-Host "[10/10] Validation finale et manifeste de preuve..."
Verify-Signature $Exe
Verify-Signature $Setup
$hash = Get-FileHash $Setup -Algorithm SHA256
$manifest = @{{
    app = $AppName
    version = $Version
    setup = [IO.Path]::GetFileName($Setup)
    sha256 = $hash.Hash
    built_at_utc = [DateTime]::UtcNow.ToString("o")
    source_tests = "PASSED"
    source_self_test = "PASSED"
    frozen_exe_test = "PASSED"
    authenticode_exe = "VALID"
    authenticode_setup = "VALID"
    clean_install_test = "PASSED"
    installed_app_test = "PASSED"
    uninstall_test = "PASSED"
    release_status = "VALIDATED_FOR_REMOTE_WINDOWS_INSTALL"
}} | ConvertTo-Json -Depth 3
$manifest | Set-Content -Encoding UTF8 (Join-Path $ReleaseDir "release-manifest.json")

Write-Host "RELEASE CLIENT VALIDEE POUR INSTALLATION DISTANTE: $Setup" -ForegroundColor Green
'''
    (agent_dir / "build_release.ps1").write_text(powershell, encoding="utf-8")

    (agent_dir / "build_release.bat").write_text(
        '@echo off\r\n'
        'cd /d "%~dp0"\r\n'
        'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_release.ps1"\r\n'
        'if errorlevel 1 (\r\n'
        '  echo.\r\n'
        '  echo RELEASE CLIENT BLOQUEE. Aucun installateur ne doit etre livre.\r\n'
        '  pause\r\n'
        '  exit /b 1\r\n'
        ')\r\n'
        'echo.\r\n'
        'echo Release client validee pour installation distante.\r\n'
        'pause\r\n',
        encoding="utf-8",
    )

    (agent_dir / "RELEASE_WINDOWS.md").write_text(
        f"""# Release Windows client — {app_name}\n\n"
        "Cette chaîne est **fail-closed** : aucun Setup client n'est validé tant que tous les tests source et métier, le self-test, le vrai EXE compilé, les signatures, l'installation Windows propre, le test de l'application installée et la désinstallation n'ont pas tous réussi.\n\n"
        "## Prérequis sur la machine de build\n"
        "- Windows 10/11 x64 ;\n"
        "- Python 3.11+ ;\n"
        "- Inno Setup 6 ;\n"
        "- Windows SDK (`signtool.exe`) ;\n"
        "- certificat de signature de code FEWURA accessible au processus de build.\n\n"
        "## Règle de livraison\n"
        "Seul un Setup accompagné de `release-manifest.json` avec `release_status=VALIDATED_FOR_REMOTE_WINDOWS_INSTALL` est livrable. Toute autre sortie est un build de développement ou QA et doit être refusée par FORGE.\n\n"
        "## PC client distant\n"
        "Le client installe uniquement le Setup signé. Python, pip, les scripts BAT et le code source ne sont pas requis sur le PC distant.\n""",
        encoding="utf-8",
    )
