import time
import uuid

import pytest

from fake_discord import FakeDiscord
from flbp import discord_ipc
from flbp.discord_ipc import DiscordClient, Status, discord_running

ACTIVITY = {"type": 0, "details": "Composing · Summer Vibes", "state": "140 BPM"}


def wait_until(condition, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture(autouse=True)
def quick(monkeypatch):
    monkeypatch.setattr(discord_ipc, "UPDATE_INTERVAL", 0.5)
    monkeypatch.setattr(discord_ipc, "RETRY_INTERVAL", 0.2)


@pytest.fixture
def discord():
    fake = FakeDiscord()
    yield fake
    fake.stop()


@pytest.fixture
def client(discord):
    client = DiscordClient("1555738506310066286", discord.prefix)
    yield client
    client.stop()


def test_shows_the_activity(discord, client):
    client.show(ACTIVITY)
    assert wait_until(lambda: discord.last == ACTIVITY)
    assert discord.client_id == "1555738506310066286"
    assert client.status == Status.CONNECTED
    assert client.user == "Tester"


def test_text_beyond_ascii(discord, client):
    activity = {"type": 0, "details": "Composing · 📄 [Drums 🥁] Mélodie"}
    client.show(activity)
    assert wait_until(lambda: discord.last == activity)


def test_nothing_to_show_closes_the_connection(discord, client):
    client.show(ACTIVITY)
    assert wait_until(lambda: discord.last == ACTIVITY)
    client.show(None)
    assert discord.disconnected.wait(3)
    assert wait_until(lambda: client.status == Status.OFF)


def test_quick_changes_are_grouped(discord, client):
    client.show(ACTIVITY)
    assert wait_until(lambda: discord.last == ACTIVITY)
    for number in range(5):
        client.show({**ACTIVITY, "state": f"{number} BPM"})
        time.sleep(0.02)
    assert wait_until(lambda: discord.last == {**ACTIVITY, "state": "4 BPM"})
    assert len(discord.activities) == 2
    assert discord.activities[1][0] - discord.activities[0][0] >= 0.45


def test_same_activity_sent_once(discord, client):
    client.show(ACTIVITY)
    assert wait_until(lambda: discord.last == ACTIVITY)
    client.show(dict(ACTIVITY))
    time.sleep(1.2)
    assert len(discord.activities) == 1


def test_shown_again_after_discord_restarts(discord, client):
    client.show(ACTIVITY)
    assert wait_until(lambda: discord.last == ACTIVITY)
    discord.kick()
    assert wait_until(lambda: discord.connections == 2 and len(discord.activities) == 2)
    assert discord.last == ACTIVITY


def test_answers_pings(discord, client):
    client.show(ACTIVITY)
    assert wait_until(lambda: discord.last == ACTIVITY)
    discord.ping()
    assert wait_until(lambda: discord.pongs == [{"nonce": "ping"}])


def test_discord_not_running():
    client = DiscordClient("1555738506310066286", rf"\\.\pipe\flbp-test-{uuid.uuid4().hex}-")
    try:
        client.show(ACTIVITY)
        assert wait_until(lambda: client.status == Status.NO_DISCORD)
    finally:
        client.stop()


def test_discord_opened_after_the_app():
    prefix = rf"\\.\pipe\flbp-test-{uuid.uuid4().hex}-"
    client = DiscordClient("1555738506310066286", prefix)
    fake = None
    try:
        client.show(ACTIVITY)
        assert wait_until(lambda: client.status == Status.NO_DISCORD)
        fake = FakeDiscord(prefix=prefix)
        assert wait_until(lambda: fake.last == ACTIVITY)
        assert client.status == Status.CONNECTED
    finally:
        client.stop()
        if fake:
            fake.stop()


def test_application_refused():
    fake = FakeDiscord(refuse=True)
    client = DiscordClient("1", fake.prefix)
    try:
        client.show(ACTIVITY)
        assert wait_until(lambda: client.status == Status.REFUSED)
        assert client.error == "Invalid Client ID"
    finally:
        client.stop()
        fake.stop()


def test_activity_refused_isnt_sent_again():
    fake = FakeDiscord(reject_activities=True)
    client = DiscordClient("1555738506310066286", fake.prefix)
    try:
        client.show(ACTIVITY)
        assert wait_until(lambda: client.error == 'child "activity" fails')
        time.sleep(1.2)
        assert len(fake.activities) == 1
        assert client.status == Status.CONNECTED
    finally:
        client.stop()
        fake.stop()


def test_discord_running(discord):
    assert discord_running(discord.prefix)
    assert not discord_running(rf"\\.\pipe\flbp-test-{uuid.uuid4().hex}-")
