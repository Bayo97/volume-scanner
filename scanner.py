import ccxt
import time
import requests
import threading
import os
from datetime import datetime, timedelta

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_IDS = [int(x) for x in os.environ.get("CHAT_IDS", "").split(",") if x.strip()]

MY_PRIVATE_ID = 542711955   # Twój prywatny chat_id

MIN_VOLUME_24H = 250_000

EXCHANGE_LINKS = {
    "CoinEx":  "https://www.coinex.com/en/exchange/{base}-usdt",
    "Bybit":    "https://www.bybit.com/trade/spot/{base}/USDT",
    "Gate.io":  "https://www.gate.io/trade/{base}_USDT",
    "MEXC":    "https://www.mexc.com/exchange/{base}_USDT",
    "KuCoin":   "https://www.kucoin.com/trade/{base}-USDT",
    "OKX":     "https://www.okx.com/trade-spot/{base}-usdt",
}

exchanges = [ccxt.coinex(), ccxt.bybit(), ccxt.gateio(), ccxt.mexc(), ccxt.kucoin(), ccxt.okx()]

start_time = time.time()
total_alerts = 0
today_alerts = 0
hour_alerts = 0
last_alerts = []
seen_alerts = set()

def format_uptime(sec): return str(timedelta(seconds=int(sec))).split('.')[0]

def send(msg, to_private=False):
    for cid in CHAT_IDS:
        try:
            if to_private and cid != MY_PRIVATE_ID:
                continue
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                          data={"chat_id": cid, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True},
                          timeout=10)
        except:
            pass

send("CEX Pump & Dump Scanner 2025 uruchomiony\nCoinEx • Bybit • Gate • MEXC • KuCoin • OKX\nŁapie longi i shorty w pierwszych minutach")

def polling():
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                             params={"timeout": 15}, timeout=20).json()
            for u in r.get("result", []):
                if "message" in u:
                    cid = u["message"]["chat"]["id"]
                    txt = u["message"].get("text", "").lower().strip()
                    if cid == MY_PRIVATE_ID:
                        if txt in ["/start", "/help"]:
                            send("CEX Pump & Dump Scanner v12.2025\n\nKomendy:\n/stats\n/uptime\n/top")
                        elif txt == "/stats":
                            send(f"Uptime: {format_uptime(time.time()-start_time)}\nAlertów: {total_alerts} | Dziś: {today_alerts} | Godzina: {hour_alerts}")
                        elif txt in ["/uptime", "/status"]:
                            send(f"Żyję – uptime: {format_uptime(time.time()-start_time)}")
                        elif txt == "/top":
                            send("Ostatnie 10:\n\n" + "\n".join(last_alerts[-10:]) if last_alerts else "Czekamy na mięso...")
        except:
            pass
        time.sleep(5)

threading.Thread(target=polling, daemon=True).start()

print("CEX Pump & Dump Scanner 2025 działa idealnie!")

while True:
    try:
        for ex in exchanges:
            try:
                markets = ex.load_markets()
                pairs = [s for s in markets if "USDT" in s and markets[s]["active"]]
                for s in pairs:
                    try:
                        o = ex.fetch_ohlcv(s, "5m", limit=50)
                        if len(o) < 30: continue

                        current_price = o[-1][4]
                        vol_now = o[-1][5]
                        vol_prev = sum(x[5] for x in o[-25:-1]) / 24
                        if vol_prev == 0: continue
                        ratio = vol_now / vol_prev
                        price_ch = (current_price - o[-2][4]) / o[-2][4] * 100
                        ticker = ex.fetch_ticker(s)
                        vol24 = ticker.get("quoteVolume", vol_now * current_price)

                        if ratio > 9 and abs(price_ch) > 5 and vol24 > MIN_VOLUME_24H:
                            base = s.split("/")[0].split(":")[0].upper()
                            alert_id = f"{base}_{ex.name}_{'L' if price_ch > 0 else 'S'}"
                            if alert_id in seen_alerts: continue
                            seen_alerts.add(alert_id)

                            link = EXCHANGE_LINKS.get(ex.name, "https://dexscreener.com/search?q=" + base)
                            link = link.replace("{base}", base)

                            direction = "LONG 🚀" if price_ch > 0 else "SHORT 💥"

                            msg = f"🚨 {base}/USDT na {ex.name}\n" \
                                  f"Cena: ${current_price:.8f} ({price_ch:+.2f}%)\n" \
                                  f"Vol ×{ratio:.1f}\n" \
                                  f"{direction}\n" \
                                  f"<a href='{link}'>OTWÓRZ NATYCHMIAST</a>"

                            send(msg)
                            total_alerts += 1
                            today_alerts += 1
                            hour_alerts += 1
                            last_alerts.append(f"{datetime.now().strftime('%H:%M')} | {base} | {ex.name} | {direction} | {price_ch:+.2f}%")
                    except: continue
                time.sleep(1)
            except Exception as e:
                send(f"Błąd {ex.name}: {e}", to_private=True)

        seen_alerts.clear()

        time.sleep(300)
    except Exception as e:
        send(f"Krytyczny błąd: {e}", to_private=True)
        time.sleep(60)
