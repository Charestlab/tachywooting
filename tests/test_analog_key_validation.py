import pytest

from tachywooting import wooting_utils
from tachywooting.wooting_utils import WOOTING_ACQUISITION


class FakeLib:
    WootingAnalogResult_NoMapping = -1993

    def wooting_analog_read_analog(self, code):
        return self.WootingAnalogResult_NoMapping if code == 4 else 0.0


def test_validate_analog_keys_rejects_unmapped_keys(monkeypatch):
    acquisition = WOOTING_ACQUISITION.__new__(WOOTING_ACQUISITION)
    acquisition.initialized = True
    monkeypatch.setattr(wooting_utils, "lib", FakeLib())

    with pytest.raises(RuntimeError, match="Analog key"):
        acquisition.validate_analog_keys(["a"])


def test_validate_analog_keys_returns_mapped_keycodes(monkeypatch):
    acquisition = WOOTING_ACQUISITION.__new__(WOOTING_ACQUISITION)
    acquisition.initialized = True
    monkeypatch.setattr(wooting_utils, "lib", FakeLib())

    assert acquisition.validate_analog_keys(["b"]) == [5]
