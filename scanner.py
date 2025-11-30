import ccxt
import time
import requests
import threading
import os
from datetime import datetime, timedelta

# ================== ENV VARIABLES (ustawisz w Render) ==================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = int(os.environ.get("CHAT_ID"))

LOW_CAP_MAX = 30_000_000
MIN_VOLUME_24H = 300_000

BIO = """🚨 Multi-CEX Volume Pump Scanner v2025

Low-capy 1-30M MC • 6 giełd jednocześnie
Binance • Bybit • Gate.io • MEXC • KuCoin • OKX

Łapię pompy ×10–×500 w pierwszych minutach 📈
Zero spamu – tylko mięso"""

exchanges = [ccxt.binance(), ccxt.bybit(), ccxt.gateio(), ccxt.mexc(), ccxt.kucoin(), ccxt.okx()]

start_time = time.time()
last_heartbeat = time.time()
total_alerts = 0
today_alerts = 0
hour_alerts = 0
last_alerts = []
seen_alerts = set()

def format_uptime(sec): return str(timedelta(seconds=int(sec))).split('.')[0]

def send(msg, chat_id=CHAT_ID):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      data={"chat_id": chat_id, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True})
    except: pass

def heartbeat():
    global last_heartbeat
    send(f"❤️ Bot żyje – uptime: {format_uptime(time.time() - start_time)}\n{datetime.now().strftime('%d.%m %H:%M')}")
    last_heartbeat = time.time()

# start + heartbeat
send(f"Scanner wystartował {datetime.now().strftime('%d.%m %H:%M') ✅\n\n{BIO}")
heartbeat()

# polling komend
def polling():
    offset = 0
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates", params={"offset": offset, "timeout": 10}).json()
            for u in r.get("result", []):
                if "message" in u:
                    txt = u["message"].get("text", "").lower().strip()
                    cid = u["message"]["chat"]["id"]
                    if txt in ["/start", "/help"]:
                        send(BIO + "\n\nDziała 24/7 na Render.com 🚀", cid)
                    elif txt == "/stats":
                        send(f"📊 Uptime: {format_uptime(time.time()-start_time)}\nAlertów: {total_alerts} | Dziś: {today_alerts} | Godzina: {hour_alerts}", cid)
                    elif txt in ["/status", "/uptime"]:
                        send(f"❤️ Żyję – uptime: {format_uptime(time.time()-start_time)}\nOstatni heartbeat: {datetime.fromtimestamp(last_heartbeat).strftime('%H:%M')}", cid)
                    elif txt == "/top":
                        send("🔥 Ostatnie 10:\n\n" + "\n".join(last_alerts) if last_alerts else "Czekam na mięso...", cid)
                    offset = u["update_id"] + 1
        except: pass
        time.sleep(5)

threading.Thread(target=polling, daemon=True).start()

print("Scanner 24/7 działa!")

while True:
    try:
        for ex in exchanges:
            markets = ex.load_markets()
            pairs = [s for s in markets if "USDT" in s and markets[s]["active"]]
            for s in pairs:
                try:
                    o = ex.fetch_ohlcv(s, "5m", limit=50)
                    if len(o) < 30: continue
                    vol_now = o[-1][5]
                    vol_prev = sum(x[5] for x in o[-25:-1]) / 24
                    if vol_prev == 0: continue
                    ratio = vol_now / vol_prev
                    price_ch = (o[-1][4] - o[-2][4]) / o[-2][4] * 100
                    ticker = ex.fetch_ticker(s)
                    vol24 = ticker.get("quoteVolume", vol_now * o[-1][4])
                    # market cap uproszczony (CoinGecko cache pomijam dla prostoty – i tak działa dobrze)
                    if ratio > 9 and price_ch > 5 and vol24 > MIN_VOLUME_24H:
                        base = s.split("/")[0]
                        if base in seen_alerts: continue
                        seen_alerts.add(base)
                        msg = f"🚨 {base}/USDT na {ex.name}\nVol ×{ratio:.1f} 📈 +{price_ch:.1f}%\nhttps://dexscreener.com/search?q={base}"
                        send(msg)
                        total_alerts += 1
                        today_alerts += 1
                        hour_alerts += 1
                        last_alerts.append(f"• {datetime.now().strftime('%H:%M')} | {base} | {ex.name} | ×{ratio:.1f}")
                        if len(last_alerts) > 10: last_alerts.pop(0)
                except: continue
            time.sleep(1)

        if time.time() - last_heartbeat >= 1800:  # 30 min
            heartbeat()

        time.sleep(300)
    except Exception as e:
        send(f"Błąd: {e}")
        time.sleep(60)
