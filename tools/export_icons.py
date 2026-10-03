"""
Exports the app's pictures:

- assets/icons/*.png at 1024 px, from the .svg beside them: the images Discord downloads from the repository
- assets/icons/fl-studio.png: FL's fruit on a dark square, the large image of the status
- src/flbp/resources/icons/*.png at 128 px: the same, for the preview in the settings window
- src/flbp/resources/fruit.png: the fruit alone, for the app's icon
- assets/app.ico: the icon of the .exe

    .venv\\Scripts\\python tools\\export_icons.py

Push the 1024 px pictures to GitHub after changing one, and raise the version in presence.ASSETS_URL so Discord
downloads them again.
"""
import pathlib
import shutil
import struct
import sys

from PySide6 import QtCore, QtGui, QtSvg

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from flbp.ui import drawing  # noqa: E402

ICONS = ROOT / "assets" / "icons"
FRUIT = ROOT / "assets" / "fl-fruit.png"
FL_FRUIT = pathlib.Path(r"C:\Program Files\Image-Line\FL Studio 2025\Artwork\Skins\Default\BigFruit.png")
RESOURCES = ROOT / "src" / "flbp" / "resources"
SIZE = 1024
PREVIEW_SIZE = 128
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def render_svg(svg_path, size):
    renderer = QtSvg.QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        raise RuntimeError(f"{svg_path.name} couldn't be read")
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return image


def logo(fruit, size):
    """Discord's large image: the fruit on a dark square, the way FL Studio shows it on its splash screen."""
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtGui.QColor("#2B3238"))
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
    scaled = fruit.scaledToHeight(round(size * 0.8), QtCore.Qt.TransformationMode.SmoothTransformation)
    painter.drawImage(round((size - scaled.width()) / 2 + size * 0.01), round((size - scaled.height()) / 2), scaled)
    painter.end()
    return image


def save(image, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(path)):
        raise RuntimeError(f"{path} couldn't be written")


def write_ico(images, path):
    """An .ico holding one PNG per size, which Windows reads since Vista."""
    blobs = []
    for image in images:
        buffer = QtCore.QBuffer()
        buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        blobs.append((image.width(), bytes(buffer.data())))
    header = struct.pack("<HHH", 0, 1, len(blobs))
    offset = len(header) + 16 * len(blobs)
    entries = b""
    for size, blob in blobs:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
    path.write_bytes(header + entries + b"".join(blob for _, blob in blobs))


def main():
    application = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication(sys.argv)
    if not FRUIT.exists():
        shutil.copyfile(FL_FRUIT, FRUIT)  # FL Studio's own picture, copied once
    fruit = QtGui.QImage(str(FRUIT))

    for svg_path in sorted(ICONS.glob("*.svg")):
        save(render_svg(svg_path, SIZE), svg_path.with_suffix(".png"))
        save(render_svg(svg_path, PREVIEW_SIZE), RESOURCES / "icons" / f"{svg_path.stem}.png")
        print(svg_path.stem)
    save(logo(fruit, SIZE), ICONS / "fl-studio.png")
    save(logo(fruit, PREVIEW_SIZE), RESOURCES / "icons" / "fl-studio.png")
    save(fruit.scaledToHeight(256, QtCore.Qt.TransformationMode.SmoothTransformation), RESOURCES / "fruit.png")
    print("fl-studio")

    fruit_small = QtGui.QImage(str(RESOURCES / "fruit.png"))
    write_ico([drawing.app_icon_image(fruit_small, size, drawing.BADGE_COLORS["shown"]) for size in ICO_SIZES],
              ROOT / "assets" / "app.ico")
    print("app.ico")
    del application


if __name__ == "__main__":
    main()
