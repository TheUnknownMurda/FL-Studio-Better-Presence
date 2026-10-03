"""
Pictures drawn by the app: its icon with a dot in the color of the status, and the images of the preview.
"""
from PySide6 import QtCore, QtGui

BADGE_COLORS = {
    "shown": "#5865F2",  # Discord shows the status
    "not_shown": "#80848E",  # FL Studio is closed, or the status is hidden
    "problem": "#F0B232",  # Discord isn't open, or refused the app
}
ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def app_icon_image(fruit, size, badge_color=None):
    """The app's icon: FL's fruit, with a round badge in the corner when given its color."""
    image = QtGui.QImage(size, size, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
    scaled = fruit.scaled(size, size, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                          QtCore.Qt.TransformationMode.SmoothTransformation)
    # Moved left a little, so the badge hides less of the fruit
    shift = size * 0.07 if badge_color else 0
    painter.drawImage(QtCore.QPointF((size - scaled.width()) / 2 - shift, (size - scaled.height()) / 2), scaled)
    if badge_color:
        diameter = size * 0.44
        gap = max(1.0, size * 0.07)
        badge = QtCore.QRectF(size - diameter, size - diameter, diameter, diameter)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        # A transparent ring sets the badge apart from the fruit
        painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Clear)
        painter.setBrush(QtCore.Qt.GlobalColor.black)
        painter.drawEllipse(badge.adjusted(-gap, -gap, gap, gap))
        painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setBrush(QtGui.QColor(badge_color))
        painter.drawEllipse(badge)
    painter.end()
    return image


def app_icon(fruit, badge_color=None):
    """The app's icon at every size Windows asks for, each drawn rather than shrunk, so it stays sharp."""
    icon = QtGui.QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(QtGui.QPixmap.fromImage(app_icon_image(fruit, size, badge_color)))
    return icon


def rounded_pixmap(image, size, radius, ratio):
    """The image as a square of size logical pixels with rounded corners, sharp on high-density screens."""
    pixmap = QtGui.QPixmap(round(size * ratio), round(size * ratio))
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
    rect = QtCore.QRectF(0, 0, size * ratio, size * ratio)
    path = QtGui.QPainterPath()
    path.addRoundedRect(rect, radius * ratio, radius * ratio)
    painter.setClipPath(path)
    painter.drawImage(rect, image)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def badge_pixmap(image, size, ring, ring_color, ratio):
    """A round icon in a ring of the card's color, the way Discord draws the small image."""
    pixmap = QtGui.QPixmap(round(size * ratio), round(size * ratio))
    pixmap.fill(QtCore.Qt.GlobalColor.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
    painter.setPen(QtCore.Qt.PenStyle.NoPen)
    painter.setBrush(QtGui.QColor(ring_color))
    painter.drawEllipse(QtCore.QRectF(0, 0, size * ratio, size * ratio))
    inner = QtCore.QRectF(ring * ratio, ring * ratio, (size - 2 * ring) * ratio, (size - 2 * ring) * ratio)
    path = QtGui.QPainterPath()
    path.addEllipse(inner)
    painter.setClipPath(path)
    if image is not None:
        painter.drawImage(inner, image)
    else:
        # The user's own image is on the web: a picture symbol stands for it
        painter.fillRect(inner, QtGui.QColor("#4E5058"))
        painter.setPen(QtGui.QPen(QtGui.QColor("white"), 1.6 * ratio))
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        frame = inner.adjusted(inner.width() * 0.28, inner.height() * 0.3, -inner.width() * 0.28, -inner.height() * 0.3)
        painter.drawRoundedRect(frame, 1.5 * ratio, 1.5 * ratio)
        mountain = QtGui.QPainterPath()
        mountain.moveTo(frame.left(), frame.bottom())
        mountain.lineTo(frame.center().x() - frame.width() * 0.05, frame.top() + frame.height() * 0.45)
        mountain.lineTo(frame.right(), frame.bottom())
        painter.drawPath(mountain)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap
