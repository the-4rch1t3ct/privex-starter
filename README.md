# PriveX Trading API Starter

Fastest way to connect a self-hosted agent to PriveX.

This repo gives you a minimal Python client and CLI with one goal: prove authenticated connectivity with one command.

## Quickstart

```bash
git clone <your-repo-url>
cd privex-starter
pip install -r requirements.txt
privex init
privex connect
```

`privex init` prompts for your API key, **network (Base or COTI)**, and optional subaccount address, writes `.env`, and can run the connection test when you pass `--connect`.

Alternative install:

```bash
pip install -e .
```

Makefile flow (API key in onboarding):

```bash
make setup
make init
```

`make init` runs `privex init --connect`: prompts for API key, network (Base/COTI), and optional subaccount, writes `.env`, then runs the connection test. No manual `.env` editing.

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

Set values in `.env`:

- `PRIVEX_BASE_URL` (default: `https://tradingapi.prvx.io`)
- `PRIVEX_API_KEY` (required)
- `PRIVEX_NETWORK` (default: `base`) — `base` or `coti`
- `PRIVEX_SUBACCOUNT_ID` (recommended; required when key has multiple subaccounts)
- `PRIVEX_TIMEOUT` (default: `15`)

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

## Examples

```bash
python examples/connect.py
python examples/get_positions.py
python examples/place_order.py --market-id 1 --side LONG --quantity 1 --leverage 5
```
