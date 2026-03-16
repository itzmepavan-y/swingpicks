"""
India Swing Picks — Server (serve-only mode)
Data is pushed via upload_data.py from your Mac.
Server just serves the dashboard + JSON files.
No data fetching on server = no IP blocking issues.
"""
import os,json,logging
from datetime import datetime,timedelta
from pathlib import Path
from functools import wraps
from flask import Flask,request,session,redirect,url_for,send_from_directory,jsonify,render_template_string

logging.basicConfig(level=logging.INFO,format="%(asctime)s [%(levelname)s] %(message)s")
log=logging.getLogger(__name__)
app=Flask(__name__,static_folder="static")
app.secret_key=os.environ.get("SECRET_KEY","changeme")
app.permanent_session_lifetime=timedelta(days=30)
APP_USERNAME=os.environ.get("APP_USERNAME","pavan")
APP_PASSWORD=os.environ.get("APP_PASSWORD","swing2026")
STATIC=Path(__file__).parent/"static"
DATA_FILE=STATIC/"swing_data.json"
IDX_FILE=STATIC/"index_data.json"

def login_required(f):
    @wraps(f)
    def dec(*a,**k):
        if not session.get("logged_in"):return redirect(url_for("login"))
        return f(*a,**k)
    return dec

LOGIN_HTML="""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Login — Swing Picks</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Playfair+Display:wght@600&display=swap" rel="stylesheet">
<style>*{box-sizing:border-box;margin:0;padding:0}body{background:#f0f4ff;font-family:'DM Sans',sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}.card{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:44px 40px;width:100%;max-width:400px;box-shadow:0 8px 40px rgba(15,76,138,.1)}.logo{font-family:'Playfair Display',serif;font-size:24px;color:#0f4c8a}.logo span{color:#b45309}.sub{font-size:12px;color:#6b7280;margin:4px 0 28px}label{display:block;font-size:12px;font-weight:600;color:#374151;margin-bottom:6px}input{width:100%;padding:11px 14px;border:1.5px solid #e5e7eb;border-radius:9px;font-size:14px;outline:none}input:focus{border-color:#0f4c8a}.field{margin-bottom:20px}button{width:100%;padding:12px;background:#0f4c8a;color:#fff;border:none;border-radius:9px;font-size:14px;font-weight:600;cursor:pointer;margin-top:4px}.err{background:#fee2e2;color:#991b1b;border-radius:8px;padding:10px 14px;font-size:12.5px;margin-bottom:18px}.foot{font-size:10.5px;color:#9ca3af;text-align:center;margin-top:20px}</style></head>
<body><div class="card"><div class="logo">India Swing <span>Picks</span></div>
<div class="sub">NSE Screener · Data pushed daily from Mac · 2026</div>
{% if error %}<div class="err">{{ error }}</div>{% endif %}
<form method="POST">
<div class="field"><label>Username</label><input type="text" name="username" required autofocus></div>
<div class="field"><label>Password</label><input type="password" name="password" required></div>
<button>Sign In →</button></form>
<div class="foot">Personal research tool · Not SEBI-registered advice</div>
</div></body></html>"""

@app.route("/login",methods=["GET","POST"])
def login():
    err=None
    if request.method=="POST":
        if request.form.get("username","").strip()==APP_USERNAME and request.form.get("password","").strip()==APP_PASSWORD:
            session["logged_in"]=True;session.permanent=True
            return redirect(url_for("index"))
        err="Incorrect username or password."
    return render_template_string(LOGIN_HTML,error=err)

@app.route("/logout")
def logout():
    session.clear();return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    return send_from_directory("static","india_swing_final.html")

@app.route("/swing_data.json")
@login_required
def get_data():
    if DATA_FILE.exists():
        return send_from_directory("static","swing_data.json")
    return jsonify({"error":"No data yet. Run upload_data.py on your Mac."}),404

@app.route("/index_data.json")
@login_required
def get_idx():
    if IDX_FILE.exists():
        return send_from_directory("static","index_data.json")
    return jsonify({"error":"No index data yet."}),404

@app.route("/api/status")
@login_required
def api_status():
    info={"data_ready":DATA_FILE.exists(),"mode":"serve-only (data pushed from Mac)"}
    if DATA_FILE.exists():
        try:
            d=json.loads(DATA_FILE.read_text())
            info["last_updated"]=d.get("meta",{}).get("updated_at","?")
            info["stocks"]=d.get("meta",{}).get("total_stocks",0)
            info["scanned"]=d.get("meta",{}).get("scanned",0)
            age=(datetime.now().timestamp()-DATA_FILE.stat().st_mtime)/3600
            info["data_age_hours"]=round(age,1)
        except:pass
    return jsonify(info)

log.info("="*40)
log.info("India Swing Picks — Serve-only mode")
log.info("Push data with: python3 upload_data.py")
log.info("="*40)

if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port,debug=False)
