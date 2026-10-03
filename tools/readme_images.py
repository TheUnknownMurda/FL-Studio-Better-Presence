"""
Draws the pictures of the README in docs/images, without showing anything on screen, from a pretend
FL Studio and Discord: the user's settings and Discord status aren't touched.

    .venv\\Scripts\\python tools\\readme_images.py
"""
import os
import pathlib
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images"
os.environ["FLBP_CONFIG_DIR"] = tempfile.mkdtemp(prefix="flbp-readme-")
os.environ["FLBP_NO_STARTUP"] = "1"
sys.path.insert(0, str(ROOT / "src"))

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

from flbp.discord_ipc import Status  # noqa: E402
from flbp.engine import Engine  # noqa: E402
from flbp.fl_watcher import FLState, Panel  # noqa: E402
from flbp.settings import Settings  # noqa: E402
from flbp.ui import RESOURCES  # noqa: E402
from flbp.ui.settings_window import PreviewPanel, SettingsWindow  # noqa: E402

SONG = FLState(running=True, project="Summer Vibes", unsaved=True, version="2025",
               panel=Panel("piano_roll", "Lead synth"), foreground=True)
ELAPSED = 47 * 60 + 12


class PretendFL:
    def poll(self):
        return SONG

    def user_input_in_fl(self, state):
        return True


class PretendDiscord:
    status = Status.CONNECTED
    user = "producer"
    error = ""
    pipe_prefix = r"\\.\pipe\flbp-readme-"

    def show(self, activity):
        pass

    def stop(self):
        pass


def pump(seconds=0.3):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QtWidgets.QApplication.processEvents()
        time.sleep(0.02)


def engine_with(settings):
    started = time.time() - ELAPSED
    engine = Engine(settings, PretendDiscord(), PretendFL(), clock=lambda: started)
    engine.tick()
    engine.bpm = 140.0  # as read from the saved project
    engine.refresh()
    return engine


def settings_picture(settings):
    window = SettingsWindow(settings, engine_with(settings))
    window.setAttribute(QtCore.Qt.WidgetAttribute.WA_DontShowOnScreen)
    window.show()
    window.resize(920, 780)
    pump()
    window.grab().save(str(OUT / "settings.png"))
    window.close()


def status_picture(settings):
    """The status alone, as friends see it, with what shows on hover."""
    holder = QtWidgets.QWidget()
    holder.setObjectName("SettingsWindow")
    holder.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
    holder.setAttribute(QtCore.Qt.WidgetAttribute.WA_DontShowOnScreen)
    with open(RESOURCES.parent / "ui" / "style.qss", encoding="utf-8") as file:
        holder.setStyleSheet(file.read().replace("{resources}", RESOURCES.as_posix()))
    layout = QtWidgets.QVBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    panel = PreviewPanel()
    panel.setFixedWidth(400)
    layout.addWidget(panel)
    holder.show()
    engine = engine_with(settings)
    panel.show_status(engine.preview(), engine.hidden, engine.discord)
    panel.connection.hide()
    pump()
    holder.resize(400, panel.sizeHint().height())
    pump()
    holder.grab().save(str(OUT / "status.png"))
    holder.close()


def icons_picture():
    items = [("composing", "Composing", "Piano roll"), ("arranging", "Arranging", "Playlist"),
             ("beatmaking", "Beat making", "Channel rack"), ("mixing", "Mixing", "Mixer"),
             ("sounddesign", "Sound design", "Plugin windows"), ("browsing", "Browsing sounds", "Browser"),
             ("idle", "Idle", "Away for a while")]
    scale, cell_w, cell_h, icon, margin = 2, 112, 118, 56, 24
    width, height = margin * 2 + len(items) * cell_w, margin * 2 + cell_h
    image = QtGui.QImage(width * scale, height * scale, QtGui.QImage.Format.Format_ARGB32)
    image.setDevicePixelRatio(scale)
    image.fill(QtGui.QColor("#1E1F22"))
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
    name_font = QtGui.QFont("Segoe UI", 8)
    name_font.setBold(True)
    window_font = QtGui.QFont("Segoe UI", 8)
    for index, (name, label, window) in enumerate(items):
        x = margin + index * cell_w
        picture = QtGui.QImage(str(ROOT / "assets" / "icons" / f"{name}.png"))
        painter.drawImage(QtCore.QRectF(x + (cell_w - icon) / 2, margin + 4, icon, icon), picture)
        for font, color, top, text in ((name_font, "#F2F3F5", icon + 14, label), (window_font, "#949BA4", icon + 34, window)):
            painter.setFont(font)
            painter.setPen(QtGui.QColor(color))
            painter.drawText(QtCore.QRectF(x, margin + top, cell_w, 20), QtCore.Qt.AlignmentFlag.AlignHCenter, text)
    painter.end()
    image.save(str(OUT / "icons.png"))


def main():
    application = QtWidgets.QApplication(sys.argv)
    application.styleHints().setColorScheme(QtCore.Qt.ColorScheme.Dark)
    OUT.mkdir(parents=True, exist_ok=True)
    settings = Settings()
    settings.update(button_label="My SoundCloud", button_url="https://soundcloud.com/")
    settings_picture(settings)
    status_picture(settings)
    icons_picture()
    print("saved", ", ".join(path.name for path in sorted(OUT.glob("*.png"))))
    del application


if __name__ == "__main__":
    main()
