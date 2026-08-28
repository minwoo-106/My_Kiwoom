# Kiwoom REST API Mock-Trading MVP

This project is permanently restricted to the Kiwoom mock-trading REST API.
It cannot use `https://api.kiwoom.com`; only `https://mockapi.kiwoom.com` is permitted.

## Authentication setup

1. Copy `.env.example` to `.env`.
2. Put only your **mock-investment** App Key and Secret Key in `.env`.
3. Do not share or commit `.env`.
4. Run:

   ```powershell
   .\.venv\Scripts\python.exe -m app.main auth
   ```

On success, the command prints the mock-mode banner and token expiration only. It never prints the token.

## Read-only mock queries

```powershell
.\.venv\Scripts\python.exe -m app.main accounts
.\.venv\Scripts\python.exe -m app.main portfolio
.\.venv\Scripts\python.exe -m app.main quote --stock-code 005930
```

Account numbers are masked in terminal output. These commands are read-only and use only the mock host.

## Manual mock order (not automatic)

The MVP only permits one-share KRX market orders and requires an explicit confirmation phrase. Do not run this until you intend to change your mock account balance.

```powershell
.\.venv\Scripts\python.exe -m app.main manual-buy --stock-code 005930 --quantity 1 --confirm MOCK-ORDER
```

An order request is never retried. Check its status before placing any additional order.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Source of truth

Use the current official Kiwoom REST API guide before each new endpoint is implemented:
https://openapi.kiwoom.com/guide/apiguide
