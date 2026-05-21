import ccxt
import time
import os
from supabase import create_client, Client

# Supabase тохиргоо (Railway-ийн Environment Variables-д хийж өгөх)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Kucoin тохиргоо
exchange = ccxt.kucoin({
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

# Real% болон 1h% тооцохын тулд анхны үнийг санах ойд хадгалах
session_initial_prices = {}

def fetch_and_push():
    global session_initial_prices
    print(f"🔄 Fetching market data: {time.strftime('%H:%M:%S')}")
    
    try:
        # 1. Зах зээлийн мэдээлэл болон Limits татах
        markets = exchange.load_markets()
        tickers = exchange.fetch_tickers()
        
        payload = []
        usdt_pairs = [s for s in markets.keys() if s.endswith('/USDT')]

        for sym in usdt_pairs:
            if sym not in tickers: continue
            
            t = tickers[sym]
            ask = float(t.get('ask') or t.get('last') or 0)
            bid = float(t.get('bid') or 0)
            
            if ask == 0: continue

            # Анхны үнийг бүртгэх (Real% зориулж)
            if sym not in session_initial_prices:
                session_initial_prices[sym] = ask

            # Тооцооллууд
            spread = ((ask - bid) / ask * 100) if ask > 0 else 0
            min_amount = markets[sym]['limits']['amount']['min'] or 0
            min_usdt = min_amount * ask
            real_change = ((ask - session_initial_prices[sym]) / session_initial_prices[sym] * 100)
            vol = float(t.get('quoteVolume') or 0)
            ch_24 = float(t.get('percentage') or 0)

            # Supabase-рүү илгээх дата
            data = {
                "symbol": sym,
                "bid": bid,
                "ask": ask,
                "spread": round(spread, 2),
                "min_usdt": round(min_usdt, 4),
                "volume": round(vol, 2),
                "real_change": round(real_change, 2),
                "change_24h": round(ch_24, 2),
                "updated_at": "now()"
            }
            payload.append(data)

        # 2. Supabase-рүү бөөнөөр нь Upsert хийх (Хамгийн хурдан арга)
        if payload:
            supabase.table("market_data").upsert(payload).execute()
            print(f"✅ Pushed {len(payload)} coins to Supabase.")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🚀 Data Worker Starting...")
    while True:
        fetch_and_push()
        time.sleep(5) # 5 секунд тутамд шинэчилнэ (Railway-ийн ачааллаас хамаарч тохируулж болно)
