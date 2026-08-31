"""모의투자 전용 MVP의 명령줄 진입점입니다."""

from __future__ import annotations

import argparse
from datetime import datetime

from app.config import ConfigurationError, Settings
from app.kiwoom.auth import AuthenticationError, KiwoomAuthClient
from app.kiwoom.account import AccountService
from app.kiwoom.client import KiwoomApiError, KiwoomReadClient
from app.kiwoom.market import MarketService
from app.kiwoom.orders import AUTO_CONFIRMATION, MANUAL_CONFIRMATION, AutoMockOrderService, ManualMockOrderService
from app.monitoring.dashboard import DashboardDataProvider, run_dashboard, run_auto_dashboard
from app.storage.sqlite import TradingStore
from app.strategy.runner import DryRunStrategyRunner
from app.strategy.settings import TradingSettings


def _mask_account(account: str) -> str:
    return f"******{account[-4:]}" if len(account) >= 4 else "[unavailable]"


def main() -> int:
    parser = argparse.ArgumentParser(description="키움 모의투자 MVP")
    parser.add_argument("command", choices=["auth", "accounts", "portfolio", "quote", "manual-buy", "manual-sell", "dashboard", "auto-dashboard", "auto-trade", "auto-trade-dashboard", "strategy-dry-run", "strategy-loop", "daily-summary"], help="실행할 기능")
    parser.add_argument("--stock-code", default="005930", help="조회할 KRX 6자리 종목코드")
    parser.add_argument("--quantity", type=int, default=1, help="수동 주문 수량(MVP에서는 1주만 허용)")
    parser.add_argument("--confirm", default="", help=f"주문에만 필요한 확인 문구: {MANUAL_CONFIRMATION}")
    parser.add_argument("--refresh-seconds", type=float, default=10.0, help="대시보드 API 조회 주기(최소 5초, 기본 10초)")
    parser.add_argument("--once", action="store_true", help="대시보드를 한 번만 표시하고 종료")
    parser.add_argument("--loop-seconds", type=float, default=60.0, help="전략 반복 분석 주기(최소 30초, 기본 60초)")
    args = parser.parse_args()

    print("=" * 48)
    print("        KIWOOM MOCK TRADING MODE")
    print("=" * 48)
    try:
        settings = Settings.load()
        if args.command == "auth":
            client = KiwoomAuthClient(settings)
            try:
                token = client.request_access_token()
            finally:
                client.close()
            print("모의투자 접근 토큰 발급에 성공했습니다.")
            print(f"만료 시각: {token.expires_at}")
            return 0

        if args.command in {"manual-buy", "manual-sell"}:
            order_service = ManualMockOrderService(settings)
            try:
                if args.command == "manual-buy":
                    order = order_service.buy_market(code=args.stock_code, quantity=args.quantity, confirmation=args.confirm)
                else:
                    order = order_service.sell_market(code=args.stock_code, quantity=args.quantity, confirmation=args.confirm)
            finally:
                order_service.close()
            print(f"모의 주문이 접수되었습니다. 주문번호: {order.order_number}")
            print("추가 주문 전 체결 상태를 확인하세요. 이 명령은 주문을 재시도하지 않습니다.")
            return 0

        if args.command == "dashboard":
            if args.refresh_seconds < 5:
                raise ValueError("대시보드 조회 주기는 API 부담을 막기 위해 최소 5초여야 합니다.")
            provider = DashboardDataProvider(settings, args.stock_code)
            try:
                run_dashboard(provider, refresh_seconds=args.refresh_seconds, once=args.once)
            except KeyboardInterrupt:
                print("\n대시보드를 종료했습니다. 주문은 전혀 실행되지 않았습니다.")
            finally:
                provider.close()
            return 0
        if args.command == "auto-dashboard":
            if args.loop_seconds < 30: raise ValueError("통합 대시보드 분석 주기는 최소 30초여야 합니다.")
            try:
                run_auto_dashboard(settings, interval_seconds=args.loop_seconds)
            except KeyboardInterrupt:
                print("\n통합 DRY RUN을 종료했습니다. 주문은 전혀 실행되지 않았습니다.")
            return 0

        if args.command in {"auto-trade", "auto-trade-dashboard"}:
            trading = TradingSettings.load()
            if not trading.enable_mock_order or args.confirm != AUTO_CONFIRMATION:
                raise ValueError("자동 모의주문은 .env의 ENABLE_MOCK_ORDER=true 및 --confirm AUTO-MOCK-ORDER가 모두 필요합니다.")
            if not trading.market_holidays:
                raise ValueError("자동 모의주문은 공식 KRX 휴장일을 MARKET_HOLIDAYS에 먼저 입력해야 합니다.")
            if args.loop_seconds < 30: raise ValueError("자동 주문 분석 주기는 최소 30초여야 합니다.")
            if args.command == "auto-trade-dashboard":
                service = AutoMockOrderService(settings, runtime_confirmation=args.confirm)
                try:
                    run_auto_dashboard(settings, interval_seconds=args.loop_seconds, order_service=service, once=args.once)
                except KeyboardInterrupt:
                    print("\n모의 자동주문 대시보드를 종료했습니다. 미체결 주문은 취소되지 않으므로 체결 상태를 확인하세요.")
                finally:
                    service.close()
                return 0
            client = KiwoomReadClient(settings)
            store = TradingStore()
            service = AutoMockOrderService(settings, runtime_confirmation=args.confirm)
            try:
                runner = DryRunStrategyRunner(MarketService(client), trading, store, order_service=service)
                runner.restore_from_account()
                print("모의 자동주문 시작: Ctrl+C 종료 · 주문 접수 후 재전송하지 않고 체결만 추적합니다.")
                runner.run_forever(args.loop_seconds, lambda results: print(" | ".join(f"{r.symbol}:{r.decision.status}" for r in results)))
            except KeyboardInterrupt:
                print("\n모의 자동주문 루프를 종료했습니다. 미체결 주문은 취소하지 않았으므로 체결 상태를 확인하세요.")
            finally:
                service.close(); store.close(); client.close()
            return 0

        if args.command == "daily-summary":
            store = TradingStore()
            try:
                summary = store.daily_summary(datetime.now().strftime("%Y-%m-%d"))
            finally:
                store.close()
            print(f"오늘 결과 ({summary.date}) · 모의 자동매매 기록")
            print(f"- 신호 {summary.signals}회 / 차단 {summary.blocked}회 / 매수 {summary.buys}회 / 매도 {summary.sells}회")
            print(f"- 실현손익: {summary.realized_profit:,}원")
            return 0

        client = KiwoomReadClient(settings)
        try:
            if args.command in {"strategy-dry-run", "strategy-loop"}:
                if args.command == "strategy-loop" and args.loop_seconds < 30: raise ValueError("전략 반복 주기는 최소 30초여야 합니다.")
                store = TradingStore()
                try:
                    runner = DryRunStrategyRunner(MarketService(client), TradingSettings.load(), store)
                    runner.restore_from_account()
                    if args.command == "strategy-loop":
                        print("Trend Pullback V1 Multi · DRY RUN 반복 실행 (Ctrl+C 종료, 주문 전송 없음)")
                        runner.run_forever(args.loop_seconds, lambda results: print(" | ".join(f"{r.symbol}:{r.decision.status}" for r in results)))
                        return 0
                    results = runner.run_once()
                finally:
                    store.close()
                print("Trend Pullback V1 Multi · DRY RUN (주문 전송 없음)")
                for result in results:
                    print(f"- {result.symbol}: {result.decision.status} · {result.decision.reason}")
                return 0
            if args.command == "accounts":
                accounts = AccountService(client).list_accounts()
                print("모의투자 계좌:")
                for account in accounts:
                    print(f"- {_mask_account(account)}")
            elif args.command == "portfolio":
                summary, holdings = AccountService(client).portfolio()
                print("모의투자 잔고 요약:")
                print(f"- 예수금: {summary['deposit']:,}원")
                print(f"- 추정자산: {summary['estimated_assets']:,}원")
                print(f"- 총 손익: {summary['total_profit_loss']:,}원")
                print("보유종목:")
                for holding in holdings:
                    print(f"- {holding.code} {holding.name}: {holding.quantity:,}주 / 현재가 {holding.current_price:,}원")
            else:
                quote = MarketService(client).quote(args.stock_code)
                print(f"현재가: {quote.code} {quote.name}")
                print(f"- 현재가: {quote.current_price:,}원")
                print(f"- 전일 대비: {quote.change:,}원 ({quote.change_rate}%)")
                print(f"- 거래량: {quote.volume:,}")
        finally:
            client.close()
    except (ConfigurationError, AuthenticationError) as exc:
        print(f"인증 실패: {exc}")
        return 1
    except (KiwoomApiError, ValueError) as exc:
        print(f"요청 실패: {exc}")
        return 1
    except KeyboardInterrupt:
        print("\nDRY RUN 루프를 종료했습니다. 주문은 전혀 실행되지 않았습니다.")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
