"""Decide whose name today's automated commit is authored under.

Prints "owner" or "bot" for one repository on one day:

* Sunday: bot in every repository.
* Saturday: bot, except on one or two Saturdays per month, when one or two
  repositories commit as the owner.
* Monday-Friday: between one and five repositories commit as the owner, the
  number varying from day to day.

Commits authored as github-actions[bot] still update the repository but do not
count on the owner's GitHub contribution graph. Every choice is a pure function
of the date (no state, no clock-based randomness), so the repositories in REPOS
agree on the plan without talking to each other. Dates are UTC, matching the
commit timestamps made on the Actions runner.

Usage:
    python commit_identity.py REPO               # decision for today (UTC)
    python commit_identity.py REPO 2026-11-07    # decision for a given date
    python commit_identity.py --plan 2026-11     # owner repositories per day
"""

import calendar
import datetime as dt
import hashlib
import sys

# Shared by all *-papers repositories; keep this file identical in all of them.
SALT = "papers-commit-calendar-v1"
REPOS = (
    "ddc-papers",
    "electrosynthesis-papers",
    "photocatalysis-papers",
    "mechanochemistry-papers",
    "flow-chemistry-papers",
)
# Number of owner repositories on a weekday, drawn uniformly from this tuple.
WEEKDAY_COUNTS = (1, 2, 2, 3, 3, 3, 4, 4, 5, 5)

SATURDAY, SUNDAY = 5, 6


def _hash(text):
    return hashlib.sha256(f"{SALT}:{text}".encode()).digest()


def _pick(options, key):
    return options[int.from_bytes(_hash(key)[:8], "big") % len(options)]


def owner_saturdays(year, month):
    """Return the one or two Saturdays of the month kept for the owner."""
    weeks = calendar.Calendar().monthdatescalendar(year, month)
    saturdays = [week[SATURDAY] for week in weeks if week[SATURDAY].month == month]
    count = _pick((1, 2), f"{year:04d}-{month:02d}")
    ranked = sorted(saturdays, key=lambda day: _hash(day.isoformat()))
    return sorted(ranked[:count])


def owner_repos(day):
    """Return the repositories whose commit on `day` is authored as the owner."""
    if day.weekday() == SUNDAY:
        return []
    if day.weekday() == SATURDAY:
        if day not in owner_saturdays(day.year, day.month):
            return []
        count = _pick((1, 2), f"count:{day}")
    else:
        count = _pick(WEEKDAY_COUNTS, f"count:{day}")
    ranked = sorted(REPOS, key=lambda repo: _hash(f"{day}:{repo}"))
    return sorted(ranked[:count])


def identity(repo, day):
    if repo.lower() not in REPOS:
        print(f"warning: {repo!r} is not in REPOS; committing as bot", file=sys.stderr)
        return "bot"
    return "owner" if repo.lower() in owner_repos(day) else "bot"


def main(argv):
    if len(argv) == 2 and argv[0] == "--plan":
        year, month = map(int, argv[1].split("-"))
        for day in calendar.Calendar().itermonthdates(year, month):
            if day.month == month:
                repos = owner_repos(day)
                print(f"{day} {day:%a} {len(repos)} {' '.join(repos)}")
        return
    if len(argv) not in (1, 2):
        sys.exit(__doc__)
    if len(argv) == 2:
        day = dt.date.fromisoformat(argv[1])
    else:
        day = dt.datetime.now(dt.timezone.utc).date()
    print(identity(argv[0], day))


if __name__ == "__main__":
    main(sys.argv[1:])
