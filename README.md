# 키움 REST API 모의투자 자동매매 MVP

키움증권 REST API의 **모의투자 환경만** 사용하는 Python 자동매매 검증 프로젝트입니다. 실계좌 주문 기능과 운영 서버 연결은 구현하지 않습니다.

## 현재 가능한 것

- 모의 API 인증, 계좌·보유종목·현재가 조회
- 삼성전자·SK하이닉스·현대차·KB금융·서울식품 5종목의 완료 15분봉 분석
- 통합 CMD 대시보드: 계좌, 종목명·현재가·등락률, 전략 상태, 체결 기록, API 상태 표시
- `Trend Pullback V1 Multi` 기반 모의 자동주문: 추세·눌림·반등 조건과 위험관리 통과 시에만 시장가 1주
- 주문 접수 뒤 공식 체결 조회, SQLite 기록, 재시작 시 잔고·미체결 상태 복구
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
- 이 프로젝트는 수익을 보장하지 않는 모의 검증 도구입니다. 뉴스는 참고하되, 충분한 테스트 기록 없이 규칙을 바꾸지 않습니다.

## 테스트

```cmd
.venv\Scripts\python.exe -m pytest -q
```

## 공식 문서

[키움증권 REST API 가이드](https://openapi.kiwoom.com/guide/apiguide)
