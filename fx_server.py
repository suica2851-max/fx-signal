#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, urllib.request, os, threading, time
from datetime import datetime
from market_analysis import run_full_analysis

_calendar_cache = {"data": None, "ts": 0}
CALENDAR_TTL = 1800  # 30分キャッシュ
INVERSE_KEYWORDS = ["unemployment", "jobless", "claims", "inventories"]

def _judge_direction(country, title, forecast, actual):
    try:
        f = float(str(forecast).replace('%','').replace('K','').replace(',',''))
        a = float(str(actual).replace('%','').replace('K','').replace(',',''))
    except (ValueError, TypeError):
        return None
    inverse = any(k in title.lower() for k in INVERSE_KEYWORDS)
    beat = a > f
    if inverse: beat = not beat
    if country == "AUD": return "up" if beat else "down"
    if country == "JPY": return "down" if beat else "up"
    return None

def _impact_text(country, title, forecast, actual, direction):
    name_map = {"AUD":"豪州","JPY":"日本","USD":"米国","CNY":"中国"}
    cname = name_map.get(country, country)
    if actual in (None, "", "-"):
        return f"{cname}の指標。結果発表待ち。予想: {forecast or '--'}"
    base = f"{cname}実績 {actual}（予想 {forecast or '--'}）。"
    if direction == "up": return base + "AUD/JPYには上昇材料。"
    if direction == "down": return base + "AUD/JPYには下落材料。"
    return base + "AUD/JPYへの影響は限定的。"

def fetch_economic_calendar():
    now = time.time()
    if _calendar_cache["data"] and now - _calendar_cache["ts"] < CALENDAR_TTL:
        return _calendar_cache["data"]
    try:
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            raw = json.loads(r.read())
    except Exception as e:
        return {"ok": False, "error": str(e), "items": []}

    today = datetime.now().strftime("%Y-%m-%d")
    watch = {"AUD", "JPY", "USD", "CNY"}
    items = []
    for ev in raw:
        country = ev.get("country", "")
        if country not in watch: continue
        date_str = ev.get("date", "")
        if not date_str.startswith(today): continue
        title = ev.get("title", "")
        forecast, actual = ev.get("forecast"), ev.get("actual")
        direction = _judge_direction(country, title, forecast, actual)
        items.append({
            "time": date_str[11:16] if len(date_str) >= 16 else "--:--",
            "country": country, "title": title,
            "impact": ev.get("impact", "Low"),
            "forecast": forecast, "actual": actual,
            "direction": direction,
            "summary": _impact_text(country, title, forecast, actual, direction),
        })
    items.sort(key=lambda x: x["time"])
    result = {"ok": True, "items": items, "updated": datetime.now().strftime("%H:%M:%S")}
    _calendar_cache.update(data=result, ts=now)
    return result

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
