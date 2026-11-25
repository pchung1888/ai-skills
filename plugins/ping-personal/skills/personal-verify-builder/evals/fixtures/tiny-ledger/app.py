"""Tiny Ledger: a one-page web app over ledger.db, used as the eval fixture.

Run: python seed.py, then python app.py --port 8765
Pages:
  /health     -> plain text "ok"
  /positions  -> HTML table of open positions and a grand total market value
"""
import argparse
import html
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import queries

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "ledger.db")


def render_positions():
    con = sqlite3.connect(DB_PATH)
    try:
        rows = queries.positions(con)
    finally:
        con.close()
    total = round(sum(r[2] for r in rows), 2)
    body = "".join(
        f'<tr data-symbol="{html.escape(s)}"><td>{html.escape(s)}</td>'
        f'<td class="qty">{q}</td><td class="value">{v:.2f}</td></tr>'
        for s, q, v in rows
    )
    return (
        "<html><head><title>Positions</title></head><body>"
        "<h1>Positions</h1><table id=\"positions\">"
        "<tr><th>Symbol</th><th>Net qty</th><th>Market value</th></tr>"
        f"{body}</table>"
        f'<p>Total market value: <span id="total">{total:.2f}</span></p>'
        "</body></html>"
    )


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._send(200, "text/plain", "ok")
        elif self.path == "/positions":
            self._send(200, "text/html", render_positions())
        else:
            self._send(404, "text/plain", "not found")

    def _send(self, code, ctype, text):
        data = text.encode("ascii", "xmlcharrefreplace")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Tiny Ledger listening on http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
