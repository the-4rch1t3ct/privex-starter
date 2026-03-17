"""Smoke test: authenticated portfolio call + raw output."""

from __future__ import annotations

import json

from privex.client import PrivexClient


def main() -> None:
    client = PrivexClient()
    portfolio = client.get_portfolio()
    print(json.dumps(portfolio, indent=2))


if __name__ == "__main__":
    main()
