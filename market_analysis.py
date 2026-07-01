import os
import json
from datetime import datetime
import pandas as pd
import yfinance as yf
from anthropic import Anthropic

TICKERS = {
    "audjpy": "AUDJPY=X",
    "usdjpy": "JPY=X",
    "wti": "CL=F",
    "sp500": "^GSPC",
    "gold": "GC=F",
    "bhp": "BHP.AX",
    "au_bond": "^GACGB10",
    "jp_bond": "^JGB",
}
EMA_FAST = 20
EMA_SLOW = 50
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

def _fetch(ticker, period, interval):
    df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df

def _add_ema(df):
    df = df.copy()
    close = df["Close"].squeeze()
    df["ema_fast"] = close.ewm(span=EMA_FAST, adjust=False).mean()
    df["ema_slow"] = close.ewm(span=EMA_SLOW, adjust=False).mean()
    return df

def _classify_trend(df):
    last = df.iloc[-1]
    prev = df.iloc[-5] if len(df) >= 5 else df.iloc[0]
    fast_now = float(last["ema_fast"])
    slow_now = float(last["ema_slow"])
    fast_prev = float(prev["ema_fast"])
    ema_gap_pct = abs(fast_now - slow_now) / slow_now * 100
    slope = fast_now - fast_prev
    if fast_now > slow_now and slope > 0 and ema_gap_pct > 0.05:
        direction = "上昇"
    elif fast_now < slow_now and slope < 0 and ema_gap_pct > 0.05:
        direction = "下降"
    else:
        direction = "レンジ"
    price = float(df["Close"].squeeze().iloc[-1])
    return {"direction": direction, "price": round(price, 3),
            "ema_fast": round(fast_now, 3), "ema_slow": round(slow_now, 3)}

def get_daily_trend():
    df = _fetch(TICKERS["audjpy"], "4mo", "1d")
    return _classify_trend(_add_ema(df))

def get_h4_trend():
    df = _fetch(TICKERS["audjpy"], "60d", "1h")
    df_4h = df.resample("4h").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
    return _classify_trend(_add_ema(df_4h))

def get_market_data():
    result = {}
    pairs = [
        ("wti", TICKERS["wti"]),
        ("sp500", TICKERS["sp500"]),
        ("gold", TICKERS["gold"]),
        ("bhp", TICKERS["bhp"]),
        ("usdjpy", TICKERS["usdjpy"]),
    ]
    for label, ticker in pairs:
        try:
            df = _fetch(ticker, "5d", "1d")
            if len(df) >= 2:
                close = df["Close"].squeeze()
                change_pct = float((close.iloc[-1] / close.iloc[-2] - 1) * 100)
                result[label] = {"price": round(float(close.iloc[-1]), 3), "change_pct": round(change_pct, 2)}
            else:
                result[label] = None
        except Exception:
            result[label] = None

    for label, ticker in [("au_bond", TICKERS["au_bond"]), ("jp_bond", TICKERS["jp_bond"])]:
        try:
            df = _fetch(ticker, "5d", "1d")
            if len(df) >= 1:
                close = df["Close"].squeeze()
                result[label] = round(float(close.iloc[-1]), 3)
            else:
                result[label] = None
        except Exception:
            result[label] = None

    if result.get("au_bond") and result.get("jp_bond"):
        result["rate_diff"] = round(result["au_bond"] - result["jp_bond"], 3)
    else:
        result["rate_diff"] = None

    return result

def simple_risk_sentiment(market):
    sp500 = market.get("sp500")
    wti = market.get("wti")
    gold = market.get("gold")
    if not sp500 or not wti:
        return "不明"
    score = 0
    score += 1 if sp500["change_pct"] > 0 else -1
    score += 1 if wti["change_pct"] > 0 else -1
    if gold:
        score += -1 if gold["change_pct"] > 0.5 else 1 if gold["change_pct"] < -0.5 else 0
    if score >= 2:
        return "リスクオン"
    elif score <= -2:
        return "リスクオフ"
    return "中立"

def generate_ai_analysis(daily, h4, market, risk_sentiment):
    sp500_str = f"{market['sp500']['price']}({market['sp500']['change_pct']:+}%)" if market.get("sp500") else "取得不可"
    wti_str = f"{market['wti']['price']}({market['wti']['change_pct']:+}%)" if market.get("wti") else "取得不可"
    gold_str = f"{market['gold']['price']}({market['gold']['change_pct']:+}%)" if market.get("gold") else "取得不可"
    bhp_str = f"{market['bhp']['price']}({market['bhp']['change_pct']:+}%)" if market.get("bhp") else "取得不可"
    usdjpy_str = f"{market['usdjpy']['price']}({market['usdjpy']['change_pct']:+}%)" if market.get("usdjpy") else "取得不可"
    rate_diff_str = f"{market['rate_diff']}%" if market.get("rate_diff") else "取得不可"

    prompt = f"""あなたはAUD/JPY専門のFXアナリストです。
以下のテクニカル・マーケットデータと、あなたの知識ベース(RBA・日銀の最新スタンス、中国経済動向、直近の重要指標)を組み合わせて、総合的な地合い分析を行ってください。

【テクニカル】
日足: 方向={daily["direction"]} 価格={daily["price"]} EMA20={daily["ema_fast"]} EMA50={daily["ema_slow"]}
4時間足: 方向={h4["direction"]} 価格={h4["price"]} EMA20={h4["ema_fast"]} EMA50={h4["ema_slow"]}

【マーケットデータ(前日比)】
S&P500: {sp500_str}
WTI原油: {wti_str}
金(ゴールド): {gold_str}
BHP(鉄鉱石代替): {bhp_str}
USD/JPY: {usdjpy_str}
豪日金利差: {rate_diff_str}
リスク判定: {risk_sentiment}

【ファンダメンタル】
あなたの知識ベースから、以下を考慮してください:
- RBAの現在の金融政策スタンスと次回会合の見通し
- 日銀の現在のスタンスと円の方向性
- 中国経済の動向(AUDへの影響)
- 直近で重要だった経済指標の結果

以下フォーマットで出力(前置き不要):
推奨目線: 順張り売り / 順張り買い / レンジ想定 / 様子見 のいずれか
リスク判定: リスクオン / リスクオフ / 中立 のいずれか
テクニカル: (1文)
ファンダ: (RBA・日銀・中国を踏まえた1文)
総合判断: (2文以内、今日注目すべきポイント)
注意点: (1文)"""

    response = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=600,
        messages=[{"role": "user", "content": prompt}])
    return response.content[0].text

def run_full_analysis():
    daily = get_daily_trend()
    h4 = get_h4_trend()
    market = get_market_data()
    risk_sentiment = simple_risk_sentiment(market)
    ai_text = generate_ai_analysis(daily, h4, market, risk_sentiment)
    return {
        "timestamp": datetime.now().isoformat(),
        "daily": daily,
        "h4": h4,
        "market": market,
        "risk_sentiment": risk_sentiment,
        "ai_analysis": ai_text,
    }

if __name__ == "__main__":
    result = run_full_analysis()
    print(json.dumps(result, ensure_ascii=False, indent=2))
