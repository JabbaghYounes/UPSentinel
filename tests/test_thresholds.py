"""Tests for notification threshold gating logic."""

from __future__ import annotations

from ups.config import Config


class ThresholdChecker:
    """Minimal re-implementation of threshold logic for testing without GTK."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.notified_warn = False
        self.notified_critical = False
        self.shutdown_triggered = False
        self.notifications: list[str] = []

    def check(self, percent: int | None) -> None:
        if percent is None:
            return

        # Shutdown
        if (
            self.cfg.shutdown_enabled
            and not self.shutdown_triggered
            and percent <= self.cfg.shutdown_percent
        ):
            self.shutdown_triggered = True
            self.notifications.append(f"shutdown@{percent}")

        # Critical
        if percent <= self.cfg.critical_percent:
            if not self.notified_critical:
                self.notified_critical = True
                self.notifications.append(f"critical@{percent}")
        elif percent > self.cfg.critical_percent + 2:
            self.notified_critical = False

        # Warn
        if percent <= self.cfg.warn_percent:
            if not self.notified_warn:
                self.notified_warn = True
                self.notifications.append(f"warn@{percent}")
        elif percent > self.cfg.warn_percent + 2:
            self.notified_warn = False


class TestThresholdGating:
    """Tests for notification hysteresis."""

    def test_no_notification_above_thresholds(self) -> None:
        checker = ThresholdChecker(Config())
        for pct in [100, 80, 50, 25]:
            checker.check(pct)
        assert checker.notifications == []

    def test_warn_fires_at_threshold(self) -> None:
        checker = ThresholdChecker(Config())
        checker.check(20)
        assert "warn@20" in checker.notifications

    def test_critical_fires_at_threshold(self) -> None:
        checker = ThresholdChecker(Config())
        checker.check(10)
        assert "critical@10" in checker.notifications

    def test_no_repeat_notifications(self) -> None:
        checker = ThresholdChecker(Config())
        checker.check(20)
        checker.check(19)
        checker.check(18)
        assert checker.notifications.count("warn@20") == 1
        warn_count = sum(1 for n in checker.notifications if n.startswith("warn@"))
        assert warn_count == 1

    def test_hysteresis_prevents_flapping(self) -> None:
        checker = ThresholdChecker(Config())
        checker.check(20)  # triggers warn
        checker.check(21)  # still below reset threshold (22)
        checker.check(20)  # should NOT re-trigger
        warn_count = sum(1 for n in checker.notifications if n.startswith("warn@"))
        assert warn_count == 1

    def test_hysteresis_reset_allows_retrigger(self) -> None:
        checker = ThresholdChecker(Config())
        checker.check(20)  # triggers warn
        checker.check(23)  # above 22, resets
        checker.check(18)  # should re-trigger
        warn_count = sum(1 for n in checker.notifications if n.startswith("warn@"))
        assert warn_count == 2

    def test_critical_hysteresis(self) -> None:
        checker = ThresholdChecker(Config())
        checker.check(10)  # triggers critical
        checker.check(11)  # still below reset (12)
        checker.check(9)   # should NOT re-trigger
        crit_count = sum(1 for n in checker.notifications if n.startswith("critical@"))
        assert crit_count == 1

    def test_critical_reset_and_retrigger(self) -> None:
        checker = ThresholdChecker(Config())
        checker.check(10)  # triggers
        checker.check(13)  # resets
        checker.check(8)   # re-triggers
        crit_count = sum(1 for n in checker.notifications if n.startswith("critical@"))
        assert crit_count == 2

    def test_none_percent_no_crash(self) -> None:
        checker = ThresholdChecker(Config())
        checker.check(None)
        assert checker.notifications == []

    def test_full_drain_sequence(self) -> None:
        checker = ThresholdChecker(Config())
        for pct in [50, 30, 20, 15, 10, 5, 3]:
            checker.check(pct)
        assert "warn@20" in checker.notifications
        assert "critical@10" in checker.notifications

    def test_shutdown_disabled_by_default(self) -> None:
        checker = ThresholdChecker(Config())
        checker.check(3)
        shutdown = [n for n in checker.notifications if n.startswith("shutdown@")]
        assert shutdown == []

    def test_shutdown_triggers_once(self) -> None:
        cfg = Config(shutdown_enabled=True, shutdown_percent=5)
        checker = ThresholdChecker(cfg)
        checker.check(5)
        checker.check(4)
        checker.check(3)
        shutdown = [n for n in checker.notifications if n.startswith("shutdown@")]
        assert shutdown == ["shutdown@5"]

    def test_custom_thresholds(self) -> None:
        cfg = Config(warn_percent=30, critical_percent=15)
        checker = ThresholdChecker(cfg)
        checker.check(30)
        checker.check(15)
        assert "warn@30" in checker.notifications
        assert "critical@15" in checker.notifications
