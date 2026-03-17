"""Environment-based configuration for the PriveX client."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

NETWORK_TO_CHAIN_ID: dict[str, int] = {
    "base": 8453,
    "coti": 2632500,
}
SUPPORTED_NETWORKS = list(NETWORK_TO_CHAIN_ID.keys())


@dataclass(frozen=True)
class PrivexConfig:
    base_url: str
    api_key: str
    subaccount_id: str | None
    timeout: float
    network: str
    chain_id: int


def load_config() -> PrivexConfig:
    """Load configuration from environment and .env file."""
    load_dotenv()

    base_url = os.getenv("PRIVEX_BASE_URL", "https://tradingapi.prvx.io").strip().rstrip("/")
    api_key = os.getenv("PRIVEX_API_KEY", "").strip()
    subaccount_id = os.getenv("PRIVEX_SUBACCOUNT_ID", "").strip() or None
    timeout_raw = os.getenv("PRIVEX_TIMEOUT", "15").strip()
    network_raw = os.getenv("PRIVEX_NETWORK", "base").strip().lower()
    chain_id_raw = os.getenv("PRIVEX_CHAIN_ID", "").strip()

    if not api_key:
        raise ValueError(
            "Missing PRIVEX_API_KEY. Add it to your .env file and try again."
        )

    try:
        timeout = float(timeout_raw)
    except ValueError as exc:
        raise ValueError(
            f"Invalid PRIVEX_TIMEOUT value '{timeout_raw}'. Use a number like 15."
        ) from exc

    if chain_id_raw:
        try:
            chain_id = int(chain_id_raw)
        except ValueError as exc:
            raise ValueError(
                f"Invalid PRIVEX_CHAIN_ID value '{chain_id_raw}'. Use an integer (e.g. 8453 for Base)."
            ) from exc
        network = network_raw or "custom"
    else:
        if network_raw not in NETWORK_TO_CHAIN_ID:
            raise ValueError(
                f"Invalid PRIVEX_NETWORK '{network_raw}'. Use one of: {', '.join(SUPPORTED_NETWORKS)}"
            )
        network = network_raw
        chain_id = NETWORK_TO_CHAIN_ID[network]

    return PrivexConfig(
        base_url=base_url,
        api_key=api_key,
        subaccount_id=subaccount_id,
        timeout=timeout,
        network=network,
        chain_id=chain_id,
    )
