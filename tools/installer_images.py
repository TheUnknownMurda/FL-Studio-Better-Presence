"""
Draws the pictures of the installer in installer/: the large one beside its last page, and the small one in the
corner of the others, at each size Windows' display scales ask for.

    .venv\\Scripts\\python tools\\installer_images.py
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "installer"
ICONS = ROOT / "assets" / "icons"
sys.path.insert(0, str(ROOT / "src"))

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

from flbp.ui import drawing  # noqa: E402

# The sizes Inno Setup shows its pictures at, from 100% to 250% display scale, as its documentation lists them
WIZARD_SIZES = ((202, 386), (269, 515), (336, 643), (430, 824), (534, 1022))
SMALL_SIZES = (58, 77, 97, 124, 159)
WIDTH, HEIGHT = 202, 386  # what the large picture is drawn in, scaled to each size

BACKGROUND_TOP, BACKGROUND_BOTTOM = "#2B2D31", "#1A1B1E"
BLURPLE = QtGui.QColor("#5865F2")
CARD = "#111214"
TEXT_BARS = (("#F2F3F5", 46), ("#DBDEE1", 70), ("#B5BAC1", 40), ("#23A55A", 50))  # name, details, state, time


def pen_free(painter):
    painter.setPen(QtCore.Qt.PenStyle.NoPen)


def draw_status_card(painter, top):
    """A Discord status without words: FL Studio's logo with the small icon, and lines where the texts go."""
    card = QtCore.QRectF(18, top, WIDTH - 36, 92)
    pen_free(painter)
    painter.setBrush(QtGui.QColor(CARD))
    painter.drawRoundedRect(card, 10, 10)
    painter.setBrush(QtGui.QColor("#4E5058"))
    painter.drawRoundedRect(QtCore.QRectF(card.left() + 12, card.top() + 12, 40, 5), 2.5, 2.5)  # "Playing"

    logo = QtCore.QRectF(card.left() + 12, card.top() + 26, 52, 52)
    path = QtGui.QPainterPath()
    path.addRoundedRect(logo, 8, 8)
    painter.save()
    painter.setClipPath(path)
    painter.drawImage(logo, QtGui.QImage(str(ICONS / "fl-studio.png")))
    painter.restore()
    # The small icon, in a ring of the card's color, as Discord draws it
    ring = QtCore.QRectF(logo.right() - 15, logo.bottom() - 15, 24, 24)
    painter.setBrush(QtGui.QColor(CARD))
    painter.drawEllipse(ring)
    painter.drawImage(ring.adjusted(3, 3, -3, -3), QtGui.QImage(str(ICONS / "mixing.png")))

    left = logo.right() + 14
    for index, (color, width) in enumerate(TEXT_BARS):
        painter.setBrush(QtGui.QColor(color))
        height = 7 if index == 0 else 6
        painter.drawRoundedRect(QtCore.QRectF(left, logo.top() + 4 + index * 12.5, width, height), height / 2, height / 2)


def wizard_image(width, height):
    image = QtGui.QImage(width, height, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
    painter.scale(width / WIDTH, height / HEIGHT)
    area = QtCore.QRectF(0, 0, WIDTH, HEIGHT)
    background = QtGui.QLinearGradient(0, 0, 0, HEIGHT)
    background.setColorAt(0, QtGui.QColor(BACKGROUND_TOP))
    background.setColorAt(1, QtGui.QColor(BACKGROUND_BOTTOM))
    painter.fillRect(area, background)
    glow = QtGui.QRadialGradient(WIDTH / 2, 132, 120)
    for stop, alpha in ((0, 110), (0.55, 40), (1, 0)):
        color = QtGui.QColor(BLURPLE)
        color.setAlpha(alpha)
        glow.setColorAt(stop, color)
    painter.fillRect(area, glow)

    fruit = QtGui.QImage(str(ROOT / "assets" / "fl-fruit.png"))
    size = 112
    icon = drawing.app_icon_image(fruit, round(size * width / WIDTH))
    painter.drawImage(QtCore.QRectF((WIDTH - size) / 2, 76, size, size), icon)
    draw_status_card(painter, 222)
    painter.end()
    return image


def small_image(size):
    fruit = QtGui.QImage(str(ROOT / "assets" / "fl-fruit.png"))
    return drawing.app_icon_image(fruit, size, drawing.BADGE_COLORS["shown"])


def main():
    application = QtWidgets.QApplication(sys.argv)
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    for width, height in WIZARD_SIZES:
        wizard_image(width, height).save(str(OUT / f"wizard-{width}.png"))
    for size in SMALL_SIZES:
        small_image(size).save(str(OUT / f"small-{size}.png"))
    print("saved", ", ".join(path.name for path in sorted(OUT.glob("*.png"))))
    del application


if __name__ == "__main__":
    main()
