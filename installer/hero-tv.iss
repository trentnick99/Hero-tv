; HERO TV - Windows installer (built automatically on GitHub, see .github/workflows/windows.yml).
; Installs for the current user only (no administrator rights needed) into %LOCALAPPDATA%\Programs\HERO TV,
; so HERO TV can keep updating itself and you can still edit its config files. Your videos, favorites, resume points
; and settings live elsewhere (%LOCALAPPDATA%\HeroTV and your media folder) and are never touched by this installer.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\package\HERO TV"
#endif

[Setup]
AppId={{8B7C5E2A-4F1D-4C3B-9E7A-5A1B2C3D4E5F}
AppName=HERO TV
AppVersion={#AppVersion}
AppVerName=HERO TV {#AppVersion}
AppPublisher=HERO TV
DefaultDirName={localappdata}\Programs\HERO TV
DefaultGroupName=HERO TV
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64ModeOnly=x64compatible
OutputDir=..\installer-out
OutputBaseFilename=HERO-TV-Setup-v{#AppVersion}
SetupIconFile=..\assets\hero-tv.ico
UninstallDisplayIcon={app}\HERO-TV.exe
UninstallDisplayName=HERO TV
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Put a HERO TV icon on the desktop"; GroupDescription: "Shortcuts:"

[Files]
; Everything except your own settings files...
Source: "{#SourceDir}\*"; DestDir: "{app}"; Excludes: "config\channels.json,config\auto-sort.json,config\checklist.json,config\free-sources.json,data\*.sqlite3*"; Flags: ignoreversion recursesubdirs createallsubdirs
; ...which are only put in place the first time, and are kept if you uninstall (your channels and keywords).
Source: "{#SourceDir}\config\channels.json"; DestDir: "{app}\config"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#SourceDir}\config\auto-sort.json"; DestDir: "{app}\config"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#SourceDir}\config\checklist.json"; DestDir: "{app}\config"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#SourceDir}\config\free-sources.json"; DestDir: "{app}\config"; Flags: onlyifdoesntexist uninsneveruninstall

[Icons]
Name: "{group}\HERO TV"; Filename: "{app}\HERO-TV.exe"; Parameters: "launch --quiet"; WorkingDir: "{app}"; Comment: "Your own TV network"
Name: "{group}\HERO TV tools folder"; Filename: "{app}"; Comment: "Update, backup and other helpers"
Name: "{group}\Uninstall HERO TV"; Filename: "{uninstallexe}"
Name: "{userdesktop}\HERO TV"; Filename: "{app}\HERO-TV.exe"; Parameters: "launch --quiet"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\HERO-TV.exe"; Parameters: "launch --quiet"; Description: "Start HERO TV now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Close a running HERO TV before its files are removed.
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM HERO-TV.exe"; Flags: runhidden; RunOnceId: "StopHeroTV"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.update-stage"
Type: filesandordirs; Name: "{app}\.update-backup"
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{app}\app-build.txt"
