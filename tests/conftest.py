import json
from pathlib import Path

import pytest

from services.scanner.parse import parse_report
from services.scanner.run_lighthouse import ScanResult

FIXTURE = Path(__file__).parent / "fixtures" / "lhr_small.json"


@pytest.fixture
def lhr() -> dict:
    return json.loads(FIXTURE.read_text())


@pytest.fixture
def scan_result(lhr) -> ScanResult:
    return ScanResult(report=parse_report(lhr), raw=lhr, duration_ms=1234.0)
