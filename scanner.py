import ccxt
import time
import requests
import threading
import os
from datetime import datetime, timedelta

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = int(os.environ.get("CHAT_ID"))

LOW_CAP_MAX = 30_000_000
MIN_VOLUME_24H = 300_000

BIO = """Multi-CEX Volume Pump Scanner v2025

Low-capy 1-30M MC - 6 gield jednoczesnie
Binance - Bybit - Gate.io - MEXC - KuCoin - OKX

Lapie pompy x10-x500 w pierwszych minutach

Zero spamu - tylko prawdziwe okazje"""

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
    send(f"Bot zyje - uptime: {format_uptime(time.time() - start_time)}\n{datetime.now().strftime('%d.%m %H:%M')}")
    last_heartbeat = time.time()

send(f"Scanner wystartowal {datetime.now().strftime('%d.%m %H:%M')}\n\n{BIO}")
heartbeat()

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
                        send(BIO + "\n\nDziala 24/7 | Copyright: Coinn.pl", cid)
                    elif txt == "/stats":
                        send(f"Uptime: {format_uptime(time.time()-start_time)}\nAlertow: {total_alerts} | Dzis: {today_alerts} | Godzina: {hour_alerts}", cid)
                    elif txt in ["/status", "/uptime"]:
                        send(f"Zyje - uptime: {format_uptime(time.time()-start_time)}\nOstatni heartbeat: {datetime.fromtimestamp(last_heartbeat).strftime('%H:%M')}", cid)
                    elif txt == "/top":
                        send("Ostatnie 10:\n\n" + "\n".join(last_alerts) if last_alerts else "Czekamy na pompy...", cid)
                    offset = u["update_id"] + 1
        except: pass
        time.sleep(5)

threading.Thread(target=polling, daemon=True).start()

print("Scanner 24/7 dziala!")

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
                    vol_prev = sum(x[5] for x in o[-25:-1]) / 24   # <-- naprawione!
                    if vol_prev == 0: continue
                    ratio = vol_now / vol_prev
                    price_ch = (o[-1][4] - o[-2][4]) / o[-2][4] * 100
                    ticker = ex.fetch_ticker(s)
                    vol24 = ticker.get("quoteVolume", vol_now * o[-1][4])
                    if ratio > 9 and price_ch > 5 and vol24 > MIN_VOLUME_24H:
                        base = s.split("/")[0]
                        if base in seen_alerts: continue
                        seen_alerts.add(base)
                        msg = f"{base}/USDT na {ex.name}\nVol x{ratio:.1f} +{price_ch:.1f}%\nhttps://dexscreener.com/search?q={base}"
                        send(msg)
                        total_alerts += 1
                        today_alerts += 1
                        hour_alerts += 1
                        last_alerts.append(f"{datetime.now().strftime('%H:%M')} | {base} | {ex.name} | x{ratio:.1f}")
                        if len(last_alerts) > 10: last_alerts.pop(0)
                except: continue
            time.sleep(1)

        if time.time() - last_heartbeat >= 1800:
            heartbeat()

        time.sleep(300)
    except Exception as e:
        send(f"Blad: {e}")
        time.sleep(60)
