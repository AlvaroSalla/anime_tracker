; Inno Setup Script para AnimeTracker v1.0.1
; Requisito: Inno Setup 6+ (https://jrsoftware.org/isdl.php)
;
; Instrucciones:
;   1. pip install pyinstaller
;   2. pyinstaller anime_tracker.spec
;   3. Abrir este .iss en Inno Setup Compiler
;   4. Build > Compile
;
; Update limpia de v1.0.0 → v1.0.1 sin borrar datos del usuario.

#define MyAppName "AnimeTracker"
#define MyAppVersion "1.0.1"
#define MyAppExeName "AnimeTracker v1.0.1.exe"

[Setup]
AppId={{B8A3C8E1-4F2D-4A6E-9C7D-1F5E2D8A3B4C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppName}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=.
OutputBaseFilename=AnimeTrackerV1.0.1
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
UninstallDisplayIcon={app}\icon.ico
UninstallDisplayName={#MyAppName} v{#MyAppVersion}
SetupIconFile=icon.ico
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "dist\AnimeTracker v1.0.1\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\AnimeTracker v1.0.1"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\AnimeTracker v1.0.1"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[UninstallDelete]
Type: files; Name: "{app}\*.log"
Type: files; Name: "{app}\animes_api.db"
Type: dirifempty; Name: "{app}"

[Code]
function InitializeSetup: Boolean;
begin
  Result := True;
end;

procedure InitializeWizard;
begin
  WizardForm.PageDescriptionLabel.Caption := 'Asistente de instalacion de AnimeTracker v1.0.1';
end;
