#define MyAppName "Forge"
#define MyAppVersion GetEnv("ACTIONS_BUILD_VERSION")
#ifdef MyAppVersion
#else
  #define MyAppVersion "1.0.0"
#endif

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={pf}\\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputBaseFilename=Forge_Installer_{#MyAppVersion}
Compression=lzma
SolidCompression=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\\French.isl"

[Files]
Source: "{#GetCurrentDir()}\\dist\\Forge.exe"; DestDir: "{app}"; Flags: ignoreversion
; If there are data files, add them here, e.g.:
; Source: "{#GetCurrentDir()}\\dist\\data\\*"; DestDir: "{app}\\data"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\\{#MyAppName}"; Filename: "{app}\\Forge.exe"
Name: "{userdesktop}\\{#MyAppName}"; Filename: "{app}\\Forge.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\\Forge.exe"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
// No custom Pascal code needed for basic installer
