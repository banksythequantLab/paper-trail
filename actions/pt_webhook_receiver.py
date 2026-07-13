"""Local webhook receiver for the Paper Trail self-contained Action demo.

Listens for alerts POSTed by the DataHub Action (running inside the
datahub-actions container) and (a) appends them to a JSONL log for programmatic
verification and (b) serves a small HTML page so the event -> action loop is
visible in a browser. No external services, no secrets, no Slack.

  python actions/pt_webhook_receiver.py     # listens on 0.0.0.0:8757
"""
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PT_WEBHOOK_PORT", "8757"))
LOG = os.environ.get("PT_WEBHOOK_LOG",
                     os.path.join(os.path.dirname(os.path.abspath(__file__)), "pt_alerts.jsonl"))
ALERTS = []


def _load():
    if os.path.exists(LOG):
        for line in open(LOG, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    ALERTS.append(json.loads(line))
                except Exception:
                    pass


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/plain"):
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            data = json.loads(raw or b"{}")
        except Exception:
            data = {"raw": raw.decode("utf-8", "replace")}
        rec = {"received_at": time.strftime("%Y-%m-%d %H:%M:%S"), **data}
        ALERTS.append(rec)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"[receiver] ALERT {rec}", flush=True)
        self._send(200, "ok")

    def do_GET(self):
        rows = "".join(
            f"<tr><td>{a.get('received_at','')}</td>"
            f"<td>{a.get('category','')} / {a.get('operation','')}</td>"
            f"<td class='tag'>{(a.get('modifier') or '').split(':')[-1]}</td>"
            f"<td>{a.get('entityUrn','')}</td></tr>"
            for a in reversed(ALERTS))
        html = (
            "<html><head><title>Paper Trail - DataHub Action alerts</title>"
            "<meta http-equiv='refresh' content='3'>"
            "<style>body{font-family:'Segoe UI',Arial;background:#0d1117;color:#e6edf3;padding:32px}"
            "h1{color:#58a6ff;margin:0 0 4px}p{color:#8b949e;margin:0 0 20px}"
            "table{border-collapse:collapse;width:100%}"
            "td,th{border-bottom:1px solid #30363d;padding:9px 12px;text-align:left;font-size:14px}"
            "th{color:#8b949e;font-weight:600}.tag{color:#3fb950;font-weight:700}"
            ".c{color:#f85149;font-weight:700}</style></head><body>"
            "<h1>Paper Trail &mdash; DataHub Action alerts</h1>"
            f"<p><span class='c'>{len(ALERTS)}</span> alert(s) delivered from DataHub's event stream "
            "&rarr; this webhook (no Slack, fully self-contained)</p>"
            "<table><tr><th>received</th><th>event</th><th>tag</th><th>asset</th></tr>"
            f"{rows}</table></body></html>")
        self._send(200, html, "text/html")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    _load()
    print(f"[receiver] listening on 0.0.0.0:{PORT}  log={LOG}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
