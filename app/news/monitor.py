"""OpenDART 공식 공시를 읽어 위험 신호만 만드는 모듈입니다.

이 모듈은 주문 서비스나 전략 엔진을 호출하지 않습니다.
"""
from __future__ import annotations

import html
import io
import os
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from time import monotonic
from typing import Iterable
from xml.etree import ElementTree

import httpx


KST = timezone(timedelta(hours=9), name="KST")
RED_TERMS = ("거래정지", "상장폐지", "파산", "부도", "회생절차", "횡령", "배임", "영업정지", "감사의견 거절")
YELLOW_TERMS = ("유상증자", "전환사채", "실적 부진", "실적 악화", "소송", "감사의견 한정", "관리종목")


class NewsLevel(StrEnum):
    GOOD = "양호"
    CAUTION = "주의"
    RISK = "위험"
    UNAVAILABLE = "오류/지연"
    DISABLED = "미설정"


@dataclass(frozen=True)
class NewsSettings:
    opendart_api_key: str = ""
    poll_seconds: int = 600
    stale_seconds: int = 1_800

    @classmethod
    def load(cls) -> "NewsSettings":
        poll = int(os.getenv("NEWS_POLL_SECONDS", "600"))
        stale = int(os.getenv("NEWS_STALE_SECONDS", "1800"))
        if poll < 300 or stale < poll:
            raise ValueError("NEWS_POLL_SECONDS는 300초 이상이고 NEWS_STALE_SECONDS보다 작아야 합니다.")
        return cls(os.getenv("OPENDART_API_KEY", "").strip(), poll, stale)


@dataclass(frozen=True)
class NewsItem:
    title: str
    summary: str
    url: str
    published_at: datetime | None
    source: str


@dataclass(frozen=True)
class NewsRiskState:
    symbol: str
    level: NewsLevel
    reason: str
    checked_at: datetime | None
    latest_title: str = ""


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(value or ""))).strip()


class DartSource:
    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=20.0)
        self._owns_client = client is None
        self._corp_by_stock: dict[str, str] | None = None

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _corp_codes(self) -> dict[str, str]:
        if self._corp_by_stock is not None:
            return self._corp_by_stock
        response = self.client.get("https://opendart.fss.or.kr/api/corpCode.xml", params={"crtfc_key": self.api_key})
        response.raise_for_status()
        mapping: dict[str, str] = {}
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            root = ElementTree.fromstring(archive.read("CORPCODE.xml"))
        for entry in root.findall("list"):
            stock, corp = (entry.findtext("stock_code") or "").strip(), (entry.findtext("corp_code") or "").strip()
            if stock and corp:
                mapping[stock] = corp
        self._corp_by_stock = mapping
        return mapping

    def fetch(self, symbol: str) -> list[NewsItem]:
        corp_code = self._corp_codes().get(symbol)
        if not corp_code:
            return []
        today = datetime.now(KST).strftime("%Y%m%d")
        start = (datetime.now(KST) - timedelta(days=1)).strftime("%Y%m%d")
        response = self.client.get("https://opendart.fss.or.kr/api/list.json", params={"crtfc_key": self.api_key, "corp_code": corp_code, "bgn_de": start, "end_de": today, "page_count": 20})
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") not in {"000", "013"}:
            raise RuntimeError(f"OpenDART 오류 {payload.get('status')}: {payload.get('message', '')}")
        return [NewsItem(_plain(row.get("report_nm", "")), "공식 공시", "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + row.get("rcept_no", ""), None, "OPENDART") for row in payload.get("list", [])]


class NewsMonitor:
    def __init__(self, settings: NewsSettings, *, dart: DartSource | None = None, clock=lambda: datetime.now(KST)) -> None:
        self.settings, self.clock = settings, clock
        self.dart = dart or (DartSource(settings.opendart_api_key) if settings.opendart_api_key else None)
        self._last_attempt = 0.0
        self._last_success: datetime | None = None
        self._states: dict[str, NewsRiskState] = {}

    def close(self) -> None:
        if self.dart: self.dart.close()

    def states(self, symbols: Iterable[str]) -> dict[str, NewsRiskState]:
        return {symbol: self._states.get(symbol, NewsRiskState(symbol, NewsLevel.DISABLED, "OpenDART API 키 미설정", None)) for symbol in symbols}

    def refresh(self, symbols: Iterable[str]) -> dict[str, NewsRiskState]:
        symbols = tuple(symbols)
        if not self.dart:
            return self.states(symbols)
        if monotonic() - self._last_attempt < self.settings.poll_seconds:
            return self._with_stale_status(symbols)
        self._last_attempt = monotonic()
        now = self.clock()
        for symbol in symbols:
            articles: list[NewsItem] = []; errors: list[str] = []; successes = 0
            if self.dart:
                try:
                    articles.extend(self.dart.fetch(symbol)); successes += 1
                except (httpx.HTTPError, RuntimeError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
                    errors.append(f"OpenDART {exc}")
            if successes:
                self._last_success = now
                self._states[symbol] = self._classify(symbol, articles, now, errors)
            else:
                self._states[symbol] = NewsRiskState(symbol, NewsLevel.UNAVAILABLE, "OpenDART API 오류: " + (" / ".join(errors)[:80] or "응답 없음"), self._last_success)
        return self._with_stale_status(symbols)

    def _with_stale_status(self, symbols: Iterable[str]) -> dict[str, NewsRiskState]:
        if self._last_success and (self.clock() - self._last_success).total_seconds() > self.settings.stale_seconds:
            return {symbol: NewsRiskState(symbol, NewsLevel.UNAVAILABLE, "공시 데이터 갱신 지연", self._last_success) for symbol in symbols}
        return self.states(symbols)

    def _classify(self, symbol: str, articles: list[NewsItem], checked_at: datetime, errors: list[str]) -> NewsRiskState:
        unique: list[NewsItem] = []; seen: set[str] = set()
        for item in articles:
            key = item.url or item.title
            if item.title and key not in seen:
                unique.append(item); seen.add(key)
        text_items = [(item, f"{item.title} {item.summary}") for item in unique]
        red = [(item, term) for item, text in text_items for term in RED_TERMS if term in text]
        yellow = [(item, term) for item, text in text_items for term in YELLOW_TERMS if term in text]
        latest = unique[0].title if unique else ""
        if red:
            item, term = red[0]
            return NewsRiskState(symbol, NewsLevel.RISK, f"{item.source} 위험 키워드: {term}", checked_at, item.title)
        if yellow:
            item, term = yellow[0]
            return NewsRiskState(symbol, NewsLevel.CAUTION, f"{item.source} 주의 키워드: {term} ({len(yellow)}건)", checked_at, item.title)
        suffix = " · 일부 소스 오류" if errors else ""
        return NewsRiskState(symbol, NewsLevel.GOOD, "공식 공시에 정의된 위험·주의 키워드 없음" + suffix, checked_at, latest)
