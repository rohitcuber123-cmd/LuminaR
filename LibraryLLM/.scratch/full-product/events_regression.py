import sys
from datetime import datetime, timezone
sys.path.insert(0, r"D:\SDC\LibraryLLM")
sys.path.insert(0, r"D:\SDC\LibraryLLM\tests\events")
import test_events as events
import test_event_presets as presets
events.NOW = presets.NOW = datetime.now(timezone.utc)
import pytest
raise SystemExit(pytest.main(['tests/events/test_events.py', 'tests/events/test_event_presets.py', '-q', '--junitxml=reports/full_product_regression_events.xml']))
