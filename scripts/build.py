#!/usr/bin/env python3
"""Render index.html from data/latest.json. No dependencies beyond the Python stdlib."""
import json, datetime, html, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
d = json.loads((ROOT / "data" / "latest.json").read_text())
e = html.escape

def n(x):
    return f"{x:,}" if isinstance(x, int) else f"{x:,.1f}"

def pct(a, b):
    return round(100 * a / b) if b else 0

def bar(p, cls=""):
    return f'<div class="bar {cls}"><span style="width:{min(p,100)}%"></span></div>'

def table(headers, rows, foot=None, num_cols=()):
    th = "".join(f'<th class="{"num" if i in num_cols else ""}">{e(h)}</th>' for i, h in enumerate(headers))
    body = "".join("<tr>" + "".join(f'<td class="{"num" if i in num_cols else ""}">{c}</td>' for i, c in enumerate(r)) + "</tr>" for r in rows)
    tf = ""
    if foot:
        tf = "<tfoot><tr>" + "".join(f'<td class="{"num" if i in num_cols else ""}">{c}</td>' for i, c in enumerate(foot)) + "</tr></tfoot>"
    return f'<div class="tw"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody>{tf}</table></div>'

g = d["atAGlance"]; sf = d["salesforce"]; rm = d["routeMap"]; geo = d["geotab"]
gen = datetime.datetime.fromisoformat(d["generatedAt"])
gen_label = gen.strftime("%b %-d, %Y, %-I:%M %p") + " ET"

kpis = [
    ("Closed Won", n(g["closedWon"]), "units, product start " + d["asOfLabel"].rsplit(",",1)[0], "green"),
    ("Trials", n(g["trials"]), "new Trial leads", "blue"),
    ("Collect / Cancel", n(g["collectCancel"]), "moved from Closed Won", "amber"),
    ("Closed Lost", n(g["closedLost"]), "accounts lost", "red"),
    ("RouteMap", f'{g["routeMap"]["done"]}/{g["routeMap"]["total"]}', f'{g["routeMap"]["pct"]}% done &middot; {g["routeMap"]["locations"]} locations &middot; {g["routeMap"]["pending"]} pending' + bar(g["routeMap"]["pct"]), "teal"),
    ("Geotab", f'{g["geotab"]["vehicles"]} vehicles', f'{n(g["geotab"]["trips"])} trips &middot; {n(g["geotab"]["miles"])} miles', "blue"),
    ("Units on Hire", n(g["unitsOnHire"]["total"]), f'across {g["unitsOnHire"]["locations"]} locations', "green"),
]
kpi_html = "".join(f'<div class="kpi {c}"><div class="kl">{e(l)}</div><div class="kv">{v}</div><div class="ks">{s}</div></div>' for l, v, s, c in kpis)

cw = table(["Location", "Units"], [[e(r["location"]), n(r["units"])] for r in sf["closedWon"]["byLocation"]] + [["All other locations", "0"]],
           ["Total", n(sf["closedWon"]["total"])], (1,))
tr = table(["Location", "New Trials"], [[e(r["location"]), n(r["count"])] for r in sf["trials"]["byLocation"]],
           ["Total", n(sf["trials"]["total"])], (1,))
cc = table(["Location", "Count", "Accounts"], [[e(r["location"]), n(r["count"]), e("; ".join(r["accounts"])) + (f'<div class="sub">{e(r["note"])}</div>' if r.get("note") else "")] for r in sf["collectCancel"]["byLocation"]],
           ["Total", n(sf["collectCancel"]["total"]), ""], (1,))
cl = table(["Location", "Count", "From", "Accounts"], [[e(r["location"]), n(r["count"]), e(r["from"]), e("; ".join(r["accounts"]))] for r in sf["closedLost"]["byLocation"]],
           ["Total", n(sf["closedLost"]["total"]), "", ""], (1,))
u = sf["unitsOnHire"]; umax = max(r["units"] for r in u["top"])
uh_top = table(["Top locations", "Units", ""], [[e(r["location"]), n(r["units"]), bar(pct(r["units"], umax), "slim")] for r in u["top"]], None, (1,))
uh_small = table(["Smallest locations", "Units", ""], [[e(r["location"]), n(r["units"]), bar(pct(r["units"], umax), "slim")] for r in u["smallest"]], None, (1,))

def rmrow(r):
    p = pct(r["done"], r["total"])
    pend = f'<span class="pill warn">{r["pending"]}</span>' if r["pending"] >= 10 else str(r["pending"])
    return [e(r["location"]), f'{r["done"]}/{r["total"]}', f'<div class="pc">{bar(p,"slim")}<b>{p}%</b></div>', pend, f'{r["mtdDone"]}/{r["mtdTotal"]}', f'{pct(r["mtdDone"], r["mtdTotal"])}%']
t = rm["dayTotal"]
rmt = table(["Location", "Oct 8 done/total", "Oct 8 %", "Pending", "Month to date", "MTD %"], [rmrow(r) for r in rm["day"]],
            ["Oct 8 total", f'{t["done"]}/{t["total"]}', f'{pct(t["done"], t["total"])}%', f'{t["pending"]}*', "", ""], (1, 3, 4, 5))
rmo = table(["Location", "Month to date", "MTD %", "Pending"], [[e(r["location"]), f'{r["mtdDone"]}/{r["mtdTotal"]}', f'{pct(r["mtdDone"], r["mtdTotal"])}%', str(r["pending"])] for r in rm["mtdOnly"]], None, (1, 2, 3))
mtd = rm["monthToDate"]

gt = geo["total"]
geot = table(["Vehicle", "Zone", "Start", "End", "Trips", "Miles"],
             [[e(v["vehicle"]) + (' <span class="ast" title="Time zone assumed">*</span>' if v.get("zoneAssumed") else ""), e(v["zone"]), e(v["start"]), e(v["end"]), n(v["trips"]), n(v["miles"])] for v in geo["vehicles"]],
             [f'Total ({gt["vehicles"]} vehicles)', "", "", "", n(gt["trips"]), n(gt["miles"])], (4, 5))

page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Floral Image Ops &middot; Executive Dashboard</title>
<meta name="robots" content="noindex">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{{--bg:#f4f6f9;--card:#fff;--ink:#0f1f33;--muted:#5b6b80;--line:#e3e8ef;--blue:#1f5fbf;--blue2:#e8f0fc;--green:#1f9d6b;--green2:#e6f6ef;--teal:#0f8a95;--teal2:#e3f4f5;--amber:#c27a0e;--amber2:#fdf3e2;--red:#c2413b;--red2:#fcebea}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1200px;margin:0 auto;padding:0 20px}}
header{{background:linear-gradient(120deg,#0f2f5c 0%,#1f5fbf 60%,#1f9d6b 140%);color:#fff;padding:28px 0 76px}}
.hd{{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap}}
.brand{{font-size:13px;letter-spacing:.14em;text-transform:uppercase;opacity:.8;font-weight:600}}
h1{{margin:4px 0 0;font-size:30px;font-weight:800;letter-spacing:-.02em}}
.asof{{text-align:right}}
.asof .d{{font-size:22px;font-weight:700}}
.asof .u{{font-size:12.5px;opacity:.8}}
.badge{{display:inline-block;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.25);border-radius:999px;padding:3px 10px;font-size:12px;margin-top:8px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin-top:-52px}}
.kpi{{background:var(--card);border-radius:14px;padding:16px 16px 14px;box-shadow:0 1px 2px rgba(15,31,51,.06),0 6px 20px rgba(15,31,51,.06);border-top:4px solid var(--blue)}}
.kpi.green{{border-color:var(--green)}}.kpi.teal{{border-color:var(--teal)}}.kpi.amber{{border-color:var(--amber)}}.kpi.red{{border-color:var(--red)}}
.kl{{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:600}}
.kv{{font-size:30px;font-weight:800;letter-spacing:-.02em;margin:4px 0 2px;white-space:nowrap}}
.ks{{font-size:12.5px;color:var(--muted)}}
.ks .bar{{margin-top:8px}}
section{{margin-top:28px}}
h2{{font-size:19px;margin:0 0 12px;font-weight:700;display:flex;align-items:center;gap:10px}}
h2 .dot{{width:10px;height:10px;border-radius:3px;background:var(--blue)}}
h2 .dot.g{{background:var(--green)}}h2 .dot.t{{background:var(--teal)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,460px),1fr));gap:16px}}
.grid>*,.card{{min-width:0}}
.card{{background:var(--card);border-radius:14px;padding:18px;box-shadow:0 1px 2px rgba(15,31,51,.05);border:1px solid var(--line)}}
.card h3{{margin:0 0 4px;font-size:14px;font-weight:700;display:flex;justify-content:space-between;align-items:baseline}}
.card h3 .big{{font-size:20px;font-weight:800;color:var(--blue)}}
.card .note{{font-size:12.5px;color:var(--muted);margin:8px 0 0}}
.tw{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
table{{width:100%;border-collapse:collapse;font-size:14px;margin-top:8px}}
th{{text-align:left;font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:600;padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}}
td{{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
tbody tr:hover{{background:#f8fafc}}
tfoot td{{font-weight:700;border-bottom:none;border-top:2px solid var(--ink)}}
.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
.sub{{font-size:12px;color:var(--muted)}}
.bar{{height:8px;background:var(--blue2);border-radius:99px;overflow:hidden;min-width:60px}}
.bar span{{display:block;height:100%;background:linear-gradient(90deg,var(--teal),var(--green));border-radius:99px}}
.bar.slim{{height:6px}}
.pc{{display:flex;align-items:center;gap:8px;min-width:120px}}.pc .bar{{flex:1}}.pc b{{font-weight:600;font-size:13px;width:38px;text-align:right}}
.pill{{display:inline-block;padding:1px 8px;border-radius:99px;font-weight:700;font-size:12.5px}}
.pill.warn{{background:var(--amber2);color:var(--amber)}}
.callout{{display:flex;gap:10px;align-items:flex-start;background:var(--amber2);border:1px solid #f3dcb3;color:#7a4c06;border-radius:10px;padding:10px 14px;font-size:13.5px;margin-top:12px}}
.mtd{{display:flex;gap:24px;flex-wrap:wrap;align-items:center}}
.mtd .v{{font-size:26px;font-weight:800}}
.mtd .bar{{height:10px;width:260px;max-width:100%}}
.ast{{color:var(--amber);font-weight:700;cursor:help}}
ul.notes{{margin:10px 0 0;padding-left:18px;font-size:13px;color:var(--muted)}}
footer{{margin:36px 0 0;padding:22px 0 40px;border-top:1px solid var(--line);font-size:12.5px;color:var(--muted)}}
footer p{{margin:4px 0}}
footer a{{color:var(--blue)}}
@media (max-width:640px){{h1{{font-size:24px}}.asof{{text-align:left}}.kv{{font-size:24px}}.grid{{grid-template-columns:minmax(0,1fr)}}.mtd .bar{{width:100%}}.mtd>div{{flex:1 1 100%}}.kpis{{grid-template-columns:repeat(2,1fr)}}td,th{{padding:7px 8px}}}}
</style>
</head>
<body>
<header><div class="wrap hd">
  <div><div class="brand">Executive Scorecard</div><h1>Floral Image Ops</h1><div class="badge">{e(d["window"])}</div></div>
  <div class="asof"><div class="u">As of</div><div class="d">{e(d["asOfLabel"])}</div><div class="u">Last updated {e(gen_label)}</div></div>
</div></header>
<main class="wrap">
<div class="kpis">{kpi_html}</div>

<section><h2><span class="dot"></span>Salesforce</h2>
<div class="grid">
  <div class="card"><h3>Closed Won <span class="big">{sf["closedWon"]["total"]}</span></h3><div class="sub">Product start Oct 8, stage Closed Won (units)</div>{cw}<p class="note">{e(sf["closedWon"]["note"])}</p></div>
  <div class="card"><h3>Trials <span class="big">{sf["trials"]["total"]}</span></h3><div class="sub">New leads created as Trial</div>{tr}
    <p class="note"><b>Pending:</b> {sf["pending"]["total"]} &mdash; {e(sf["pending"]["note"])}<br><b>Closed No:</b> {sf["closedNo"]["total"]}</p></div>
  <div class="card"><h3>Cancel / Collect <span class="big" style="color:var(--amber)">{sf["collectCancel"]["total"]}</span></h3><div class="sub">Closed Won to Collect/Cancel</div>{cc}</div>
  <div class="card"><h3>Closed Lost <span class="big" style="color:var(--red)">{sf["closedLost"]["total"]}</span></h3><div class="sub">Status moved to Closed Lost</div>{cl}</div>
</div>
<div class="card" style="margin-top:16px"><h3>Units on Hire <span class="big" style="color:var(--green)">{n(u["total"])}</span></h3><div class="sub">Active products on Closed Won across {u["locations"]} locations (point in time)</div>
  <div class="grid" style="margin-top:4px"><div>{uh_top}</div><div>{uh_small}</div></div><p class="note">{e(u["note"])}</p></div>
</section>

<section><h2><span class="dot t"></span>RouteMap Refresh</h2>
<div class="card">
  <div class="mtd">
    <div><div class="kl">Oct 8</div><div class="v">{t["done"]}/{t["total"]} <span style="font-size:16px;color:var(--muted)">({pct(t["done"], t["total"])}%)</span></div>{bar(pct(t["done"], t["total"]))}</div>
    <div><div class="kl">Month to date</div><div class="v">{n(mtd["done"])}/{n(mtd["total"])} <span style="font-size:16px;color:var(--muted)">({mtd["pct"]}%)</span></div>{bar(mtd["pct"])}</div>
    <div><div class="kl">Pending</div><div class="v">{t["pending"]}</div><div class="sub">across all locations</div></div>
  </div>
  <div class="callout">&#9888; <span><b>Watch:</b> {e(rm["watch"])}</span></div>
  <h3 style="margin-top:18px">Oct 8 activity by location</h3>{rmt}
  <p class="note">* {e(t["note"])}.</p>
</div>
<div class="grid" style="margin-top:16px">
  <div class="card"><h3>No Oct 8 activity &mdash; month to date only</h3>{rmo}</div>
  <div class="card"><h3>No changeovers this month</h3><p class="note" style="font-size:14px;color:var(--ink)">{e(", ".join(rm["zeroMonth"]))}</p><p class="note">These locations show 0/0 for the whole month in RouteMap.</p></div>
</div>
</section>

<section><h2><span class="dot g"></span>Geotab Vehicle Start / End</h2>
<div class="card"><div class="sub">{e(geo["note"])}</div>{geot}
<ul class="notes">{"".join(f"<li>{e(x)}</li>" for x in geo["notes"])}</ul></div>
</section>

<footer>
  <p><b>Auto-updated weekdays from FI Ops Manager.</b> Snapshot data: <a href="data/latest.json">data/latest.json</a>.</p>
  <p>Salesforce window: calendar day Oct 8, 2026, Eastern time. The 7 AM-to-7 AM digest showed 12 Closed Won, including 1 more Fort Lauderdale unit starting Oct 9. Units on hire taken from the Oct 8 Salesforce bot digest, not re-pulled live.</p>
  <p>Geotab: Oct 8 only, local times; Oct 9 left out because the data is partial.</p>
</footer>
</main>
</body>
</html>
"""
(ROOT / "index.html").write_text(page)
print("wrote index.html")
