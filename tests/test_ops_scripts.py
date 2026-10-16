"""The monitoring setup script has to stay runnable and keep its guarantees.

These tests cannot call GCP, and should not. What they can do is stop the script
rotting: valid shell, valid JSON in the alert policies, and the four things it
promises still present. A monitoring script that silently stopped creating one of
its alerts would be worse than none, because you would believe you were covered.

The outage that prompted this: the scanner failed every request for an hour while
the API stayed healthy, so nothing based on uptime or 5xx would have fired. That
is why a log-based condition on the scanner is asserted separately.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "infra" / "setup_monitoring.sh"


@pytest.fixture(scope="module")
def src() -> str:
    return SCRIPT.read_text()


def test_the_script_exists_and_is_executable():
    assert SCRIPT.exists()
    assert SCRIPT.stat().st_mode & 0o111, "needs to be executable"


@pytest.mark.skipif(not shutil.which("bash"), reason="bash not available")
def test_it_is_valid_shell():
    r = subprocess.run(["bash", "-n", str(SCRIPT)], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_it_refuses_to_run_without_its_inputs(src):
    """Failing on a missing variable beats creating alerts that go nowhere."""
    assert ': "${PROJECT_ID:?' in src
    assert ': "${ALERT_EMAIL:?' in src


def test_it_sets_strict_mode(src):
    assert "set -euo pipefail" in src


def policies(src: str) -> list[dict]:
    """The alert policy JSON documents, rendered out of their heredocs."""
    out = []
    for name in ("POLICY_UPTIME", "POLICY_SCAN"):
        m = re.search(name + r"\" <<'JSON'\n(.*?)\nJSON", src, re.DOTALL)
        assert m, f"{name} heredoc not found"
        # Quoted heredoc: bash writes these bytes verbatim, so the only
        # substitution the script makes is the channel placeholder.
        body = m.group(1).replace("__CHANNEL__", "projects/p/notificationChannels/1")
        out.append(json.loads(body))
    return out


def test_both_alert_policies_are_valid_json(src):
    """A malformed policy fails at the gcloud call, after some resources exist."""
    assert len(policies(src)) == 2


def test_every_policy_notifies_somewhere(src):
    """An alert with no channel is a log line nobody reads."""
    for p in policies(src):
        assert p["notificationChannels"], p["displayName"]


def test_a_policy_covers_the_scanner_failing_while_the_api_stays_healthy(src):
    """The exact gap from the incident. Uptime on /health would not have fired,
    because the API was fine the whole time; the scanner was not."""
    scan = next(p for p in policies(src) if "scans" in p["displayName"])
    cond = scan["conditions"][0]["conditionMatchedLog"]["filter"]
    assert "antarctica-scanner" in cond
    assert "severity>=ERROR" in cond


def test_the_scanner_alert_is_rate_limited(src):
    """A crash loop logs continuously; one email per failure is how people start
    ignoring the alerts."""
    scan = next(p for p in policies(src) if "scans" in p["displayName"])
    assert scan["alertStrategy"]["notificationRateLimit"]["period"]


def test_the_uptime_alert_needs_more_than_one_region(src):
    """Threshold above 1 failing region, so a single flaky prober stays quiet."""
    up = next(p for p in policies(src) if "down" in p["displayName"])
    t = up["conditions"][0]["conditionThreshold"]
    assert t["comparison"] == "COMPARISON_GT"
    assert t["thresholdValue"] >= 1


def test_it_checks_health_on_both_services(src):
    assert "antarctica-api" in src
    assert "antarctica-scanner" in src
    assert "--path=/health" in src


def test_it_creates_a_budget_with_thresholds(src):
    """Cost alerts: the checklist item, and the reason it is on the list."""
    assert "budgets create" in src
    for pct in ("0.5", "0.9", "1.0"):
        assert f"percent={pct}" in src


def test_it_is_safe_to_run_twice(src):
    """Re-running setup should not duplicate channels, checks, policies or budgets."""
    for marker in ("(exists)", "(${name} exists)"):
        assert marker in src
