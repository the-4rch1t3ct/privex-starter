# PriveX Trading API Starter

Fastest way to connect a self-hosted agent to PriveX.

This repo gives you a minimal Python client and CLI with one goal: prove authenticated connectivity with one command.

## Quickstart

```bash
git clone https://github.com/the-4rch1t3ct/privex-starter
cd privex-starter
make setup
make init
```

`make setup` creates a virtual environment and installs dependencies (avoids system Python / externally-managed-environment). `make init` runs the onboarding: prompts for API key, **network (Base or COTI)**, and optional subaccount, writes `.env`, then runs the connection test.

Without Make (venv + editable install so the `privex` CLI is available):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/privex init --connect
```

Runtime-only deps (no package install): `requirements.txt`. For the CLI and `import privex`, use `requirements-dev.txt` (includes editable `-e .`) or `pip install -e .` after installing `requirements.txt`.

## Expected Output

```text
✔ Connected to PriveX
Portfolio Value: 1000000000000000000
Open Positions: 2
```

If something is wrong, you get a clear error, for example:

```text
❌ Authentication failed - check API key or permissions.
```

## API Discovery (from Swagger)

Swagger source: [https://tradingapi.prvx.io/api#/](https://tradingapi.prvx.io/api#/)  
OpenAPI JSON: [https://tradingapi.prvx.io/api-json](https://tradingapi.prvx.io/api-json)

- **Base URL:** `https://tradingapi.prvx.io`
- **Auth header (exact):** `x-api-key: <API_KEY>`
- **Subaccount handling:** `subaccountAddress` in query/body, plus `chainId` for account/position endpoints

### Endpoints used in this starter

- **Public check:** `GET /`
- **API key validation / subaccount scope:** `POST /v1/api-keys/list-permissions`
  - Header: `x-api-key`
  - Response shape: `ListApiKeyPermissionDto` (`isValid`, `subaccounts[]`)
- **Portfolio balance:** `GET /v1/accounts/subaccount/balance`
  - Query: `subaccountAddress`, `chainId`
  - Header: `x-api-key`
  - Response shape: `SubaccountDetailsDto`
- **Open positions:** `GET /v1/positions/all`
  - Query: `subaccountAddress`, `chainId`
  - Header: `x-api-key`
  - Response shape: `PositionDto[]`
- **Market data:** `GET /v1/markets/{chainId}/by-symbol/{symbol}`
- **Place order:** `POST /v1/trade/create-position` with `CreatePositionDto`

### Response envelope

PriveX docs define this envelope:

```json
{
  "success": true,
  "statusMessage": "OK",
  "data": {},
  "error": {
    "code": "string",
    "message": "string"
  }
}
```

Client behavior:
- If `success=false`, raise explicit error with API message/code.
- If endpoint returns direct DTO/list instead of envelope, accept it.

## Configuration

Copy and edit if you prefer not to use `privex init`:

```bash
cp .env.example .env
```

Set values in `.env`:

- `PRIVEX_BASE_URL` (default: `https://tradingapi.prvx.io`)
- `PRIVEX_API_KEY` (required)
- `PRIVEX_NETWORK` (default: `base`) — `base` or `coti`
- `PRIVEX_SUBACCOUNT_ID` (recommended; required when key has multiple subaccounts)
- `PRIVEX_TIMEOUT` (default: `8` seconds) — lower for tight agent loops; raise for slow networks. The HTTP session retries transient 5xx on idempotent requests (e.g. GET) twice with backoff; POST is not retried.

## Networks

You can connect to **Base** or **COTI**. Choose during `privex init`, or switch anytime:

```bash
privex network base
privex network coti
privex network coti --connect
```

## Commands

- `privex init` - prompt for API key, network (Base/COTI), and optional subaccount, write `.env` (use `--connect` to test after)
- `privex network <base|coti>` - switch network; use `--connect` to test after
- `privex connect` - validates key, fetches portfolio, counts open positions
- `privex status` - network, subaccount, portfolio summary, open position count (good for health checks)
- `privex positions` - prints open positions
- `privex order --market-id 1 --side LONG --quantity 1 --leverage 5` - basic market order example
- `privex quickstart` - same as `connect`, useful as a first-run command

## API Key, Subaccounts, Permissions

You create API keys and delegate permissions from PriveX account controls.

- API key is passed via `x-api-key`.
- Access is scoped by delegated subaccounts.
- Trading operations require the delegated permission set for the target subaccount.

If `privex connect` fails:
- verify the API key is valid
- verify subaccount delegation exists
- verify required permissions are granted
- verify `PRIVEX_SUBACCOUNT_ID` matches delegated `subaccountAddress`

## Embedding in an agent

Single import, env-based config, one client to pass into your strategy loop:

```python
from privex import PrivexClient

client = PrivexClient()  # loads .env, reuses session

portfolio = client.get_portfolio()
positions = client.get_positions()
market = client.get_market("ETH-USD")
# pass client into your decision logic
```

Error contract for agent logic:

- **`PrivexAuthError`** — auth or permission failure; trigger re-auth or key rotation.
- **`PrivexError`** — other failure (network, API, validation); retry or back off.

```python
from privex import PrivexClient, PrivexError, PrivexAuthError

client = PrivexClient()

try:
    portfolio = client.get_portfolio()
except PrivexAuthError:
    # escalate: re-auth or rotate key
    ...
except PrivexError:
    # transient; retry or pause strategy
    ...
```

Optional safe helper (returns `None` on auth failure so the agent can branch without try/except):

```python
from privex import PrivexClient, get_portfolio_safe

client = PrivexClient()
data = get_portfolio_safe(client)
if data is None:
    # handle unauthorized
    ...
```

`place_order` validates payloads with `validate_create_position_payload` before calling the API. After changing `.env` at runtime, use a new `PrivexClient(load_config())` or call `client.reset_cache()` if you reload config on the same instance.

Concurrent / async strategies: this package uses synchronous `requests`. For async, use `httpx` or similar with the same URLs, headers (`x-api-key`), and request bodies.

## Examples

```bash
python examples/connect.py
python examples/get_positions.py
python examples/place_order.py --market-id 1 --side LONG --quantity 1 --leverage 5
```
