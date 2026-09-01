# 키움 REST API 모의투자 자동매매 MVP

키움증권 REST API의 **모의투자 환경만** 사용하는 Python 자동매매 검증 프로젝트입니다. 실계좌 주문 기능과 운영 서버 연결은 구현하지 않습니다.

## 현재 가능한 것

- 모의 API 인증, 계좌·보유종목·현재가 조회
- 삼성전자·SK하이닉스·현대차·KB금융·서울식품 5종목의 완료 15분봉 분석
- 통합 CMD 대시보드: 계좌, 보유 종목별 매입·평가금액·손익·수익률, 종목명·현재가·등락률, 전략 상태, 체결 기록, API 상태 표시
- `Trend Pullback V1 Multi` 기반 모의 자동주문: 추세·눌림·반등 조건과 위험관리 통과 시에만 시장가 1주
- 주문 접수 뒤 공식 체결 조회, SQLite 기록, 재시작 시 잔고·미체결 상태 복구
- 주간 운영 리포트: 성과·신호·차단 사유·API 오류·프로그램 시작 횟수 집계
- 모든 signal/trade에 전략·설정 버전과 Git 커밋 해시 기록
- stale market data 감지 및 Emergency Stop에 의한 신규 매수 차단
- 종목별 뉴스 위험 신호등: 양호·주의·위험·오류/지연 표시 (주문과 완전 분리)
- 장외·주말·등록 휴장일에는 분석 요청과 주문을 멈추고 당일 요약 표시

## 가장 쉬운 실행 방법

프로젝트 폴더의 `감시 시작.bat`를 더블 클릭하세요. 하나의 CMD 창에서 5종목 대시보드와 모의 자동주문이 실행됩니다. 종료는 `Ctrl+C`입니다.

자동 모의주문이 작동하려면 `.env`에 모의투자 키와 아래 설정이 필요합니다. `.env`는 절대 Git에 올리거나 공유하지 마세요.

```text
ENABLE_MOCK_ORDER=true
MARKET_HOLIDAYS=공식 KRX 휴장일을 YYYY-MM-DD 형식으로 쉼표로 입력
```

명령어를 직접 실행할 때는 다음을 사용합니다.

```cmd
cd /d "C:\Users\ckdem\OneDrive\바탕 화면\Kiwoom"
.venv\Scripts\python.exe -m app.main auto-trade-dashboard --loop-seconds 60 --confirm AUTO-MOCK-ORDER
```

화면만 안전하게 보고 싶다면 주문 없는 DRY RUN을 실행합니다.

```cmd
.venv\Scripts\python.exe -m app.main auto-dashboard --loop-seconds 60
```

모든 명령어와 사용 설명은 [CMD_명령어_안내.md](CMD_명령어_안내.md), 전략 상태와 세부 규칙은 [규칙.md](규칙.md)를 참고하세요.

## 주간 운영 리포트

최근 7일의 저장 기록을 자동 집계합니다. 컴퓨터가 꺼져 있던 시간은 새 기록이 생기지 않지만, 이미 저장된 기록은 다음 실행 때도 그대로 집계됩니다.

```cmd
.venv\Scripts\python.exe -m app.main weekly-report
```

특정 날짜를 마지막 날로 지정하려면 다음처럼 실행합니다.

```cmd
.venv\Scripts\python.exe -m app.main weekly-report --report-end-date 2026-09-04
```

리포트에는 체결·승패·승률·실현손익·평균 이익/손실·Profit Factor·최대 연속손실, 종목별 성과, 신호/진입/차단/API 오류/프로그램 시작 횟수가 포함됩니다.

## 뉴스 위험 신호등

뉴스 기능은 자동 매수·매도와 연결되지 않습니다. 5종목 감시 표의 `뉴스` 열과 `전략 / 신호 통계`에서 종목별·전체 상태를 표시합니다.

- **양호(초록)**: 마지막 정상 조회에서 정의된 위험·주의 키워드가 없음
- **주의(노랑)**: 유상증자·실적 부진·리콜·소송·파업 등 확인이 필요한 뉴스 또는 공시
- **위험(빨강)**: 거래정지·상장폐지·파산·부도·횡령·배임·영업정지 등 중대한 위험 키워드
- **오류/지연(빨강)**: 뉴스 API가 실패했거나 마지막 정상 조회가 오래됨
- **미설정(회색)**: 뉴스 API 키가 아직 없음. 양호를 뜻하지 않음

`.env`에 아래 키를 넣으면 다음 대시보드 시작부터 동작합니다. 키는 Git에 올리지 않습니다.

```text
NAVER_NEWS_CLIENT_ID=
NAVER_NEWS_CLIENT_SECRET=
OPENDART_API_KEY=
NEWS_POLL_SECONDS=600
NEWS_STALE_SECONDS=1800
```

네이버 키는 [네이버 개발자센터 뉴스 검색 API](https://developers.naver.com/docs/serviceapi/search/news/news.md)에서, 공시 키는 [OpenDART](https://opendart.fss.or.kr/)에서 발급받습니다. 둘 중 하나만 입력해도 감시는 가능하지만, 두 API를 함께 쓰는 편이 더 안전합니다.

## 현재 전략 요약

- 상승 추세: 종가와 EMA20이 EMA60 위
- 눌림: EMA20과 0.5% 이내
- 반등: EMA20 위·직전 완료봉보다 상승·RSI(14) 30~70
- 손절/익절: ATR(14) × 1.5 손절, 손절 폭의 2배 익절
- 안전 제한: 동시 보유 2종목, 하루 신규 진입 3회, 종목별 하루 1회, 연속 손실 3회, 일일 실현손실 -1%, 15:10 뒤 신규 매수 차단

`WAIT`, `TREND_BLOCKED`, `PULLBACK`은 오류가 아니라 조건이 아직 충분하지 않아 주문하지 않는 정상 상태입니다.

## 안전 원칙

- `https://mockapi.kiwoom.com`만 허용합니다.
- 주문은 모의계좌 시장가 1주만 가능하며, 자동 재전송하지 않습니다.
- API·체결조회 오류가 나면 신규 매수는 차단합니다.
- 마지막 정상 시장 데이터 수신 후 `.env`의 `STALE_DATA_SECONDS`를 넘기면 `STALE_DATA`로 표시하고 신규 매수를 차단합니다.
- `.env`의 `EMERGENCY_STOP=true`는 신규 모의 매수를 즉시 중단합니다. 이미 보유한 종목의 손절·익절·추세청산 매도는 유지합니다.
- 이 프로젝트는 수익을 보장하지 않는 모의 검증 도구입니다. 뉴스는 참고하되, 충분한 테스트 기록 없이 규칙을 바꾸지 않습니다.

## 테스트

```cmd
.venv\Scripts\python.exe -m pytest -q
```

## 공식 문서

[키움증권 REST API 가이드](https://openapi.kiwoom.com/guide/apiguide)
