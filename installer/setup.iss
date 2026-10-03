; Inno Setup recipe of dist\FL-Studio-Better-Presence-Setup.exe, the installer of the app that PyInstaller builds
; in dist\FL-Studio-Better-Presence\. build.bat runs both.
;
; It installs the app for the current user, without administrator rights, in %LOCALAPPDATA%\Programs, adds it to
; the Start menu and to Windows' list of installed apps, then starts it. Run again, it updates the app: the app
; quits first so its files can be replaced, and its settings are kept. The pictures come from
; tools\installer_images.py.

#define AppName "FL Studio Better Presence"
#define FileName "FL-Studio-Better-Presence"
#define AppExe FileName + ".exe"
#define Built SourcePath + "..\dist\" + FileName
#define AppVersion GetStringFileInfo(Built + "\" + AppExe, "ProductVersion")
#define Repository "https://github.com/TheUnknownMurda/FL-Studio-Better-Presence"
#if AppVersion == ""
  #error The app isn't built: run PyInstaller first, or build.bat
#endif
; Where the app asks Windows to start it at sign-in (src\flbp\startup.py), and keeps its settings
; (src\flbp\settings.py). Tests compile the installer with others, given to ISCC with /D.
#ifndef WindowsKey
  #define WindowsKey "Software\Microsoft\Windows\CurrentVersion"
#endif
#ifndef SettingsFolder
  #define SettingsFolder "{userappdata}\" + AppName
#endif

[Setup]
; Tells Windows it's the same app from one version to the next: never change it
AppId={{CB45EBF7-719E-44CB-AEB9-DA90E2C74952}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=TheUnknownMurda
AppPublisherURL=https://github.com/TheUnknownMurda
AppSupportURL={#Repository}/issues
AppUpdatesURL={#Repository}/releases/latest
AppCopyright=TheUnknownMurda
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName} Setup
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#AppName}
; Two pages: Install, then Finish
DisableWelcomePage=no
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
ShowLanguageDialog=no
WizardStyle=modern dynamic
WizardImageFile=wizard-*.png
WizardSmallImageFile=small-*.png
; Or Windows in dark mode would show Inno Setup's own pictures
WizardImageFileDynamicDark=wizard-*.png
WizardSmallImageFileDynamicDark=small-*.png
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
; Setup starts the app itself at the end
RestartApplications=no
; In the temporary folder, to understand a problem a user tells about
SetupLogging=yes
OutputDir=..\dist
OutputBaseFilename={#FileName}-Setup
Compression=lzma2/max
SolidCompression=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "ptbr"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "pt"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "nl"; MessagesFile: "compiler:Languages\Dutch.isl"
Name: "pl"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Messages]
; What the app does, on the first page, rather than "close all other applications"
WelcomeLabel2=This will install [name/ver] on your computer.%n%nYour Discord status will show your friends what you're making in FL Studio.
fr.WelcomeLabel2=Cet assistant va vous guider dans l'installation de [name/ver] sur votre ordinateur.%n%nVotre statut Discord montrera à vos amis ce que vous créez dans FL Studio.
de.WelcomeLabel2=Dieser Assistent wird jetzt [name/ver] auf Ihrem Computer installieren.%n%nIhr Discord-Status zeigt Ihren Freunden dann, woran Sie in FL Studio arbeiten.
es.WelcomeLabel2=Este programa instalará [name/ver] en su sistema.%n%nSu estado de Discord mostrará a sus amigos lo que está creando en FL Studio.
it.WelcomeLabel2=[name/ver] sarà installato sul computer.%n%nIl tuo stato su Discord mostrerà ai tuoi amici a cosa stai lavorando in FL Studio.
ptbr.WelcomeLabel2=Isto instalará o [name/ver] no seu computador.%n%nSeu status do Discord mostrará aos seus amigos o que você está criando no FL Studio.
pt.WelcomeLabel2=O Assistente de Instalação irá instalar o [name/ver] no seu computador.%n%nO seu estado do Discord mostrará aos seus amigos o que está a criar no FL Studio.
nl.WelcomeLabel2=Hiermee wordt [name/ver] geïnstalleerd op deze computer.%n%nUw Discord-status laat uw vrienden zien waar u in FL Studio aan werkt.
pl.WelcomeLabel2=Aplikacja [name/ver] zostanie teraz zainstalowana na komputerze.%n%nTwój status na Discordzie pokaże znajomym, nad czym pracujesz w FL Studio.
ru.WelcomeLabel2=Программа установит [name/ver] на ваш компьютер.%n%nВаш статус в Discord покажет друзьям, над чем вы работаете в FL Studio.
; What happens next, on the last page, rather than "launch it from its shortcuts" (or, in French, from the desktop)
FinishedLabel=[name] is installed.%n%nIt runs next to the clock and starts with Windows: open FL Studio, and your Discord status shows what you're making. To change its settings, open it from the Start menu.
fr.FinishedLabel=[name] est installé.%n%nIl fonctionne à côté de l'horloge et démarre avec Windows : ouvrez FL Studio, et votre statut Discord montre ce que vous créez. Pour changer ses réglages, ouvrez-le depuis le menu Démarrer.
de.FinishedLabel=[name] ist installiert.%n%nEs läuft neben der Uhr und startet mit Windows: Öffnen Sie FL Studio, und Ihr Discord-Status zeigt, woran Sie arbeiten. Um die Einstellungen zu ändern, öffnen Sie es über das Startmenü.
es.FinishedLabel=[name] está instalado.%n%nSe ejecuta junto al reloj y se inicia con Windows: abra FL Studio y su estado de Discord mostrará lo que está creando. Para cambiar su configuración, ábralo desde el menú Inicio.
it.FinishedLabel=[name] è installato.%n%nFunziona accanto all'orologio e si avvia con Windows: apri FL Studio e il tuo stato su Discord mostrerà a cosa stai lavorando. Per cambiarne le impostazioni, aprilo dal menu Start.
ptbr.FinishedLabel=O [name] foi instalado.%n%nEle fica ao lado do relógio e inicia com o Windows: abra o FL Studio e seu status do Discord mostrará o que você está criando. Para alterar as configurações, abra-o pelo menu Iniciar.
pt.FinishedLabel=O [name] foi instalado.%n%nFunciona junto ao relógio e inicia com o Windows: abra o FL Studio e o seu estado do Discord mostrará o que está a criar. Para alterar as definições, abra-o a partir do menu Iniciar.
nl.FinishedLabel=[name] is geïnstalleerd.%n%nHet draait naast de klok en start met Windows: open FL Studio en uw Discord-status toont waar u aan werkt. Open het via het menu Start om de instellingen te wijzigen.
pl.FinishedLabel=Aplikacja [name] została zainstalowana.%n%nDziała obok zegara i uruchamia się razem z systemem Windows: otwórz FL Studio, a Twój status na Discordzie pokaże, nad czym pracujesz. Aby zmienić ustawienia, otwórz ją z menu Start.
ru.FinishedLabel=[name] установлен.%n%nПриложение работает рядом с часами и запускается вместе с Windows: откройте FL Studio, и ваш статус в Discord покажет, над чем вы работаете. Чтобы изменить настройки, откройте его из меню «Пуск».

[CustomMessages]
DeleteSettings=Also delete your settings and statistics?%n%nKeep them if you might install the app again.
fr.DeleteSettings=Supprimer aussi vos réglages et vos statistiques ?%n%nGardez-les si vous pensez réinstaller l'application.
de.DeleteSettings=Auch Ihre Einstellungen und Statistiken löschen?%n%nBehalten Sie sie, falls Sie die App erneut installieren möchten.
es.DeleteSettings=¿Eliminar también su configuración y sus estadísticas?%n%nConsérvelas si piensa volver a instalar la aplicación.
it.DeleteSettings=Eliminare anche le impostazioni e le statistiche?%n%nConservale se pensi di reinstallare l'app.
ptbr.DeleteSettings=Excluir também suas configurações e estatísticas?%n%nMantenha-as se pretende instalar o aplicativo novamente.
pt.DeleteSettings=Eliminar também as suas definições e estatísticas?%n%nMantenha-as se pretende instalar a aplicação novamente.
nl.DeleteSettings=Ook uw instellingen en statistieken verwijderen?%n%nBewaar ze als u de app later opnieuw wilt installeren.
pl.DeleteSettings=Usunąć również ustawienia i statystyki?%n%nZachowaj je, jeśli zamierzasz ponownie zainstalować aplikację.
ru.DeleteSettings=Удалить также ваши настройки и статистику?%n%nСохраните их, если планируете снова установить приложение.

[InstallDelete]
; What an older version installed, which this one may not have anymore
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#Built}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; With the app's own identity, so Windows shows its name and icon in its notifications
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "Shows what you're making in FL Studio in your Discord status"; AppUserModelID: "TheUnknownMurda.FLStudioBetterPresence"

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; The app quits first, so its files can be removed
Filename: "{app}\{#AppExe}"; Parameters: "--quit"; Flags: runhidden waituntilterminated; RunOnceId: "QuitApp"

[Code]
const
  RunKey = '{#WindowsKey}\Run';
  ApprovedKey = '{#WindowsKey}\Explorer\StartupApproved\Run';

function AppCommand(): String;
begin
  Result := '"' + ExpandConstant('{app}\{#AppExe}') + '" --background';
end;

// The first page installs: its button and text say so, rather than "Next"
procedure CurPageChanged(CurPageID: Integer);
var
  Text: String;
begin
  if CurPageID = wpWelcome then
  begin
    WizardForm.NextButton.Caption := SetupMessage(msgButtonInstall);
    Text := WizardForm.WelcomeLabel2.Caption;
    // "Click Install to continue with the installation", from the page this one replaces
    StringChangeEx(Text, SetupMessage(msgClickNext), SetupMessage(msgReadyLabel2b), True);
    WizardForm.WelcomeLabel2.Caption := Text;
  end;
end;

// Before an update: the app quits, so its files can be replaced. Setup starts it again at the end.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  if FileExists(ExpandConstant('{app}\{#AppExe}')) then
    Exec(ExpandConstant('{app}\{#AppExe}'), '--quit', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  // When Windows starts the app at sign-in, it now starts this one, even if it started an older copy from elsewhere
  if (CurStep = ssPostInstall) and RegValueExists(HKCU, RunKey, '{#AppName}') then
    RegWriteStringValue(HKCU, RunKey, '{#AppName}', AppCommand());
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Command, Folder: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    // Windows stops starting the app at sign-in, unless it starts a copy of it from another folder
    if RegQueryStringValue(HKCU, RunKey, '{#AppName}', Command) and
       (Pos(Lowercase(ExpandConstant('{app}\')), Lowercase(Command)) > 0) then
    begin
      RegDeleteValue(HKCU, RunKey, '{#AppName}');
      RegDeleteValue(HKCU, ApprovedKey, '{#AppName}');
    end;
  end
  else if CurUninstallStep = usPostUninstall then
  begin
    Folder := ExpandConstant('{#SettingsFolder}');
    if DirExists(Folder) and (SuppressibleMsgBox(CustomMessage('DeleteSettings'), mbConfirmation,
                                                 MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES) then
      DelTree(Folder, True, True, True);
  end;
end;
