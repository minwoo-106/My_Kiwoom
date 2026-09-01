from datetime import datetime, timedelta

from app.news.monitor import NewsItem, NewsLevel, NewsMonitor, NewsSettings


class Source:
    def __init__(self, items=None, error=None):
        self.items, self.error = items or [], error
    def fetch(self, value):
        if self.error:
            raise self.error
        return self.items
    def close(self):
        pass


def test_news_monitor_marks_official_serious_event_as_risk():
    now = datetime(2026, 9, 1, 10, 0)
    monitor = NewsMonitor(NewsSettings(opendart_api_key="x"), dart=Source([NewsItem("삼성전자 거래정지 관련 공시", "", "one", now, "OPENDART")]), clock=lambda: now)
    try:
        state = monitor.refresh(("005930",))["005930"]
        assert state.level == NewsLevel.RISK
        assert "거래정지" in state.reason
    finally:
        monitor.close()


def test_news_monitor_marks_caution_and_api_failure_without_order_action():
    now = datetime(2026, 9, 1, 10, 0)
    caution = NewsMonitor(NewsSettings(opendart_api_key="x"), dart=Source([NewsItem("실적 부진 관련 공시", "", "one", now, "OPENDART")]), clock=lambda: now)
    failed = NewsMonitor(NewsSettings(opendart_api_key="x"), dart=Source(error=RuntimeError("timeout")), clock=lambda: now)
    try:
        assert caution.refresh(("005930",))["005930"].level == NewsLevel.CAUTION
        assert failed.refresh(("005930",))["005930"].level == NewsLevel.UNAVAILABLE
    finally:
        caution.close(); failed.close()


def test_news_monitor_uses_disabled_and_stale_states_without_keys():
    now = datetime(2026, 9, 1, 10, 0)
    disabled = NewsMonitor(NewsSettings(), clock=lambda: now)
    try:
        assert disabled.refresh(("005930",))["005930"].level == NewsLevel.DISABLED
    finally:
        disabled.close()
    monitor = NewsMonitor(NewsSettings(opendart_api_key="x", poll_seconds=300, stale_seconds=1_800), dart=Source([NewsItem("정상 공시", "", "one", now, "OPENDART")]), clock=lambda: now)
    try:
        assert monitor.refresh(("005930",))["005930"].level == NewsLevel.GOOD
        monitor._last_success = now - timedelta(seconds=1_801)
        assert monitor._with_stale_status(("005930",))["005930"].level == NewsLevel.UNAVAILABLE
    finally:
        monitor.close()
