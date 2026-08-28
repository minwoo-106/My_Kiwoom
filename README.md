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

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## 구현 기준

새 API를 구현하기 전에는 항상 최신 키움 공식 REST API 가이드를 확인합니다.
https://openapi.kiwoom.com/guide/apiguide
