"""Fetch and print open positions."""

from __future__ import annotations

import json

from privex.client import PrivexClient


def main() -> None:
    client = PrivexClient()
    positions = client.get_positions()
    print(json.dumps(positions, indent=2))


if __name__ == "__main__":
    main()
