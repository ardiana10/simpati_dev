[Setup]
AppName=SIMPATI
AppVersion=1.1
DefaultDirName={autopf}\SIMPATI
DefaultGroupName=SIMPATI

OutputDir=dist\installer
OutputBaseFilename=SIMPATI_Setup

Compression=lzma2
SolidCompression=yes

SetupIconFile=icons\iconKPU.ico
WizardImageFile=icons\installer_banner.bmp
WizardSmallImageFile=icons\installer_logo.bmp

UninstallDisplayIcon={app}\SIMPATI.exe
PrivilegesRequired=admin

[Files]
Source: "dist\SIMPATI\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\SIMPATI"; Filename: "{app}\SIMPATI.exe"
Name: "{commondesktop}\SIMPATI"; Filename: "{app}\SIMPATI.exe"

[Run]
Filename: "{app}\SIMPATI.exe"; Description: "Jalankan SIMPATI"; Flags: nowait postinstall skipifsilent