"""
upload_data.py — Run this on your Mac every morning
Fetches live data → copies to static/ → git push → Render updates
RUN: cd ~/Downloads/swingapp_v2 && python3 upload_data.py
"""
import subprocess,sys,os,json,shutil
from datetime import datetime
from pathlib import Path

HERE=Path(__file__).parent
DATA_DST=HERE/"static"/"swing_data.json"

print(f"\n{'='*50}\nIndia Swing Picks — Data Upload\n{datetime.now().strftime('%d %b %Y %H:%M')}\n{'='*50}\n")

# Step 1: Find and run refresh script
print("Step 1/3 — Fetching live NSE data from your Mac...")
refresh=None
for loc in [HERE/"refresh_swing_data_v2.py",
            HERE.parent/"refresh_swing_data_v2.py",
            Path.home()/"Downloads"/"refresh_swing_data_v2.py"]:
    if loc.exists():refresh=loc;break

if not refresh:
    print("ERROR: refresh_swing_data_v2.py not found in this folder or Downloads.")
    sys.exit(1)

r=subprocess.run([sys.executable,str(refresh)],cwd=str(refresh.parent))
if r.returncode!=0:
    print("ERROR: Data fetch failed.");sys.exit(1)

# Step 2: Copy JSON to static/
print("\nStep 2/3 — Copying data...")
src=refresh.parent/"swing_data.json"
if not src.exists():
    print(f"ERROR: swing_data.json not found at {src}");sys.exit(1)

DATA_DST.parent.mkdir(parents=True,exist_ok=True)
shutil.copy(src,DATA_DST)

with open(DATA_DST) as f:d=json.load(f)
count=d.get("meta",{}).get("total_stocks",0)
updated=d.get("meta",{}).get("updated_at","")[:16]
failed=d.get("meta",{}).get("failed",[])
print(f"  ✓ {count} stocks · {updated}")
if failed:print(f"  ⚠ Failed ({len(failed)}): {', '.join(failed[:8])}")

# Step 3: Git push
print("\nStep 3/3 — Pushing to GitHub → Render...")
os.chdir(HERE)
for cmd in [
    ["git","add","static/swing_data.json"],
    ["git","commit","-m",f"data: {count} stocks {datetime.now().strftime('%d-%b %H:%M')}"],
    ["git","push"]
]:
    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode!=0:
        if"nothing to commit"in r.stdout+r.stderr:
            print("  ℹ No changes (data unchanged)");break
        print(f"  ERROR: {r.stderr}");sys.exit(1)
    else:
        print(f"  ✓ {' '.join(cmd[:2])}")

print(f"\n{'='*50}")
print(f"✅ DONE — Site updates in ~2 min")
print(f"   https://swingpicks.onrender.com")
print(f"   Click ↻ Refresh Data")
print(f"{'='*50}\n")
