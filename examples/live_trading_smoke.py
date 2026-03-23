#!/usr/bin/env python3
"""
Live smoke test for PriveX trading-related API endpoints.

  - Read-only by default (safe): health, permissions, account, markets, pricing, solvers, positions.
  - Optional --live: places a small MARKET order then closes it (REAL MONEY — requires confirmation).

Requires a configured .env (see README). Run from repo root with venv active:

  .venv/bin/python examples/live_trading_smoke.py
  .venv/bin/python examples/live_trading_smoke.py --live --i-confirm-risk
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

# Allow running as `python examples/live_trading_smoke.py` from repo root
if __name__ == "__main__":
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

from privex import PrivexClient, PrivexError


def _short(obj: Any, limit: int = 800) -> str:
    s = json.dumps(obj, indent=2, default=str)
    if len(s) > limit:
        return s[:limit] + "\n... (truncated)"
    return s


def _ok(name: str, fn: Any) -> None:
    print(f"\n=== {name} ===")
    try:
        out = fn() if callable(fn) else fn
        print(_short(out))
    except Exception as exc:  # noqa: BLE001 — surface any API failure
        print(f"FAIL: {exc}")
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="PriveX trading API live smoke test")
    parser.add_argument(
        "--symbol",
        default=os.getenv("PRIVEX_SMOKE_SYMBOL", "ETHUSDT"),
        help="Market symbol as returned by the venue (e.g. ETHUSDT on COTI, ETH-USD on Base)",
    )
    parser.add_argument(
        "--solver",
        default=os.getenv("PRIVEX_SMOKE_SOLVER", "PERPS_HUB"),
        help="Solver for solver endpoints (default PERPS_HUB)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Place a small real MARKET order and close it (costs fees / margin)",
    )
    parser.add_argument(
        "--i-confirm-risk",
        action="store_true",
        help="Required with --live: you accept loss of funds / fees on a real account",
    )
    parser.add_argument(
        "--quantity",
        type=float,
        default=float(os.getenv("PRIVEX_SMOKE_QTY", "0.001")),
        help="Order quantity for --live (default 0.001 — must meet venue minimums)",
    )
    parser.add_argument(
        "--leverage",
        type=float,
        default=float(os.getenv("PRIVEX_SMOKE_LEV", "1")),
        help="Leverage for --live (default 1)",
    )
    parser.add_argument(
        "--side",
        choices=("LONG", "SHORT"),
        default="LONG",
        help="Position side for --live",
    )
    args = parser.parse_args()

    client = PrivexClient()
    sub = client.get_active_subaccount()
    chain_id = int(sub["chainId"])
    addr = sub["subaccountAddress"]

    print("PriveX trading smoke test")
    print(f"Network chain_id={chain_id} subaccount={addr[:10]}…{addr[-6:]}")

    # --- Read-only (Swagger trading-related surface) ---
    _ok("GET / (health)", lambda: client.health())
    _ok("POST /v1/api-keys/list-permissions", lambda: client.get_api_key_permissions())
    _ok("GET /v1/accounts/subaccount/details", lambda: client.get_subaccount_details())
    _ok("GET /v1/accounts/subaccount/balance", lambda: client.get_portfolio())
    _ok("GET /v1/markets/aggregated/{chainId}", lambda: client.get_aggregated_markets())
    market_row = client.get_market(args.symbol)
    _ok(f"GET /v1/markets/{{chainId}}/by-symbol/{args.symbol}", lambda: market_row)
    mid = int(market_row.get("id") or 0)
    if mid:
        _ok(
            "GET /v1/solvers/notional-cap",
            lambda: client.get_solver_notional_cap(solver=args.solver, market_id=mid),
        )
    _ok(f"GET /v1/pricing/mark-price/{args.symbol}", lambda: client.get_mark_price(args.symbol))
    _ok(f"GET /v1/pricing/last-price/{args.symbol}", lambda: client.get_last_price(args.symbol))
    _ok(
        "GET /v1/solvers/locked-parameters",
        lambda: client.get_solver_locked_parameters(
            solver=args.solver,
            market_name=args.symbol,
            leverage=args.leverage,
        ),
    )
    _ok(
        "GET /v1/solvers/price-range",
        lambda: client.get_solver_price_range(solver=args.solver, market_name=args.symbol),
    )
    _ok(
        "GET /v1/solvers/open-interest",
        lambda: client.get_solver_open_interest(solver=args.solver),
    )

    positions = client.get_positions()
    _ok("GET /v1/positions/all", lambda: positions)

    # Position status endpoints need real IDs from an open position
    sample_pid: str | None = None
    for p in positions:
        st = str(p.get("status", ""))
        if st in ("OPENED", "PENDING", "RESERVED") or p.get("id") is not None:
            sample_pid = str(p.get("tempId") or p.get("id") or "")
            break

    if sample_pid:
        pid = sample_pid
        _ok(
            "GET /v1/positions/open-request/status",
            lambda: client.get_position_open_status(pid),
        )
    else:
        print("\n=== GET /v1/positions/open-request/status ===\nSKIP (no open position id to query)")

    # TP/SL list (POST) — only if we have quote ids
    quote_ids_for_tpsl: list[str] = []
    for p in positions:
        qid = p.get("id")
        if qid is not None:
            quote_ids_for_tpsl.append(str(qid))
    if quote_ids_for_tpsl:
        _ok(
            "POST /v1/tpsl/list",
            lambda: client.list_tpsl_for_positions(quote_ids_for_tpsl[:5]),
        )
    else:
        print("\n=== POST /v1/tpsl/list ===\nSKIP (no quote ids)")

    print("\n=== POST /v1/tpsl/create ===\nSKIP (requires signed payload per API — not automated here)")

    # Trade write endpoints: only with --live
    if not args.live:
        print("\n--- Read-only phase complete. ---")
        print("To run a REAL small market order + close, add: --live --i-confirm-risk")
        print("(Also review --quantity / --leverage / min market size on the venue.)")
        return 0

    if not args.i_confirm_risk:
        print("Refusing --live without --i-confirm-risk.", file=sys.stderr)
        return 2

    print("\n*** LIVE TRADING: real funds at risk (fees, margin, liquidation). ***")
    input("Type Enter to continue or Ctrl+C to abort... ")

    market_id = int(market_row.get("id") or 0)
    if not market_id:
        print("Could not read market id from get_market response.", file=sys.stderr)
        return 1

    payload = {
        "marketId": market_id,
        "subaccountAddress": addr,
        "chainId": chain_id,
        "leverage": args.leverage,
        "positionType": args.side,
        "orderType": "MARKET",
        "quantity": args.quantity,
        "slippage": 0.05,
        "solver": args.solver,
    }

    print("\n=== POST /v1/trade/create-position ===")
    print(_short(payload, 400))
    create_out = client.place_order(payload)
    print(_short(create_out))

    # Poll for a position / quote id
    quote_id: int | None = None
    for _ in range(12):
        time.sleep(2)
        positions_after = client.get_positions()
        for p in positions_after:
            mid = p.get("marketId")
            if mid == market_id and p.get("id") is not None:
                quote_id = int(p["id"])
                break
        if quote_id is not None:
            break
    if quote_id is None:
        print(
            "Could not resolve quoteId from positions after open; check UI / API manually.",
            file=sys.stderr,
        )
        return 1

    print(f"\nResolved quoteId={quote_id} — closing via POST /v1/trade/close-position.")

    print(
        "\n=== GET /v1/positions/close-request/status ===\n"
        "SKIP (needs closeRequestId from the close flow / sequencer — call manually if needed)"
    )

    close_payload = {
        "quoteId": quote_id,
        "quantityToClose": args.quantity,
        "chainId": chain_id,
        "orderType": "MARKET",
        "slippage": 0.05,
    }
    print("\n=== POST /v1/trade/close-position ===")
    print(_short(close_payload))
    close_out = client.close_position(close_payload)
    print(_short(close_out))

    print("\n=== POST /v1/trade/cancel-quote / cancel-close-request ===")
    print(
        "SKIP by default — only valid for pending quotes/close requests; "
        "calling with wrong ids can error harmlessly but is omitted here."
    )

    print("\n--- Live smoke test finished. Verify balances in the PriveX UI. ---")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PrivexError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        raise SystemExit(1)
