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
`# 1회 분석 후 종료합니다. 계속 자동 실행되는 명령은 아직 없습니다.`

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

## 5. 테스트

```cmd
.venv\Scripts\python.exe -m pytest -q
```

`# 기능 수정 후 자동 테스트를 실행합니다.`

## 현재 자동매매 상태

- 자동 주문 시작/중지 명령은 아직 구현 전입니다.
- 현재 자동화 관련 기능은 `strategy-dry-run`이며, 신호만 분석하고 주문하지 않습니다.
- 대시보드는 조회 전용입니다.
- 컴퓨터 또는 실행 중인 프로그램을 끄면 대시보드·분석도 멈춥니다.
