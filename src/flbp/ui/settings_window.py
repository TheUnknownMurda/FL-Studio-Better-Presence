"""
The settings window: every setting on the left, and on the right what friends see in Discord, read from the
engine every second. Every change is saved and sent to Discord right away.
"""
import datetime
import logging
import time

from PySide6 import QtCore, QtGui, QtWidgets

from .. import APP_NAME, presence, startup
from ..discord_ipc import Status, discord_running
from ..settings import IDLE_MINUTES_RANGE
from ..stats import format_duration
from . import RESOURCES, drawing
from .widgets import (Card, PlaceholderBar, Segmented, Switch, SwitchCard, SwitchRow, WeekBars, message_label,
                      set_text_quietly, show_message, text_field)

log = logging.getLogger("flbp")

SMALL_ICONS = {"task": "What I'm doing", "custom": "My image", "none": "None"}
IDLE_ACTIONS = {"show": "Show “Idle”", "hide": "Hide my status", "off": "Do nothing"}
SECRET_MODES = {"off": "Off", "always": "Always", "some": "Some projects"}
TIMER_MODES = {"session": "This session", "fl": "Since FL Studio opened", "project": "Whole project"}
BUTTON_LINKS = {"mine": "My link", "project": "The project's link"}


def icon_image(name):
    image = QtGui.QImage(str(RESOURCES / "icons" / f"{name}.png"))
    return None if image.isNull() else image


def elapsed_text(start):
    seconds = max(0, int(time.time()) - int(start))
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours}:{minutes:02}:{seconds:02} elapsed" if hours else f"{minutes:02}:{seconds:02} elapsed"


# ---------------------------------------------------------------------------------------------------------------
# Groups of settings


class LineCard(Card):
    """A line of the status: automatic, set with switches, or the user's own text."""

    def __init__(self, title, hint, switches, example):
        super().__init__(title, hint)
        self.mode = Segmented({"auto": "Automatic", "custom": "My own text"})
        self.content.addWidget(self.mode)

        self._automatic = QtWidgets.QWidget()
        automatic_layout = QtWidgets.QVBoxLayout(self._automatic)
        automatic_layout.setContentsMargins(0, 2, 0, 0)
        automatic_layout.setSpacing(10)
        self.switches = {}
        for key, (label, example_text) in switches.items():
            row = SwitchRow(label, example_text)
            row.toggled.connect(self.changed)
            automatic_layout.addWidget(row)
            self.switches[key] = row
        self.content.addWidget(self._automatic)

        self._custom = QtWidgets.QWidget()
        custom_layout = QtWidgets.QVBoxLayout(self._custom)
        custom_layout.setContentsMargins(0, 2, 0, 0)
        custom_layout.setSpacing(6)
        self.field = text_field(f"e.g. {example}", 128)
        custom_layout.addWidget(self.field)
        custom_layout.addWidget(PlaceholderBar(self.field))
        self.note = message_label("warning")
        custom_layout.addWidget(self.note)
        self.content.addWidget(self._custom)

        # Suggested when "My own text" is chosen, so the line doesn't start empty
        self.suggestion = ""
        self.mode.changed.connect(self._mode_changed)
        self.field.textChanged.connect(self._text_changed)

    def load(self, text, switches):
        for key, on in switches.items():
            self.switches[key].set_on(on)
        set_text_quietly(self.field, text)
        self.mode.set_value("custom" if text else "auto")
        self._show_mode()
        self._check_text()

    def text(self):
        """The user's own text, or an empty one for the automatic text."""
        return self.field.text().strip() if self.mode.value() == "custom" else ""

    def _mode_changed(self, mode):
        if mode == "custom" and not self.field.text().strip():
            set_text_quietly(self.field, self.suggestion)
        self._show_mode()
        self._check_text()
        if mode == "custom":
            self.field.setFocus()
            self.field.end(False)
        self.changed.emit()

    def _show_mode(self):
        custom = self.mode.value() == "custom"
        self._automatic.setVisible(not custom)
        self._custom.setVisible(custom)

    def _text_changed(self):
        self._check_text()
        self.changed.emit()

    def _check_text(self):
        text = self.field.text().strip()
        typo = presence.unknown_placeholder(text)
        if typo:
            show_message(self.note, f"“{typo}” isn't a placeholder and will be shown as is. "
                                    f"Use the buttons above to insert one.")
        elif not text:
            show_message(self.note, "Empty: the automatic text is shown.")
        else:
            show_message(self.note, "")


class IconCard(Card):
    """The small round icon on the FL Studio logo."""

    HINTS = {
        "task": "Changes with the window you work in. Hovering it shows the window, like Mixer · Insert 3.",
        "custom": "Your own picture, like your logo: a link to a PNG or JPG image on the web.",
        "none": "Only the FL Studio logo is shown.",
    }

    def __init__(self):
        super().__init__("Small icon")
        self.mode = Segmented(SMALL_ICONS)
        self.content.addWidget(self.mode)
        self.explanation = QtWidgets.QLabel()
        self.explanation.setObjectName("hint")
        self.explanation.setWordWrap(True)
        self.content.addWidget(self.explanation)

        self._custom = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(self._custom)
        grid.setContentsMargins(0, 2, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        self.link = text_field("https://.../my-logo.png", 256)
        self.hover = text_field("e.g. {task} on {project}", 128)
        grid.addWidget(QtWidgets.QLabel("Image link"), 0, 0)
        grid.addWidget(self.link, 0, 1)
        self.link_error = message_label("error")
        grid.addWidget(self.link_error, 1, 1)
        grid.addWidget(QtWidgets.QLabel("On hover"), 2, 0)
        grid.addWidget(self.hover, 2, 1)
        grid.addWidget(PlaceholderBar(self.hover), 3, 1)
        self.hover_note = message_label("warning")
        grid.addWidget(self.hover_note, 4, 1)
        grid.setColumnStretch(1, 1)
        self.content.addWidget(self._custom)

        self.mode.changed.connect(self._mode_changed)
        self.link.textChanged.connect(self._fields_changed)
        self.hover.textChanged.connect(self._fields_changed)

    def load(self, icon, link, hover):
        self.mode.set_value(icon)
        set_text_quietly(self.link, link)
        set_text_quietly(self.hover, hover)
        self._show_mode()
        self._check()

    def choice(self):
        return self.mode.value()

    def link_text(self):
        return self.link.text().strip()

    def hover_text(self):
        return self.hover.text().strip()

    def _mode_changed(self, mode):
        self._show_mode()
        self._check()
        if mode == "custom" and not self.link_text():
            self.link.setFocus()
        self.changed.emit()

    def _fields_changed(self):
        self._check()
        self.changed.emit()

    def _show_mode(self):
        self.explanation.setText(self.HINTS[self.choice()])
        self._custom.setVisible(self.choice() == "custom")

    def _check(self):
        link = self.link_text()
        if not link:
            show_message(self.link_error, "Paste the link of your image to show it.")
        elif presence.link_problem(link):
            show_message(self.link_error, f"The link {presence.link_problem(link)}.")
        else:
            show_message(self.link_error, "")
        typo = presence.unknown_placeholder(self.hover_text())
        show_message(self.hover_note, f"“{typo}” isn't a placeholder and will be shown as is." if typo else "")


class ButtonCard(Card):
    """A button under the status, for friends: to the user's link, or to the open project's."""

    def __init__(self):
        super().__init__("Button", "A link under your status that your friends can click. "
                                   "Discord doesn't show it to you.")
        self.source = Segmented(BUTTON_LINKS)
        self.content.addWidget(self.source)
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        self.label_field = text_field("My SoundCloud", 32)
        self.link = text_field("https://soundcloud.com/...", 512)
        grid.addWidget(QtWidgets.QLabel("Text"), 0, 0)
        grid.addWidget(self.label_field, 0, 1)
        self.link_label = QtWidgets.QLabel("Link")
        grid.addWidget(self.link_label, 1, 0)
        grid.addWidget(self.link, 1, 1)
        self.error = message_label("error")
        grid.addWidget(self.error, 2, 1)
        grid.setColumnStretch(1, 1)
        self.content.addLayout(grid)
        self.explanation = QtWidgets.QLabel()
        self.explanation.setObjectName("hint")
        self.explanation.setWordWrap(True)
        self.content.addWidget(self.explanation)
        self._project_link = ""
        self.source.changed.connect(self._fields_changed)
        self.label_field.textChanged.connect(self._fields_changed)
        self.link.textChanged.connect(self._fields_changed)

    def load(self, label, link, source):
        self.source.set_value(source)
        set_text_quietly(self.label_field, label)
        set_text_quietly(self.link, link)
        self._check()

    def label(self):
        return self.label_field.text().strip()

    def link_text(self):
        return self.link.text().strip()

    def show_project_link(self, link):
        """The link typed in the open project's Project info, shown when the button uses it."""
        if link != self._project_link:
            self._project_link = link
            self._check()

    def _fields_changed(self):
        self._check()
        self.changed.emit()

    def _check(self):
        mine = self.source.value() == "mine"
        self.link_label.setVisible(mine)
        self.link.setVisible(mine)
        label, link = self.label(), self.link_text()
        if mine:
            self.explanation.hide()
            if bool(label) != bool(link):
                show_message(self.error, "Fill in both the text and the link to show the button.")
            elif link and presence.link_problem(link):
                show_message(self.error, f"The link {presence.link_problem(link)}.")
            else:
                show_message(self.error, "")
            return
        show_message(self.error, "" if label else "Type the text of the button to show it.")
        now = f" Now: {self._project_link}." if self._project_link else ""
        self.explanation.setText("The link typed in the open project's Project info (F11), like your YouTube "
                                 f"channel. A project without one shows no button, and neither does secret mode.{now}")
        self.explanation.show()


class SecretCard(Card):
    """Hiding the project's names: never, always, or for the projects whose name holds a word."""

    HINTS = {
        "off": "Every project shows its name.",
        "always": "Hides the names of the project, the channels and the windows, for client work. "
                  "Also in the menu of the app's icon.",
        "some": "Hides them only for the projects whose name holds one of these words, separated by commas.",
    }

    def __init__(self):
        super().__init__("Secret mode")
        self.mode = Segmented(SECRET_MODES)
        self.content.addWidget(self.mode)
        self.words = text_field("client, #private", 200)
        self.content.addWidget(self.words)
        self.explanation = QtWidgets.QLabel()
        self.explanation.setObjectName("hint")
        self.explanation.setWordWrap(True)
        self.content.addWidget(self.explanation)
        self.mode.changed.connect(self._mode_changed)
        self.words.textChanged.connect(self.changed)

    def load(self, mode, words):
        self.mode.set_value(mode)
        set_text_quietly(self.words, words)
        self._show_mode()

    def words_text(self):
        return ", ".join(word.strip() for word in self.words.text().split(",") if word.strip())

    def _mode_changed(self, mode):
        self._show_mode()
        if mode == "some":
            self.words.setFocus()
        self.changed.emit()

    def _show_mode(self):
        self.words.setVisible(self.mode.value() == "some")
        self.explanation.setText(self.HINTS[self.mode.value()])


class TimerCard(Card):
    """What the status' timer counts."""

    HINTS = {
        "session": "Restarts for each project you open.",
        "fl": "Counts the time since FL Studio was opened, whatever the project.",
        "project": "All the time spent on the project: what FL Studio counted and saved in it, plus this session.",
    }

    def __init__(self):
        super().__init__("Timer")
        self.mode = Segmented(TIMER_MODES)
        self.content.addWidget(self.mode)
        self.explanation = QtWidgets.QLabel()
        self.explanation.setObjectName("hint")
        self.explanation.setWordWrap(True)
        self.content.addWidget(self.explanation)
        self.mode.changed.connect(self._mode_changed)

    def load(self, mode):
        self.mode.set_value(mode)
        self.explanation.setText(self.HINTS[mode])

    def _mode_changed(self, mode):
        self.explanation.setText(self.HINTS[mode])
        self.changed.emit()


class StatsCard(Card):
    """The time spent in FL Studio this week, from the statistics kept on this computer."""

    def __init__(self):
        super().__init__("Your week in FL Studio", "Counted while FL Studio is open and you aren't away. "
                                                   "Kept on this computer only.")
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(24)
        self.bars = WeekBars()
        row.addWidget(self.bars, 0, QtCore.Qt.AlignmentFlag.AlignBottom)
        texts = QtWidgets.QVBoxLayout()
        texts.setSpacing(4)
        self.total = QtWidgets.QLabel()
        self.total.setObjectName("statsTotal")
        self.today = QtWidgets.QLabel()
        self.top = QtWidgets.QLabel()
        self.top.setWordWrap(True)
        for label in (self.today, self.top):
            label.setObjectName("hint")
        for label in (self.total, self.today, self.top):
            texts.addWidget(label)
        row.addLayout(texts, 1)
        row.setAlignment(texts, QtCore.Qt.AlignmentFlag.AlignTop)  # a stretch here would make the card grow
        self.content.addLayout(row)

    def show_stats(self, stats, now):
        week = stats.week(now)
        self.bars.set_days([seconds for _, seconds in week], datetime.date.fromtimestamp(now).weekday())
        self.total.setText(format_duration(sum(seconds for _, seconds in week)))
        self.today.setText(f"this week · {format_duration(stats.today(now))} today")
        top = stats.top_project(now)
        if top and top[1] >= 60:
            name = top[0] or "an untitled project"
            self.top.setText(f"Most worked on: {name}, {format_duration(top[1])}")
        else:
            self.top.setText("")


class AwayCard(Card):
    """What happens when FL Studio isn't used for a while."""

    def __init__(self):
        super().__init__("When you're away", "The timer pauses while you don't use FL Studio, "
                                             "and the time away isn't counted.")
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QtWidgets.QLabel("After"))
        self.minutes = QtWidgets.QSpinBox()
        self.minutes.setRange(*IDLE_MINUTES_RANGE)
        self.minutes.setSuffix(" min")
        self.minutes.setFixedWidth(100)
        row.addWidget(self.minutes)
        row.addWidget(QtWidgets.QLabel("without using FL Studio:"))
        row.addStretch()
        self.content.addLayout(row)
        self.action = Segmented(IDLE_ACTIONS)
        self.content.addWidget(self.action)
        self.keep = SwitchRow("Keep my own text", "Otherwise the first line says Idle.")
        self.content.addWidget(self.keep)
        self.minutes.valueChanged.connect(self.changed)
        self.action.changed.connect(self.changed)
        self.keep.toggled.connect(self.changed)

    def load(self, minutes, action, keep):
        self.minutes.blockSignals(True)
        self.minutes.setValue(minutes)
        self.minutes.blockSignals(False)
        self.action.set_value(action)
        self.keep.set_on(keep)


# ---------------------------------------------------------------------------------------------------------------
# Preview


class PreviewPanel(QtWidgets.QFrame):
    """What friends see in Discord."""

    _LOGO_SIZE = 72
    _BADGE_SIZE = 30

    NOTES = {
        "closed": ("info", "FL Studio isn't open, so here is an example. Your status shows up as soon as you open it."),
        "off": ("hiddenNote", "Your status is hidden. Turn on “Show my status” to show it again."),
        "away": ("hiddenNote", "Hidden while you're away. It comes back as soon as you use FL Studio."),
    }

    def __init__(self):
        super().__init__()
        self.setObjectName("previewPanel")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        title = QtWidgets.QLabel("WHAT YOUR FRIENDS SEE")
        title.setObjectName("sectionLabel")
        layout.addWidget(title)

        self.banner = message_label("banner")
        layout.addWidget(self.banner)
        self.notes = {kind: message_label(kind) for kind in ("info", "hiddenNote")}
        for note in self.notes.values():
            layout.addWidget(note)

        self.card = QtWidgets.QFrame()
        self.card.setObjectName("activityCard")
        card_layout = QtWidgets.QVBoxLayout(self.card)
        card_layout.setContentsMargins(12, 10, 12, 12)
        card_layout.setSpacing(10)
        header = QtWidgets.QLabel("PLAYING")
        header.setObjectName("activityHeader")
        card_layout.addWidget(header)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(12)
        images = QtWidgets.QWidget()
        images.setFixedSize(self._LOGO_SIZE + 8, self._LOGO_SIZE + 8)
        self.logo = QtWidgets.QLabel(images)
        self.logo.setGeometry(0, 0, self._LOGO_SIZE, self._LOGO_SIZE)
        self.badge = QtWidgets.QLabel(images)
        offset = self._LOGO_SIZE + 8 - self._BADGE_SIZE
        self.badge.setGeometry(offset, offset, self._BADGE_SIZE, self._BADGE_SIZE)
        row.addWidget(images, 0, QtCore.Qt.AlignmentFlag.AlignTop)
        texts = QtWidgets.QVBoxLayout()
        texts.setSpacing(2)
        name = QtWidgets.QLabel("FL Studio")
        name.setObjectName("activityName")
        texts.addWidget(name)
        self.details = QtWidgets.QLabel()
        self.state = QtWidgets.QLabel()
        self.timer = QtWidgets.QLabel()
        for label, kind in ((self.details, "activityLine"), (self.state, "activityLine"), (self.timer, "activityTimer")):
            label.setObjectName(kind)
            label.setWordWrap(True)
            texts.addWidget(label)
        row.addLayout(texts, 1)
        row.setAlignment(texts, QtCore.Qt.AlignmentFlag.AlignTop)
        card_layout.addLayout(row)
        # As tall as its content: the space left in the panel goes below the hover texts
        self.card.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Maximum)
        self.button = QtWidgets.QLabel()
        self.button.setObjectName("activityButton")
        self.button.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.button)
        layout.addWidget(self.card)

        hover_title = QtWidgets.QLabel("WHEN HOVERING")
        hover_title.setObjectName("sectionLabel")
        layout.addWidget(hover_title)
        hover = QtWidgets.QGridLayout()
        hover.setHorizontalSpacing(10)
        hover.setVerticalSpacing(6)
        self.badge_text = QtWidgets.QLabel()
        self.logo_text = QtWidgets.QLabel()
        for line, (caption, label) in enumerate((("Small icon", self.badge_text), ("FL Studio logo", self.logo_text))):
            caption_label = QtWidgets.QLabel(caption.upper())
            caption_label.setObjectName("hoverName")
            hover.addWidget(caption_label, line, 0, QtCore.Qt.AlignmentFlag.AlignTop)
            label.setObjectName("hoverText")
            label.setWordWrap(True)
            hover.addWidget(label, line, 1)
        hover.setColumnStretch(1, 1)
        layout.addLayout(hover)
        layout.addStretch()
        self.connection = QtWidgets.QLabel()
        self.connection.setObjectName("connection")
        self.connection.setWordWrap(True)
        layout.addWidget(self.connection)
        note = QtWidgets.QLabel("Discord updates your status every few seconds at most.")
        note.setObjectName("hint")
        note.setWordWrap(True)
        layout.addWidget(note)

        self._logo_image = icon_image("fl-studio")
        self._shown_badge = None
        self._ratio = None

    def show_status(self, activity, hidden, discord):
        """Shows the activity, why it is hidden if it is, and how the connection to Discord is going."""
        if discord.status == Status.REFUSED:
            banner = "Discord refused the app: " + discord.error
        elif discord.status == Status.CONNECTED and discord.error:
            banner = "Discord refused your status: " + discord.error
        elif hidden == "closed" or discord.status == Status.CONNECTED or discord_running(discord.pipe_prefix):
            banner = ""
        else:
            banner = "Discord isn't open. Your status shows up as soon as the Discord app runs."
        show_message(self.banner, banner)
        kind, text = self.NOTES.get(hidden, ("", ""))
        for note_kind, note in self.notes.items():
            show_message(note, text if note_kind == kind else "")
        # A hidden status is drawn faded. The effect is only set then, since it blurs text a little.
        if hidden and self.card.graphicsEffect() is None:
            fade = QtWidgets.QGraphicsOpacityEffect(self.card)
            fade.setOpacity(0.35 if hidden != "closed" else 0.6)
            self.card.setGraphicsEffect(fade)
        elif not hidden and self.card.graphicsEffect() is not None:
            self.card.setGraphicsEffect(None)

        if discord.status == Status.CONNECTED and discord.user:
            self.connection.setText(f"● Connected to Discord as {discord.user}")
        elif discord.status == Status.CONNECTED:
            self.connection.setText("● Connected to Discord")
        else:
            self.connection.setText("")
        self.connection.setVisible(bool(self.connection.text()))

        # Drawn again at the density of the screen the window is on
        ratio = self.devicePixelRatioF()
        if ratio != self._ratio:
            self._ratio = ratio
            self._shown_badge = None
            if self._logo_image is not None:
                self.logo.setPixmap(drawing.rounded_pixmap(self._logo_image, self._LOGO_SIZE, 8, ratio))

        activity = activity or {}
        for label, key in ((self.details, "details"), (self.state, "state")):
            label.setText(activity.get(key, ""))
            label.setVisible(bool(activity.get(key)))
        start = (activity.get("timestamps") or {}).get("start")
        self.timer.setText(elapsed_text(start) if start else "")
        self.timer.setVisible(bool(start))
        buttons = activity.get("buttons") or []
        self.button.setText(buttons[0]["label"] if buttons else "")
        self.button.setVisible(bool(buttons))

        assets = activity.get("assets") or {}
        small_image = assets.get("small_image", "")
        if small_image != self._shown_badge:
            self._shown_badge = small_image
            if not small_image:
                self.badge.clear()
            else:
                # The app's icons ship with it, the user's own image is on the web
                name = presence.icon_name(small_image)
                image = icon_image(name) if name else None
                self.badge.setPixmap(drawing.badge_pixmap(image, self._BADGE_SIZE, 3, "#232428", ratio))
        self.badge_text.setText(assets.get("small_text") or ("No text" if small_image else "No small icon"))
        self.logo_text.setText(assets.get("large_text", ""))


# ---------------------------------------------------------------------------------------------------------------
# Window


class SettingsWindow(QtWidgets.QWidget):

    changed = QtCore.Signal()  # a setting changed: the tray menu shows it too

    def __init__(self, settings, engine):
        super().__init__()
        self.settings = settings
        self.engine = engine
        self.setObjectName("SettingsWindow")
        self.setWindowTitle(APP_NAME)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground)
        with open(RESOURCES.parent / "ui" / "style.qss", encoding="utf-8") as file:
            self.setStyleSheet(file.read().replace("{resources}", RESOURCES.as_posix()))

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(16)
        root.addLayout(self._header())

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(16)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        column = QtWidgets.QWidget()
        column_layout = QtWidgets.QVBoxLayout(column)
        column_layout.setContentsMargins(0, 0, 10, 0)
        column_layout.setSpacing(12)
        self.first_line = LineCard(
            "First line", "What you're doing in FL Studio, and on which project.",
            {"show_task": ("What you're doing", "Composing, Arranging, Mixing, Sound design..."),
             "show_project": ("Project name", "Summer Vibes, as FL Studio's title bar shows it")},
            "{task} · {project}")
        self.first_line.suggestion = "{task} · {project}"
        self.second_line = LineCard(
            "Second line", "The tempo of your project.",
            {"show_bpm": ("Tempo", "140 BPM, read from your project each time you save it")},
            "{bpm} · {genre}")
        self.second_line.suggestion = "{bpm}"
        self.secret_card = SecretCard()
        self.small_icon = IconCard()
        self.button_card = ButtonCard()
        self.away_card = AwayCard()
        self.timer_card = TimerCard()
        self.stats_card = StatsCard()
        self.startup_card = SwitchCard("Start with Windows", "Your status appears when FL Studio opens and "
                                                             "goes away when it closes, without opening this app.")
        self._cards = (self.first_line, self.second_line, self.secret_card, self.small_icon, self.button_card,
                       self.away_card, self.timer_card)
        for card in self._cards + (self.stats_card, self.startup_card):
            column_layout.addWidget(card)
        column_layout.addStretch()
        scroll.setWidget(column)
        body.addWidget(scroll, 1)
        self.preview = PreviewPanel()
        self.preview.setFixedWidth(330)
        body.addWidget(self.preview)
        root.addLayout(body, 1)
        root.addLayout(self._footer())

        self.load()

        # Typing is applied once it pauses, every other change right away
        self._apply_timer = QtCore.QTimer(self)
        self._apply_timer.setSingleShot(True)
        self._apply_timer.setInterval(300)
        self._apply_timer.timeout.connect(self.apply)
        for card in self._cards:
            card.changed.connect(lambda: self._apply_timer.start())
        self._enabled.toggled.connect(lambda checked: self._apply_timer.start())
        self.startup_card.toggled.connect(self._startup_toggled)

        self._preview_timer = QtCore.QTimer(self)
        self._preview_timer.setInterval(1000)
        self._preview_timer.timeout.connect(self.refresh_preview)
        self._preview_timer.start()
        self.refresh_preview()

        available = (self.screen() or QtWidgets.QApplication.primaryScreen()).availableGeometry()
        self.setMinimumSize(780, 520)
        self.resize(min(920, available.width() - 40), min(800, available.height() - 60))

    def _header(self):
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(16)
        titles = QtWidgets.QVBoxLayout()
        titles.setSpacing(2)
        title = QtWidgets.QLabel(APP_NAME)
        title.setObjectName("title")
        titles.addWidget(title)
        subtitle = QtWidgets.QLabel("Shows what you're making in FL Studio on your Discord profile.")
        subtitle.setObjectName("subtitle")
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)
        label = QtWidgets.QLabel("Show my status")
        label.setObjectName("switchLabel")
        header.addWidget(label, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        self._enabled = Switch()
        self._enabled.setToolTip("Hides your status from Discord while the app keeps running.\n"
                                 "Also in the menu of the app's icon, next to the clock.")
        header.addWidget(self._enabled, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        return header

    def _footer(self):
        footer = QtWidgets.QHBoxLayout()
        footer.setSpacing(12)
        # "Reset to defaults" asks for a confirmation in its place
        self._reset = QtWidgets.QPushButton("Reset to defaults")
        self._reset.setObjectName("flat")
        self._reset.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        footer.addWidget(self._reset)
        self._confirm = QtWidgets.QWidget()
        confirm_layout = QtWidgets.QHBoxLayout(self._confirm)
        confirm_layout.setContentsMargins(0, 0, 0, 0)
        confirm_layout.setSpacing(8)
        confirm_layout.addWidget(QtWidgets.QLabel("Reset every setting?"))
        reset = QtWidgets.QPushButton("Reset")
        reset.setObjectName("danger")
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setObjectName("flat")
        for button in (reset, cancel):
            button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            confirm_layout.addWidget(button)
        self._confirm.hide()
        footer.addWidget(self._confirm)
        self._reset.clicked.connect(lambda: self._ask_reset(True))
        cancel.clicked.connect(lambda: self._ask_reset(False))
        reset.clicked.connect(self.reset_to_defaults)
        footer.addStretch()
        saved = QtWidgets.QLabel("Changes are saved right away. The app keeps running next to the clock.")
        saved.setObjectName("hint")
        footer.addWidget(saved)
        close = QtWidgets.QPushButton("Close")
        close.setObjectName("primary")
        close.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        close.setDefault(True)
        close.clicked.connect(self.close)
        footer.addWidget(close)
        return footer

    def load(self):
        """Shows the saved settings."""
        settings = self.settings
        self._enabled.set_quietly(settings["enabled"])
        self.first_line.load(settings["custom_details"],
                             {"show_task": settings["show_task"], "show_project": settings["show_project"]})
        self.second_line.load(settings["custom_state"], {"show_bpm": settings["show_bpm"]})
        self.secret_card.load(settings["secret_mode"], settings["secret_words"])
        self.small_icon.load(settings["small_icon"], settings["small_icon_url"], settings["small_icon_text"])
        self.button_card.load(settings["button_label"], settings["button_url"], settings["button_link"])
        self.away_card.load(settings["idle_minutes"], settings["idle_action"], settings["custom_text_while_idle"])
        self.timer_card.load(settings["timer_mode"])
        self.startup_card.switch.set_quietly(startup.is_enabled())
        self.startup_card.switch.setEnabled(startup.available())
        if not startup.available():
            self.startup_card.set_hint("Only for the app's .exe, not when it runs from its Python sources.")
        self._update_visibility()

    def apply(self):
        """Saves every setting and updates the status."""
        self._apply_timer.stop()
        secret_mode = self.secret_card.mode.value()
        values = {
            "enabled": self._enabled.isChecked(),
            "secret_mode": secret_mode,
            "secret_words": self.secret_card.words_text(),
            "show_task": self.first_line.switches["show_task"].is_on(),
            "show_project": self.first_line.switches["show_project"].is_on(),
            "show_bpm": self.second_line.switches["show_bpm"].is_on(),
            "custom_details": self.first_line.text(),
            "custom_state": self.second_line.text(),
            "small_icon": self.small_icon.choice(),
            "small_icon_url": self.small_icon.link_text(),
            "small_icon_text": self.small_icon.hover_text(),
            "button_label": self.button_card.label(),
            "button_url": self.button_card.link_text(),
            "button_link": self.button_card.source.value(),
            "idle_minutes": self.away_card.minutes.value(),
            "idle_action": self.away_card.action.value(),
            "custom_text_while_idle": self.away_card.keep.is_on(),
            "timer_mode": self.timer_card.mode.value(),
        }
        if secret_mode != "always":
            values["secret_mode_before"] = secret_mode  # where unchecking Secret mode in the icon's menu goes back to
        if any(self.settings[key] != value for key, value in values.items()):
            self.settings.update(**values)
            self.engine.refresh()
            self.changed.emit()
        self._update_visibility()
        self.refresh_preview()

    def _ask_reset(self, asking):
        self._reset.setVisible(not asking)
        self._confirm.setVisible(asking)

    def reset_to_defaults(self):
        self._ask_reset(False)
        self.settings.reset()
        self.load()
        self.engine.refresh()
        self.changed.emit()
        self.refresh_preview()

    def _startup_toggled(self, checked):
        try:
            startup.set_enabled(checked)
        except OSError as error:
            log.warning("Couldn't change starting with Windows: %s", error)
        self.startup_card.switch.set_quietly(startup.is_enabled())  # what Windows really does

    def flush(self):
        """Applies what was typed in the last moments, before a setting changes elsewhere."""
        if self._apply_timer.isActive():
            self.apply()

    def refresh_preview(self):
        self.preview.show_status(self.engine.preview(), self.engine.hidden, self.engine.discord)
        self.stats_card.show_stats(self.engine.stats, self.engine.clock())
        project = self.engine.project
        self.button_card.show_project_link(presence.project_link(project.url) if project else "")

    def _update_visibility(self):
        # Keeping the own text only matters with an own text, while "Idle" is shown
        custom = bool(self.first_line.text() or self.second_line.text())
        self.away_card.keep.setVisible(custom and self.away_card.action.value() == "show")

    def closeEvent(self, event):
        self.flush()
        self._preview_timer.stop()
        super().closeEvent(event)
