from flbp import presence
from flbp.fl_watcher import FLState, Panel
from flbp.flp import ProjectInfo
from flbp.settings import DEFAULTS

STATE = FLState(running=True, project="Summer Vibes", unsaved=True, version="2025",
                panel=Panel("piano_roll", "Lead synth"), foreground=True)


def settings(**changes):
    return {**DEFAULTS, **changes}


def build(state=STATE, bpm=140.0, idle=False, timer_start=1000, project=None, project_time=None, **changes):
    info = project or ProjectInfo(bpm=bpm)
    return presence.build(state, info, settings(**changes), idle, timer_start, project_time)


def with_panel(kind, detail=""):
    return FLState(**{**STATE.__dict__, "panel": Panel(kind, detail)})


def test_automatic_status():
    activity = build()
    assert activity["type"] == 0
    assert activity["details"] == "Composing · Summer Vibes*"
    assert activity["state"] == "140 BPM"
    assert activity["timestamps"] == {"start": 1000}
    assets = activity["assets"]
    assert presence.icon_name(assets["large_image"]) == "fl-studio"
    assert assets["large_text"] == "FL Studio 2025"
    assert presence.icon_name(assets["small_image"]) == "composing"
    assert assets["small_text"] == "Piano roll · Lead synth"
    assert "buttons" not in activity


def test_fl_studio_closed():
    assert build(FLState()) is None


def test_every_window():
    expected = {"piano_roll": ("Composing", "composing"), "playlist": ("Arranging", "arranging"),
                "channel_rack": ("Beat making", "beatmaking"), "mixer": ("Mixing", "mixing"),
                "plugin": ("Sound design", "sounddesign"), "browser": ("Browsing sounds", "browsing")}
    for kind, (task, icon) in expected.items():
        activity = build(with_panel(kind))
        assert activity["details"] == f"{task} · Summer Vibes*"
        assert presence.icon_name(activity["assets"]["small_image"]) == icon


def test_effect_window():
    activity = build(with_panel("effect", "Fruity Parametric EQ 2 (Pad 1)"))
    assert activity["details"] == "Mixing · Summer Vibes*"
    assert presence.icon_name(activity["assets"]["small_image"]) == "mixing"
    assert activity["assets"]["small_text"] == "Fruity Parametric EQ 2 · Pad 1"
    assert build(with_panel("effect", "Fruity Limiter (Master)"), secret_mode="always")["assets"]["small_text"] == "Effect"


def test_window_details_when_hovering():
    assert build(with_panel("piano_roll"))["assets"]["small_text"] == "Piano roll"
    assert build(with_panel("mixer", "Insert 3"))["assets"]["small_text"] == "Mixer · Insert 3"
    # A channel and its mixer insert named alike, as FL does by default
    assert build(with_panel("plugin", "Pad 1 (Pad 1)"))["assets"]["small_text"] == "Pad 1"
    assert build(with_panel("plugin", "Lead (main) (Insert 3)"))["assets"]["small_text"] == "Lead (main) · Insert 3"
    assert build(with_panel("plugin", "Serum (Insert 2)"))["assets"]["small_text"] == "Serum · Insert 2"
    assert build(with_panel("channel_rack"))["assets"]["small_text"] == "Channel rack"


def test_before_any_window():
    activity = build(FLState(**{**STATE.__dict__, "panel": None}))
    assert activity["details"] == "Making music · Summer Vibes*"
    assert "small_image" not in activity["assets"]


def test_new_project_without_tempo():
    activity = build(FLState(running=True, version="2025", panel=Panel("playlist")), bpm=None)
    assert activity["details"] == "Arranging"
    assert "state" not in activity


def test_secret_mode():
    activity = build(secret_mode="always")
    assert activity["details"] == "Composing"
    assert activity["assets"]["small_text"] == "Piano roll"
    assert "Summer" not in str(activity) and "Lead" not in str(activity)


def test_switches():
    assert build(show_task=False)["details"] == "Working on Summer Vibes*"
    assert build(show_project=False)["details"] == "Composing"
    activity = build(show_task=False, show_project=False, show_bpm=False)
    assert "details" not in activity and "state" not in activity


def test_idle():
    activity = build(idle=True)
    assert activity["details"] == "Idle · Summer Vibes*"
    assert "timestamps" not in activity  # the timer pauses
    assert presence.icon_name(activity["assets"]["small_image"]) == "idle"
    assert activity["assets"]["small_text"] == "Idle"


def test_own_text():
    activity = build(custom_details="{task} on {project}", custom_state="{bpm} in FL {version}")
    assert activity["details"] == "Composing on Summer Vibes*"
    assert activity["state"] == "140 BPM in FL 2025"


def test_own_text_with_an_empty_placeholder():
    assert build(custom_details="{task} · {project}", secret_mode="always")["details"] == "Composing"
    assert build(custom_details="{project} | {task}", secret_mode="always")["details"] == "Composing"
    assert build(custom_state="Tempo: {bpm}", bpm=None)["state"] == "Tempo"


def test_own_text_while_idle():
    assert build(custom_details="Working on my album", idle=True)["details"] == "Idle · Summer Vibes*"
    kept = build(custom_details="Working on my album", idle=True, custom_text_while_idle=True)
    assert kept["details"] == "Working on my album"


def test_names_are_not_read_as_placeholders():
    state = FLState(**{**STATE.__dict__, "project": "{bpm}", "unsaved": False})
    assert build(state, custom_details="{project} · {task}")["details"] == "{bpm} · Composing"


def test_small_icon_choices():
    assert "small_image" not in build(small_icon="none")["assets"]
    custom = build(small_icon="custom", small_icon_url="https://example.com/logo.png", small_icon_text="{task}")
    assert custom["assets"]["small_image"] == "https://example.com/logo.png"
    assert custom["assets"]["small_text"] == "Composing"
    assert "small_image" not in build(small_icon="custom", small_icon_url="logo.png")["assets"]


def test_button():
    activity = build(button_label="My SoundCloud", button_url="https://soundcloud.com/me")
    assert activity["buttons"] == [{"label": "My SoundCloud", "url": "https://soundcloud.com/me"}]
    assert "buttons" not in build(button_label="My SoundCloud", button_url="soundcloud.com/me")
    assert "buttons" not in build(button_label="", button_url="https://soundcloud.com/me")


def test_text_length():
    state = FLState(**{**STATE.__dict__, "project": "🎹" * 100})
    details = build(state)["details"]
    assert len(details.encode("utf-16-le")) // 2 <= 128 and details.endswith("…")
    assert "state" not in build(custom_state="a")


def test_half_an_emoji_in_a_file_name():
    # As in a project the user saved: "(Melody\ud834 ♪\ud834\ud834)", where each 𝄞 lost its second half
    state = FLState(**{**STATE.__dict__, "project": "(Melody\ud834 ♪\ud834\ud834) 🥁"})
    details = build(state)["details"]
    details.encode("utf-8")  # valid text
    assert details == "Composing · (Melody ♪) 🥁*"


def test_unknown_placeholders():
    assert presence.unknown_placeholder("{task} · {project}") == ""
    assert presence.unknown_placeholder("{task] · {project}") == "{task]"
    assert presence.unknown_placeholder("{tempo}") == "{tempo}"


def test_links():
    assert presence.link_problem("https://soundcloud.com/me") == ""
    assert presence.link_problem("soundcloud.com/me") == "must start with https://"
    assert presence.link_problem("https://sound cloud.com") == "can't contain spaces"
    assert presence.link_problem("https://") == "isn't complete"


DEMO = ProjectInfo(bpm=143.0, title="Mic Check Ready", url="https://www.youtube.com/c/JayCactusTV", genre="UK Drill",
                   artists="Jay Cactus x Confz", spent=11 * 3600)


def test_exporting():
    state = FLState(**{**STATE.__dict__, "export_file": "Summer Vibes.wav"})
    activity = build(state)
    assert activity["details"] == "Exporting · Summer Vibes*"
    assert presence.icon_name(activity["assets"]["small_image"]) == "exporting"
    assert activity["assets"]["small_text"] == "Summer Vibes.wav"
    assert build(state, secret_mode="always")["assets"]["small_text"] == "Export"


def test_project_info_placeholders():
    activity = build(project=DEMO, project_time=11 * 3600 + 54 * 60, custom_state="{bpm} · {genre}",
                     custom_details="{task} for {artists} · {time}")
    assert activity["state"] == "143 BPM · UK Drill"
    assert activity["details"] == "Composing for Jay Cactus x Confz · 11 h 54"
    # Without them, they go with their separator; the artists could name a client
    assert build(custom_state="{bpm} · {genre}")["state"] == "140 BPM"
    assert build(project=DEMO, custom_details="{task} for {artists}", secret_mode="always")["details"] == "Composing for"


def test_button_to_the_projects_link():
    activity = build(project=DEMO, button_link="project", button_label="Watch on YouTube")
    assert activity["buttons"] == [{"label": "Watch on YouTube", "url": "https://www.youtube.com/c/JayCactusTV"}]
    without = ProjectInfo(bpm=140.0)
    assert "buttons" not in build(project=without, button_link="project", button_label="Watch")
    assert "buttons" not in build(project=DEMO, button_link="project", button_label="Watch", secret_mode="always")
    assert "buttons" not in build(project=DEMO, button_link="project", button_label="")
    # A link typed without its https://
    other = ProjectInfo(bpm=95.0, url=" www.instagram.com/astesoficial")
    assert build(project=other, button_link="project", button_label="Instagram")["buttons"][0]["url"] == \
        "https://www.instagram.com/astesoficial"


def test_secret_for_some_projects():
    client = FLState(**{**STATE.__dict__, "project": "CLIENT - Radio jingle", "unsaved": False})
    assert build(client, secret_mode="some", secret_words="client, #private")["details"] == "Composing"
    assert build(secret_mode="some", secret_words="client, #private")["details"] == "Composing · Summer Vibes*"
    by_file = FLState(**{**STATE.__dict__, "project": "Jingle", "project_file": r"C:\Work\#private Jingle.flp"})
    assert build(by_file, secret_mode="some", secret_words="client, #private")["details"] == "Composing"
    assert build(client, secret_mode="some", secret_words="")["details"] == "Composing · CLIENT - Radio jingle"


def test_export_progress():
    state = FLState(**{**STATE.__dict__, "export_file": "Summer Vibes.wav", "export_progress": 17})
    assert build(state)["assets"]["small_text"] == "Summer Vibes.wav · 17%"
    assert build(state, secret_mode="always")["assets"]["small_text"] == "Export · 17%"
