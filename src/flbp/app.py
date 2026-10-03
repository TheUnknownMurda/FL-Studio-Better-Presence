"""
The app: its icon next to the clock with its menu, and the settings window. It shows what you're making in
FL Studio in your Discord status, from when FL Studio opens until it closes.

    FL-Studio-Better-Presence.exe                 starts the app and opens its settings
    FL-Studio-Better-Presence.exe --background    starts it quietly, as at Windows sign-in
    FL-Studio-Better-Presence.exe --quit          quits the running app

Starting it again while it runs opens the settings of the running app.
"""
import ctypes
import getpass
import logging
import logging.handlers
import os
import sys

from PySide6 import QtCore, QtGui, QtNetwork, QtWidgets

from . import APP_NAME, __version__, startup
from .discord_ipc import Status
from .engine import Engine
from .settings import Settings, config_dir
from .ui import RESOURCES, drawing
from .ui.settings_window import SettingsWindow

log = logging.getLogger("flbp")

INSTANCE_NAME = f"FLStudioBetterPresence-{getpass.getuser()}"
ERROR_ALREADY_EXISTS = 183
ASFW_ANY = 0xFFFFFFFF


def describe(engine):
    """(badge, text): the color of the icon's badge, and what the first line of its menu says."""
    discord = engine.discord
    if engine.hidden == "closed":
        return "not_shown", "Waiting for FL Studio"
    if engine.hidden == "off":
        return "not_shown", "Status hidden"
    if engine.hidden == "away":
        return "not_shown", "Hidden while you're away"
    if discord.status == Status.REFUSED:
        return "problem", "Discord refused the app"
    if discord.status == Status.NO_DISCORD:
        return "problem", "Discord isn't open"
    if discord.status == Status.CONNECTED:
        return "shown", "Showing: " + ((engine.activity or {}).get("details") or "FL Studio")
    return "shown", "Connecting to Discord…"


class App(QtCore.QObject):

    def __init__(self, settings, engine=None, welcome=False):
        super().__init__()
        self.settings = settings
        self.engine = engine or Engine(settings)
        self.window = None
        self.welcome = welcome  # tells where the app went when its window first closes
        self._fruit = QtGui.QImage(str(RESOURCES / "fruit.png"))
        self._icons = {}
        self._shown = None  # the state the icon and the menu show
        self._logged = None  # the state last written to the log
        self._last_error = None

        self.tray = QtWidgets.QSystemTrayIcon()
        self.tray.activated.connect(self._activated)
        self.menu = QtWidgets.QMenu()
        self.status_action = self.menu.addAction("")
        self.status_action.setEnabled(False)
        self.menu.addSeparator()
        self.enabled_action = self.menu.addAction("Show my status")
        self.enabled_action.setCheckable(True)
        self.enabled_action.toggled.connect(lambda checked: self._change(enabled=checked))
        self.secret_action = self.menu.addAction("Secret mode")
        self.secret_action.setCheckable(True)
        self.secret_action.toggled.connect(lambda checked: self._change(secret=checked))
        self.menu.addSeparator()
        self.menu.addAction("Settings…").triggered.connect(self.show_settings)
        self.menu.addAction("Quit").triggered.connect(self.quit)
        self.tray.setContextMenu(self.menu)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        self.tick()
        self._sync_menu()
        self.tray.show()

    def tick(self):
        try:
            self.engine.tick()
            self._last_error = None
        except Exception as error:
            if repr(error) != self._last_error:  # written once, not every second
                self._last_error = repr(error)
                log.exception("Couldn't update the status")
        self._show_state()

    def _show_state(self):
        badge, text = describe(self.engine)
        # Written when the status or the connection changes, not at every change of window
        discord = self.engine.discord
        logged = badge, discord.status, discord.error
        if logged != self._logged:
            self._logged = logged
            log.info("%s%s", text, f" (Discord: {discord.error})" if discord.error else "")
        if (badge, text) != self._shown:
            if self._shown is None or badge != self._shown[0]:
                self.tray.setIcon(self._icon(badge))
            self._shown = badge, text
            self.status_action.setText(text)
            tooltip = f"{APP_NAME}\n{text}"
            self.tray.setToolTip(tooltip if len(tooltip) < 128 else tooltip[:126] + "…")

    def _icon(self, badge):
        if badge not in self._icons:
            self._icons[badge] = drawing.app_icon(self._fruit, drawing.BADGE_COLORS[badge])
        return self._icons[badge]

    def _activated(self, reason):
        if reason in (QtWidgets.QSystemTrayIcon.ActivationReason.Trigger,
                      QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_settings()

    def _change(self, **changes):
        """A change made from the menu."""
        if all(self.settings[key] == value for key, value in changes.items()):
            return
        self.settings.update(**changes)
        self.engine.refresh()
        if self.window is not None:
            self.window.load()
            self.window.refresh_preview()
        self._show_state()

    def _sync_menu(self):
        for action, key in ((self.enabled_action, "enabled"), (self.secret_action, "secret")):
            action.blockSignals(True)
            action.setChecked(self.settings[key])
            action.blockSignals(False)
        self._show_state()

    def show_settings(self):
        if self.window is None:
            self.window = SettingsWindow(self.settings, self.engine)
            self.window.setWindowIcon(self._icon("shown"))
            self.window.changed.connect(self._sync_menu)
            self.window.destroyed.connect(self._window_closed)
            self.window.show()
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def _window_closed(self, *args):
        self.window = None
        if self.welcome:
            self.welcome = False
            self.tray.showMessage(APP_NAME, "Still running here, next to the clock: your status follows FL Studio. "
                                            "Click the icon for the settings.", self._icon("shown"), 8000)

    def quit(self):
        if self.window is not None:
            self.window.close()
        self.timer.stop()
        self.tray.hide()
        self.engine.stop()  # removes the status from Discord at once
        log.info("Quit")
        QtWidgets.QApplication.quit()


class Instance(QtCore.QObject):
    """Makes sure only one copy of the app runs, and lets a second one ask it to open its settings."""

    message = QtCore.Signal(str)

    def __init__(self):
        super().__init__()
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        # Kept for as long as the app runs: Windows releases it when the app quits, even after a crash
        self._mutex = kernel32.CreateMutexW(None, False, "Local\\" + INSTANCE_NAME)
        self.first = ctypes.get_last_error() != ERROR_ALREADY_EXISTS
        self._server = None

    def listen(self):
        self._server = QtNetwork.QLocalServer(self)
        self._server.setSocketOptions(QtNetwork.QLocalServer.SocketOption.UserAccessOption)
        QtNetwork.QLocalServer.removeServer(INSTANCE_NAME)  # left behind by a crash
        self._server.listen(INSTANCE_NAME)
        self._server.newConnection.connect(self._receive)

    def _receive(self):
        socket = self._server.nextPendingConnection()
        if socket is None:
            return
        socket.waitForReadyRead(1000)
        self.message.emit(bytes(socket.readAll()).decode("utf-8", "replace"))
        socket.disconnectFromServer()

    @staticmethod
    def send(text):
        """Sends a message to the app that runs. True when it got it."""
        socket = QtNetwork.QLocalSocket()
        socket.connectToServer(INSTANCE_NAME)
        if not socket.waitForConnected(2000):
            return False
        # Lets the running app bring its window to the front, which Windows only allows the app in front
        ctypes.windll.user32.AllowSetForegroundWindow(ASFW_ANY)
        socket.write(text.encode("utf-8"))
        socket.waitForBytesWritten(1000)
        socket.disconnectFromServer()
        return True


def setup_logging():
    """A short log in the settings folder, to understand a problem a user tells about."""
    folder = config_dir()
    os.makedirs(folder, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(os.path.join(folder, "log.txt"), maxBytes=256_000,
                                                   backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    sys.excepthook = lambda kind, error, trace: log.critical("Unexpected error", exc_info=(kind, error, trace))


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    background = "--background" in argv
    # Its own identity in the taskbar, rather than Python's when run from the sources
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TheUnknownMurda.FLStudioBetterPresence")
    application = QtWidgets.QApplication(argv)
    application.setApplicationName(APP_NAME)
    application.setApplicationVersion(__version__)
    application.setQuitOnLastWindowClosed(False)
    application.styleHints().setColorScheme(QtCore.Qt.ColorScheme.Dark)  # dark title bar and menu

    instance = Instance()
    if not instance.first:
        # Already running: it opens its settings, unless Windows started this copy
        if "--quit" in argv:
            Instance.send("quit")
        elif not background:
            Instance.send("settings")
        return 0
    if "--quit" in argv:
        return 0  # not running
    instance.listen()

    setup_logging()
    settings = Settings()
    first_run = settings.first_run
    log.info("%s %s started%s", APP_NAME, __version__, " at sign-in" if background else "")
    if first_run:
        settings.save()
        startup.set_enabled(True)
    startup.refresh()

    app = App(settings, welcome=first_run)

    def received(text):
        if text == "settings":
            app.show_settings()
        elif text == "quit":
            app.quit()

    instance.message.connect(received)
    application.aboutToQuit.connect(app.engine.stop)
    if first_run or not background:
        app.show_settings()
    return application.exec()
