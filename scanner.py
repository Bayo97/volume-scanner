import ccxt
import time
import requests
import threading
import os
from datetime import datetime, timedelta

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_IDS = [int(x) for x in os.environ.get("CHAT_IDS", "").split(",") if x.strip()]

MY_USER_ID = 542711955   # Twój user_id – działa w grupie i prywatnie

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
last_alerts = []
seen_alerts = set()
scanner_active = True

def format_uptime(sec): return str(timedelta(seconds=int(sec))).split('.')[0]

def send(msg):
    for cid in CHAT_IDS:
        try:
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                          data={"chat_id": cid, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True},
                          timeout=10)
        except:
            pass

send("CEX Scanner 2025 uruchomiony – wpisz /help po komendy")

def polling():
    offset = None
    while True:
        try:
            params = {"timeout": 20}
            if offset:
                params["offset"] = offset

            r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                             params=params, timeout=25).json()

            for u in r.get("result", []):
                offset = u["update_id"] + 1

                if "message" not in u:
                    continue

                user_id = u["message"]["from"]["id"]
                txt = u["message"].get("text", "").strip()

                print(f"ODEBRANO od user_id {user_id}: {txt}")  # widzisz w Logs

                if user_id != MY_USER_ID:
                    continue  # tylko Ty możesz używać komend

                txt = txt.lower()

                if txt in ["/start", "/help"]:
                    send("CEX Pump Scanner v12.2025\n\nKomendy:\n/startcex – włącz alerty\n/stopcex – wyłącz alerty\n/last lub /alert – ostatnie 10 alertów\n/stats – statystyki\n/uptime – czas działania")
                elif txt == "/startcex":
                    global scanner_active
                    scanner_active = True
                    send("Alerty włączone")
                elif txt == "/stopcex":
                    scanner_active = False
                    send("Alerty wyłączone")
                elif txt in ["/last", "/alert"]:
                    if last_alerts:
                        send("Ostatnie 10 alertów:\n\n" + "\n".join(last_alerts[-10:]))
                    else:
                        send("Brak alertów")
                elif txt == "/stats":
                    send(f"Uptime: {format_uptime(time.time()-start_time)}\nAlertów ogółem: {total_alerts} | Dziś: {today_alerts}")
                elif txt == "/uptime":
                    send(f"Uptime: {format_uptime(time.time()-start_time)}")
        except Exception as e:
            print(f"Polling błąd: {e}")
        time.sleep(5)

threading.Thread(target=polling, daemon=True).start()

print("CEX Scanner – finalna wersja, działa idealnie")

while True:
    if not scanner_active:
        time.sleep(60)
        continue

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
                            link = link.replace("{base}", base}", base)

                            direction = "LONG 🚀" if price_ch > 0 else "SHORT 💥"
                            timestamp = datetime.now().strftime('%d.%m %H:%M')

                            msg = f"🚨 {base}/USDT na {ex.name}\n" \
                                  f"Cena: ${current_price:.8f} ({price_ch:+.2f}%)\n" \
                                  f"Vol ×{ratio:.1f}\n" \
                                  f"{direction}\n" \
                                  f"<a href='{link}'>OTWÓRZ NATYCHMIAST</a>"

                            send(msg)
                            total_alerts += 1
                            today_alerts += 1
                            last_alerts.append(f"{timestamp} | {base} | {ex.name} | {direction} | {price_ch:+.2f}%")
                    except: continue
                time.sleep(1)
            except Exception as e:
                print(f"Błąd {ex.name}: {e}")

        seen_alerts.clear()
        time.sleep(300)
    except Exception as e:
        print(f"Krytyczny błąd: {e}")
        time.sleep(60)
