import collections
import csv
import glob
import json
import math
import os
import random
import re
import statistics as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = "."
os.makedirs(f"{OUT}/figures", exist_ok=True)
os.makedirs(f"{OUT}/data", exist_ok=True)

CCP_PAT = re.compile(
    r"\b(LCH\b|LCH\.|CLEARNET|LONDON CLEARING|CHICAGO MERCANTILE EXCH"
    r"|CME CLEARING|CME GROUP|BOARD OF TRADE OF THE CITY OF CHICAGO"
    r"|CHICAGO BOARD OF TRADE|\bCBOT\b|ICE CLEAR|INTERCONTINENTAL EXCHANGE"
    r"|OPTIONS CLEARING CORP|FIXED INCOME CLEARING|\bFICC\b|\bNSCC\b|\bDTCC\b"
    r"|EUREX CLEARING|JAPAN SECURITIES CLEARING|\bJSCC\b|NASDAQ CLEARING"
    r"|CBOE CLEAR|EURONEXT CLEARING|ASX CLEAR|CLEARING HOUSE|CLEARINGHOUSE"
    r"|CENTRAL COUNTERPART|NEW YORK MERCANTILE EXCH|\bCOMEX\b|\bNYMEX\b"
    r"|MINNEAPOLIS GRAIN EXCH|MONTREAL EXCHANGE|B3 S\.A|BM&FBOVESPA)", re.I)

F = collections.defaultdict(lambda: [0., 0., 0., 0.])
META, ENT = {}, collections.defaultdict(float)
for p in sorted(glob.glob("data/panel/*.json")):
    d = json.load(open(p, encoding="utf8"))
    for per, sid, sn, cik, rn, na, fc, fb, nc, nb in d["funds"]:
        v = F[(per, sid)]
        v[0] += fc; v[1] += fb; v[2] += nc; v[3] += nb
        META[(per, sid)] = (rn or "?", na or 0.0)
    for per, isfx, clr, nm, val in d["entities"]:
        ENT[nm] += val

rows = sorted(ENT.items(), key=lambda kv: -kv[1])
with open(f"{OUT}/data/counterparty_classification.csv", "w", newline="",
          encoding="utf8") as fh:
    w = csv.writer(fh)
    w.writerow(["counterparty_name", "classification", "notional_usd_summed",
                "matched_pattern"])
    for nm, v in rows:
        m = CCP_PAT.search(nm or "")
        w.writerow([nm, "CCP" if m else "BILATERAL", f"{v:.0f}",
                    m.group(0) if m else ""])
nccp = sum(1 for nm, _ in rows if CCP_PAT.search(nm or ""))
print(f"entity list: {len(rows):,} names, {nccp} classified CCP -> "
      f"{OUT}/data/counterparty_classification.csv")

fam = collections.defaultdict(lambda: [0., 0., 0., 0., set()])
for k, v in F.items():
    a = fam[META[k][0]]
    for i in range(4):
        a[i] += v[i]
    a[4].add(k[1])
FAM = []
for rn, (fc, fb, nc, nb, s) in fam.items():
    tot = fc + fb + nc + nb
    if tot < 3e10 or len(s) < 5:
        continue
    FAM.append((rn, tot, 100 * (fc + nc) / tot, (nc + nb) / tot, len(s)))
FAM.sort(key=lambda r: -r[1])
cl = [r[2] for r in FAM]
print(f"families: {len(FAM)}  <25%: {sum(1 for c in cl if c<25)}  "
      f">75%: {sum(1 for c in cl if c>75)}  mean {st.mean(cl):.1f} sd {st.pstdev(cl):.1f}")
with open(f"{OUT}/data/family_clearing.csv", "w", newline="", encoding="utf8") as fh:
    w = csv.writer(fh)
    w.writerow(["registrant", "notional_usd", "cleared_pct", "eligible_share", "n_funds"])
    for r in FAM:
        w.writerow([r[0], f"{r[1]:.0f}", f"{r[2]:.2f}", f"{r[3]:.4f}", r[4]])

random.seed(7)
sim = []
for _ in range(3000):
    V = math.exp(random.gauss(math.log(2e11), 1.9))
    e = min(1., max(0., random.betavariate(1.6, 1.2)))
    sim.append(e * 100 if 1.0 * e * V > 4.0e10 else 0.0)
fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.1))
ax[0].hist(cl, bins=22, color="#c0392b", edgecolor="w")
ax[0].set_xlabel("Centrally cleared share of derivative notional (\\%)")
ax[0].set_ylabel("Fund families")
ax[0].set_title(f"(a) Data: {len(FAM)} fund families", fontsize=10)
ax[0].grid(axis="y", alpha=.3)
ax[1].hist(sim, bins=22, color="#2c7fb8", edgecolor="w")
ax[1].set_xlabel("Centrally cleared share (\\%)")
ax[1].set_title("(b) Fixed-cost model, 3,000 simulated complexes", fontsize=10)
ax[1].grid(axis="y", alpha=.3)
plt.tight_layout(); plt.savefig(f"{OUT}/figures/fig1_bimodal.pdf")

top = FAM[:20][::-1]
fig, ax = plt.subplots(figsize=(8.2, 6.4))
ax.barh([r[0][:34] for r in top], [r[2] for r in top],
        color=["#2c7fb8" if r[2] > 50 else "#c0392b" for r in top])
ax.set_xlabel("Centrally cleared share of derivative notional (\\%)")
ax.set_xlim(0, 100); ax.grid(axis="x", alpha=.3); ax.tick_params(labelsize=8)
plt.tight_layout(); plt.savefig(f"{OUT}/figures/fig2_families.pdf")

fig, ax = plt.subplots(1, 2, figsize=(11, 4.3))
ax[0].scatter([r[3] for r in FAM], [r[2] for r in FAM], s=18, alpha=.6,
              color="#2c7fb8")
ax[0].set_xlabel("Clearing-eligible share of book (non-FX)")
ax[0].set_ylabel("Cleared share (\\%)"); ax[0].grid(alpha=.3)
ax[0].set_title("(a) Eligibility", fontsize=10)
ax[1].scatter([math.log10(r[1]) for r in FAM], [r[2] for r in FAM], s=18,
              alpha=.6, color="#c0392b")
ax[1].set_xlabel("$\\log_{10}$ derivative notional (USD)")
ax[1].set_ylabel("Cleared share (\\%)"); ax[1].grid(alpha=.3)
ax[1].set_title("(b) Scale", fontsize=10)
plt.tight_layout(); plt.savefig(f"{OUT}/figures/fig3_mechanism.pdf")

def qb(keys):
    a = sum(F[k][1] for k in keys); b = sum(F[k][3] for k in keys)
    return 100 * a / (a + b) if a + b else float("nan")
ALL = list(F)
famclr = collections.defaultdict(lambda: [0., 0.])
for k in ALL:
    famclr[META[k][0]][0] += F[k][0] + F[k][2]
    famclr[META[k][0]][1] += sum(F[k])
hi = {rn for rn, (c, t) in famclr.items() if t > 0 and 100 * c / t > 50}
nas = sorted(META[k][1] for k in ALL if META[k][1] > 0); med = nas[len(nas)//2]
srt = sorted(ALL, key=lambda k: -sum(F[k]))
top5 = set(sorted(famclr, key=lambda r: -famclr[r][1])[:5])
specs = [
    ("Baseline", qb(ALL)),
    ("December periods", qb([k for k in ALL if k[0].endswith("-12")])),
    ("March periods", qb([k for k in ALL if k[0].endswith("-03")])),
    ("October periods", qb([k for k in ALL if k[0].endswith("-10")])),
    ("High-clearing families", qb([k for k in ALL if META[k][0] in hi])),
    ("Low-clearing families", qb([k for k in ALL if META[k][0] not in hi])),
    ("Net assets $\\geq$ median", qb([k for k in ALL if META[k][1] >= med])),
    ("Net assets $<$ median", qb([k for k in ALL if 0 < META[k][1] < med])),
    ("ex-PIMCO", qb([k for k in ALL if META[k][0] != "PIMCO Funds"])),
    ("ex-top-5 families", qb([k for k in ALL if META[k][0] not in top5])),
    ("2019--2022", qb([k for k in ALL if k[0] < "2023"])),
    ("2023--2026", qb([k for k in ALL if k[0] >= "2023"])),
    ("Drop top 1\\% funds", qb(srt[len(srt)//100:])),
    ("Drop top 5\\% funds", qb(srt[len(srt)//20:])),
]
specs.sort(key=lambda r: r[1])
fig, ax = plt.subplots(figsize=(8, 5))
ax.barh([s[0] for s in specs], [s[1] for s in specs],
        color=["#2c7fb8" if s[0] == "Baseline" else "#95a5a6" for s in specs])
ax.axvline(15, ls="--", c="k", lw=1.1)
ax.set_xlabel("FX forwards as \\% of bilateral notional")
ax.set_xlim(0, 100); ax.grid(axis="x", alpha=.3); ax.tick_params(labelsize=8)
plt.tight_layout(); plt.savefig(f"{OUT}/figures/fig4_speccurve.pdf")
qs = [s[1] for s in specs]
print(f"spec curve: min {min(qs):.1f} max {max(qs):.1f} median {st.median(qs):.1f}")
print("figures written")
