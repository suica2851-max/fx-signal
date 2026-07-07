#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, urllib.request, os, threading, time
from datetime import datetime
from market_analysis import run_full_analysis

def get_audjpy():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/AUDJPY=X?interval=1m&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        chart = data["chart"]["result"][0]
        meta = chart["meta"]
        price = meta.get("regularMarketPrice", 0)
        prev = meta.get("previousClose", 0)
        high = meta.get("regularMarketDayHigh", 0)
        low = meta.get("regularMarketDayLow", 0)
        closes = chart.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        closes = [c for c in closes if c is not None]
        return {
            "price": round(price, 3),
            "prev": round(prev, 3),
            "high": round(high, 3),
            "low": round(low, 3),
            "closes": [round(c, 3) for c in closes[-30:]],
            "time": datetime.now().strftime("%H:%M:%S"),
            "ok": True
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/market-analysis":
            try:
                result = run_full_analysis()
                body = json.dumps(result, ensure_ascii=False).encode()
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api":
            body = json.dumps(get_audjpy()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return
        try:
            with open("audjpy-dashboard.html", "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        except:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8765))
    print(f"KOTAX起動 → port {PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
