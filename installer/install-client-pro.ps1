param(
  [string]$InstallerPath = "Forge_Installer.exe",
  [string]$InstallDir = "C:\Program Files\Forge",
  [switch]$Quiet
)

# Resolve installer path relative to script
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$installer = if (Test-Path $InstallerPath) { Resolve-Path $InstallerPath } elseif (Test-Path (Join-Path $scriptDir $InstallerPath)) { Resolve-Path (Join-Path $scriptDir $InstallerPath) } else { Write-Error "Installer not found: $InstallerPath"; exit 2 }

$flags = "/VERYSILENT /NORESTART"
if ($Quiet) { $flags = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART" }

Write-Host "Running installer: $installer"
Start-Process -FilePath $installer -ArgumentList $flags -Wait -NoNewWindow

# Optionally verify installed file exists
$exe = Join-Path -Path $InstallDir -ChildPath "Forge.exe"
if (Test-Path $exe) { Write-Host "Installed to $exe"; exit 0 } else { Write-Error "Installation seems to have failed; $exe not found"; exit 3 }
