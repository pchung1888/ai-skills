"""SQL used by the Positions page. This is the stored-procedure stand-in for the eval."""

# One row per symbol: net quantity and market value of OPEN trades only.
POSITIONS_SQL = """
SELECT symbol,
       SUM(qty) AS net_qty,
       ROUND(SUM(qty * price), 2) AS market_value
FROM trades
WHERE status = 'open'
GROUP BY symbol
ORDER BY symbol
"""


def positions(con):
    """Return a list of (symbol, net_qty, market_value) tuples."""
    return con.execute(POSITIONS_SQL).fetchall()
