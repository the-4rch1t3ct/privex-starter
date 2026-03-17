"""Example market order placement."""

from __future__ import annotations

import argparse
import json

from privex.client import PrivexClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market-id", type=int, required=True)
    parser.add_argument("--side", choices=["LONG", "SHORT"], required=True)
    parser.add_argument("--quantity", type=float, required=True)
    parser.add_argument("--leverage", type=float, required=True)
    parser.add_argument("--slippage", type=float, default=0.01)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
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
    response = client.place_order(payload)
    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()
