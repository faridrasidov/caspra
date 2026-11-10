from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from scripts.reader_simulator import ReaderJournal


class PowerLoss(BaseException):
    pass


class TestReaderJournal:
    def setup_tap(self, path, deadline=None):
        journal = ReaderJournal(path)
        key = uuid4()
        journal.prepare(key, "CARD")
        journal.authorize(
            key,
            {
                "id": str(uuid4()),
                "execute_before": (
                    deadline or datetime.now(UTC) + timedelta(seconds=30)
                ).isoformat(),
            },
        )
        return journal, key

    def test_replay_does_not_repeat_physical_effect(self, tmp_path):
        journal, key = self.setup_tap(tmp_path / "journal.sqlite")
        effects = []
        assert journal.activate(key, lambda: effects.append("pulse")) == "activated"
        assert journal.activate(key, lambda: effects.append("pulse")) == "activated"
        assert effects == ["pulse"]

    def test_restart_after_uncertain_effect_never_repeats_it(self, tmp_path):
        path = tmp_path / "journal.sqlite"
        journal, key = self.setup_tap(path)
        effects = []

        def pulse_then_crash():
            effects.append("pulse")
            raise PowerLoss("power lost")

        with pytest.raises(PowerLoss, match="power lost"):
            journal.activate(key, pulse_then_crash)
        assert ReaderJournal(path).activate(key, lambda: effects.append("pulse")) == "unknown"
        assert effects == ["pulse"]

    def test_expired_authorization_does_not_activate(self, tmp_path):
        journal, key = self.setup_tap(
            tmp_path / "journal.sqlite", datetime.now(UTC) - timedelta(seconds=1)
        )
        effects = []
        assert journal.activate(key, lambda: effects.append("pulse")) == "failed"
        assert effects == []
