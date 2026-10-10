#!/usr/bin/env python3
"""Render index.html from data/latest.json. No dependencies beyond the Python stdlib.

The page includes a client-side location filter: rows carry data-loc (a normalized
location key) and a JSON blob (#loc-data) holds per-location aggregates for the KPI cards.
RouteMap completion is shown as done/total counts only (no percentages or progress bars).
"""
import json, datetime, html, pathlib, re, unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
d = json.loads((ROOT / "data" / "latest.json").read_text())
e = html.escape

def n(x):
    return f"{x:,}" if isinstance(x, int) else f"{x:,.1f}"

def pct(a, b):
    return round(100 * a / b) if b else 0

def bar(p, cls=""):
    # Relative-size bar. Used for Units on Hire only, never for RouteMap completion.
    return f'<div class="bar {cls}"><span style="width:{min(p,100)}%"></span></div>'

def norm(s):
    """Normalize a location name for filtering: drop accents, 'Floral Image', 'FI'; casefold."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    s = re.sub(r"floral\s+image", " ", s)
    s = re.sub(r"\bfi\b", " ", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def display(s):
    s = re.sub(r"(?i)floral\s+image", "", s)
    s = re.sub(r"\bFI\b", "", s)
    return re.sub(r"\s+", " ", s).strip()

def table(headers, rows, foot=None, num_cols=(), locs=None, empty_cols=None):
    th = "".join(f'<th class="{"num" if i in num_cols else ""}">{e(h)}</th>' for i, h in enumerate(headers))
    body = ""
    for ri, r in enumerate(rows):
        loc = locs[ri] if locs else None
        attr = f' data-loc="{e(loc)}"' if loc is not None else ""
        body += f"<tr{attr}>" + "".join(f'<td class="{"num" if i in num_cols else ""}">{c}</td>' for i, c in enumerate(r)) + "</tr>"
    body += f'<tr class="empty" hidden><td colspan="{len(headers)}">No rows for <b class="loc-name"></b>.</td></tr>'
    tf = ""
    if foot:
        tf = '<tfoot class="all-only"><tr>' + "".join(f'<td class="{"num" if i in num_cols else ""}">{c}</td>' for i, c in enumerate(foot)) + "</tr></tfoot>"
    return f'<div class="tw"><table class="filt"><thead><tr>{th}</tr></thead><tbody>{body}</tbody>{tf}</table></div>'

g = d["atAGlance"]; sf = d["salesforce"]; rm = d["routeMap"]; geo = d["geotab"]
gen = datetime.datetime.fromisoformat(d["generatedAt"])
gen_label = gen.strftime("%b %-d, %Y, %-I:%M %p") + " ET"
day = d["asOfLabel"].rsplit(",", 1)[0]  # e.g. "Oct 8"

# ---------- location index + per-location aggregates ----------
names = {}  # key -> display name (RouteMap name preferred, else Salesforce name stripped of FI)
def reg(name, prefer=False):
    k = norm(name)
    if k and (prefer or k not in names):
        names[k] = display(name)
    return k

u = sf["unitsOnHire"]
for sec in ("closedWon", "trials", "collectCancel", "closedLost"):
    for r in sf[sec].get("byLocation", []):
        reg(r["location"])
for r in u["top"] + u["smallest"]:
    reg(r["location"])
for r in rm["day"] + rm["mtdOnly"]:
    reg(r["location"], prefer=True)
for name in rm["zeroMonth"]:
    reg(name, prefer=True)

agg = {k: {"closedWon": 0, "trials": 0, "collectCancel": 0, "closedLost": 0, "rm": None, "uoh": None, "geo": []} for k in names}
for r in sf["closedWon"]["byLocation"]: agg[norm(r["location"])]["closedWon"] += r["units"]
for r in sf["trials"]["byLocation"]: agg[norm(r["location"])]["trials"] += r["count"]
for r in sf["collectCancel"]["byLocation"]: agg[norm(r["location"])]["collectCancel"] += r["count"]
for r in sf["closedLost"]["byLocation"]: agg[norm(r["location"])]["closedLost"] += r["count"]
for r in u["top"] + u["smallest"]: agg[norm(r["location"])]["uoh"] = r["units"]
for r in rm["day"]:
    agg[norm(r["location"])]["rm"] = {"kind": "day", "done": r["done"], "total": r["total"], "pending": r["pending"], "mtdDone": r["mtdDone"], "mtdTotal": r["mtdTotal"]}
for r in rm["mtdOnly"]:
    agg[norm(r["location"])]["rm"] = {"kind": "mtd", "done": 0, "total": 0, "pending": r["pending"], "mtdDone": r["mtdDone"], "mtdTotal": r["mtdTotal"]}
for name in rm["zeroMonth"]:
    agg[norm(name)]["rm"] = {"kind": "zero", "done": 0, "total": 0, "pending": 0, "mtdDone": 0, "mtdTotal": 0}

# Geotab vehicles are fleet-wide; match a vehicle to a location only when its label names the city (or a known abbreviation).
GEO_ALIASES = {"ftla": "fort lauderdale", "fw": "fort worth"}
def geo_loc(label):
    lab = " " + norm(label) + " "
    for k in sorted(names, key=len, reverse=True):
        if f" {k} " in lab:
            return k
    for tok in lab.split():
        if tok in GEO_ALIASES and GEO_ALIASES[tok] in names:
            return GEO_ALIASES[tok]
    return ""
for v in geo["vehicles"]:
    k = geo_loc(v["vehicle"])
    v["_loc"] = k
    if k:
        agg[k]["geo"].append({"vehicle": v["vehicle"], "trips": v["trips"], "miles": v["miles"]})

locations = sorted(({"key": k, "name": names[k]} for k in names), key=lambda x: x["name"])
loc_data = {"locations": locations, "agg": agg, "day": day,
            "all": {"geoVehicles": geo["total"]["vehicles"], "uohTotal": u["total"], "uohLocations": u["locations"]}}
loc_json = json.dumps(loc_data, separators=(",", ":")).replace("</", "<\\/")
options = "".join(f'<option value="{e(l["key"])}">{e(l["name"])}</option>' for l in locations)

# ---------- KPI cards ----------
rmg = g["routeMap"]
kpis = [
    ("closedWon", "Closed Won", n(g["closedWon"]), "units, product start " + day, "green"),
    ("trials", "Trials", n(g["trials"]), "new Trial leads", "blue"),
    ("collectCancel", "Collect / Cancel", n(g["collectCancel"]), "moved from Closed Won", "amber"),
    ("closedLost", "Closed Lost", n(g["closedLost"]), "accounts lost", "red"),
    ("rm", "RouteMap", f'{rmg["done"]}/{rmg["total"]}', f'{rmg["locations"]} locations &middot; {rmg["pending"]} pending', "teal"),
    ("geo", "Geotab", f'{g["geotab"]["vehicles"]} vehicles', f'{n(g["geotab"]["trips"])} trips &middot; {n(g["geotab"]["miles"])} miles', "blue"),
    ("uoh", "Units on Hire", n(g["unitsOnHire"]["total"]), f'across {g["unitsOnHire"]["locations"]} locations', "green"),
]
kpi_html = "".join(f'<div class="kpi {c}" data-kpi="{k}"><div class="kl">{e(l)}</div><div class="kv">{v}</div><div class="ks">{s}</div></div>' for k, l, v, s, c in kpis)

# ---------- Salesforce tables ----------
L = lambda rows: [norm(r["location"]) for r in rows]
cwr = sf["closedWon"]["byLocation"]
cw = table(["Location", "Units"], [[e(r["location"]), n(r["units"])] for r in cwr] + [["All other locations", "0"]],
           ["Total", n(sf["closedWon"]["total"])], (1,), L(cwr) + ["__other"])
trr = sf["trials"]["byLocation"]
tr = table(["Location", "New Trials"], [[e(r["location"]), n(r["count"])] for r in trr],
           ["Total", n(sf["trials"]["total"])], (1,), L(trr))
ccr = sf["collectCancel"]["byLocation"]
cc = table(["Location", "Count", "Accounts"], [[e(r["location"]), n(r["count"]), e("; ".join(r["accounts"])) + (f'<div class="sub">{e(r["note"])}</div>' if r.get("note") else "")] for r in ccr],
           ["Total", n(sf["collectCancel"]["total"]), ""], (1,), L(ccr))
clr = sf["closedLost"]["byLocation"]
cl = table(["Location", "Count", "From", "Accounts"], [[e(r["location"]), n(r["count"]), e(r["from"]), e("; ".join(r["accounts"]))] for r in clr],
           ["Total", n(sf["closedLost"]["total"]), "", ""], (1,), L(clr))
umax = max(r["units"] for r in u["top"])
uh_top = table(["Top locations", "Units", ""], [[e(r["location"]), n(r["units"]), bar(pct(r["units"], umax), "slim")] for r in u["top"]], None, (1,), L(u["top"]))
uh_small = table(["Smallest locations", "Units", ""], [[e(r["location"]), n(r["units"]), bar(pct(r["units"], umax), "slim")] for r in u["smallest"]], None, (1,), L(u["smallest"]))

# ---------- RouteMap (counts only, no percentages) ----------
def rmrow(r):
    pend = f'<span class="pill warn">{r["pending"]}</span>' if r["pending"] >= 10 else str(r["pending"])
    return [e(r["location"]), f'{r["done"]}/{r["total"]}', pend, f'{n(r["mtdDone"])}/{n(r["mtdTotal"])}']
t = rm["dayTotal"]; mtd = rm["monthToDate"]
rmt = table(["Location", f"{day} done/total", "Pending", "Month to date"], [rmrow(r) for r in rm["day"]],
            [f"{day} total", f'{t["done"]}/{t["total"]}', f'{t["pending"]}*', f'{n(mtd["done"])}/{n(mtd["total"])}&dagger;'], (1, 2, 3), L(rm["day"]))
rmo = table(["Location", "Month to date", "Pending"], [[e(r["location"]), f'{n(r["mtdDone"])}/{n(r["mtdTotal"])}', str(r["pending"])] for r in rm["mtdOnly"]], None, (1, 2), L(rm["mtdOnly"]))
zero_chips = "".join(f'<span class="chip" data-loc="{e(norm(x))}">{e(x)}</span>' for x in rm["zeroMonth"])
watch_loc = next((k for k in sorted(names, key=len, reverse=True) if f" {k} " in " " + norm(rm["watch"]) + " "), "")

gt = geo["total"]
geot = table(["Vehicle", "Zone", "Start", "End", "Trips", "Miles"],
             [[e(v["vehicle"]) + (' <span class="ast" title="Time zone assumed">*</span>' if v.get("zoneAssumed") else ""), e(v["zone"]), e(v["start"]), e(v["end"]), n(v["trips"]), n(v["miles"])] for v in geo["vehicles"]],
             [f'Total ({gt["vehicles"]} vehicles)', "", "", "", n(gt["trips"]), n(gt["miles"])], (4, 5), [v["_loc"] for v in geo["vehicles"]])

JS = r'''<script>
(function(){
  var D = JSON.parse(document.getElementById('loc-data').textContent);
  var sel = document.getElementById('loc-select'), clr = document.getElementById('loc-clear'), stat = document.getElementById('loc-status');
  function norm(s){
    s = (s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
    return s.replace(/floral\s+image/g,' ').replace(/\bfi\b/g,' ').replace(/[^\w\s]/g,' ').replace(/\s+/g,' ').trim();
  }
  function fmt(x){ return typeof x === 'number' ? x.toLocaleString('en-US', Number.isInteger(x) ? {} : {minimumFractionDigits:1, maximumFractionDigits:1}) : x; }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  var kpis = {}, orig = {};
  document.querySelectorAll('[data-kpi]').forEach(function(el){ kpis[el.dataset.kpi] = el; orig[el.dataset.kpi] = [el.querySelector('.kv').innerHTML, el.querySelector('.ks').innerHTML]; });
  var aggEls = document.querySelectorAll('[data-agg]');
  aggEls.forEach(function(el){ el.dataset.all = el.innerHTML; });
  function setK(k, v, s){ kpis[k].querySelector('.kv').innerHTML = v; kpis[k].querySelector('.ks').innerHTML = s; }
  function nameOf(key){ for (var i=0;i<D.locations.length;i++) if (D.locations[i].key===key) return D.locations[i].name; return key; }

  function apply(key){
    var on = !!key, a = on ? D.agg[key] : null, nm = on ? nameOf(key) : '';
    document.body.classList.toggle('filtered', on);
    stat.textContent = on ? 'Showing ' + nm + ' only' : 'Showing all ' + D.locations.length + ' locations';
    clr.hidden = !on;
    document.querySelectorAll('.loc-name').forEach(function(el){ el.textContent = nm; });
    // tables
    document.querySelectorAll('table.filt').forEach(function(tb){
      var shown = 0;
      tb.querySelectorAll('tbody tr[data-loc]').forEach(function(tr){ var ok = !on || tr.dataset.loc === key; tr.hidden = !ok; if (ok) shown++; });
      var em = tb.querySelector('tr.empty'); if (em) em.hidden = !on || shown > 0;
    });
    document.querySelectorAll('.chip[data-loc], .loc-block[data-loc]').forEach(function(el){ el.hidden = on && el.dataset.loc !== key; });
    document.querySelectorAll('.chips').forEach(function(c){ var any = c.querySelector('.chip:not([hidden])'); var em = c.parentNode.querySelector('.chips-empty'); if (em) em.hidden = !!any; });
    document.querySelectorAll('.all-only').forEach(function(el){ el.hidden = on; });
    document.querySelectorAll('.loc-only').forEach(function(el){ el.hidden = !on; });
    // card header totals
    aggEls.forEach(function(el){ el.innerHTML = on ? fmt(a[el.dataset.agg]) : el.dataset.all; });
    // RouteMap tiles
    var r = on ? a.rm : null;
    document.getElementById('rm-day').innerHTML = on ? (r ? r.done + '/' + r.total : '&mdash;') : document.getElementById('rm-day').dataset.all;
    document.getElementById('rm-mtd').innerHTML = on ? (r ? fmt(r.mtdDone) + '/' + fmt(r.mtdTotal) : '&mdash;') : document.getElementById('rm-mtd').dataset.all;
    document.getElementById('rm-pend').innerHTML = on ? (r ? r.pending : '&mdash;') : document.getElementById('rm-pend').dataset.all;
    document.getElementById('rm-pend-sub').textContent = on ? (r ? nm : 'not in RouteMap') : 'across all locations';
    if (!on) { Object.keys(kpis).forEach(function(k){ setK(k, orig[k][0], orig[k][1]); }); return; }
    var tag = ' &middot; ' + esc(nm);
    setK('closedWon', fmt(a.closedWon), 'units' + tag);
    setK('trials', fmt(a.trials), 'new Trial leads' + tag);
    setK('collectCancel', fmt(a.collectCancel), 'moved from Closed Won' + tag);
    setK('closedLost', fmt(a.closedLost), 'accounts lost' + tag);
    if (!r) setK('rm', '&mdash;', esc(nm) + ' not in RouteMap');
    else if (r.kind === 'zero') setK('rm', '0/0', esc(nm) + ' &middot; no changeovers this month');
    else if (r.kind === 'mtd') setK('rm', '0/0', esc(nm) + ' &middot; no ' + esc(D.day) + ' activity &middot; MTD ' + fmt(r.mtdDone) + '/' + fmt(r.mtdTotal) + ' &middot; ' + r.pending + ' pending');
    else setK('rm', r.done + '/' + r.total, esc(nm) + ' &middot; ' + r.pending + ' pending');
    if (a.geo.length) {
      var tr = 0, mi = 0; a.geo.forEach(function(v){ tr += v.trips; mi += v.miles; });
      setK('geo', a.geo.length + (a.geo.length === 1 ? ' vehicle' : ' vehicles'), fmt(tr) + ' trips &middot; ' + fmt(Math.round(mi*10)/10) + ' miles &middot; matched by vehicle name');
    } else setK('geo', '&mdash;', 'Geotab is fleet-wide (' + D.all.geoVehicles + ' vehicles); none labeled ' + esc(nm));
    if (a.uoh != null) setK('uoh', fmt(a.uoh), esc(nm) + ' &middot; of ' + fmt(D.all.uohTotal) + ' total');
    else setK('uoh', '&mdash;', esc(nm) + ' not in top/smallest list (' + D.all.uohLocations + ' locations total)');
  }
  ['rm-day','rm-mtd','rm-pend'].forEach(function(id){ var el = document.getElementById(id); el.dataset.all = el.innerHTML; });

  function fromUrl(){
    var q = new URLSearchParams(location.search).get('loc');
    if (!q) { var m = location.hash.match(/loc=([^&]*)/); if (m) q = decodeURIComponent(m[1].replace(/\+/g,' ')); }
    var k = norm(q); return D.agg[k] ? k : '';
  }
  function toUrl(key){
    var u = new URL(location.href); u.hash = '';
    if (key) u.searchParams.set('loc', nameOf(key)); else u.searchParams.delete('loc');
    history.replaceState(null, '', u.pathname + u.search);
  }
  sel.addEventListener('change', function(){ apply(sel.value); toUrl(sel.value); });
  clr.addEventListener('click', function(){ sel.value = ''; apply(''); toUrl(''); });
  window.addEventListener('popstate', function(){ var k = fromUrl(); sel.value = k; apply(k); });
  var k0 = fromUrl(); sel.value = k0; apply(k0);
})();
</script>
'''

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
[hidden]{{display:none!important}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1200px;margin:0 auto;padding:0 20px}}
.toolbar{{position:sticky;top:0;z-index:20;background:rgba(15,47,92,.96);backdrop-filter:saturate(1.4) blur(8px);-webkit-backdrop-filter:saturate(1.4) blur(8px);color:#fff;border-bottom:1px solid rgba(255,255,255,.12);box-shadow:0 2px 10px rgba(15,31,51,.18)}}
.tb{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:10px 20px}}
.tb label{{font-size:12px;letter-spacing:.1em;text-transform:uppercase;font-weight:600;opacity:.85}}
.tb select{{font:inherit;font-size:14px;font-weight:600;color:var(--ink);background:#fff;border:0;border-radius:999px;padding:6px 34px 6px 14px;min-width:200px;cursor:pointer;appearance:none;-webkit-appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8'%3E%3Cpath d='M1 1l5 5 5-5' fill='none' stroke='%235b6b80' stroke-width='2'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 12px center}}
.tb button{{font:inherit;font-size:13px;font-weight:600;color:#fff;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.3);border-radius:999px;padding:5px 12px;cursor:pointer}}
.tb button:hover{{background:rgba(255,255,255,.24)}}
.tb .st{{font-size:13px;opacity:.85;margin-left:auto}}
body.filtered .tb .st{{opacity:1;font-weight:600}}
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
tr.empty td{{color:var(--muted);font-style:italic;text-align:center}}
tfoot td{{font-weight:700;border-bottom:none;border-top:2px solid var(--ink)}}
.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
.sub{{font-size:12px;color:var(--muted)}}
.bar{{height:8px;background:var(--blue2);border-radius:99px;overflow:hidden;min-width:60px}}
.bar span{{display:block;height:100%;background:linear-gradient(90deg,var(--teal),var(--green));border-radius:99px}}
.bar.slim{{height:6px}}
.pill{{display:inline-block;padding:1px 8px;border-radius:99px;font-weight:700;font-size:12.5px}}
.pill.warn{{background:var(--amber2);color:var(--amber)}}
.chips{{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}}
.chip{{display:inline-block;background:var(--teal2);color:var(--teal);border-radius:999px;padding:3px 12px;font-size:13px;font-weight:600}}
.callout{{display:flex;gap:10px;align-items:flex-start;background:var(--amber2);border:1px solid #f3dcb3;color:#7a4c06;border-radius:10px;padding:10px 14px;font-size:13.5px;margin-top:12px}}
.callout.info{{background:var(--blue2);border-color:#cddcf5;color:#1a4a94}}
.mtd{{display:flex;gap:40px;flex-wrap:wrap;align-items:flex-start}}
.mtd .v{{font-size:26px;font-weight:800;font-variant-numeric:tabular-nums}}
.ast{{color:var(--amber);font-weight:700;cursor:help}}
ul.notes{{margin:10px 0 0;padding-left:18px;font-size:13px;color:var(--muted)}}
footer{{margin:36px 0 0;padding:22px 0 40px;border-top:1px solid var(--line);font-size:12.5px;color:var(--muted)}}
footer p{{margin:4px 0}}
footer a{{color:var(--blue)}}
@media (max-width:640px){{h1{{font-size:24px}}.asof{{text-align:left}}.kv{{font-size:24px}}.grid{{grid-template-columns:minmax(0,1fr)}}.mtd>div{{flex:1 1 40%}}.kpis{{grid-template-columns:repeat(2,1fr)}}td,th{{padding:7px 8px}}.tb .st{{margin-left:0;flex-basis:100%}}.tb select{{flex:1;min-width:0}}}}
</style>
</head>
<body>
<div class="toolbar" role="region" aria-label="Location filter"><div class="wrap tb" style="padding-left:20px;padding-right:20px">
  <label for="loc-select">Location</label>
  <select id="loc-select"><option value="">All locations</option>{options}</select>
  <button type="button" id="loc-clear" hidden>Clear</button>
  <span class="st" id="loc-status">Showing all {len(locations)} locations</span>
</div></div>
<header><div class="wrap hd">
  <div><div class="brand">Executive Scorecard</div><h1>Floral Image Ops</h1><div class="badge">{e(d["window"])}</div></div>
  <div class="asof"><div class="u">As of</div><div class="d">{e(d["asOfLabel"])}</div><div class="u">Last updated {e(gen_label)}</div></div>
</div></header>
<main class="wrap">
<div class="kpis">{kpi_html}</div>

<section><h2><span class="dot"></span>Salesforce</h2>
<div class="grid">
  <div class="card"><h3>Closed Won <span class="big" data-agg="closedWon">{sf["closedWon"]["total"]}</span></h3><div class="sub">Product start {day}, stage Closed Won (units)</div>{cw}<p class="note all-only">{e(sf["closedWon"]["note"])}</p></div>
  <div class="card"><h3>Trials <span class="big" data-agg="trials">{sf["trials"]["total"]}</span></h3><div class="sub">New leads created as Trial</div>{tr}
    <p class="note all-only"><b>Pending:</b> {sf["pending"]["total"]} &mdash; {e(sf["pending"]["note"])}<br><b>Closed No:</b> {sf["closedNo"]["total"]}</p></div>
  <div class="card"><h3>Cancel / Collect <span class="big" style="color:var(--amber)" data-agg="collectCancel">{sf["collectCancel"]["total"]}</span></h3><div class="sub">Closed Won to Collect/Cancel</div>{cc}</div>
  <div class="card"><h3>Closed Lost <span class="big" style="color:var(--red)" data-agg="closedLost">{sf["closedLost"]["total"]}</span></h3><div class="sub">Status moved to Closed Lost</div>{cl}</div>
</div>
<div class="card" style="margin-top:16px"><h3>Units on Hire <span class="big all-only" style="color:var(--green)">{n(u["total"])}</span></h3><div class="sub">Active products on Closed Won across {u["locations"]} locations (point in time)</div>
  <div class="grid" style="margin-top:4px"><div>{uh_top}</div><div>{uh_small}</div></div><p class="note">{e(u["note"])} Only the top and smallest locations are listed.</p></div>
</section>

<section><h2><span class="dot t"></span>RouteMap Refresh</h2>
<div class="card">
  <div class="mtd">
    <div><div class="kl">{day} done/total</div><div class="v" id="rm-day">{t["done"]}/{t["total"]}</div></div>
    <div><div class="kl">Month to date</div><div class="v" id="rm-mtd">{n(mtd["done"])}/{n(mtd["total"])}</div></div>
    <div><div class="kl">Pending</div><div class="v" id="rm-pend">{t["pending"]}</div><div class="sub" id="rm-pend-sub">across all locations</div></div>
  </div>
  <div class="callout loc-block" data-loc="{e(watch_loc)}">&#9888; <span><b>Watch:</b> {e(rm["watch"])}</span></div>
  <h3 style="margin-top:18px">{day} activity by location</h3>{rmt}
  <p class="note all-only">* {e(t["note"])}. &dagger; Month to date across all locations, including those with no {day} activity.</p>
</div>
<div class="grid" style="margin-top:16px">
  <div class="card"><h3>No {day} activity &mdash; month to date only</h3>{rmo}</div>
  <div class="card"><h3>No changeovers this month</h3><div class="chips">{zero_chips}</div><p class="note chips-empty" hidden><b class="loc-name"></b> is not on this list.</p><p class="note">These locations show 0/0 for the whole month in RouteMap.</p></div>
</div>
</section>

<section><h2><span class="dot g"></span>Geotab Vehicle Start / End</h2>
<div class="card"><div class="sub">{e(geo["note"])}</div>
<div class="callout info loc-only" hidden>&#9432; <span>Geotab is fleet-wide. Vehicles are shown for <b class="loc-name"></b> only when the vehicle label names the city (e.g. &ldquo;FTLA&rdquo; = Fort Lauderdale, &ldquo;FW&rdquo; = Fort Worth).</span></div>
{geot}
<ul class="notes">{"".join(f"<li>{e(x)}</li>" for x in geo["notes"])}</ul></div>
</section>

<footer>
  <p><b>Auto-updated weekdays from FI Ops Manager.</b> Snapshot data: <a href="data/latest.json">data/latest.json</a>. Filter link: add <code>?loc=Dallas</code> to the URL.</p>
  <p>Salesforce window: calendar day Oct 8, 2026, Eastern time. The 7 AM-to-7 AM digest showed 12 Closed Won, including 1 more Fort Lauderdale unit starting Oct 9. Units on hire taken from the Oct 8 Salesforce bot digest, not re-pulled live.</p>
  <p>Geotab: Oct 8 only, local times; Oct 9 left out because the data is partial.</p>
</footer>
</main>
<script type="application/json" id="loc-data">{loc_json}</script>
"""
page += JS + "</body>\n</html>\n"
(ROOT / "index.html").write_text(page)
print("wrote index.html")
