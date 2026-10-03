"""
The controls of the settings window, in the colors of Discord's dark theme since it is about a Discord status.
"""
from PySide6 import QtCore, QtGui, QtWidgets


class Switch(QtWidgets.QCheckBox):
    """An on/off switch, in Discord's colors."""

    _ON = QtGui.QColor("#5865F2")
    _OFF = QtGui.QColor("#4E5058")
    _KNOB = QtGui.QColor("white")
    _FOCUS = QtGui.QColor("#8C96FF")

    def __init__(self, checked=False):
        super().__init__()
        self.setChecked(checked)
        self.setFixedSize(40, 22)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._position = float(checked)
        self._animation = QtCore.QPropertyAnimation(self, b"position")
        self._animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self._animation.setDuration(120)
        self.toggled.connect(self._animate)

    def hitButton(self, position):
        return self.rect().contains(position)  # the whole switch reacts to clicks

    def set_quietly(self, checked):
        """Changes the switch without telling anyone, to show a setting changed elsewhere."""
        self.blockSignals(True)
        self.setChecked(checked)
        self.blockSignals(False)
        self.update()

    def _animate(self, checked):
        self._animation.stop()
        self._animation.setEndValue(float(checked))
        self._animation.start()

    def paintEvent(self, event):
        if self._animation.state() != QtCore.QAbstractAnimation.State.Running:
            self._position = float(self.isChecked())  # also follows changes made with signals blocked
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(0.4)
        track = QtCore.QRectF(1, 1, self.width() - 2, self.height() - 2)
        t = self._position
        color = QtGui.QColor(
            round(self._OFF.red() + (self._ON.red() - self._OFF.red()) * t),
            round(self._OFF.green() + (self._ON.green() - self._OFF.green()) * t),
            round(self._OFF.blue() + (self._ON.blue() - self._OFF.blue()) * t))
        painter.setPen(QtGui.QPen(self._FOCUS, 1.5) if self.hasFocus() else QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRoundedRect(track, track.height() / 2, track.height() / 2)
        diameter = track.height() - 6
        x = track.left() + 3 + (track.width() - diameter - 6) * t
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.setBrush(self._KNOB)
        painter.drawEllipse(QtCore.QRectF(x, track.top() + 3, diameter, diameter))

    def _get_position(self):
        return self._position

    def _set_position(self, value):
        self._position = value
        self.update()

    position = QtCore.Property(float, _get_position, _set_position)


class Segmented(QtWidgets.QFrame):
    """A choice between a few options, all visible at once."""

    changed = QtCore.Signal(str)

    def __init__(self, choices, value=None):
        super().__init__()
        self.setObjectName("segmented")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self._buttons = {}
        self._value = None
        for key, label in choices.items():
            button = QtWidgets.QPushButton(label)
            button.setObjectName("segment")
            button.setCheckable(True)
            button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, key=key: self._pick(key))
            layout.addWidget(button)
            self._buttons[key] = button
        self.set_value(value if value in choices else next(iter(choices)))

    def value(self):
        return self._value

    def set_value(self, value):
        self._value = value
        for key, button in self._buttons.items():
            button.setChecked(key == value)

    def _pick(self, value):
        changed = value != self._value
        self.set_value(value)  # a click on the chosen option would otherwise uncheck it
        if changed:
            self.changed.emit(value)


class Card(QtWidgets.QFrame):
    """A group of settings, with a title and a short explanation."""

    changed = QtCore.Signal()

    def __init__(self, title, hint=""):
        super().__init__()
        self.setObjectName("card")
        self.content = QtWidgets.QVBoxLayout(self)
        self.content.setContentsMargins(16, 14, 16, 16)
        self.content.setSpacing(10)
        self.heading = QtWidgets.QHBoxLayout()
        self.heading.setSpacing(12)
        titles = QtWidgets.QVBoxLayout()
        titles.setSpacing(3)
        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("cardTitle")
        titles.addWidget(title_label)
        self.hint = QtWidgets.QLabel()
        self.hint.setObjectName("hint")
        self.hint.setWordWrap(True)
        titles.addWidget(self.hint)
        self.heading.addLayout(titles, 1)
        self.content.addLayout(self.heading)
        self.set_hint(hint)

    def set_hint(self, hint):
        self.hint.setText(hint)
        self.hint.setVisible(bool(hint))


class SwitchCard(Card):
    """A card that is a single switch, beside its title."""

    toggled = QtCore.Signal(bool)

    def __init__(self, title, hint=""):
        super().__init__(title, hint)
        self.content.setContentsMargins(16, 14, 16, 14)
        self.switch = Switch()
        self.heading.addWidget(self.switch, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.switch.toggled.connect(self.toggled)
        self.switch.toggled.connect(lambda checked: self.changed.emit())
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        # A click on the text works too, not only on the switch
        if (event.button() == QtCore.Qt.MouseButton.LeftButton and self.switch.isEnabled()
                and self.rect().contains(event.position().toPoint())):
            self.switch.toggle()
        super().mouseReleaseEvent(event)


class SwitchRow(QtWidgets.QWidget):
    """A switch, what it does, and an example underneath."""

    toggled = QtCore.Signal(bool)

    def __init__(self, label, example=""):
        super().__init__()
        layout = QtWidgets.QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(1)
        text = QtWidgets.QLabel(label)
        text.setObjectName("switchLabel")
        layout.addWidget(text, 0, 0)
        if example:
            example_label = QtWidgets.QLabel(example)
            example_label.setObjectName("hint")
            example_label.setWordWrap(True)
            layout.addWidget(example_label, 1, 0)
        self.switch = Switch()
        layout.addWidget(self.switch, 0, 1, 2 if example else 1, 1,
                         QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        layout.setColumnStretch(0, 1)
        self.switch.toggled.connect(self.toggled)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        # A click on the text works too, not only on the switch
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.switch.toggle()
        super().mouseReleaseEvent(event)

    def is_on(self):
        return self.switch.isChecked()

    def set_on(self, on):
        self.switch.set_quietly(on)


class FlowLayout(QtWidgets.QLayout):
    """Lays its widgets out in a row that goes on to a new line when the space runs out."""

    def __init__(self, parent=None, spacing=6):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return QtCore.Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QtCore.QRect(0, 0, width, 0), move=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, move=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _arrange(self, rect, move):
        x, y, line_height = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > rect.right() + 1 and line_height:
                x, y, line_height = rect.x(), y + line_height + self._spacing, 0
            if move:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), hint))
            x += hint.width() + self._spacing
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y()


class PlaceholderBar(QtWidgets.QWidget):
    """Buttons inserting in a text field a placeholder that Discord shows as its value."""

    BUTTONS = (("{task}", "Task", "What you're doing, like Composing"),
               ("{project}", "Project", "The project's name, like Summer Vibes"),
               ("{bpm}", "BPM", "The tempo of the saved project, like 140 BPM"),
               ("{version}", "Version", "FL Studio's version, like 2025"),
               ("{genre}", "Genre", "The genre typed in the project's Project info, like UK Drill"),
               ("{artists}", "Artists", "The artists typed in the project's Project info"),
               ("{time}", "Time", "The time spent on the project, counted by FL Studio, like 11 h 54"))

    def __init__(self, field):
        super().__init__()
        layout = FlowLayout(self)
        label = QtWidgets.QLabel("Insert")
        label.setObjectName("hint")
        label.setMinimumHeight(22)
        layout.addWidget(label)
        for placeholder, name, tip in self.BUTTONS:
            button = QtWidgets.QPushButton(name)
            button.setObjectName("chip")
            button.setToolTip(f"{placeholder}: {tip}")
            button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)  # keeps the text cursor in the field
            button.clicked.connect(lambda checked=False, text=placeholder: self._insert(field, text))
            layout.addWidget(button)

    @staticmethod
    def _insert(field, text):
        field.insert(text)
        field.setFocus()


class WeekBars(QtWidgets.QWidget):
    """Seven bars, Monday to Sunday, for the time spent in FL Studio each day: today's stands out."""

    _BAR = QtGui.QColor("#4E5058")
    _TODAY = QtGui.QColor("#5865F2")
    _LABEL = QtGui.QColor("#949BA4")
    NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

    def __init__(self):
        super().__init__()
        self.setFixedSize(7 * 34, 110)
        self._values = [0.0] * 7
        self._today = -1

    def set_days(self, values, today):
        if list(values) != self._values or today != self._today:
            self._values, self._today = list(values), today
            self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        font = painter.font()
        font.setPointSizeF(8)
        painter.setFont(font)
        label_height = 18
        top = 4
        tallest = max(self._values) or 1.0
        for index, value in enumerate(self._values):
            x = index * 34 + 6
            height = max(3.0, (self.height() - label_height - top) * value / tallest) if value else 3.0
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(self._TODAY if index == self._today else self._BAR)
            painter.drawRoundedRect(QtCore.QRectF(x, self.height() - label_height - height, 22, height), 4, 4)
            painter.setPen(self._LABEL)
            painter.drawText(QtCore.QRectF(index * 34, self.height() - label_height + 2, 34, label_height),
                             QtCore.Qt.AlignmentFlag.AlignHCenter, self.NAMES[index])


def text_field(placeholder, max_length):
    field = QtWidgets.QLineEdit()
    field.setPlaceholderText(placeholder)
    field.setMaxLength(max_length)
    field.setClearButtonEnabled(True)
    return field


def message_label(kind):
    label = QtWidgets.QLabel()
    label.setObjectName(kind)
    label.setWordWrap(True)
    label.hide()
    return label


def show_message(label, text):
    label.setText(text)
    label.setVisible(bool(text))


def set_text_quietly(field, text):
    field.blockSignals(True)
    field.setText(text)
    field.blockSignals(False)
