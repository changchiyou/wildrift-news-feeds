#!/usr/bin/env python3
"""Twitter feed producer watchdog: classify the producer's current state.

Reads the tweets-status.json published by the publish-feeds pipeline (see
pages.yml "Record twitter feed status" step) and prints a JSON decision:

  state   healthy | failing
  streak  consecutive trailing failed runs (from history)
  reason  human-readable explanation

A failing state covers:
  - the status file is missing/unreadable (pipeline never recorded, Pages down)
  - the latest recorded run had a non-zero twitter.py rc
  - the pipeline has been silent for more than STALE_HOURS (cron disabled,
    job cancelled before the record step, Pages deploy broken, ...)

The workflow (.github/workflows/twitter-watchdog.yml) turns state transitions
into Discord notifications and red/green runs.
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

DEFAULT_URL = "https://changchiyou.github.io/wildrift-news-feeds/tweets-status.json"
STALE_HOURS = float(os.environ.get("STALE_HOURS", "4"))


def load(source):
    if source.startswith(("http://", "https://")):
        req = urllib.request.Request(source, headers={"User-Agent": "twitter-watchdog"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    with open(source) as fh:
        return json.load(fh)


def main():
    source = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    decision = {"state": "healthy", "streak": 0, "reason": "ok", "run_url": ""}

    try:
        data = load(source)
    except Exception as exc:  # noqa: BLE001 - any failure means "cannot confirm health"
        decision.update(state="failing", reason=f"status file unavailable: {exc}")
    else:
        history = data.get("history", [])

        def failed(entry):
            # rc non-zero, or None (step skipped / never produced a status)
            return entry.get("rc") != 0

        streak = 0
        for entry in reversed(history):
            if failed(entry):
                streak += 1
            else:
                break

        updated_at = data.get("updated_at", "")
        try:
            age_h = (
                datetime.now(timezone.utc) - datetime.fromisoformat(updated_at)
            ).total_seconds() / 3600
            age_txt = f"{age_h:.1f}h"
        except (TypeError, ValueError):
            age_h = float("inf")
            age_txt = "unknown"

        decision["streak"] = streak
        decision["run_url"] = data.get("run_url", "")
        decision["updated_at"] = updated_at

        if age_h > STALE_HOURS:
            decision.update(
                state="failing",
                reason=(
                    f"pipeline silent for {age_txt} (>{STALE_HOURS:g}h); "
                    "last run may have died before recording status"
                ),
            )
        elif history and failed(history[-1]):
            decision.update(
                state="failing", reason=f"twitter.py exited rc={history[-1].get('rc')}"
            )

    print(json.dumps(decision))

    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a") as fh:
            for key, value in decision.items():
                fh.write(f"{key}={value}\n")


if __name__ == "__main__":
    main()
