#define ProductName "Cricket Broadcast System"
#define ProductVersion "1.6.0-rc.3"
#define ProductExe "CricketBroadcastSystem.exe"
#ifndef ProductId
  #define ProductId "{{68A95CA1-D445-45D9-85AF-632D0411E3E4}"
#endif
#ifndef OutputName
  #define OutputName "CricketBroadcastSystem-Setup"
#endif

[Setup]
AppId={#ProductId}
AppName={#ProductName}
AppVersion={#ProductVersion}
AppVerName={#ProductName} {#ProductVersion} (test build)
AppPublisher=Cricket Broadcast System
AppPublisherURL=https://github.com/Jacky123213/Cricket-Broadcast-System
DefaultDirName={localappdata}\Programs\CricketBroadcastSystem
DefaultGroupName={#ProductName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.17763
OutputDir=..\dist
OutputBaseFilename={#OutputName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#ProductExe}
AppMutex=Local\CricketBroadcastSystem
CloseApplications=no
RestartApplications=no
SetupLogging=yes
VersionInfoVersion=1.6.0.3
VersionInfoProductVersion=1.6.0.3
VersionInfoProductTextVersion={#ProductVersion}
InfoBeforeFile=installer-info.txt
UninstallFilesDir={app}\uninstall

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
; Only the audited PyInstaller output, never the source app's private folders.
Source: "..\dist\CricketBroadcastSystem\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\.tools\MicrosoftEdgeWebview2Setup.exe"; Flags: dontcopy
Source: "..\INSTALLER_TEST_CHECKLIST.md"; DestDir: "{app}"
Source: "..\INSTALLER_README.md"; DestDir: "{app}"

[Icons]
Name: "{group}\{#ProductName}"; Filename: "{app}\{#ProductExe}"
Name: "{group}\Setup & connections"; Filename: "{app}\{#ProductExe}"; Parameters: "--setup"
Name: "{group}\Clean-PC test checklist"; Filename: "{app}\INSTALLER_TEST_CHECKLIST.md"
Name: "{group}\Uninstall {#ProductName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#ProductName}"; Filename: "{app}\{#ProductExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ProductExe}"; Description: "Open {#ProductName} and choose Host or Connect"; Flags: nowait postinstall skipifsilent

[Code]
var
  RuntimePage: TInputOptionWizardPage;

function RuntimeInstalled: Boolean;
var Version: String;
begin
  Result := (RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0')) or
            (RegQueryStringValue(HKLM32, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0'));
end;

procedure InitializeWizard;
begin
  RuntimePage := CreateInputOptionPage(wpSelectTasks, 'Desktop viewer prerequisite',
    'Microsoft Edge WebView2 Runtime',
    'If WebView2 is missing, the installer needs permission to download and install Microsoft''s shared, automatically updated desktop viewer. This does not install Python. Internet access is needed only if WebView2 is missing. The runtime will not be removed when you uninstall this app.', False, False);
  RuntimePage.Add('I approve installing Microsoft WebView2 if it is missing');
  RuntimePage.Values[0] := False;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = RuntimePage.ID) and RuntimeInstalled;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var Code: Integer;
begin
  Result := '';
  if CheckForMutexes('Local\CricketBroadcastSystem') then begin
    Result := 'Close Cricket Broadcast System before upgrading. Your saved files will not be changed.';
    exit;
  end;
  if RuntimeInstalled then exit;
  if not RuntimePage.Values[0] then begin
    Result := 'WebView2 is missing and installation was not approved. Go Back to approve it, install WebView2 yourself, or cancel. No runtime has been installed.';
    exit;
  end;
  ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
  if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, Code) then begin
    Result := 'Could not launch Microsoft WebView2 setup. Install its Runtime from Microsoft, then try again.';
    exit;
  end;
  if ((Code <> 0) and (Code <> 3010)) or not RuntimeInstalled then
    Result := 'WebView2 installation did not finish. Check internet access and install the Runtime from Microsoft before trying again.';
  NeedsRestart := Code = 3010;
end;

function InitializeUninstall: Boolean;
begin
  Result := not CheckForMutexes('Local\CricketBroadcastSystem');
  if not Result then
    SuppressibleMsgBox('Close Cricket Broadcast System before uninstalling. Your matches, certificates and recordings will be kept.', mbError, MB_OK, IDOK);
end;

// No UninstallDelete rules for AppData, certificates, recordings or WebView2.
