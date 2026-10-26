[Setup]
AppId={{__APP_ID__}
AppName=__GAME_NAME__
AppVersion=0.1.0
AppPublisher=Xbox Port MCP - adaptación personal
DefaultDirName={code:InstallFolder}
DefaultGroupName=__GAME_NAME__
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=build
OutputBaseFilename=Instalar
Compression=zip/1
SolidCompression=no
SetupIconFile=artwork\game.ico
UninstallDisplayIcon={app}\Game.ico
WizardStyle=modern light polar
WizardSizePercent=140,135
WizardImageFile=artwork\welcome.png
WizardSmallImageFile=artwork\header.png
DisableWelcomePage=no
DisableProgramGroupPage=yes
CloseApplications=yes
RestartApplications=no
CreateUninstallRegKey=ShouldRegister

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"

[Files]
Source: "payload\*"; Excludes: "settings.toml"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "payload\settings.toml"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "artwork\game.ico"; DestDir: "{app}"; DestName: "Game.ico"
Source: "artwork\slide-*.bmp"; Flags: dontcopy

[Icons]
Name: "{group}\__GAME_NAME__"; Filename: "{app}\__EXE_NAME__"; WorkingDir: "{app}"; IconFilename: "{app}\Game.ico"
Name: "{group}\Desinstalar"; Filename: "{uninstallexe}"
Name: "{userdesktop}\__GAME_NAME__"; Filename: "{app}\__EXE_NAME__"; WorkingDir: "{app}"; IconFilename: "{app}\Game.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\__EXE_NAME__"; WorkingDir: "{app}"; Description: "Iniciar el juego"; Flags: nowait postinstall skipifsilent

[Code]
var
  Art: TBitmapImage;
  Ready: Boolean;
  LastSlide: Integer;

function ShouldRegister: Boolean;
begin
  Result := ExpandConstant('{param:NoRegister|0}') <> '1';
end;

function InstallFolder(Param: String): String;
var
  Base: String;
begin
  Base := GetEnv('LOCALAPPDATA');
  if Base = '' then begin
    Base := GetEnv('USERPROFILE');
    if Base = '' then RaiseException('No se pudo localizar la carpeta del usuario.');
    Base := AddBackslash(Base) + 'AppData\Local';
  end;
  Result := AddBackslash(Base) + 'Programs\__GAME_NAME__';
end;

procedure InitializeWizard;
var
  Index: Integer;
begin
  Ready := False;
  LastSlide := 0;
  Art := TBitmapImage.Create(WizardForm);
  Art.Parent := WizardForm.InstallingPage;
  Art.Left := 0;
  Art.Top := WizardForm.ProgressGauge.Top + WizardForm.ProgressGauge.Height + ScaleY(18);
  Art.Width := WizardForm.InstallingPage.ClientWidth;
  Art.Height := WizardForm.InstallingPage.ClientHeight - Art.Top - ScaleY(20);
  Art.Stretch := True;
  for Index := 0 to 3 do ExtractTemporaryFile('slide-' + IntToStr(Index) + '.bmp');
  Art.Bitmap.LoadFromFile(ExpandConstant('{tmp}\slide-0.bmp'));
  Ready := True;
end;

procedure CurInstallProgressChanged(CurProgress, MaxProgress: Integer);
var
  Index: Integer;
begin
  if not Ready or (MaxProgress <= 0) then Exit;
  Index := Round((CurProgress / MaxProgress) * 3);
  if Index > 3 then Index := 3;
  if Index < 0 then Index := 0;
  if Index <> LastSlide then begin
    Art.Bitmap.LoadFromFile(ExpandConstant('{tmp}\slide-') + IntToStr(Index) + '.bmp');
    LastSlide := Index;
  end;
end;
