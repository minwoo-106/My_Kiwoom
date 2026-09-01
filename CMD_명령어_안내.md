# 키움 모의투자 MVP - CMD 명령어 안내

> **중요: 이 프로젝트는 키움 모의투자만 사용합니다. 실계좌 주문은 지원하지 않습니다.**

## 0. CMD를 열 때마다 먼저 할 일

```cmd
cd /d "C:\Users\ckdem\OneDrive\바탕 화면\Kiwoom"
```

`# 프로젝트 폴더로 이동합니다. 아래 명령은 모두 이 위치에서 실행하세요.`

## 1. 인증·계좌·시세 조회

```cmd
.venv\Scripts\python.exe -m app.main auth
```

`# 모의투자 App Key와 Secret Key로 인증되는지 확인합니다. 토큰 값은 표시하지 않습니다.`

```cmd
.venv\Scripts\python.exe -m app.main accounts
```

`# 모의투자 계좌를 조회합니다. 계좌번호는 일부 마스킹됩니다.`

```cmd
.venv\Scripts\python.exe -m app.main portfolio
```

`# 예수금, 총자산, 손익, 보유 종목을 조회합니다. 주문은 하지 않습니다.`

```cmd
.venv\Scripts\python.exe -m app.main quote --stock-code 005930
```

`# 종목 시세를 조회합니다. 005930 자리에 여섯 자리 종목코드를 넣을 수 있습니다.`

## 2. 실시간 터미널 대시보드

```cmd
.venv\Scripts\python.exe -m app.main dashboard --stock-code 005930
```

`# 잔고·시세·API 상태를 같은 화면에서 갱신합니다. 주문하지 않습니다.`
`# 종료하려면 Ctrl + C를 누르세요.`

```cmd
.venv\Scripts\python.exe -m app.main dashboard --stock-code 005930 --once
```

`# 대시보드를 한 번만 출력하고 종료합니다. 화면 확인용입니다.`

```cmd
.venv\Scripts\python.exe -m app.main dashboard --stock-code 005930 --refresh-seconds 15
```

`# 15초마다 조회합니다. 최소 조회 주기는 5초입니다.`

## 3. 멀티종목 전략 분석 - DRY RUN

```cmd
.venv\Scripts\python.exe -m app.main strategy-dry-run
```

`# 5개 감시 종목의 15분봉을 분석합니다.`
`# 신호와 위험 차단 사유만 SQLite에 저장합니다.`
`# 현재는 주문을 전혀 보내지 않는 DRY RUN 모드입니다.`
`# 1회 분석 후 종료합니다.`

```cmd
.venv\Scripts\python.exe -m app.main strategy-loop --loop-seconds 60
```

`# 5종목을 60초 간격으로 계속 분석합니다. 주문은 전혀 보내지 않습니다.`
`# Ctrl + C를 누르면 안전하게 종료합니다.`

```cmd
.venv\Scripts\python.exe -m app.main auto-dashboard --loop-seconds 60
```

`# 가장 권장하는 평상시 관제 화면입니다.`
`# 5종목의 완료 15분봉, 전략 상태, 위험 차단 사유, 잔고, 당일 결과를 한 화면에서 보여줍니다.`
`# 이 명령도 DRY RUN이며 주문을 전혀 보내지 않습니다.`

기본 감시 종목: 삼성전자(005930), SK하이닉스(000660), 현대차(005380), KB금융(105560), 서울식품(004410)

```cmd
.venv\Scripts\python.exe -m app.main daily-summary
```

`# 장 마감 후에도 오늘의 신호 수·차단 수·매수·매도·실현손익 기록을 보여줍니다.`
`# 현재 DRY RUN이라 매수·매도·실현손익이 0인 것은 정상입니다.`

## 4. 수동 모의주문

```cmd
.venv\Scripts\python.exe -m app.main manual-buy --stock-code 005930 --quantity 1 --confirm MOCK-ORDER
```

`# 005930을 모의 시장가로 1주 매수합니다.`
`# 모의 계좌 잔고는 바뀌지만 실제 돈이나 실계좌에는 영향이 없습니다.`

```cmd
.venv\Scripts\python.exe -m app.main manual-sell --stock-code 005930 --quantity 1 --confirm MOCK-ORDER
```

`# 해당 종목을 모의 시장가로 1주 매도합니다.`
`# 실행 전 portfolio 명령으로 보유 수량을 확인하세요.`

## 5. 자동 모의주문 (지금은 실행하지 않아도 됩니다)

자동 주문은 **모의계좌만** 대상으로 구현돼 있지만, 잔고를 바꿀 수 있으므로 아래 명령은 충분히 확인한 뒤에만 실행하세요. 실계좌 서버는 지원하지 않습니다.

먼저 `.env`에 다음 두 항목을 준비합니다.

```text
ENABLE_MOCK_ORDER=true
MARKET_HOLIDAYS=공식 KRX 휴장일을 YYYY-MM-DD 형식으로 쉼표로 입력
```

```cmd
.venv\Scripts\python.exe -m app.main auto-trade-dashboard --loop-seconds 60 --confirm AUTO-MOCK-ORDER
```

`# 자동 모의주문과 5종목 관제 화면을 한 CMD에서 실행합니다.`
`# ENABLE_MOCK_ORDER, 휴장일 목록, AUTO-MOCK-ORDER 확인문구가 모두 없으면 시작되지 않습니다.`
`# 시장가 1주만 접수하며, 접수 후에는 재전송하지 않고 체결 상태를 조회합니다.`
`# 15:10 이후·장 마감·주말·등록 휴장일에는 신규 매수를 차단합니다.`

```cmd
.venv\Scripts\python.exe -m app.main auto-trade-dashboard --once --confirm AUTO-MOCK-ORDER
```

`# 장외 또는 화면 점검 때 한 번만 출력하고 종료합니다. 장 마감에는 주문하지 않습니다.`

## 6. 테스트

```cmd
.venv\Scripts\python.exe -m pytest -q
```

`# 기능 수정 후 자동 테스트를 실행합니다.`

## 7. 주간 운영 리포트

```cmd
.venv\Scripts\python.exe -m app.main weekly-report
```

`# 최근 7일의 체결·승패·승률·손익·Profit Factor·연속손실·종목별 성과를 집계합니다.`
`# BUY_SIGNAL, 실제 진입, RISK_BLOCKED 사유, API 오류, 프로그램 시작 횟수도 함께 표시합니다.`

```cmd
.venv\Scripts\python.exe -m app.main weekly-report --report-end-date 2026-09-04
```

`# 지정한 날짜를 마지막 날로 하는 7일 리포트를 출력합니다.`

## 8. 긴급 신규 매수 중단

`.env`에 아래처럼 입력하면 다음 감시 주기부터 신규 모의 매수가 모두 중단됩니다.`

```text
EMERGENCY_STOP=true
```

`# 대시보드에 빨간색으로 표시됩니다. 기존 보유 종목의 손절·익절·추세청산 매도는 안전을 위해 계속 허용합니다.`
`# 다시 켜려면 EMERGENCY_STOP=false로 바꾸고 감시 프로그램을 재시작하세요.`

```text
STALE_DATA_SECONDS=180
```

`# 마지막 정상 시장 데이터 수신 뒤 180초 이상 새 데이터를 받지 못하면 STALE_DATA로 표시하고 신규 매수를 차단합니다.`

## 9. 뉴스 위험 신호등 설정

뉴스 기능은 주문하지 않습니다. 5종목 감시 표에서 종목별로 `양호`(초록)·`주의`(노랑)·`위험`(빨강)·`오류/지연`(빨강)을 표시합니다.

`.env`에 네이버 뉴스 검색 API 키와 선택적으로 OpenDART 키를 넣습니다.

```text
NAVER_NEWS_CLIENT_ID=
NAVER_NEWS_CLIENT_SECRET=
OPENDART_API_KEY=
NEWS_POLL_SECONDS=600
NEWS_STALE_SECONDS=1800
```

`# 키가 없으면 회색 미설정으로 표시됩니다. 이는 양호 상태가 아닙니다.`
`# 뉴스 신호등은 자동 매수·매도·위험관리 규칙을 바꾸지 않습니다.`
`# 키 입력 뒤 감시 프로그램을 다시 시작하세요.`

## 현재 자동매매 상태

- 평상시에는 `auto-dashboard` 하나만 켜면 됩니다. 이 화면은 주문 없는 안전한 DRY RUN입니다.
- 실제 모의 자동주문은 위의 `auto-trade-dashboard`만 사용하며, 세 가지 안전 조건을 모두 통과해야 합니다.
- 주문·체결 상태는 저장소와 키움 공식 체결 조회로 추적하고, 재시작 시 잔고·미체결 주문을 먼저 복구합니다.
- 컴퓨터 또는 실행 중인 프로그램을 끄면 대시보드·분석도 멈춥니다.
