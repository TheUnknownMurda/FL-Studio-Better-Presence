"""
Builds the Discord status from what FL Studio shows and the user's settings.
"""
import re

from .flp import format_bpm

# For each of FL's windows: what the user is doing, the window's name in FL, and its icon
WINDOWS = {
    "piano_roll": ("Composing", "Piano roll", "composing"),
    "playlist": ("Arranging", "Playlist", "arranging"),
    "channel_rack": ("Beat making", "Channel rack", "beatmaking"),
    "mixer": ("Mixing", "Mixer", "mixing"),
    "effect": ("Mixing", "Effect", "mixing"),  # an effect's window, opened from the mixer
    "plugin": ("Sound design", "Plugin", "sounddesign"),  # an instrument's window
    "browser": ("Browsing sounds", "Browser", "browsing"),
}
DEFAULT_TASK = "Making music"  # until the user works in one of the windows above
IDLE_TASK = "Idle"
IDLE_ICON = "idle"
LOGO = "fl-studio"
SEPARATOR = " · "
PLACEHOLDERS = ("task", "project", "bpm", "version")

# Discord downloads the images from the project's repository. HEAD is its default branch, and the version
# makes Discord download an image again after it changed.
ASSETS_URL = "https://raw.githubusercontent.com/TheUnknownMurda/FL-Studio-Better-Presence/HEAD/assets/icons/{}.png?v=1"

# Characters that separate two parts of a text, like "Composing · Summer Vibes"
_SEPARATORS = r"[·•|/:,\-–—]"


def build(state, bpm, settings, idle=False, timer_start=None):
    """The activity for Discord, as a dict, or None when FL Studio isn't running."""
    if not state.running:
        return None
    window = WINDOWS.get(state.panel.kind) if state.panel else None
    task = IDLE_TASK if idle else window[0] if window else DEFAULT_TASK
    project = state.project + ("*" if state.unsaved else "") if state.project and not settings["secret"] else ""
    values = {"task": task, "project": project, "bpm": f"{format_bpm(bpm)} BPM" if bpm else "",
              "version": state.version}
    # While idle, the user's own text gives way to "Idle", unless the user wants to keep it
    own_text = not idle or settings["custom_text_while_idle"]

    if settings["custom_details"] and own_text:
        details = fill(settings["custom_details"], values)
    else:
        shown_task = task if idle or settings["show_task"] else ""
        shown_project = project if settings["show_project"] else ""
        if shown_task and shown_project:
            details = shown_task + SEPARATOR + shown_project
        else:
            details = shown_task or (f"Working on {shown_project}" if shown_project else "")
    if settings["custom_state"] and own_text:
        state_text = fill(settings["custom_state"], values)
    else:
        state_text = values["bpm"] if settings["show_bpm"] else ""

    activity = {"type": 0}
    for key, text in (("details", details), ("state", state_text)):
        text = discord_text(text)
        if text:
            activity[key] = text
    if timer_start and not idle:
        activity["timestamps"] = {"start": int(timer_start)}  # the timer pauses while idle

    assets = activity["assets"] = {"large_image": ASSETS_URL.format(LOGO),
                                   "large_text": f"FL Studio {state.version}".strip()}
    small_image, small_text = small_icon(state, window, idle, settings, values)
    if small_image:
        assets["small_image"] = small_image
        small_text = discord_text(small_text)
        if small_text:
            assets["small_text"] = small_text

    label = discord_text(settings["button_label"], minimum=1, maximum=32)
    if label and is_link(settings["button_url"], 512):
        activity["buttons"] = [{"label": label, "url": settings["button_url"]}]
    return activity


def small_icon(state, window, idle, settings, values):
    """(image, text shown when hovering it) for the small icon on the FL Studio logo, or (None, "")."""
    mode = settings["small_icon"]
    if mode == "custom":
        link = settings["small_icon_url"].strip()
        return (link, fill(settings["small_icon_text"], values)) if is_link(link, 256) else (None, "")
    if mode != "task":
        return None, ""
    if idle:
        return ASSETS_URL.format(IDLE_ICON), IDLE_TASK
    if not window:
        return None, ""
    return ASSETS_URL.format(window[2]), window_text(state.panel, settings["secret"])


def window_text(panel, secret=False):
    """The window the user works in, like "Mixer · Insert 3", "808 Kick · Insert 1" or "Piano roll"."""
    name = WINDOWS[panel.kind][1]
    if secret or not panel.detail:
        return name  # the names in FL could tell about the project
    if panel.kind in ("plugin", "effect"):
        # "Serum (Insert 2)" gives "Serum · Insert 2", and "Pad 1 (Pad 1)", with its insert named alike, "Pad 1"
        match = re.match(r"^(.*?)\s*\(([^()]*)\)$", panel.detail)
        if not match:
            return panel.detail
        plugin, insert = match.group(1), match.group(2)
        return plugin if insert.lower() == plugin.lower() else plugin + SEPARATOR + insert
    return name + SEPARATOR + panel.detail


def fill(template, values):
    """
    The text with each {placeholder} replaced by its value. An empty placeholder takes the separator next to it
    away, so "{task} · {project}" gives "Composing" in secret mode.
    """
    for name, value in values.items():
        if not value:
            placeholder = re.escape("{" + name + "}")
            template = re.sub(rf"\s*{_SEPARATORS}\s*{placeholder}|{placeholder}\s*{_SEPARATORS}?", "", template)
    # In one pass, so a value can't be read as a placeholder
    text = re.sub(r"\{(%s)\}" % "|".join(values), lambda match: values[match.group(1)], template)
    return " ".join(text.split())


def unknown_placeholder(text):
    """The first brace that isn't part of a placeholder, like "{task]", or an empty string."""
    for name in PLACEHOLDERS:
        text = text.replace("{" + name + "}", " ")
    match = re.search(r"\{[^\s{}]*[}\])]?|\}", text)
    return match.group() if match else ""


def discord_text(text, minimum=2, maximum=128):
    """
    The text as Discord accepts it, or None when it is too short. Discord rejects the whole status when a text
    is too short or too long, and counts like JavaScript: an emoji counts as 2.
    """
    # FL can save a project under a name holding half an emoji, which isn't valid text anywhere else: it goes
    text = (text or "").encode("utf-16-le", "surrogatepass").decode("utf-16-le", "ignore").strip()
    if _length(text) < minimum:
        return None
    if _length(text) > maximum:
        kept = []
        length = 0
        for character in text:
            length += _length(character)
            if length > maximum - 1:
                break
            kept.append(character)
        text = "".join(kept).rstrip() + "…"
    return text


def _length(text):
    return len(text.encode("utf-16-le")) // 2


def is_link(link, maximum):
    """True for a web link Discord can use. A broken one would make Discord reject the whole status."""
    return bool(link) and not link_problem(link) and len(link) <= maximum


def link_problem(link):
    """Why a web link can't be used, or an empty string."""
    if not link.startswith(("https://", "http://")):
        return "must start with https://"
    if " " in link:
        return "can't contain spaces"
    if "." not in link.split("://", 1)[1]:
        return "isn't complete"
    return ""


def icon_name(image):
    """The name of one of the app's icons from its link, like "composing", or None for another image."""
    prefix, _, suffix = ASSETS_URL.partition("{}")
    if image and image.startswith(prefix) and image.endswith(suffix):
        return image[len(prefix):len(image) - len(suffix)]
    return None
