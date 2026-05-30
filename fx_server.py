#!/usr/bin/env python3
"""
AUD/JPY リアルタイム価格サーバー
yfinance経由でデータ取得 → ローカルHTMLにCORS対応で提供
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, urllib.request, urllib.error, os
from datetime import datetime

def get_audjpy():
    try:
        # Yahoo Finance API (yfinance相当のエンドポイント)
        url = "https://query1.finance.yahoo.com/v8/finance/chart/AUDJPY=X?interval=1m&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        chart = data["chart"]["result"][0]
        meta  = chart["meta"]
        price = meta.get("regularMarketPrice", 0)
        prev  = meta.get("previousClose", 0)
        high  = meta.get("regularMarketDayHigh", 0)
        low   = meta.get("regularMarketDayLow", 0)
        # 直近60本の終値
        closes = chart.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        closes = [c for c in closes if c is not None]
        return {
            "price": round(price, 3),
            "prev":  round(prev, 3),
            "high":  round(high, 3),
            "low":   round(low, 3),
            "closes": [round(c, 3) for c in closes[-30:]],
            "time":  datetime.now().strftime("%H:%M:%S"),
            "ok": True
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")  # CORS許可
        self.end_headers()
        self.wfile.write(json.dumps(get_audjpy()).encode())

    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]} {args[1]}")

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8765))
    print(f"✅ AUD/JPY サーバー起動 → http://localhost:{PORT}")
    print("停止するには Ctrl+C")
    HTTPServer(("localhost", PORT), Handler).serve_forever()
