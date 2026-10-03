"""
The time spent in FL Studio, day by day and by project, counted while FL Studio is open and the user isn't away.
Kept on this computer only, in stats.json beside the settings.
"""
import datetime
import json
import logging
import os
import time

from .settings import config_dir

log = logging.getLogger("flbp")

KEEP_DAYS = 60
SAVE_INTERVAL = 60  # seconds between two saves while counting: little is lost if the app is stopped abruptly
UNTITLED = ""  # the key of projects that were never saved


def format_duration(seconds):
    """'42 min', or '11 h 54' from an hour on."""
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02}"


class Stats:

    def __init__(self, path=None):
        self.path = path or os.path.join(config_dir(), "stats.json")
        self.days = {}  # {"2026-10-03": {"total": seconds, "projects": {name: seconds}}}
        self._changed = False
        self._saved_at = time.monotonic()
        self.load()

    def load(self):
        try:
            with open(self.path, encoding="utf-8-sig") as file:
                saved = json.load(file)
        except (OSError, ValueError):
            return
        days = saved.get("days") if isinstance(saved, dict) else None
        if not isinstance(days, dict):
            return
        for day, entry in days.items():
            if not isinstance(entry, dict) or not isinstance(entry.get("total"), (int, float)):
                continue
            projects = entry.get("projects") if isinstance(entry.get("projects"), dict) else {}
            self.days[day] = {"total": float(entry["total"]),
                              "projects": {str(name): float(seconds) for name, seconds in projects.items()
                                           if isinstance(seconds, (int, float))}}

    def add(self, seconds, project, now):
        """Counts seconds spent on a project at the given time."""
        entry = self.days.setdefault(self._day(now), {"total": 0.0, "projects": {}})
        entry["total"] += seconds
        entry["projects"][project] = entry["projects"].get(project, 0.0) + seconds
        self._changed = True
        if time.monotonic() - self._saved_at >= SAVE_INTERVAL:
            self.save()

    def save(self):
        if not self._changed:
            return
        oldest = (datetime.date.today() - datetime.timedelta(days=KEEP_DAYS)).isoformat()
        self.days = {day: entry for day, entry in self.days.items() if day >= oldest}
        temporary = self.path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(temporary, "w", encoding="utf-8") as file:
                json.dump({"days": self.days}, file, indent=1)
            os.replace(temporary, self.path)
        except OSError as error:
            log.warning("Couldn't save the statistics: %s", error)
            return
        self._changed = False
        self._saved_at = time.monotonic()

    def today(self, now):
        return self.days.get(self._day(now), {}).get("total", 0.0)

    def week(self, now):
        """[(day, seconds)] from Monday to Sunday of this week."""
        monday = datetime.date.fromtimestamp(now) - datetime.timedelta(days=datetime.date.fromtimestamp(now).weekday())
        days = [monday + datetime.timedelta(days=offset) for offset in range(7)]
        return [(day, self.days.get(day.isoformat(), {}).get("total", 0.0)) for day in days]

    def top_project(self, now):
        """(name, seconds) of the project worked on the most this week, or None. The name is "" when untitled."""
        totals = {}
        for day, _ in self.week(now):
            for name, seconds in self.days.get(day.isoformat(), {}).get("projects", {}).items():
                totals[name] = totals.get(name, 0.0) + seconds
        if not totals:
            return None
        name = max(totals, key=totals.get)
        return name, totals[name]

    @staticmethod
    def _day(now):
        return datetime.date.fromtimestamp(now).isoformat()
