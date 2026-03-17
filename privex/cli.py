"""Command-line interface for the PriveX starter."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .client import PrivexAuthError, PrivexClient, PrivexError


def _extract_portfolio_value(portfolio: dict[str, Any]) -> str:
    for key in ("allocatedBalance", "balance", "equity", "totalValue"):
        value = portfolio.get(key)
        if value not in (None, ""):
            return str(value)
    return "N/A"


def _print_positions(positions: list[dict[str, Any]]) -> None:
    if not positions:
        print("No open positions.")
        return

    print(f"Open positions: {len(positions)}")
    for idx, pos in enumerate(positions, start=1):
        symbol = pos.get("symbol") or pos.get("marketSymbol") or pos.get("marketId", "unknown")
        side = pos.get("positionType", "N/A")
        qty = pos.get("quantity", "N/A")
        status = pos.get("status", "N/A")
        print(f"{idx}. {symbol} | {side} | qty={qty} | status={status}")


def cmd_connect(_: argparse.Namespace) -> int:
    client = PrivexClient()
    portfolio = client.get_portfolio()
    positions = client.get_positions()

    print("✔ Connected to PriveX")
    print(f"Portfolio Value: {_extract_portfolio_value(portfolio)}")
    print(f"Open Positions: {len(positions)}")
    return 0


def cmd_positions(_: argparse.Namespace) -> int:
    client = PrivexClient()
    positions = client.get_positions()
    _print_positions(positions)
    return 0


def cmd_order(args: argparse.Namespace) -> int:
    client = PrivexClient()
    subaccount = client.get_active_subaccount()
    payload = {
        "marketId": args.market_id,
        "subaccountAddress": subaccount["subaccountAddress"],
        "chainId": subaccount["chainId"],
        "leverage": args.leverage,
        "positionType": args.side,
        "orderType": "MARKET",
        "quantity": args.quantity,
        "slippage": args.slippage,
    }
    result = client.place_order(payload)
    print("Order submitted.")
    print(json.dumps(result, indent=2))
    return 0


def cmd_quickstart(_: argparse.Namespace) -> int:
    return cmd_connect(_)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="privex", description="PriveX Trading API starter CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    connect_parser = subparsers.add_parser("connect", help="Validate and fetch portfolio + positions")
    connect_parser.set_defaults(func=cmd_connect)

    positions_parser = subparsers.add_parser("positions", help="List open positions")
    positions_parser.set_defaults(func=cmd_positions)

    order_parser = subparsers.add_parser("order", help="Place a basic market order")
    order_parser.add_argument("--market-id", type=int, required=True, help="Market ID (integer)")
    order_parser.add_argument(
        "--side",
        choices=["LONG", "SHORT"],
        required=True,
        help="Position side",
    )
    order_parser.add_argument("--quantity", type=float, required=True, help="Order quantity")
    order_parser.add_argument("--leverage", type=float, required=True, help="Leverage value")
    order_parser.add_argument(
        "--slippage",
        type=float,
        default=0.01,
        help="Slippage tolerance for market orders (default 0.01)",
    )
    order_parser.set_defaults(func=cmd_order)

    quickstart_parser = subparsers.add_parser(
        "quickstart", help="Check config and run connection test"
    )
    quickstart_parser.set_defaults(func=cmd_quickstart)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    except PrivexAuthError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    except PrivexError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
