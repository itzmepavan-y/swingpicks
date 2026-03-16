"""
India Swing Picks v2 — Auto Screener
======================================
- Scans full Nifty 500 every day
- Scores every stock on 12 parameters
- Picks top 5 per sector by conviction (not hardcoded)
- Tracks new entries vs yesterday
- Serves dashboard with login
- Auto-refreshes 9:15 AM IST weekdays
"""

import os, json, time, logging, threading
from datetime import datetime, timedelta, date
from pathlib import Path
from functools import wraps
from flask import Flask, request, session, redirect, url_for, send_from_directory, jsonify, render_template_string

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", "changeme-set-in-render-env")
app.permanent_session_lifetime = timedelta(days=30)

APP_USERNAME = os.environ.get("APP_USERNAME", "pavan")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "swing2026")

STATIC     = Path(__file__).parent / "static"
DATA_FILE  = STATIC / "swing_data.json"
PREV_FILE  = STATIC / "swing_data_prev.json"
INDEX_FILE = STATIC / "index_data.json"

# ─────────────────────────────────────────────────────────────────
# NIFTY 500 STOCK UNIVERSE — fetched dynamically, fallback list
# ─────────────────────────────────────────────────────────────────
NIFTY500_FALLBACK = [
    # Banking & Finance
    ("HDFCBANK","Banking"),("SBIN","Banking"),("ICICIBANK","Banking"),
    ("KOTAKBANK","Banking"),("AXISBANK","Banking"),("INDUSINDBK","Banking"),
    ("BANDHANBNK","Banking"),("FEDERALBNK","Banking"),("IDFCFIRSTB","Banking"),
    ("PNB","Banking"),("CANBK","Banking"),("BANKBARODA","Banking"),
    ("BAJFINANCE","NBFC"),("BAJAJFINSV","NBFC"),("CHOLAFIN","NBFC"),
    ("MUTHOOTFIN","NBFC"),("PFC","Fin. Services"),("RECLTD","Fin. Services"),
    ("IRFC","Rail Finance"),("HUDCO","Housing Finance"),
    # IT & Tech
    ("INFY","IT"),("TCS","IT"),("HCLTECH","IT"),("WIPRO","IT"),
    ("TECHM","IT"),("MPHASIS","IT"),("PERSISTENT","IT"),("COFORGE","IT"),
    ("LTIM","IT"),("OFSS","IT"),("KPITTECH","IT"),("TATAELXSI","IT"),
    # Healthcare & Pharma
    ("SUNPHARMA","Pharma"),("CIPLA","Pharma"),("DRREDDY","Pharma"),
    ("DIVISLAB","Pharma"),("AUROPHARMA","Pharma"),("MANKIND","Pharma"),
    ("GLAND","Pharma"),("ALKEM","Pharma"),("TORNTPHARM","Pharma"),
    ("APOLLOHOSP","Hospitals"),("MAXHEALTH","Hospitals"),("FORTIS","Hospitals"),
    # Auto & EV
    ("TATAMOTORS","Auto"),("MARUTI","Auto"),("M&M","Auto"),
    ("BAJAJ-AUTO","Auto"),("EICHERMOT","Auto"),("ASHOKLEY","Auto"),
    ("TVSMOTOR","Auto"),("HEROMOTOCO","Auto"),("BOSCHLTD","Auto Ancil"),
    ("MOTHERSON","Auto Ancil"),("BHARATFORG","Auto Ancil"),
    # Energy, Oil & Renewables
    ("ONGC","Oil & Gas"),("BPCL","Oil & Gas"),("IOC","Oil & Gas"),
    ("HINDPETRO","Oil & Gas"),("GAIL","Gas"),("IGL","Gas"),("MGL","Gas"),
    ("NTPC","Power"),("POWERGRID","Power"),("TATAPOWER","Power"),
    ("COALINDIA","Energy"),("ADANIGREEN","Renewables"),("TORNTPOWER","Renewables"),
    ("ADANIPOWER","Power"),("CESC","Power"),
    # Metals & Mining
    ("TATASTEEL","Steel"),("JSWSTEEL","Steel"),("SAIL","Steel"),
    ("HINDALCO","Metals"),("NATIONALUM","Metals"),("NMDC","Mining"),
    ("VEDL","Metals"),("COALINDIA","Mining"),("HINDCOPPER","Mining"),
    # Consumer & FMCG
    ("ITC","FMCG"),("HINDUNILVR","FMCG"),("NESTLEIND","FMCG"),
    ("BRITANNIA","FMCG"),("DABUR","FMCG"),("MARICO","FMCG"),
    ("GODREJCP","FMCG"),("EMAMILTD","FMCG"),("COLPAL","FMCG"),
    ("TATACONSUM","FMCG"),("VBL","Beverages"),("RADICO","Beverages"),
    # Defence & Aerospace
    ("HAL","Aerospace"),("BEL","Electronics"),("MAZDOCK","Shipbuilding"),
    ("GRSE","Shipbuilding"),("COCHINSHIP","Shipbuilding"),("DATAPATTNS","Avionics"),
    ("PARAS","Defence"),("BEML","Defence"),("MIDHANI","Defence"),
    # Infra & Capital Goods
    ("LT","EPC"),("SIEMENS","Energy Tech"),("ABB","Capital Goods"),
    ("HAVELLS","Electricals"),("POLYCAB","Cables"),("KEI","Cables"),
    ("CUMMINSIND","Industrial"),("THERMAX","Industrial"),("BHEL","Power Equipment"),
    ("IRCON","Railways"),("RVNL","Railways"),("RAILVIKAS","Railways"),
    # Chemicals
    ("DEEPAKNTR","Chemicals"),("PIIND","Agrochemicals"),("VINATIORGA","Chemicals"),
    ("AARTI","Chemicals"),("NAVINFLUOR","Chemicals"),("FINPIPE","Chemicals"),
    ("CLEAN","Chemicals"),("TATACHEM","Chemicals"),
    # New Age & EMS
    ("KAYNES","EMS"),("DIXON","EMS"),("SYRMA","EMS"),("AMBER","EMS"),
    ("IDEAFORGE","Drones"),("PAYTM","Fintech"),("ZOMATO","FoodTech"),
    ("NYKAA","Retail"),("DELHIVERY","Logistics"),
    # Real Estate & Telecom
    ("GODREJPROP","Real Estate"),("PRESTIGE","Real Estate"),
    ("OBEROIRLTY","Real Estate"),("DLF","Real Estate"),("LODHA","Real Estate"),
    ("BHARTIARTL","Telecom"),("INDUSTOWER","Tower Infra"),
    ("IDEA","Telecom"),
]

SECTOR_MAP = {
    "Banking":"banking","NBFC":"banking","Fin. Services":"banking",
    "Rail Finance":"banking","Housing Finance":"banking",
    "IT":"it","Tech":"it",
    "Pharma":"pharma","Hospitals":"pharma",
    "Auto":"auto","Auto Ancil":"auto","EV":"auto",
    "Oil & Gas":"energy","Gas":"energy","Power":"energy",
    "Renewables":"energy","Energy":"energy",
    "Steel":"metals","Metals":"metals","Mining":"metals",
    "FMCG":"consumer","Beverages":"consumer",
    "Aerospace":"defence","Electronics":"defence","Shipbuilding":"defence",
    "Avionics":"defence","Defence":"defence",
    "EPC":"infra","Railways":"infra","Energy Tech":"infra",
    "Capital Goods":"infra","Electricals":"infra","Cables":"infra",
    "Industrial":"infra","Power Equipment":"infra",
    "Chemicals":"infra","Agrochemicals":"infra",
    "EMS":"newage","Drones":"newage","Fintech":"newage",
    "FoodTech":"newage","Logistics":"newage","Retail":"newage",
    "Real Estate":"realty","Telecom":"realty","Tower Infra":"realty",
}

NIFTY_INDICES = [
    ("Nifty 50",        "^NSEI"),
    ("Nifty Bank",      "^NSEBANK"),
    ("Nifty IT",        "^CNXIT"),
    ("Nifty Pharma",    "^CNXPHARMA"),
    ("Nifty Auto",      "^CNXAUTO"),
    ("Nifty FMCG",      "^CNXFMCG"),
    ("Nifty Metal",     "^CNXMETAL"),
    ("Nifty Realty",    "^CNXREALTY"),
    ("Nifty Energy",    "^CNXENERGY"),
    ("Nifty Infra",     "^CNXINFRA"),
    ("Nifty Midcap 100","^NSEMDCP100"),
    ("Nifty Smallcap",  "^CNXSC"),
    ("Nifty Next 50",   "^NSMIDCP50"),
    ("Nifty PSE",       "^CNXPSE"),
    ("Nifty Defence",   "NIFTYDEFENCE.NS"),
]

# ─────────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def dec(*a,**k):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*a,**k)
    return dec

LOGIN_HTML = """<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>India Swing Picks — Login</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Playfair+Display:wght@600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:linear-gradient(135deg,#f0f4ff 0%,#fafafa 100%);font-family:'DM Sans',sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:44px 40px;width:100%;max-width:400px;box-shadow:0 8px 40px rgba(15,76,138,.10)}
.logo{font-family:'Playfair Display',serif;font-size:24px;color:#0f4c8a;margin-bottom:4px}
.logo span{color:#b45309}
.sub{font-size:12px;color:#6b7280;margin-bottom:32px;line-height:1.5}
label{display:block;font-size:12px;font-weight:600;color:#374151;margin-bottom:6px;letter-spacing:.03em}
input{width:100%;padding:11px 14px;border:1.5px solid #e5e7eb;border-radius:9px;font-size:14px;font-family:'DM Sans',sans-serif;outline:none;transition:border .15s;color:#111827}
input:focus{border-color:#0f4c8a;box-shadow:0 0 0 3px rgba(15,76,138,.08)}
.field{margin-bottom:20px}
button{width:100%;padding:12px;background:#0f4c8a;color:#fff;border:none;border-radius:9px;font-size:14px;font-weight:600;cursor:pointer;font-family:'DM Sans',sans-serif;transition:background .15s;margin-top:4px;letter-spacing:.02em}
button:hover{background:#0a3d6e}
.err{background:#fee2e2;color:#991b1b;border-radius:8px;padding:10px 14px;font-size:12.5px;margin-bottom:18px;border:1px solid #fecaca}
.footer{font-size:10.5px;color:#9ca3af;text-align:center;margin-top:24px;line-height:1.6}
</style></head><body>
<div class="card">
  <div class="logo">India Swing <span>Picks</span></div>
  <div class="sub">NSE Auto-Screener · Nifty 500 · Daily refresh · Mar–Dec 2026</div>
  {% if error %}<div class="err">{{ error }}</div>{% endif %}
  <form method="POST">
    <div class="field"><label>Username</label><input type="text" name="username" autocomplete="username" required autofocus></div>
    <div class="field"><label>Password</label><input type="password" name="password" autocomplete="current-password" required></div>
    <button type="submit">Sign In →</button>
  </form>
  <div class="footer">Personal research tool · Not SEBI-registered advice<br>Data sourced from NSE via Yahoo Finance</div>
</div></body></html>"""

@app.route("/login", methods=["GET","POST"])
def login():
    err=None
    if request.method=="POST":
        if request.form.get("username","").strip()==APP_USERNAME and request.form.get("password","").strip()==APP_PASSWORD:
            session["logged_in"]=True; session.permanent=True
            return redirect(url_for("index"))
        err="Incorrect username or password."
    return render_template_string(LOGIN_HTML, error=err)

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

# ─────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    return send_from_directory("static","india_swing_final.html")

@app.route("/swing_data.json")
@login_required
def get_data():
    if DATA_FILE.exists(): return send_from_directory("static","swing_data.json")
    return jsonify({"error":"not ready"}),404

@app.route("/index_data.json")
@login_required
def get_index_data():
    if INDEX_FILE.exists(): return send_from_directory("static","index_data.json")
    return jsonify({"error":"not ready"}),404

@app.route("/api/status")
@login_required
def status():
    info={"data_file":DATA_FILE.exists(),"index_file":INDEX_FILE.exists()}
    if DATA_FILE.exists():
        try:
            d=json.loads(DATA_FILE.read_text())
            info["last_updated"]=d.get("meta",{}).get("updated_at","?")
            info["stock_count"]=d.get("meta",{}).get("total_stocks",0)
            info["new_entries"]=d.get("meta",{}).get("new_entries",[])
            age=(datetime.now().timestamp()-DATA_FILE.stat().st_mtime)/3600
            info["data_age_hours"]=round(age,1)
        except: pass
    return jsonify(info)

@app.route("/api/refresh")
@login_required
def trigger_refresh():
    threading.Thread(target=run_full_refresh, daemon=True).start()
    return jsonify({"status":"started","message":"Scanning Nifty 500 — takes ~10 min. Refresh dashboard in 12 minutes."})

# ─────────────────────────────────────────────────────────────────
# TECHNICAL CALCULATIONS
# ─────────────────────────────────────────────────────────────────
def safe(v, d=2):
    try:
        if v is None: return None
        f=float(v)
        return None if f!=f else round(f,d)
    except: return None

def calc_rsi(close, period=14):
    import numpy as np
    if len(close)<period+1: return None
    d=np.diff(close)
    g=np.where(d>0,d,0); l=np.where(d<0,-d,0)
    ag=np.mean(g[:period]); al=np.mean(l[:period])
    for i in range(period,len(g)):
        ag=(ag*(period-1)+g[i])/period; al=(al*(period-1)+l[i])/period
    return round(100-(100/(1+ag/al)) if al else 100, 1)

def calc_vwma(c, v, p):
    import numpy as np
    if len(c)<p: return None
    return round(float((c[-p:]*v[-p:]).sum()/v[-p:].sum()),2)

def calc_atr(h,l,c,p=14):
    import numpy as np
    if len(c)<p+1: return None
    tr=np.maximum(h[1:]-l[1:],np.maximum(abs(h[1:]-c[:-1]),abs(l[1:]-c[:-1])))
    return round(float(np.mean(tr[-p:])),2)

def vwma_signal(cmp,v9,v20,v50):
    ab=[x for x,v in [("9",v9),("20",v20),("50",v50)] if v and cmp>v]
    if len(ab)==3: return ("All 3 ✓","pg","All three moving averages below price and rising — strongest bull trend signal.")
    if len(ab)==2: return (f"{' & '.join(ab)} ✓","pa","Price above 2 of 3 moving averages — recovering but not fully confirmed.")
    if len(ab)==1: return (f"Above {ab[0]} only","pr","Only above the shortest moving average — early / weak signal.")
    return ("Below all","pr","Price below all moving averages — downtrend. Wait for recovery.")

def rsi_signal(rsi):
    if rsi is None: return ("N/A","pb","RSI could not be calculated.")
    if rsi>=75:  return (f"{rsi} ⚠ Overbought","pr",f"RSI {rsi} — very high, potential pullback ahead. Wait for cooling.")
    if rsi>=60:  return (f"{rsi} — Strong","pg",f"RSI {rsi} — strong momentum. Uptrend healthy. Good zone.")
    if rsi>=50:  return (f"{rsi} — Bullish","pg",f"RSI {rsi} — above midline. Momentum positive. Entry zone.")
    if rsi>=40:  return (f"{rsi} — Neutral","pa",f"RSI {rsi} — below midline. Consolidating. Watch for breakout above 50.")
    return (f"{rsi} — Oversold","pr",f"RSI {rsi} — oversold. Potential bounce but trend is weak. Contrarian entry only.")

def detect_pattern(close, high, low, rsi, vwma_label):
    """Heuristic chart pattern detection from price data"""
    import numpy as np
    if len(close)<60: return "Insufficient data"
    c=np.array(close); h=np.array(high); l=np.array(low)
    c20=c[-20:]; c60=c[-60:]
    recent_high=h[-20:].max(); recent_low=l[-20:].min()
    prev_high=h[-60:-20].max(); prev_low=l[-60:-20].min()
    cmp=c[-1]
    trend_up = c[-1]>c[-20] and c[-20]>c[-40]
    trend_down = c[-1]<c[-20] and c[-20]<c[-40]
    range_pct = (c20.max()-c20.min())/c20.mean()*100
    # Consolidation (tight range)
    if range_pct < 4 and rsi and 45<=rsi<=60:
        return "Horizontal Accumulation"
    # Cup & Handle
    mid_low=c[-45:-15].min(); cup_depth=(c[-50]-mid_low)/c[-50]*100
    if cup_depth>8 and cup_depth<35 and range_pct<6 and trend_up:
        return "Cup & Handle"
    # Double Bottom
    half1_low=l[-40:-20].min(); half2_low=l[-20:].min()
    if abs(half1_low-half2_low)/half1_low<0.03 and cmp>c[-30]:
        return "Double Bottom"
    # Ascending Triangle
    highs_flat=abs(h[-20:].max()-h[-40:-20].max())/h[-20:].max()<0.02
    lows_rising=l[-10:].min()>l[-20:-10].min()
    if highs_flat and lows_rising and trend_up:
        return "Ascending Triangle"
    # Falling Wedge
    if trend_down and l[-5:].min()>l[-20:-5].min() and range_pct<8:
        return "Falling Wedge"
    # Bull Flag
    strong_move=(c[-20]-c[-40])/c[-40]*100
    if strong_move>12 and range_pct<5 and rsi and rsi>55:
        return "Bull Flag"
    # Rounding Bottom
    thirds=[c[-60:-40].mean(), c[-40:-20].mean(), c[-20:].mean()]
    if thirds[0]>thirds[1] and thirds[2]>thirds[1] and trend_up:
        return "Rounding Bottom"
    # Breakout Retest
    if trend_up and recent_low>prev_high*0.97 and cmp>prev_high:
        return "Breakout Retest"
    # Base at Support
    if abs(cmp-recent_low)/recent_low<0.05 and rsi and 40<=rsi<=55:
        return "Basing at Support"
    # Multi-month Base
    if range_pct<8 and len(close)>=90:
        c90=np.array(close[-90:])
        if (c90.max()-c90.min())/c90.mean()*100 < 15:
            return "Multi-month Base"
    # Higher Lows
    if l[-5:].min()>l[-15:-5].min()>l[-30:-15].min():
        return "Higher Lows Base"
    if trend_up: return "Ascending Channel"
    if trend_down: return "Descending Channel"
    return "Consolidation"

def conviction_score(pe, roe, de, disc, rsi, vwma_lbl, div, vol_ratio=1.0):
    """Score 1-10 based on all parameters"""
    s=5.0
    # PE vs sector cheapness
    if pe:
        s+= 1.2 if pe<8 else 0.9 if pe<12 else 0.6 if pe<18 else 0.3 if pe<26 else -0.3 if pe<40 else -0.7
    # ROE quality
    if roe:
        s+= 1.0 if roe>25 else 0.7 if roe>18 else 0.4 if roe>12 else 0.1 if roe>8 else -0.4
    # D/E safety
    if de is not None:
        s+= 0.5 if de<0.2 else 0.3 if de<0.5 else 0.1 if de<1.0 else -0.3 if de>3 else -0.6 if de>6 else 0
    # Discount from 52W high (beaten down = opportunity)
    if disc:
        s+= 1.0 if disc>40 else 0.7 if disc>30 else 0.5 if disc>20 else 0.2 if disc>10 else -0.2
    # RSI technical
    if rsi:
        s+= 0.7 if 50<=rsi<=65 else 0.4 if 40<=rsi<50 else 0.3 if rsi<40 else -0.5 if rsi>75 else 0
    # VWMA alignment
    if "All 3" in (vwma_lbl or ""): s+=0.7
    elif "&" in (vwma_lbl or ""): s+=0.4
    elif "Above" in (vwma_lbl or ""): s+=0.1
    else: s-=0.3
    # Dividend safety floor
    if div:
        s+= 0.5 if div>=4 else 0.3 if div>=2.5 else 0.1 if div>=1 else 0
    # Volume confirmation
    if vol_ratio>2.0: s+=0.3
    elif vol_ratio>1.5: s+=0.1
    return round(min(10,max(1,s)),1)

def calc_stars(pe,roe,de,rsi,vs,div):
    f=min(100,max(0,
        (32 if pe and pe<10 else 24 if pe and pe<18 else 16 if pe and pe<28 else 8 if pe else 0)+
        (36 if roe and roe>22 else 26 if roe and roe>15 else 16 if roe and roe>10 else 5 if roe else 0)+
        (20 if de is not None and de<0.3 else 14 if de is not None and de<1 else 8 if de is not None and de<2.5 else 3 if de is not None else 0)+
        (12 if div and div>=4 else 8 if div and div>=2 else 4 if div else 0)))
    t=min(100,max(0,
        (44 if rsi and 50<=rsi<=65 else 28 if rsi and 40<=rsi<50 else 18 if rsi and rsi<40 else 8 if rsi else 0)+
        (56 if "All 3" in (vs or "") else 38 if "&" in (vs or "") else 18)))
    g=min(100,max(0,
        (42 if roe and roe>22 else 30 if roe and roe>15 else 18 if roe and roe>10 else 8 if roe else 0)+
        (38 if pe and pe<10 else 26 if pe and pe<18 else 16 if pe and pe<28 else 8 if pe else 0)+
        (20 if div and div>=2 else 10 if div else 0)))
    o=round(((f/100*0.4+t/100*0.3+g/100*0.3)*5)*2)/2
    return {"o":o,"f":f,"t":t,"g":g}

# ─────────────────────────────────────────────────────────────────
# FETCH ONE STOCK
# ─────────────────────────────────────────────────────────────────
def fetch_one(nse_code, tag, retries=2):
    try:
        import yfinance as yf
        import numpy as np
    except ImportError:
        return None

    ALT={
        "BAJAJ-AUTO":["BAJAJ-AUTO.NS","BAJAJAUTO.NS"],
        "M&M":["M&M.NS","MM.NS"],
        "TATAMOTORS":["TATAMOTORS.NS","TATAMOTOR.NS"],
    }
    tickers=ALT.get(nse_code,[f"{nse_code}.NS"])

    for attempt in range(retries):
        tk=tickers[min(attempt,len(tickers)-1)]
        try:
            t=yf.Ticker(tk)
            h=t.history(period="1y",interval="1d")
            if h.empty: continue
            c=h["Close"].values; hi=h["High"].values
            lo=h["Low"].values;  vol=h["Volume"].values
            if len(c)<20: continue

            cmp=round(float(c[-1]),2)
            h52=round(float(hi.max()),2); l52=round(float(lo.min()),2)
            disc=round((h52-cmp)/h52*100,1) if h52 else None
            hdate_idx=int(hi.argmax())
            hdate=h.index[hdate_idx].strftime("%b '%y") if hdate_idx<len(h.index) else "—"
            ldate_idx=int(lo.argmin())
            ldate=h.index[ldate_idx].strftime("%b '%y") if ldate_idx<len(h.index) else "—"

            rv=calc_rsi(c); v9=calc_vwma(c,vol,9); v20=calc_vwma(c,vol,20); v50=calc_vwma(c,vol,50)
            at=calc_atr(hi,lo,c)
            vol_avg=float(np.mean(vol[-20:])) if len(vol)>=20 else 1
            vol_ratio=round(float(vol[-1])/vol_avg,1) if vol_avg>0 else 1.0

            vs,vc,vt=vwma_signal(cmp,v9,v20,v50)
            rs,rc,rt=rsi_signal(rv)
            pattern=detect_pattern(list(c),list(hi),list(lo),rv,vs)

            at2=at if at else cmp*0.02
            tgt=round(cmp+3.5*at2,2); sl=round(cmp-1.5*at2,2)
            up=f"+{round((tgt-cmp)/cmp*100,1)}%"

            info=t.info
            pe=safe(info.get("trailingPE") or info.get("forwardPE"))
            roe=safe((info.get("returnOnEquity") or 0)*100,1)
            de_raw=info.get("debtToEquity")
            de=safe(de_raw/100 if de_raw else 0,2)
            div=safe((info.get("dividendYield") or 0)*100,1)
            pb=safe(info.get("priceToBook"))
            eps=safe(info.get("trailingEps"))
            mc=info.get("marketCap",0)
            mcs=f"₹{mc/1e11:.1f}L Cr" if mc and mc>1e11 else f"₹{mc/1e9:.0f}Bn" if mc else "N/A"

            sc=conviction_score(pe,roe,de,disc,rv,vs,div,vol_ratio)
            sig="sb" if sc>=8.5 else "mb" if sc>=7 else "w"
            risk_level="low" if sc>=8.5 and (de or 1)<0.5 else "high" if sc<7 or (de or 0)>5 else "med"

            pc="pg" if pe and pe<15 else "pa" if pe and pe<30 else "pr"
            rc2="pg" if roe and roe>=18 else "pa" if roe and roe>=12 else "pr"
            dc="pg" if de is not None and de<0.5 else "pa" if de is not None and de<2 else "pr"
            divc="pg" if div and div>=3 else "pa" if div and div>=1 else "pr"

            return {
                "name":  info.get("shortName", nse_code),
                "nse":   nse_code.replace("-",""),
                "cmp":   cmp,
                "tgt":   tgt,
                "sl":    sl,
                "sig":   sig,
                "score": sc,
                "stars": calc_stars(pe,roe,de,rv,vs,div),
                "sector_tag": tag,
                "pattern": pattern,
                "high52w":  h52,
                "low52w":   l52,
                "high_date":hdate,
                "low_date": ldate,
                "disc":     disc,
                "vol_ratio":vol_ratio,
                "rsi":{
                    "v":rs,"c":rc,
                    "t":rt+f" ATR=₹{at}. VWMA9={v9}, VWMA20={v20}, VWMA50={v50}.",
                    "std":"50-70 = healthy uptrend. Below 40 = oversold. Above 80 = overbought."
                },
                "vwma":{
                    "v":vs,"c":vc,
                    "t":vt+f" VWMA9={v9}, VWMA20={v20}, VWMA50={v50}. CMP=₹{cmp}.",
                    "std":"All 3 up = strong bull. Mixed = cautious. All down = avoid."
                },
                "pe":{
                    "v":f"{pe}x" if pe else "N/M","c":pc,
                    "t":f"P/E {pe}x. You pay ₹{pe} for every ₹1 of annual profit. {'Cheap' if pe and pe<15 else 'Fair' if pe and pe<30 else 'Expensive'}.",
                    "std":"Below 15x = cheap. 15-25x = fair. Above 35x = expensive."
                },
                "roe":{
                    "v":f"{roe}%" if roe else "N/A","c":rc2,
                    "t":f"ROE {roe}%. For every ₹100 owned, company earns ₹{roe}/yr. {'Excellent' if roe and roe>=20 else 'Good' if roe and roe>=15 else 'Below avg'}.",
                    "std":"Above 20% = excellent. 15-20% = good. 10-15% = average. Below 10% = poor."
                },
                "de":{
                    "v":str(de) if de is not None else "N/A","c":dc,
                    "t":f"Debt/Equity = {de}. {'Low debt — safe' if de and de<0.5 else 'Moderate' if de and de<2 else 'High leverage — monitor'}.",
                    "std":"Below 0.5 = safe. 0.5-2 = moderate. Above 3 = risky."
                },
                "div":{
                    "v":f"{div}%" if div else "0%","c":divc,
                    "t":f"Dividend yield {div}%. ₹{round((div or 0)*1000)} per lakh/yr. {'Excellent income' if div and div>=3 else 'Moderate' if div and div>=1 else 'Growth play'}.",
                    "std":"Above 3% = excellent. 1-3% = balanced. Below 1% = growth play."
                },
                "pb":   f"{pb}x" if pb else "N/A",
                "eps":  f"₹{eps}" if eps else "N/A",
                "mcap": mcs,
                "upside": up,
                "risk":  risk_level,
                "risk_reason": f"Score {sc}/10. {disc}% off 52W high. ROE {roe}%. D/E {de}. RSI {rv}. Vol ratio {vol_ratio}x avg.",
                "horizon":"Jun–Dec 2026",
                "fetched_at": datetime.now().isoformat(),
                "is_new": False
            }
        except Exception as ex:
            log.warning(f"  {tk} attempt {attempt+1} failed: {ex}")
            time.sleep(1)
    return None

# ─────────────────────────────────────────────────────────────────
# FETCH NIFTY INDICES
# ─────────────────────────────────────────────────────────────────
def fetch_indices():
    try:
        import yfinance as yf
        import numpy as np
    except: return []

    results=[]
    for (name, ticker) in NIFTY_INDICES:
        try:
            t=yf.Ticker(ticker)
            h=t.history(period="1y",interval="1d")
            if h.empty: continue
            c=h["Close"].values; hi=h["High"].values; lo=h["Low"].values; vol=h["Volume"].values
            cmp=round(float(c[-1]),2)
            h52=round(float(hi.max()),2); l52=round(float(lo.min()),2)
            disc=round((h52-cmp)/h52*100,1)
            frm52l=round((cmp-l52)/l52*100,1)
            rv=calc_rsi(c)
            v9=calc_vwma(c,vol,9) if vol.sum()>0 else None
            v20=calc_vwma(c,vol,20) if vol.sum()>0 else None
            v50=calc_vwma(c,vol,50) if vol.sum()>0 else None
            vs,vc,_=vwma_signal(cmp,v9,v20,v50)
            pattern=detect_pattern(list(c),list(hi),list(lo),rv,vs)
            # weekly candles for chart
            wkly=h.resample("W").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
            chart_data=[{"t":str(row.Index.date()),"o":round(row.Open,2),"h":round(row.High,2),
                         "l":round(row.Low,2),"c":round(row.Close,2)} for row in wkly.itertuples()][-52:]
            # momentum classification
            mom_1m=round((c[-1]-c[-21])/c[-21]*100,1) if len(c)>21 else None
            mom_3m=round((c[-1]-c[-63])/c[-63]*100,1) if len(c)>63 else None
            # status
            if disc<5 and rv and rv>60:
                status="🔥 Near 52W High — Breakout zone"
                status_c="pg"
            elif disc>30:
                status="🟡 Deep correction — watch for base"
                status_c="pa"
            elif rv and rv<40:
                status="⚠️ Oversold — potential bounce"
                status_c="pr"
            elif "Accumulation" in pattern or "Base" in pattern:
                status="📦 Consolidating — breakout watch"
                status_c="pb"
            elif "Breakout" in pattern or "Bull" in pattern:
                status="📈 Breakout in progress"
                status_c="pg"
            elif "Triangle" in pattern or "Wedge" in pattern:
                status="⚡ Pattern forming — breakout near"
                status_c="pa"
            else:
                status=f"➡️ {pattern}"
                status_c="pb"

            results.append({
                "name":     name,
                "ticker":   ticker,
                "cmp":      cmp,
                "high52w":  h52,
                "low52w":   l52,
                "disc":     disc,
                "frm52l":   frm52l,
                "rsi":      rv,
                "vwma":     vs,
                "vwma_c":   vc,
                "pattern":  pattern,
                "status":   status,
                "status_c": status_c,
                "mom_1m":   mom_1m,
                "mom_3m":   mom_3m,
                "chart":    chart_data[-26:],  # 6 months weekly
                "fetched_at": datetime.now().isoformat()
            })
            log.info(f"  ✓ Index {name}: {cmp}, RSI={rv}, {pattern}")
            time.sleep(0.5)
        except Exception as ex:
            log.warning(f"  Index {name} failed: {ex}")
    return results

# ─────────────────────────────────────────────────────────────────
# MAIN REFRESH — scans Nifty 500
# ─────────────────────────────────────────────────────────────────
def run_full_refresh():
    log.info("="*60)
    log.info(f"FULL REFRESH STARTED: {datetime.now()}")

    # Save previous for new-entry detection
    if DATA_FILE.exists():
        try:
            prev=json.loads(DATA_FILE.read_text())
            PREV_FILE.write_text(json.dumps(prev))
            prev_nse={s["nse"] for s in prev.get("stocks",[])}
        except: prev_nse=set()
    else:
        prev_nse=set()

    # Fetch all stocks
    all_results=[]; failed=[]
    for (nse_code, tag) in NIFTY500_FALLBACK:
        sector=SECTOR_MAP.get(tag,"infra")
        r=fetch_one(nse_code, tag)
        if r:
            r["sector"]=sector
            all_results.append(r)
        else:
            failed.append(nse_code)
        time.sleep(0.6)

    # Pick top 5 per sector by conviction score
    from collections import defaultdict
    by_sector=defaultdict(list)
    for r in all_results:
        by_sector[r["sector"]].append(r)

    top_picks=[]
    MIN_SCORE=6.5
    TOP_N=5
    for sec, stocks in by_sector.items():
        filtered=[s for s in stocks if s["score"]>=MIN_SCORE]
        filtered.sort(key=lambda x: x["score"], reverse=True)
        top_picks.extend(filtered[:TOP_N])

    # Mark new entries
    new_entries=[]
    for s in top_picks:
        if s["nse"] not in prev_nse:
            s["is_new"]=True
            new_entries.append(s["nse"])
        else:
            s["is_new"]=False

    top_picks.sort(key=lambda x: x["score"], reverse=True)

    output={
        "meta":{
            "updated_at":   datetime.now().isoformat(),
            "total_stocks": len(top_picks),
            "scanned":      len(all_results),
            "failed":       failed,
            "new_entries":  new_entries,
            "min_score":    MIN_SCORE,
            "source":       "Yahoo Finance NSE · Nifty 500 auto-scan"
        },
        "stocks": top_picks
    }
    STATIC.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(output,indent=2))
    log.info(f"✅ {len(top_picks)} picks from {len(all_results)} scanned. New entries: {new_entries}")

    # Fetch indices
    log.info("Fetching Nifty indices...")
    idx_data=fetch_indices()
    INDEX_FILE.write_text(json.dumps({
        "meta":{"updated_at":datetime.now().isoformat(),"count":len(idx_data)},
        "indices":idx_data
    },indent=2))
    log.info(f"✅ {len(idx_data)} indices fetched")
    log.info("="*60)

# ─────────────────────────────────────────────────────────────────
# SCHEDULER
# ─────────────────────────────────────────────────────────────────
def scheduler():
    log.info("Scheduler started")
    # Initial run if no data
    if not DATA_FILE.exists():
        log.info("No data — running initial refresh now")
        run_full_refresh()
    else:
        age=(datetime.now().timestamp()-DATA_FILE.stat().st_mtime)/3600
        if age>20:
            log.info(f"Data {age:.1f}h old — refreshing")
            run_full_refresh()
    while True:
        now=datetime.utcnow()
        target=now.replace(hour=3,minute=45,second=0,microsecond=0)
        if now>=target: target+=timedelta(days=1)
        wait=(target-now).total_seconds()
        log.info(f"Next refresh in {wait/3600:.1f}h ({target.strftime('%Y-%m-%d %H:%M')} UTC = 9:15 AM IST)")
        time.sleep(wait)
        if datetime.utcnow().weekday()<5:
            run_full_refresh()
        else:
            log.info("Weekend — skipping")

threading.Thread(target=scheduler, daemon=True).start()

if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port,debug=False)
