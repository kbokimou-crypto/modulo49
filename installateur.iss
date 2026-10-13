; Script Inno Setup : crée Modulo49-Setup.exe à partir de dist\Modulo49
[Setup]
AppName=Modulo49
AppVersion=1.3
AppPublisher=Modulo49
DefaultDirName={autopf}\Modulo49
DefaultGroupName=Modulo49
OutputDir=installateur
OutputBaseFilename=Modulo49-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer une icône sur le Bureau"; GroupDescription: "Raccourcis :"

[Files]
Source: "dist\Modulo49\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\Modulo49"; Filename: "{app}\Modulo49.exe"
Name: "{group}\Désinstaller Modulo49"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Modulo49"; Filename: "{app}\Modulo49.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Modulo49.exe"; Description: "Lancer Modulo49"; Flags: nowait postinstall skipifsilent
