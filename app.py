#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, urllib.request, os
from datetime import datetime

def fetch_yahoo(interval, range_):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/AUDJPY=X?interval={interval}&range={range_}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.loads(r.read())

def calc_rsi(closes, period=14):
    if len(closes) < period + 1: return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0)); losses.append(max(-d, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0: return 100.0
    return round(100 - (100 / (1 + avg_gain / avg_loss)), 2)

def calc_bb(closes, period=20, num_std=2):
    if len(closes) < period: return None, None, None
    sl = closes[-period:]
    mean = sum(sl) / period
    std = (sum((x - mean)**2 for x in sl) / period) ** 0.5
    return round(mean + num_std * std, 3), round(mean, 3), round(mean - num_std * std, 3)

def calc_trend(closes, threshold=0.08):
    if len(closes) < 5: return "unknown"
    diff = closes[-1] - closes[0]
    if diff < -threshold: return "down"
    if diff > threshold: return "up"
    return "flat"

def get_data():
    try:
        d1m = fetch_yahoo("1m", "1d")
        meta = d1m["chart"]["result"][0]["meta"]
        price = round(meta.get("regularMarketPrice", 0), 3)
        prev  = round(meta.get("previousClose", 0), 3)
        high  = round(meta.get("regularMarketDayHigh", 0), 3)
        low   = round(meta.get("regularMarketDayLow", 0), 3)
        q1 = d1m["chart"]["result"][0]["indicators"]["quote"][0]
        c1 = [x for x in q1.get("close", []) if x is not None]

        d5m = fetch_yahoo("5m", "5d")
        q5  = d5m["chart"]["result"][0]["indicators"]["quote"][0]
        c5  = [x for x in q5.get("close", []) if x is not None]
        rsi5 = calc_rsi(c5, 14)
        bb_u, bb_m, bb_l = calc_bb(c5, 20, 2)
        trend5 = calc_trend(c5[-10:] if len(c5) >= 10 else c5)

        d15m = fetch_yahoo("15m", "5d")
        q15  = d15m["chart"]["result"][0]["indicators"]["quote"][0]
        c15  = [x for x in q15.get("close", []) if x is not None]
        trend15 = calc_trend(c15[-8:] if len(c15) >= 8 else c15)

        return {
            "ok": True, "price": price, "prev": prev, "high": high, "low": low,
            "closes": [round(x, 3) for x in c1[-30:]],
            "rsi5": rsi5, "bb_upper": bb_u, "bb_mid": bb_m, "bb_lower": bb_l,
            "trend5": trend5, "trend15": trend15,
            "time": datetime.now().strftime("%H:%M:%S"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api":
            body = json.dumps(get_data()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        else:
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
    def log_message(self, *args): pass

PORT = int(os.environ.get("PORT", 8765))
print(f"KOTAX起動 → port {PORT}")
HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
