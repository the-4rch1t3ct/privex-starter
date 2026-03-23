"""Minimal PriveX API client."""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import PrivexConfig, load_config


class PrivexError(Exception):
    """Base PriveX client error."""


class PrivexAuthError(PrivexError):
    """Authentication or permission-related failure."""


class PrivexClient:
    """Small client for core PriveX Trading API operations."""

    def __init__(self, config: PrivexConfig | None = None):
        self.config = config or load_config()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )
        # Idempotent methods only (default); POST is not retried to avoid duplicate orders.
        retry = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=(500, 502, 503, 504),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self._subaccount_cache: dict[str, Any] | None = None

    def reset_cache(self) -> None:
        """Clear resolved subaccount cache (e.g. after changing .env or network)."""
        self._subaccount_cache = None

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> Any:
        url = f"{self.config.base_url}{path}"
        headers: dict[str, str] = {}
        if authenticated:
            headers["x-api-key"] = self.config.api_key

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                headers=headers,
                timeout=self.config.timeout,
            )
        except requests.RequestException as exc:
            raise PrivexError(
                "Network error while calling PriveX API. Check connectivity and PRIVEX_BASE_URL."
            ) from exc

        payload: Any
        try:
            payload = response.json() if response.text else {}
        except ValueError as exc:
            raise PrivexError(
                f"PriveX API returned non-JSON response (HTTP {response.status_code})."
            ) from exc

        if isinstance(payload, dict) and "success" in payload:
            success = payload.get("success")
            if success is not True:
                error_block = payload.get("error") or {}
                message = (
                    error_block.get("message")
                    or payload.get("statusMessage")
                    or "API request failed."
                )
                code = error_block.get("code")
                if response.status_code in (401, 403):
                    raise PrivexAuthError(
                        f"Authentication failed - check API key or permissions. {message}"
                    )
                if code:
                    raise PrivexError(f"{message} (code: {code})")
                raise PrivexError(message)
            return payload.get("data")

        if response.status_code in (401, 403):
            message = payload.get("message") if isinstance(payload, dict) else None
            raise PrivexAuthError(
                f"Authentication failed - check API key or permissions. {message or ''}".strip()
            )

        if not response.ok:
            details = payload if isinstance(payload, dict) else response.text
            raise PrivexError(f"PriveX API error (HTTP {response.status_code}): {details}")

        return payload

    def health(self) -> Any:
        return self._request("GET", "/", authenticated=False)

    def get_api_key_permissions(self) -> dict[str, Any]:
        data = self._request("POST", "/v1/api-keys/list-permissions")
        if not isinstance(data, dict):
            raise PrivexError("Unexpected permissions response format from PriveX.")
        return data

    def _resolve_subaccount(self) -> dict[str, Any]:
        if self._subaccount_cache:
            if self._subaccount_cache.get("chainId") != self.config.chain_id:
                self._subaccount_cache = None
            else:
                return self._subaccount_cache

        permissions = self.get_api_key_permissions()
        if permissions.get("isValid") is False:
            raise PrivexAuthError("Authentication failed - API key is invalid.")

        subaccounts = permissions.get("subaccounts") or []
        if not subaccounts:
            raise PrivexAuthError(
                "API key is valid but has no delegated subaccounts. Grant permissions first."
            )

        # Restrict to the configured network (chain)
        chain_matches = [s for s in subaccounts if s.get("chainId") == self.config.chain_id]
        if not chain_matches:
            raise PrivexAuthError(
                f"No subaccount on this network (chain_id={self.config.chain_id}). "
                "Check PRIVEX_NETWORK or delegate access for Base/COTI."
            )

        wanted = self.config.subaccount_id
        if wanted:
            matches = [
                item
                for item in chain_matches
                if str(item.get("subaccountAddress", "")).lower() == wanted.lower()
            ]
            if not matches:
                raise PrivexAuthError(
                    "PRIVEX_SUBACCOUNT_ID not found in API key delegations. "
                    "Check subaccount address and permissions."
                )
            selected = matches[0]
        elif len(chain_matches) == 1:
            selected = chain_matches[0]
        else:
            choices = ", ".join(str(s.get("subaccountAddress")) for s in chain_matches)
            raise PrivexError(
                "Multiple subaccounts available. Set PRIVEX_SUBACCOUNT_ID in .env. "
                f"Available: {choices}"
            )

        if "chainId" not in selected:
            raise PrivexError(
                "PriveX did not return chainId for selected subaccount. Cannot continue."
            )
        self._subaccount_cache = selected
        return selected

    def get_active_subaccount(self) -> dict[str, Any]:
        """Return selected delegated subaccount with chainId and permissions."""
        return self._resolve_subaccount()

    def get_portfolio(self) -> dict[str, Any]:
        subaccount = self._resolve_subaccount()
        data = self._request(
            "GET",
            "/v1/accounts/subaccount/balance",
            params={
                "subaccountAddress": subaccount["subaccountAddress"],
                "chainId": subaccount["chainId"],
            },
        )
        if not isinstance(data, dict):
            raise PrivexError("Unexpected portfolio response format from PriveX.")
        return data

    def get_positions(self) -> list[dict[str, Any]]:
        subaccount = self._resolve_subaccount()
        data = self._request(
            "GET",
            "/v1/positions/all",
            params={
                "subaccountAddress": subaccount["subaccountAddress"],
                "chainId": subaccount["chainId"],
            },
        )
        if not isinstance(data, list):
            raise PrivexError("Unexpected positions response format from PriveX.")
        return data

    def get_market(self, symbol: str) -> dict[str, Any]:
        subaccount = self._resolve_subaccount()
        data = self._request(
            "GET",
            f"/v1/markets/{subaccount['chainId']}/by-symbol/{symbol}",
        )
        if not isinstance(data, dict):
            raise PrivexError("Unexpected market response format from PriveX.")
        return data

    def get_aggregated_markets(self) -> Any:
        return self._request(
            "GET",
            f"/v1/markets/aggregated/{self.config.chain_id}",
            authenticated=False,
        )

    def get_mark_price(self, symbol: str) -> Any:
        return self._request(
            "GET",
            f"/v1/pricing/mark-price/{symbol}",
            authenticated=False,
        )

    def get_last_price(self, symbol: str) -> Any:
        return self._request(
            "GET",
            f"/v1/pricing/last-price/{symbol}",
            authenticated=False,
        )

    def get_subaccount_details(self) -> dict[str, Any]:
        subaccount = self._resolve_subaccount()
        data = self._request(
            "GET",
            "/v1/accounts/subaccount/details",
            params={
                "subaccountAddress": subaccount["subaccountAddress"],
                "chainId": subaccount["chainId"],
            },
        )
        if not isinstance(data, dict):
            raise PrivexError("Unexpected subaccount details response format from PriveX.")
        return data

    def get_position_open_status(self, position_id: str) -> Any:
        subaccount = self._resolve_subaccount()
        return self._request(
            "GET",
            "/v1/positions/open-request/status",
            params={
                "positionId": position_id,
                "chainId": subaccount["chainId"],
            },
        )

    def get_position_close_status(self, close_request_id: str) -> Any:
        subaccount = self._resolve_subaccount()
        return self._request(
            "GET",
            "/v1/positions/close-request/status",
            params={
                "closeRequestId": close_request_id,
                "chainId": subaccount["chainId"],
            },
        )

    def close_position(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/v1/trade/close-position", json_body=payload)

    def cancel_quote(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/v1/trade/cancel-quote", json_body=payload)

    def cancel_close_request(self, payload: dict[str, Any]) -> Any:
        return self._request("POST", "/v1/trade/cancel-close-request", json_body=payload)

    def list_tpsl_for_positions(self, quote_ids: list[str]) -> Any:
        subaccount = self._resolve_subaccount()
        return self._request(
            "POST",
            "/v1/tpsl/list",
            json_body={"chainId": subaccount["chainId"], "quoteIds": quote_ids},
        )

    def get_solver_locked_parameters(
        self,
        *,
        solver: str,
        market_name: str,
        leverage: float,
    ) -> Any:
        return self._request(
            "GET",
            "/v1/solvers/locked-parameters",
            params={
                "solver": solver,
                "chainId": self.config.chain_id,
                "marketName": market_name,
                "leverage": leverage,
            },
            authenticated=False,
        )

    def get_solver_price_range(
        self,
        *,
        solver: str,
        market_name: str,
    ) -> Any:
        return self._request(
            "GET",
            "/v1/solvers/price-range",
            params={
                "solver": solver,
                "chainId": self.config.chain_id,
                "marketName": market_name,
            },
            authenticated=False,
        )

    def get_solver_open_interest(self, *, solver: str) -> Any:
        return self._request(
            "GET",
            "/v1/solvers/open-interest",
            params={"solver": solver, "chainId": self.config.chain_id},
            authenticated=False,
        )

    def get_solver_notional_cap(self, *, solver: str, market_id: int) -> Any:
        return self._request(
            "GET",
            "/v1/solvers/notional-cap",
            params={
                "solver": solver,
                "chainId": self.config.chain_id,
                "marketId": market_id,
            },
            authenticated=False,
        )

    def place_order(self, payload: dict[str, Any]) -> Any:
        validate_create_position_payload(payload)
        return self._request(
            "POST",
            "/v1/trade/create-position",
            json_body=payload,
        )


def validate_create_position_payload(payload: dict[str, Any]) -> None:
    """Lightweight checks before POST /v1/trade/create-position."""
    required = (
        "marketId",
        "subaccountAddress",
        "chainId",
        "leverage",
        "positionType",
        "orderType",
        "quantity",
    )
    missing = [k for k in required if k not in payload or payload[k] is None]
    if missing:
        raise PrivexError(f"Missing or null order fields: {', '.join(missing)}")

    mid = payload["marketId"]
    if not isinstance(mid, (int, float)) or mid <= 0:
        raise PrivexError("marketId must be a positive number.")

    if not str(payload.get("subaccountAddress", "")).strip():
        raise PrivexError("subaccountAddress must be non-empty.")

    cid = payload["chainId"]
    if not isinstance(cid, (int, float)) or cid <= 0:
        raise PrivexError("chainId must be a positive number.")

    lev = payload["leverage"]
    if not isinstance(lev, (int, float)) or lev <= 0:
        raise PrivexError("leverage must be positive.")

    pt = payload["positionType"]
    if pt not in ("LONG", "SHORT"):
        raise PrivexError("positionType must be LONG or SHORT.")

    ot = payload["orderType"]
    if ot not in ("MARKET", "LIMIT"):
        raise PrivexError("orderType must be MARKET or LIMIT.")

    qty = payload["quantity"]
    if not isinstance(qty, (int, float)) or qty <= 0:
        raise PrivexError("quantity must be positive.")

    if ot == "LIMIT":
        lp = payload.get("limitPrice")
        if lp is None or (isinstance(lp, (int, float)) and lp <= 0):
            raise PrivexError("limitPrice is required and must be positive for LIMIT orders.")


def get_portfolio_safe(client: PrivexClient) -> dict[str, Any] | None:
    """Return portfolio or None on auth failure. Useful for agent loops."""
    try:
        return client.get_portfolio()
    except PrivexAuthError:
        return None
