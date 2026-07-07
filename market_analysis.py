import os
import json
import urllib.request
from datetime import datetime
from anthropic import Anthropic

client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

def fetch_price(symbol, period="4mo", interval="1d"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={period}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
    return [c for c in closes if c is not None]

def calc_ema(closes, span):
    k = 2 / (span + 1)
    ema = closes[0]
    for c in closes[1:]:
        ema = c * k + ema * (1 - k)
    return round(ema, 3)

def classify_trend(closes):
    ema20 = calc_ema(closes, 20)
    ema50 = calc_ema(closes, 50)
    slope = calc_ema(closes[-5:], 3) - calc_ema(closes[-10:-5], 3)
    if ema20 > ema50 and slope > 0:
        direction = "上昇"
    elif ema20 < ema50 and slope < 0:
        direction = "下降"
    else:
        direction = "レンジ"
    return {"direction": direction, "price": round(closes[-1], 3),
            "ema20": ema20, "ema50": ema50}

def get_change_pct(symbol):
    try:
        closes = fetch_price(symbol, "5d", "1d")
        if len(closes) >= 2:
            return round((closes[-1] / closes[-2] - 1) * 100, 2)
    except:
        pass
    return None

def run_full_analysis():
    daily_closes = fetch_price("AUDJPY=X", "4mo", "1d")
    daily = classify_trend(daily_closes)

    h1_closes = fetch_price("AUDJPY=X", "60d", "1h")
    h4_closes = [h1_closes[i] for i in range(0, len(h1_closes), 4)]
    h4 = classify_trend(h4_closes)

    sp500 = get_change_pct("%5EGSPC")
    wti = get_change_pct("CL%3DF")
    usdjpy_closes = fetch_price("JPY%3DX", "5d", "1d")
    usdjpy = round(usdjpy_closes[-1], 3) if usdjpy_closes else None

    score = 0
    if sp500: score += 1 if sp500 > 0 else -1
    if wti: score += 1 if wti > 0 else -1
    risk = "リスクオン" if score >= 1 else "リスクオフ" if score <= -1 else "中立"

    prompt = f"""AUD/JPYの地合いを分析してください。

【日足】方向:{daily["direction"]} 価格:{daily["price"]} EMA20:{daily["ema20"]} EMA50:{daily["ema50"]}
【4時間足】方向:{h4["direction"]} 価格:{h4["price"]} EMA20:{h4["ema20"]} EMA50:{h4["ema50"]}
【相関資産】S&P500:{sp500}% WTI:{wti}% USD/JPY:{usdjpy} リスク:{risk}
【ファンダ】RBA・日銀・中国経済の動向も踏まえて分析してください。

以下フォーマットで出力(前置き不要):
推奨目線: 順張り売り / 順張り買い / レンジ想定 / 様子見 のいずれか
リスク判定: リスクオン / リスクオフ / 中立 のいずれか
テクニカル: (1文)
ファンダ: (1文)
総合判断: (2文以内)
注意点: (1文)"""

   　response = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=800,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt + "\n\n最新のRBA・日銀発言、地政学リスクはWeb検索で確認した上で反映してください。"}])
    ai_text = "\n".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    return {
        "timestamp": datetime.now().isoformat(),
        "daily": daily,
        "h4": h4,
        "sp500_change": sp500,
        "wti_change": wti,
        "usdjpy": usdjpy,
        "risk_sentiment": risk,
        "ai_analysis": ai_text,
    }

if __name__ == "__main__":
    result = run_full_analysis()
    print(json.dumps(result, ensure_ascii=False, indent=2))
