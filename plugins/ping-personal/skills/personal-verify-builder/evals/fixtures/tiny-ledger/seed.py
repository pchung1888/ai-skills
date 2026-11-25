"""Create ledger.db next to this file with a fixed set of trades.

Run: python seed.py
Running it again rebuilds the database from scratch, so every run starts from the same data.
"""
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "ledger.db")

TRADES = [
    # (symbol, qty, price, status) - cancelled trades must never count toward positions.
    ("AAPL", 100, 190.25, "open"),
    ("AAPL", -40, 192.10, "open"),
    ("AAPL", 500, 189.00, "cancelled"),
    ("MSFT", 50, 410.55, "open"),
    ("MSFT", 25, 405.00, "cancelled"),
    ("TSLA", 10, 250.333, "open"),
]


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "CREATE TABLE trades (id INTEGER PRIMARY KEY, symbol TEXT NOT NULL,"
        " qty INTEGER NOT NULL, price REAL NOT NULL, status TEXT NOT NULL)"
    )
    con.executemany("INSERT INTO trades (symbol, qty, price, status) VALUES (?, ?, ?, ?)", TRADES)
    con.commit()
    con.close()
    print("seeded", DB_PATH, len(TRADES), "trades")


if __name__ == "__main__":
    main()
