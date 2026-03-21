"""Command-line interface for the PriveX starter."""

from __future__ import annotations

import argparse
import json
import os
import sys
from getpass import getpass
from typing import Any

from .client import PrivexAuthError, PrivexClient, PrivexError
from .config import SUPPORTED_NETWORKS


def _extract_portfolio_value(portfolio: dict[str, Any]) -> str:
    for key in ("allocatedBalance", "balance", "equity", "totalValue"):
        value = portfolio.get(key)
        if value not in (None, ""):
            return str(value)
    keys = ", ".join(sorted(portfolio.keys()))
    print(
        f"⚠ Portfolio value unknown — no known balance field. Response keys: {keys}",
        file=sys.stderr,
    )
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


def cmd_status(_: argparse.Namespace) -> int:
    """Health-style summary for agents and ops."""
    client = PrivexClient()
    cfg = client.config
    sub = client.get_active_subaccount()
    portfolio = client.get_portfolio()
    positions = client.get_positions()
    value = _extract_portfolio_value(portfolio)
    print(f"Network: {cfg.network} (chain_id={cfg.chain_id})")
    print(f"Subaccount: {sub.get('subaccountAddress', 'N/A')}")
    print(f"Portfolio value (raw field): {value}")
    print(f"Open positions: {len(positions)}")
    return 0


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


def _write_env(env_path: str, lines: list[tuple[str, str]]) -> None:
    """Write .env from list of (key, value)."""
    with open(env_path, "w") as f:
        for k, v in lines:
            f.write(f"{k}={v}\n")


def _read_env(env_path: str) -> list[tuple[str, str]]:
    """Read .env into list of (key, value), preserving order."""
    if not os.path.exists(env_path):
        return []
    lines: list[tuple[str, str]] = []
    with open(env_path) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or line.strip().startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                lines.append((k.strip(), v.strip()))
    return lines


def _set_env_var(env_path: str, key: str, value: str) -> None:
    """Update or add key=value in .env; preserve other vars."""
    pairs = _read_env(env_path)
    seen = {p[0] for p in pairs}
    new_pairs = [(k, v) for k, v in pairs if k != key]
    new_pairs.append((key, value))
    _write_env(env_path, new_pairs)


def cmd_init(args: argparse.Namespace) -> int:
    """Prompt for API key, network, optional subaccount, write .env, optionally run connect."""
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path) and not args.force:
        print(f".env already exists at {env_path}. Use --force to overwrite.", file=sys.stderr)
        return 1

    print("PriveX API setup")
    print("Get your API key from the PriveX platform and delegate subaccount access.")
    api_key = (args.api_key or getpass("API key: ")).strip()
    if not api_key:
        print("❌ API key is required.", file=sys.stderr)
        return 1

    network = (args.network or input(f"Network ({'/'.join(SUPPORTED_NETWORKS)}) [base]: ").strip()).lower()
    if not network:
        network = "base"
    if network not in SUPPORTED_NETWORKS:
        print(f"❌ Invalid network. Use one of: {', '.join(SUPPORTED_NETWORKS)}", file=sys.stderr)
        return 1

    subaccount = (args.subaccount or input("Subaccount address (optional, Enter to skip): ").strip()) or ""
    base_url = args.base_url or "https://tradingapi.prvx.io"
    timeout = args.timeout or "8"

    lines = [
        ("PRIVEX_BASE_URL", base_url),
        ("PRIVEX_API_KEY", api_key),
        ("PRIVEX_NETWORK", network),
        ("PRIVEX_SUBACCOUNT_ID", subaccount),
        ("PRIVEX_TIMEOUT", timeout),
    ]
    _write_env(env_path, lines)
    print(f"✔ Wrote {env_path}")

    if args.connect:
        print("Running connection test…", flush=True)
        return cmd_connect(args)
    print("Run `privex connect` to verify.")
    return 0


def cmd_network(args: argparse.Namespace) -> int:
    """Switch network (base/coti) and optionally run connect."""
    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(env_path):
        print("❌ No .env found. Run `privex init` first.", file=sys.stderr)
        return 1

    network = args.network.lower()
    if network not in SUPPORTED_NETWORKS:
        print(f"❌ Invalid network. Use one of: {', '.join(SUPPORTED_NETWORKS)}", file=sys.stderr)
        return 1

    _set_env_var(env_path, "PRIVEX_NETWORK", network)
    print(f"✔ Network set to {network}")

    if args.connect:
        print("Running connection test…", flush=True)
        return cmd_connect(args)
    print("Run `privex connect` to verify.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="privex", description="PriveX Trading API starter CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    connect_parser = subparsers.add_parser("connect", help="Validate and fetch portfolio + positions")
    connect_parser.set_defaults(func=cmd_connect)

    status_parser = subparsers.add_parser(
        "status",
        help="Print network, subaccount, portfolio summary, position count",
    )
    status_parser.set_defaults(func=cmd_status)

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

    init_parser = subparsers.add_parser(
        "init", help="Prompt for API key and optional subaccount, write .env"
    )
    init_parser.add_argument(
        "--api-key",
        default="",
        help="API key (if not set, prompt interactively)",
    )
    init_parser.add_argument(
        "--subaccount",
        default="",
        help="Subaccount address (optional)",
    )
    init_parser.add_argument(
        "--base-url",
        default="",
        help="Base URL (default: https://tradingapi.prvx.io)",
    )
    init_parser.add_argument(
        "--network",
        default="",
        choices=SUPPORTED_NETWORKS,
        help="Network: base or coti (default: base)",
    )
    init_parser.add_argument(
        "--timeout",
        default="",
        help="Request timeout in seconds (default: 8)",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing .env",
    )
    init_parser.add_argument(
        "--connect",
        action="store_true",
        help="Run connection test after writing .env",
    )
    init_parser.set_defaults(func=cmd_init)

    network_parser = subparsers.add_parser(
        "network",
        help="Switch network (base or coti); use anytime to change",
    )
    network_parser.add_argument(
        "network",
        choices=SUPPORTED_NETWORKS,
        help="Network to use",
    )
    network_parser.add_argument(
        "--connect",
        action="store_true",
        help="Run connection test after switching",
    )
    network_parser.set_defaults(func=cmd_network)

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
