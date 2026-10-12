"""Align legacy fixed-date fixtures with the real JWT clock, without source edits.

The Events fixtures pin 6 Oct 2026; their ten-minute receipts otherwise expire
after that date. Authentication/expiry validation remains enabled.
"""
from datetime import datetime,timezone
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests/events'))
import test_events as events
import test_event_presets as presets
import pytest

events.NOW=presets.NOW=datetime.now(timezone.utc)
raise SystemExit(pytest.main(['tests/events/test_events.py','tests/events/test_event_presets.py','-q',
    '--junitxml=reports/knowledge_tools_v2_1_regression_events.xml']))
