import datetime
import json
import os
import time

from flbp.stats import Stats, format_duration

MONDAY = time.mktime(datetime.datetime(2026, 9, 28, 20, 0).timetuple())  # a Monday evening
DAY = 24 * 3600


def test_durations():
    assert format_duration(42 * 60) == "42 min"
    assert format_duration(11 * 3600 + 54 * 60 + 30) == "11 h 54"
    assert format_duration(0) == "0 min"


def test_today_week_and_top_project():
    stats = Stats()
    stats.add(3600, "Mic Check Ready", MONDAY)
    stats.add(1800, "Summer Vibes", MONDAY + DAY)
    stats.add(1200, "Mic Check Ready", MONDAY + 2 * DAY)
    stats.add(600, "Old song", MONDAY - DAY)  # the Sunday before: another week
    assert stats.today(MONDAY + 2 * DAY) == 1200
    week = stats.week(MONDAY + 2 * DAY)
    assert [seconds for _, seconds in week] == [3600, 1800, 1200, 0, 0, 0, 0]
    assert week[0][0].weekday() == 0
    assert stats.top_project(MONDAY + 2 * DAY) == ("Mic Check Ready", 4800)
    assert Stats().top_project(MONDAY) is None


def test_saved_and_read_again():
    stats = Stats()
    stats.add(90, "", time.time())
    stats.save()
    again = Stats()
    assert again.today(time.time()) == 90
    assert again.top_project(time.time()) == ("", 90)


def test_old_days_forgotten_and_damaged_file():
    stats = Stats()
    stats.add(60, "Song", time.time() - 90 * DAY)
    stats.add(60, "Song", time.time())
    stats.save()
    assert len(Stats().days) == 1
    with open(stats.path, "w", encoding="utf-8") as file:
        json.dump({"days": {"2026-10-01": {"total": "much"}, "2026-10-02": [1]}}, file)
    assert Stats().days == {}
    os.remove(stats.path)
    assert Stats().days == {}
