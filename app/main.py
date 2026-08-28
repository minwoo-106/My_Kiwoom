"""Command-line entry point for the mock-only MVP."""

from __future__ import annotations

import argparse

from app.config import ConfigurationError, Settings
from app.kiwoom.auth import AuthenticationError, KiwoomAuthClient
from app.kiwoom.account import AccountService
from app.kiwoom.client import KiwoomApiError, KiwoomReadClient
from app.kiwoom.market import MarketService
from app.kiwoom.orders import MANUAL_CONFIRMATION, ManualMockOrderService


def _mask_account(account: str) -> str:
    return f"******{account[-4:]}" if len(account) >= 4 else "[unavailable]"


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiwoom mock-trading MVP")
    parser.add_argument("command", choices=["auth", "accounts", "portfolio", "quote", "manual-buy", "manual-sell"], help="Action to run")
    parser.add_argument("--stock-code", default="005930", help="Six-digit KRX stock code for quote")
    parser.add_argument("--quantity", type=int, default=1, help="Manual order quantity; MVP only permits 1")
    parser.add_argument("--confirm", default="", help=f"Required only for orders: {MANUAL_CONFIRMATION}")
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
            print("Mock access token issued successfully.")
            print(f"Expires at: {token.expires_at}")
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
            print(f"Mock order accepted. Order number: {order.order_number}")
            print("Check fill status before any further order. This command does not retry orders.")
            return 0

        client = KiwoomReadClient(settings)
        try:
            if args.command == "accounts":
                accounts = AccountService(client).list_accounts()
                print("Mock account(s):")
                for account in accounts:
                    print(f"- {_mask_account(account)}")
            elif args.command == "portfolio":
                summary, holdings = AccountService(client).portfolio()
                print("Mock portfolio summary:")
                print(f"- Deposit: {summary['deposit']:,} KRW")
                print(f"- Estimated assets: {summary['estimated_assets']:,} KRW")
                print(f"- Total profit/loss: {summary['total_profit_loss']:,} KRW")
                print("Holdings:")
                for holding in holdings:
                    print(f"- {holding.code} {holding.name}: {holding.quantity:,} shares @ {holding.current_price:,} KRW")
            else:
                quote = MarketService(client).quote(args.stock_code)
                print(f"Quote: {quote.code} {quote.name}")
                print(f"- Current price: {quote.current_price:,} KRW")
                print(f"- Change: {quote.change:,} ({quote.change_rate}%)")
                print(f"- Volume: {quote.volume:,}")
        finally:
            client.close()
    except (ConfigurationError, AuthenticationError) as exc:
        print(f"Authentication failed: {exc}")
        return 1
    except (KiwoomApiError, ValueError) as exc:
        print(f"Request failed: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
