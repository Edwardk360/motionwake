[Setup]
AppName=MotionWake
AppVersion={#AppVersion}
AppPublisher=Edwardk360
DefaultDirName={autopf}\MotionWake
DefaultGroupName=MotionWake
OutputBaseFilename=MotionWake_Setup_v{#AppVersion}
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayName=MotionWake
UninstallDisplayIcon={app}\motionwake.exe
WizardStyle=modern

[Types]
Name: "full";        Description: "Volledige installatie (inclusief configuratiebestanden)"
Name: "softwareonly"; Description: "Alleen software (zonder configuratiebestanden)"

[Components]
Name: "main";   Description: "MotionWake applicatie"; Types: full softwareonly; Flags: fixed
Name: "config"; Description: "Standaard configuratiebestand";  Types: full

[Files]
Source: "..\dist\motionwake\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs; Components: main
Source: "..\assets\icon.ico";   DestDir: "{app}"; Flags: ignoreversion; Components: main

[Dirs]
Name: "{app}\logs"; Permissions: everyone-modify

[Icons]
Name: "{group}\MotionWake";           Filename: "{app}\motionwake.exe"; IconFilename: "{app}\icon.ico"
Name: "{group}\Verwijder MotionWake"; Filename: "{uninstallexe}"
Name: "{userstartup}\MotionWake";     Filename: "{app}\motionwake.exe"; Parameters: "--tray"; IconFilename: "{app}\icon.ico"

[Run]
Filename: "{app}\motionwake.exe"; Parameters: "--install"; Flags: runhidden; StatusMsg: "Service installeren..."
Filename: "{app}\motionwake.exe"; Parameters: "--tray";    Flags: nowait postinstall skipifsilent; Description: "MotionWake starten"

[UninstallRun]
Filename: "{app}\motionwake.exe"; Parameters: "--uninstall"; Flags: runhidden

[InstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then begin
    // Verwijder oude installatie bestanden voor nieuwe installatie
    DelTree(ExpandConstant('{app}'), True, True, True);
  end;
end;
