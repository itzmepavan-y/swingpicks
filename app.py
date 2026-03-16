"""
India Swing Picks — NSE Direct API (no Yahoo, no Stooq)
"""
import os,json,time,logging,threading,math
from datetime import datetime,timedelta
from pathlib import Path
from functools import wraps
from flask import Flask,request,session,redirect,url_for,send_from_directory,jsonify,render_template_string
import requests as req

logging.basicConfig(level=logging.INFO,format="%(asctime)s [%(levelname)s] %(message)s")
log=logging.getLogger(__name__)
app=Flask(__name__,static_folder="static")
app.secret_key=os.environ.get("SECRET_KEY","changeme")
app.permanent_session_lifetime=timedelta(days=30)
APP_USERNAME=os.environ.get("APP_USERNAME","pavan")
APP_PASSWORD=os.environ.get("APP_PASSWORD","swing2026")
STATIC=Path(__file__).parent/"static"
DATA_FILE=STATIC/"swing_data.json"
PREV_FILE=STATIC/"swing_data_prev.json"
IDX_FILE=STATIC/"index_data.json"

SECTOR_MAP={
    "Banking":"banking","NBFC":"banking","Fin. Services":"banking","Rail Finance":"banking",
    "IT":"it","Pharma":"pharma","Hospitals":"pharma",
    "Auto":"auto","Auto Ancil":"auto",
    "Oil & Gas":"energy","Gas":"energy","Power":"energy","Renewables":"energy","Energy":"energy",
    "Steel":"metals","Metals":"metals","Mining":"metals",
    "FMCG":"consumer","Beverages":"consumer",
    "Aerospace":"defence","Electronics":"defence","Shipbuilding":"defence","Defence":"defence",
    "EPC":"infra","Railways":"infra","Energy Tech":"infra","Capital Goods":"infra",
    "Electricals":"infra","Cables":"infra","Industrial":"infra","Chemicals":"infra",
    "EMS":"newage","FoodTech":"newage","Logistics":"newage",
    "Real Estate":"realty","Telecom":"realty","Tower Infra":"realty"
}

STOCKS=[
    ("HDFCBANK","Banking"),("SBIN","Banking"),("ICICIBANK","Banking"),("KOTAKBANK","Banking"),
    ("AXISBANK","Banking"),("CANBK","Banking"),("BANKBARODA","Banking"),("PNB","Banking"),
    ("BAJFINANCE","NBFC"),("CHOLAFIN","NBFC"),("MUTHOOTFIN","NBFC"),
    ("PFC","Fin. Services"),("RECLTD","Fin. Services"),("IRFC","Rail Finance"),
    ("INFY","IT"),("TCS","IT"),("HCLTECH","IT"),("WIPRO","IT"),
    ("TECHM","IT"),("MPHASIS","IT"),("PERSISTENT","IT"),("COFORGE","IT"),
    ("SUNPHARMA","Pharma"),("CIPLA","Pharma"),("DRREDDY","Pharma"),
    ("DIVISLAB","Pharma"),("MANKIND","Pharma"),("GLAND","Pharma"),
    ("APOLLOHOSP","Hospitals"),("MAXHEALTH","Hospitals"),
    ("MARUTI","Auto"),("M%26M","Auto"),("BAJAJ-AUTO","Auto"),
    ("EICHERMOT","Auto"),("ASHOKLEY","Auto"),("TVSMOTOR","Auto"),
    ("MOTHERSON","Auto Ancil"),("BHARATFORG","Auto Ancil"),
    ("ONGC","Oil & Gas"),("BPCL","Oil & Gas"),("IOC","Oil & Gas"),
    ("GAIL","Gas"),("NTPC","Power"),("POWERGRID","Power"),("TATAPOWER","Power"),
    ("COALINDIA","Energy"),("ADANIGREEN","Renewables"),
    ("JSWSTEEL","Steel"),("TATASTEEL","Steel"),("SAIL","Steel"),
    ("HINDALCO","Metals"),("NATIONALUM","Metals"),("NMDC","Mining"),("VEDL","Metals"),
    ("ITC","FMCG"),("HINDUNILVR","FMCG"),("BRITANNIA","FMCG"),
    ("DABUR","FMCG"),("MARICO","FMCG"),("EMAMILTD","FMCG"),("TATACONSUM","FMCG"),
    ("HAL","Aerospace"),("BEL","Electronics"),("MAZDOCK","Shipbuilding"),
    ("GRSE","Shipbuilding"),("BEML","Defence"),
    ("LT","EPC"),("SIEMENS","Energy Tech"),("ABB","Capital Goods"),
    ("HAVELLS","Electricals"),("POLYCAB","Cables"),("CUMMINSIND","Industrial"),
    ("THERMAX","Industrial"),("BHEL","Defence"),("RVNL","Railways"),
    ("DEEPAKNTR","Chemicals"),("PIIND","Chemicals"),("TATACHEM","Chemicals"),
    ("KAYNES","EMS"),("DIXON","EMS"),("AMBER","EMS"),
    ("ZOMATO","FoodTech"),("DELHIVERY","Logistics"),
    ("GODREJPROP","Real Estate"),("DLF","Real Estate"),
    ("BHARTIARTL","Telecom"),("INDUSTOWER","Tower Infra"),
]

NIFTY_INDICES=[
    ("Nifty 50","NIFTY%2050"),
    ("Nifty Bank","NIFTY%20BANK"),
    ("Nifty IT","NIFTY%20IT"),
    ("Nifty Pharma","NIFTY%20PHARMA"),
    ("Nifty Auto","NIFTY%20AUTO"),
    ("Nifty FMCG","NIFTY%20FMCG"),
    ("Nifty Metal","NIFTY%20METAL"),
    ("Nifty Realty","NIFTY%20REALTY"),
    ("Nifty Energy","NIFTY%20ENERGY"),
    ("Nifty Midcap 100","NIFTY%20MIDCAP%20100"),
    ("Nifty Next 50","NIFTY%20NEXT%2050"),
    ("Nifty PSE","NIFTY%20PSE"),
]

NSE_HEADERS={
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept":"application/json, text/plain, */*",
    "Accept-Language":"en-US,en;q=0.9",
    "Accept-Encoding":"gzip, deflate, br",
    "Referer":"https://www.nseindia.com/",
    "Origin":"https://www.nseindia.com",
    "Connection":"keep-alive",
    "sec-fetch-dest":"empty",
    "sec-fetch-mode":"cors",
    "sec-fetch-site":"same-origin",
}

def get_nse_session():
    s=req.Session()
    s.headers.update(NSE_HEADERS)
    try:
        s.get("https://www.nseindia.com",timeout=15)
        time.sleep(1.5)
        s.get("https://www.nseindia.com/market-data/live-equity-market",timeout=10)
        time.sleep(0.5)
        log.info("NSE session ready")
    except Exception as ex:
        log.warning(f"NSE session init: {ex}")
    return s

def safe(v,d=2):
    try:
        if v is None:return None
        f=float(v)
        return None if(math.isnan(f) or math.isinf(f))else round(f,d)
    except:return None

def calc_rsi(c,p=14):
    if len(c)<p+1:return None
    g=[max(c[i]-c[i-1],0)for i in range(1,len(c))]
    l=[max(c[i-1]-c[i],0)for i in range(1,len(c))]
    ag=sum(g[:p])/p;al=sum(l[:p])/p
    for i in range(p,len(g)):
        ag=(ag*(p-1)+g[i])/p;al=(al*(p-1)+l[i])/p
    return round(100-(100/(1+ag/al))if al else 100,1)

def calc_vwma(c,v,p):
    if len(c)<p:return None
    sv=sum(v[-p:])
    return round(sum(c[-p:][i]*v[-p:][i]for i in range(p))/sv,2)if sv else None

def calc_atr(h,l,c,p=14):
    if len(c)<p+1:return None
    trs=[max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1]))for i in range(1,len(c))]
    return round(sum(trs[-p:])/p,2)

def vwma_sig(cmp,v9,v20,v50):
    ab=[x for x,v in[("9",v9),("20",v20),("50",v50)]if v and cmp>v]
    if len(ab)==3:return("All 3 ✓","pg","All 3 moving averages below price — strongest bull trend.")
    if len(ab)==2:return(f"{' & '.join(ab)} ✓","pa","Price above 2 of 3 averages — recovering.")
    if len(ab)==1:return(f"Above {ab[0]} only","pr","Weak — above only shortest average.")
    return("Below all","pr","Price below all averages — downtrend.")

def rsi_sig(rv):
    if rv is None:return("N/A","pb","Could not calculate.")
    if rv>=75:return(f"{rv} ⚠ Overbought","pr",f"RSI {rv} — very high, pullback likely.")
    if rv>=60:return(f"{rv} — Strong","pg",f"RSI {rv} — strong momentum, healthy uptrend.")
    if rv>=50:return(f"{rv} — Bullish","pg",f"RSI {rv} — above midline, momentum positive.")
    if rv>=40:return(f"{rv} — Neutral","pa",f"RSI {rv} — below midline, consolidating.")
    return(f"{rv} — Oversold","pr",f"RSI {rv} — oversold, potential bounce.")

def detect_pat(c,h,l,rsi,vs):
    if len(c)<40:return"Consolidation"
    r20=(max(c[-20:])-min(c[-20:]))/(sum(c[-20:])/20)*100 if sum(c[-20:])>0 else 0
    tu=c[-1]>c[-20]>c[-40];td=c[-1]<c[-20]<c[-40]
    if len(c)>=40 and c[-40]>0:
        pole=(c[-20]-c[-40])/c[-40]*100
        if pole>12 and r20<5 and rsi and rsi>55:return"Bull Flag"
    if len(c)>=60 and c[-55]>0:
        ml=min(c[-50:-15]);cd=(c[-55]-ml)/c[-55]*100
        if 8<cd<35 and r20<6 and tu:return"Cup & Handle"
    if len(l)>=40:
        l1=min(l[-40:-20]);l2=min(l[-20:])
        if abs(l1-l2)/max(l1,1)<0.03 and c[-1]>c[-30]:return"Double Bottom"
    if len(h)>=40:
        ft=abs(max(h[-20:])-max(h[-40:-20]))/max(max(h[-20:]),1)<0.02
        if ft and min(l[-10:])>min(l[-20:-10]) and tu:return"Ascending Triangle"
    if td and len(l)>=20 and min(l[-5:])>min(l[-20:-5]) and r20<8:return"Falling Wedge"
    if len(c)>=60:
        t3=[sum(c[-60:-40])/20,sum(c[-40:-20])/20,sum(c[-20:])/20]
        if t3[0]>t3[1] and t3[2]>t3[1] and tu:return"Rounding Bottom"
    if len(l)>=30 and min(l[-5:])>min(l[-15:-5])>min(l[-30:-15]):return"Higher Lows Base"
    if r20<4 and rsi and 44<=rsi<=58:return"Horizontal Accumulation"
    if len(c)>=90 and(max(c[-90:])-min(c[-90:]))/(sum(c[-90:])/90)*100<15:return"Multi-month Base"
    if tu:return"Ascending Channel"
    if td:return"Descending Channel"
    return"Consolidation"

def conv_score(pe,roe,de,disc,rsi,vs,div):
    s=5.0
    if pe:s+=1.2 if pe<8 else 0.9 if pe<12 else 0.6 if pe<18 else 0.3 if pe<26 else-0.3 if pe<40 else-0.7
    if roe:s+=1.0 if roe>25 else 0.7 if roe>18 else 0.4 if roe>12 else 0.1 if roe>8 else-0.4
    if de is not None:s+=0.5 if de<0.2 else 0.3 if de<0.5 else 0.1 if de<1 else-0.3 if de>3 else-0.6 if de>6 else 0
    if disc:s+=1.0 if disc>40 else 0.7 if disc>30 else 0.5 if disc>20 else 0.2 if disc>10 else-0.2
    if rsi:s+=0.7 if 50<=rsi<=65 else 0.4 if 40<=rsi<50 else 0.3 if rsi<40 else-0.5 if rsi>75 else 0
    if"All 3"in(vs or""):s+=0.7
    elif"&"in(vs or""):s+=0.4
    elif"Above"in(vs or""):s+=0.1
    else:s-=0.3
    if div:s+=0.5 if div>=4 else 0.3 if div>=2.5 else 0.1 if div>=1 else 0
    return round(min(10,max(1,s)),1)

def calc_stars(pe,roe,de,rsi,vs,div):
    f=min(100,max(0,(32 if pe and pe<10 else 24 if pe and pe<18 else 16 if pe and pe<28 else 8 if pe else 0)+(36 if roe and roe>22 else 26 if roe and roe>15 else 16 if roe and roe>10 else 5 if roe else 0)+(20 if de is not None and de<0.3 else 14 if de is not None and de<1 else 8 if de is not None and de<2.5 else 3 if de is not None else 0)+(12 if div and div>=4 else 8 if div and div>=2 else 4 if div else 0)))
    t=min(100,max(0,(44 if rsi and 50<=rsi<=65 else 28 if rsi and 40<=rsi<50 else 18 if rsi and rsi<40 else 8 if rsi else 0)+(56 if"All 3"in(vs or"")else 38 if"&"in(vs or"")else 18)))
    g=min(100,max(0,(42 if roe and roe>22 else 30 if roe and roe>15 else 18 if roe and roe>10 else 8 if roe else 0)+(38 if pe and pe<10 else 26 if pe and pe<18 else 16 if pe and pe<28 else 8 if pe else 0)+(20 if div and div>=2 else 10 if div else 0)))
    return{"o":round(((f/100*0.4+t/100*0.3+g/100*0.3)*5)*2)/2,"f":f,"t":t,"g":g}

def fetch_one(nse,sym,tag):
    try:
        end=datetime.now();start=end-timedelta(days=380)
        sf=start.strftime("%d-%m-%Y");ef=end.strftime("%d-%m-%Y")
        url=f"https://www.nseindia.com/api/historical/cm/equity?symbol={sym}&series=[%22EQ%22]&from={sf}&to={ef}"
        r=nse.get(url,timeout=20);r.raise_for_status()
        data=r.json().get("data",[])
        if not data:
            log.warning(f"  {sym}: no history data");return None
        rows=[]
        for d in data:
            try:
                rows.append({
                    "date":d.get("CH_TIMESTAMP","")[:10],
                    "open":float(d.get("CH_OPENING_PRICE",0) or 0),
                    "high":float(d.get("CH_TRADE_HIGH_PRICE",0) or 0),
                    "low":float(d.get("CH_TRADE_LOW_PRICE",0) or 0),
                    "close":float(d.get("CH_CLOSING_PRICE",0) or 0),
                    "volume":float(d.get("CH_TOT_TRADED_QTY",0) or 0),
                })
            except:pass
        rows.sort(key=lambda x:x["date"])
        if len(rows)<20:return None
        c=[r["close"]for r in rows];h=[r["high"]for r in rows]
        l=[r["low"]for r in rows];v=[r["volume"]for r in rows]
        cmp=round(c[-1],2);h52=round(max(h),2);l52=round(min(l),2)
        disc=round((h52-cmp)/h52*100,1)if h52>0 else None
        def fmtd(d):
            try:return datetime.strptime(d[:10],"%Y-%m-%d").strftime("%b '%y")
            except:return d[:7]
        hdate=fmtd(rows[h.index(max(h))]["date"])
        ldate=fmtd(rows[l.index(min(l))]["date"])
        rv=calc_rsi(c);v9=calc_vwma(c,v,9);v20=calc_vwma(c,v,20);v50=calc_vwma(c,v,50)
        at=calc_atr(h,l,c)
        vol_avg=sum(v[-20:])/20 if len(v)>=20 and sum(v[-20:])>0 else 1
        vr=round(v[-1]/vol_avg,1)if vol_avg>0 else 1.0
        vs,vc,vt=vwma_sig(cmp,v9,v20,v50)
        rs,rc,rt=rsi_sig(rv)
        pat=detect_pat(c,h,l,rv,vs)
        at2=at if at else cmp*0.02
        tgt=round(cmp+3.5*at2,2);sl=round(cmp-1.5*at2,2)
        up=f"+{round((tgt-cmp)/cmp*100,1)}%"
        # Fundamentals from quote
        pe=roe=de=div=None
        try:
            qurl=f"https://www.nseindia.com/api/quote-equity?symbol={sym}"
            qr=nse.get(qurl,timeout=10);qd=qr.json()
            meta=qd.get("metadata",{})
            pe=safe(meta.get("pdSymbolPe") or meta.get("pdSectorPe"))
            # basic financial ratios if available
        except:pass
        sc=conv_score(pe,roe,de,disc,rv,vs,div)
        sig="sb"if sc>=8.5 else"mb"if sc>=7 else"w"
        risk="low"if sc>=8.5 and(de or 1)<0.5 else"high"if sc<7 else"med"
        pc="pg"if pe and pe<15 else"pa"if pe and pe<30 else"pr"if pe else"pb"
        return{
            "name":sym.replace("%26","&"),"nse":sym.replace("-","").replace("%26",""),
            "cmp":cmp,"tgt":tgt,"sl":sl,"sig":sig,"score":sc,
            "stars":calc_stars(pe,roe,de,rv,vs,div),
            "sector_tag":tag,"pattern":pat,
            "high52w":h52,"low52w":l52,"high_date":hdate,"low_date":ldate,"disc":disc,
            "is_new":False,
            "rsi":{"v":rs,"c":rc,"t":rt+f" ATR=₹{at}. VWMA9={v9}, 20={v20}, 50={v50}.","std":"50-70=healthy. Below 40=oversold. Above 80=overbought."},
            "vwma":{"v":vs,"c":vc,"t":vt,"std":"All 3 up=bull. Mixed=caution. All down=avoid."},
            "pe":{"v":f"{pe}x"if pe else"N/M","c":pc,"t":f"P/E {pe}. {'Cheap'if pe and pe<15 else'Fair'if pe and pe<30 else'Expensive'if pe else'N/A'}.","std":"Below 15x=cheap. 15-25x=fair. Above 35x=expensive."},
            "roe":{"v":"N/A","c":"pb","t":"Updating...","std":"Above 20%=excellent. 15-20%=good."},
            "de":{"v":"N/A","c":"pb","t":"Updating...","std":"Below 0.5=safe. Above 3=risky."},
            "div":{"v":"N/A","c":"pb","t":"Updating...","std":"Above 3%=excellent."},
            "upside":up,"risk":risk,
            "risk_reason":f"Score {sc}/10. {disc}% off 52W high. RSI {rv}.",
            "horizon":"Jun–Dec 2026","fetched_at":datetime.now().isoformat()
        }
    except Exception as ex:
        log.warning(f"  {sym} failed: {ex}");return None

def fetch_indices_data(nse):
    results=[]
    for name,idx in NIFTY_INDICES:
        try:
            end=datetime.now();start=end-timedelta(days=400)
            sf=start.strftime("%d-%m-%Y");ef=end.strftime("%d-%m-%Y")
            url=f"https://www.nseindia.com/api/historical/indicesHistory?indexType={idx}&from={sf}&to={ef}"
            r=nse.get(url,timeout=20);r.raise_for_status()
            data=r.json().get("data",{}).get("indexCloseOnlineRecords",[])
            if not data:
                log.warning(f"  Index {name}: no data");continue
            rows=[]
            for d in data:
                try:
                    rows.append({
                        "date":str(d.get("EOD_TIMESTAMP",""))[:10],
                        "close":float(d.get("EOD_CLOSE_INDEX_VAL",0) or 0),
                        "high":float(d.get("EOD_HIGH_INDEX_VAL",0) or 0),
                        "low":float(d.get("EOD_LOW_INDEX_VAL",0) or 0),
                    })
                except:pass
            rows.sort(key=lambda x:x["date"])
            if len(rows)<20:continue
            c=[r["close"]for r in rows];h=[r["high"]or r["close"] for r in rows]
            l=[r["low"]or r["close"] for r in rows];v=[1.0]*len(c)
            cmp=round(c[-1],2);h52=round(max(h),2);l52=round(min(l),2)
            disc=round((h52-cmp)/h52*100,1)if h52>0 else 0
            frm52l=round((cmp-l52)/l52*100,1)if l52>0 else 0
            rv=calc_rsi(c);v9=calc_vwma(c,v,9);v20=calc_vwma(c,v,20);v50=calc_vwma(c,v,50)
            vs,vc,_=vwma_sig(cmp,v9,v20,v50)
            pat=detect_pat(c,h,l,rv,vs)
            m1=round((c[-1]-c[-21])/c[-21]*100,1)if len(c)>21 else None
            m3=round((c[-1]-c[-63])/c[-63]*100,1)if len(c)>63 else None
            chart=[{"t":r["date"],"c":r["close"]}for r in rows[-26:]]
            if disc<5 and rv and rv>60:st,sc2="🔥 Near 52W High — Breakout zone","pg"
            elif disc>30:st,sc2="🟡 Deep correction — base watch","pa"
            elif rv and rv<40:st,sc2="⚠️ Oversold — potential bounce","pr"
            elif"Bull"in pat or"Breakout"in pat:st,sc2="📈 Breakout in progress","pg"
            elif"Triangle"in pat or"Wedge"in pat or"Flag"in pat:st,sc2="⚡ Pattern forming — breakout near","pa"
            elif"Accumulation"in pat or"Base"in pat:st,sc2="📦 Consolidating — breakout watch","pb"
            else:st,sc2=f"➡️ {pat}","pb"
            results.append({"name":name,"ticker":idx,"cmp":cmp,"high52w":h52,"low52w":l52,
                "disc":disc,"frm52l":frm52l,"rsi":rv,"vwma":vs,"vwma_c":vc,"pattern":pat,
                "status":st,"status_c":sc2,"mom_1m":m1,"mom_3m":m3,
                "chart":chart,"fetched_at":datetime.now().isoformat()})
            log.info(f"  ✓ Index {name}: {cmp} RSI={rv} {pat}")
            time.sleep(0.5)
        except Exception as ex:
            log.warning(f"  Index {name} failed: {ex}")
    return results

def run_full_refresh():
    log.info("="*50+f"\nFULL REFRESH: {datetime.now()}")
    prev_nse=set()
    if DATA_FILE.exists():
        try:
            prev=json.loads(DATA_FILE.read_text())
            PREV_FILE.write_text(json.dumps(prev))
            prev_nse={s["nse"]for s in prev.get("stocks",[])}
        except:pass
    log.info("Creating NSE session...")
    nse=get_nse_session()
    all_r=[];failed=[]
    for sym,tag in STOCKS:
        sec=SECTOR_MAP.get(tag,"infra")
        r=fetch_one(nse,sym,tag)
        if r:
            r["sector"]=sec;all_r.append(r)
            log.info(f"  ✓ {sym}: ₹{r['cmp']} RSI={r['rsi']['v']} Score={r['score']}")
        else:
            failed.append(sym);log.warning(f"  ✗ {sym}")
        time.sleep(0.5)
    from collections import defaultdict
    by_sec=defaultdict(list)
    for r in all_r:by_sec[r["sector"]].append(r)
    picks=[]
    for sec,ss in by_sec.items():
        ss.sort(key=lambda x:x["score"],reverse=True);picks.extend(ss[:5])
    new_e=[]
    for s in picks:
        if s["nse"] not in prev_nse:s["is_new"]=True;new_e.append(s["nse"])
        else:s["is_new"]=False
    picks.sort(key=lambda x:x["score"],reverse=True)
    STATIC.mkdir(parents=True,exist_ok=True)
    DATA_FILE.write_text(json.dumps({"meta":{"updated_at":datetime.now().isoformat(),"total_stocks":len(picks),"scanned":len(all_r),"failed":failed,"new_entries":new_e,"source":"NSE India Direct API"},"stocks":picks},indent=2))
    log.info(f"✅ {len(picks)} picks from {len(all_r)} scanned. Failed: {len(failed)}")
    log.info("Fetching indices...")
    nse2=get_nse_session()
    idx=fetch_indices_data(nse2)
    IDX_FILE.write_text(json.dumps({"meta":{"updated_at":datetime.now().isoformat(),"count":len(idx)},"indices":idx},indent=2))
    log.info(f"✅ {len(idx)} indices. DONE.")

def login_required(f):
    @wraps(f)
    def dec(*a,**k):
        if not session.get("logged_in"):return redirect(url_for("login"))
        return f(*a,**k)
    return dec

LOGIN_HTML="""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Login</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Playfair+Display:wght@600&display=swap" rel="stylesheet">
<style>*{box-sizing:border-box;margin:0;padding:0}body{background:#f0f4ff;font-family:'DM Sans',sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}.card{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:44px 40px;width:100%;max-width:400px;box-shadow:0 8px 40px rgba(15,76,138,.1)}.logo{font-family:'Playfair Display',serif;font-size:24px;color:#0f4c8a}.logo span{color:#b45309}.sub{font-size:12px;color:#6b7280;margin:4px 0 28px}label{display:block;font-size:12px;font-weight:600;color:#374151;margin-bottom:6px}input{width:100%;padding:11px 14px;border:1.5px solid #e5e7eb;border-radius:9px;font-size:14px;outline:none}input:focus{border-color:#0f4c8a}.field{margin-bottom:20px}button{width:100%;padding:12px;background:#0f4c8a;color:#fff;border:none;border-radius:9px;font-size:14px;font-weight:600;cursor:pointer;margin-top:4px}.err{background:#fee2e2;color:#991b1b;border-radius:8px;padding:10px 14px;font-size:12.5px;margin-bottom:18px}.foot{font-size:10.5px;color:#9ca3af;text-align:center;margin-top:20px}</style></head>
<body><div class="card"><div class="logo">India Swing <span>Picks</span></div><div class="sub">NSE Auto-Screener · Daily refresh 9:15 AM IST</div>
{% if error %}<div class="err">{{ error }}</div>{% endif %}
<form method="POST"><div class="field"><label>Username</label><input type="text" name="username" required autofocus></div><div class="field"><label>Password</label><input type="password" name="password" required></div><button>Sign In →</button></form>
<div class="foot">Personal research tool · Not SEBI advice</div></div></body></html>"""

@app.route("/login",methods=["GET","POST"])
def login():
    err=None
    if request.method=="POST":
        if request.form.get("username","").strip()==APP_USERNAME and request.form.get("password","").strip()==APP_PASSWORD:
            session["logged_in"]=True;session.permanent=True;return redirect(url_for("index"))
        err="Incorrect username or password."
    return render_template_string(LOGIN_HTML,error=err)

@app.route("/logout")
def logout():session.clear();return redirect(url_for("login"))

@app.route("/")
@login_required
def index():return send_from_directory("static","india_swing_final.html")

@app.route("/swing_data.json")
@login_required
def get_data():
    if DATA_FILE.exists():return send_from_directory("static","swing_data.json")
    return jsonify({"error":"not ready"}),404

@app.route("/index_data.json")
@login_required
def get_idx():
    if IDX_FILE.exists():return send_from_directory("static","index_data.json")
    return jsonify({"error":"not ready"}),404

@app.route("/api/status")
@login_required
def api_status():
    info={"data_ready":DATA_FILE.exists()}
    if DATA_FILE.exists():
        try:
            d=json.loads(DATA_FILE.read_text())
            info["last_updated"]=d.get("meta",{}).get("updated_at","?")
            info["stocks"]=d.get("meta",{}).get("total_stocks",0)
            info["source"]=d.get("meta",{}).get("source","?")
        except:pass
    return jsonify(info)

@app.route("/api/refresh")
@login_required
def api_refresh():
    threading.Thread(target=run_full_refresh,daemon=True).start()
    return jsonify({"status":"started","eta_minutes":12})

def scheduler():
    log.info("Scheduler started")
    if not DATA_FILE.exists():
        log.info("No data — starting initial refresh");run_full_refresh()
    else:
        age=(datetime.now().timestamp()-DATA_FILE.stat().st_mtime)/3600
        if age>20:log.info(f"Data {age:.1f}h old — refreshing");run_full_refresh()
    while True:
        now=datetime.utcnow()
        target=now.replace(hour=3,minute=45,second=0,microsecond=0)
        if now>=target:target+=timedelta(days=1)
        wait=(target-now).total_seconds()
        log.info(f"Next refresh in {wait/3600:.1f}h")
        time.sleep(wait)
        if datetime.utcnow().weekday()<5:run_full_refresh()
        else:log.info("Weekend — skipping")

threading.Thread(target=scheduler,daemon=True).start()
if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port,debug=False)
