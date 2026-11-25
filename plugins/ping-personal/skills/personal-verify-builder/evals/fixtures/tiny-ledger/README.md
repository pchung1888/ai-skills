# Tiny Ledger

A one-page web app that lists open stock positions from a SQLite database.

## Run

```
python seed.py
python app.py --port 8765
```

Then open http://127.0.0.1:8765/positions. `/health` returns `ok` when the server is up.

## Files

| File | What it is |
|---|---|
| `seed.py` | Rebuilds `ledger.db` with a fixed set of trades |
| `queries.py` | The SQL behind the Positions page |
| `app.py` | The web server and the HTML page |

## Business rule

Cancelled trades never count toward a position or the total market value.
