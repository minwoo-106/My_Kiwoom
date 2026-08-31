# 키움 REST API 모의투자 MVP

이 프로젝트는 키움 REST API의 **모의투자 환경만** 사용합니다.
`https://api.kiwoom.com` 운영 서버는 사용할 수 없으며, `https://mockapi.kiwoom.com`만 허용합니다.

## 인증 설정

1. `.env.example`을 `.env`로 복사합니다.
2. `.env`에는 **모의투자용** App Key와 Secret Key만 입력합니다.
3. `.env`는 공유하거나 Git에 커밋하지 않습니다.
4. 다음 명령을 실행합니다.

   ```powershell
   .\.venv\Scripts\python.exe -m app.main auth
   ```

성공하면 모의투자 배너와 토큰 만료 시각만 표시합니다. 토큰 자체는 출력하지 않습니다.

## 읽기 전용 모의투자 조회

```powershell
.\.venv\Scripts\python.exe -m app.main accounts
.\.venv\Scripts\python.exe -m app.main portfolio
.\.venv\Scripts\python.exe -m app.main quote --stock-code 005930
```

터미널에서는 계좌번호를 마스킹합니다. 위 명령은 모두 읽기 전용이며 모의 서버만 사용합니다.

## 수동 모의주문(자동 주문 아님)

MVP는 KRX 시장가 1주 주문만 허용하며, 명시적인 확인 문구가 필요합니다. 모의계좌 잔고를 변경할 의도가 있을 때만 실행하세요.

```powershell
.\.venv\Scripts\python.exe -m app.main manual-buy --stock-code 005930 --quantity 1 --confirm MOCK-ORDER
```

주문 요청은 절대 재시도하지 않습니다. 추가 주문 전 반드시 주문·체결 상태를 확인하세요.

## 실시간 터미널 대시보드

아래 명령은 **모의 API의 잔고와 시세만 읽어** 같은 터미널 화면을 갱신합니다. 주문·전략 실행 기능은 포함하지 않습니다. 종료하려면 `Ctrl+C`를 누르세요.

```powershell
.\.venv\Scripts\python.exe -m app.main dashboard --stock-code 005930
```

대시보드를 한 번만 출력해 화면을 확인하려면 다음처럼 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m app.main dashboard --stock-code 005930 --once
```

기본 조회 주기는 10초이며, API 부담을 막기 위해 5초보다 짧게 설정할 수 없습니다. VS Code 터미널은 가로 110칸, 세로 38줄 이상으로 넓히면 모든 패널이 가장 잘 보입니다.

`dashboard`는 단일 종목 조회 화면입니다. 5종목 전략과 통합 화면은 아래의 `auto-dashboard`를 사용하세요. 모든 화면은 기본적으로 주문을 보내지 않습니다.

## Trend Pullback V1 Multi (DRY RUN)

기본 감시 종목은 삼성전자·SK하이닉스·현대차·KB금융·서울식품의 5개입니다. 키움 공식 `ka10080` 15분봉을 이용해 상승 추세, 눌림, 반등 조건을 분석하지만 **주문은 전송하지 않습니다**.

```powershell
.\.venv\Scripts\python.exe -m app.main strategy-dry-run
.\.venv\Scripts\python.exe -m app.main strategy-loop --loop-seconds 60
.\.venv\Scripts\python.exe -m app.main auto-dashboard --loop-seconds 60
.\.venv\Scripts\python.exe -m app.main daily-summary
```

`auto-dashboard` 하나만 실행하면 5종목의 완료 15분봉·전략 상태·위험 차단 사유·계좌 현황·당일 결과를 한 화면에서 봅니다. 장 마감·주말·등록 휴장일에는 시세 분석 요청을 멈추고 당일 요약만 표시합니다. `strategy-dry-run`과 `strategy-loop`도 주문을 보내지 않습니다.

## 자동 모의주문 (기본 비활성)

자동 모의주문은 구현되어 있지만, 기본 설정에서는 절대로 켜지지 않습니다. 실행 전 공식 KRX 휴장일을 `.env`의 `MARKET_HOLIDAYS`에 입력해야 하고, `ENABLE_MOCK_ORDER=true`와 실행 시 확인문구가 모두 필요합니다. 실계좌 서버는 코드상 허용되지 않습니다.

```cmd
.venv\Scripts\python.exe -m app.main auto-trade-dashboard --loop-seconds 60 --confirm AUTO-MOCK-ORDER
```

주문은 모의 KRX 시장가 1주만 가능하며, 접수 뒤 자동 재전송하지 않고 공식 `ka10076` 체결 조회로 상태를 확인합니다. 이 명령은 모의계좌 잔고를 바꿀 수 있으므로, 실제 실행 전에는 반드시 별도 승인을 받습니다.

화면과 API 상태만 한 번 확인하려면 `--once`를 추가할 수 있습니다. 장 마감·주말·등록 휴장일에는 주문을 보내지 않습니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## 구현 기준

새 API를 구현하기 전에는 항상 최신 키움 공식 REST API 가이드를 확인합니다.
https://openapi.kiwoom.com/guide/apiguide
