"""Minimal PriveX API client."""

from __future__ import annotations

from typing import Any

import requests

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
        self._subaccount_cache: dict[str, Any] | None = None

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
            return self._subaccount_cache

        permissions = self.get_api_key_permissions()
        if permissions.get("isValid") is False:
            raise PrivexAuthError("Authentication failed - API key is invalid.")

        subaccounts = permissions.get("subaccounts") or []
        if not subaccounts:
            raise PrivexAuthError(
                "API key is valid but has no delegated subaccounts. Grant permissions first."
            )

        wanted = self.config.subaccount_id
        if wanted:
            matches = [
                item
                for item in subaccounts
                if str(item.get("subaccountAddress", "")).lower() == wanted.lower()
            ]
            if not matches:
                raise PrivexAuthError(
                    "PRIVEX_SUBACCOUNT_ID not found in API key delegations. "
                    "Check subaccount address and permissions."
                )
            selected = matches[0]
        elif len(subaccounts) == 1:
            selected = subaccounts[0]
        else:
            choices = ", ".join(str(item.get("subaccountAddress")) for item in subaccounts)
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

    def place_order(self, payload: dict[str, Any]) -> Any:
        return self._request(
            "POST",
            "/v1/trade/create-position",
            json_body=payload,
        )
