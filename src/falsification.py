import collections
import glob
import json
import re
import statistics as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

F = collections.defaultdict(lambda: [0., 0., 0., 0.])
META, ENT = {}, collections.defaultdict(float)
for p in sorted(glob.glob("data/panel/*.json")):
    d = json.load(open(p, encoding="utf8"))
    for per, sid, sn, cik, rn, na, fc, fb, nc, nb in d["funds"]:
        v = F[(per, sid)]
        v[0] += fc; v[1] += fb; v[2] += nc; v[3] += nb
        META[(per, sid)] = (rn or "?", na or 0.0)
    for per, isfx, clr, nm, val in d["entities"]:
        ENT[(per, isfx, clr, nm)] += val


def qb(keys):
    fb = sum(F[k][1] for k in keys); nb = sum(F[k][3] for k in keys)
    return 100 * fb / (fb + nb) if fb + nb else float("nan")


def clr(keys):
    t = sum(sum(F[k]) for k in keys)
    c = sum(F[k][0] + F[k][2] for k in keys)
    return 100 * c / t if t else float("nan")


ALL = list(F)
print("=" * 78)
print("P3. PLACEBO --- FX as a share of CLEARED notional (must be < 10%)")
print("=" * 78)
fc = sum(F[k][0] for k in ALL); nc = sum(F[k][2] for k in ALL)
placebo = 100 * fc / (fc + nc)
print(f"  FX share of cleared notional: {placebo:.2f}%")
print(f"  FX share of bilateral notional: {qb(ALL):.2f}%")
print(f"  -> {'PASS' if placebo < 10 else 'FAIL'}  "
      f"(ratio bilateral:cleared = {qb(ALL)/placebo:.0f}x)")

print()
print("=" * 78)
print("P1. PRE-COMMITTED SUBSAMPLE SPLITS (all four cells must exceed 40%)")
print("=" * 78)
famclr = collections.defaultdict(lambda: [0., 0.])
for k in ALL:
    rn, _ = META[k]
    famclr[rn][0] += F[k][0] + F[k][2]
    famclr[rn][1] += sum(F[k])
hi = {rn for rn, (c, t) in famclr.items() if t > 0 and 100 * c / t > 50}
A = [k for k in ALL if META[k][0] in hi]
B = [k for k in ALL if META[k][0] not in hi]
print(f"  (a) high-clearing families (n={len(hi):,}): FX share = {qb(A):5.1f}%  "
      f"[{len(A):,} fund-periods]")
print(f"      low-clearing families            : FX share = {qb(B):5.1f}%  "
      f"[{len(B):,} fund-periods]")
nas = sorted(META[k][1] for k in ALL if META[k][1] > 0)
med = nas[len(nas) // 2]
C = [k for k in ALL if META[k][1] >= med]
D = [k for k in ALL if 0 < META[k][1] < med]
print(f"  (b) net assets >= median (${med/1e6:,.0f}m): FX share = {qb(C):5.1f}%  "
      f"[{len(C):,}]")
print(f"      net assets <  median             : FX share = {qb(D):5.1f}%  [{len(D):,}]")
cells = [qb(A), qb(B), qb(C), qb(D)]
print(f"\n  -> {'PASS' if all(c > 40 for c in cells) else 'FAIL'} "
      f"(min cell {min(cells):.1f}%)")

print()
print("=" * 78)
print("P2. THE TEST MOST LIKELY TO KILL THIS --- drop the dominant complex")
print("=" * 78)
base = qb(ALL)
for drop, lab in [({"PIMCO Funds"}, "ex-PIMCO Funds"),
                  ({"PIMCO Funds", "PIMCO Variable Insurance Trust"}, "ex-all PIMCO"),
                  (set(sorted(famclr, key=lambda r: -famclr[r][1])[:5]), "ex-top-5 families"),
                  (set(sorted(famclr, key=lambda r: -famclr[r][1])[:10]), "ex-top-10 families")]:
    K = [k for k in ALL if META[k][0] not in drop]
    share = 100 * sum(sum(F[k]) for k in ALL if META[k][0] in drop) / sum(sum(F[k]) for k in ALL)
    print(f"  {lab:<22} drops {share:5.1f}% of notional -> FX share {qb(K):5.1f}% "
          f"(vs {base:.1f}, delta {qb(K)-base:+.1f}pp)")
K = [k for k in ALL if META[k][0] != "PIMCO Funds"]
print(f"\n  -> {'PASS' if abs(qb(K)-base) < 20 else 'FAIL'} on the pre-committed 20pp bound")

print()
print("=" * 78)
print("SPECIFICATION CURVE")
print("=" * 78)
specs = []


def add(lab, keys):
    specs.append((lab, qb(keys), clr(keys)))


add("baseline (all funds, all periods)", ALL)
add("December periods only", [k for k in ALL if k[0].endswith("-12")])
add("March periods only", [k for k in ALL if k[0].endswith("-03")])
add("October periods only", [k for k in ALL if k[0].endswith("-10")])
per_n = collections.Counter(k[0] for k in ALL)
add("periods with >=1000 funds", [k for k in ALL if per_n[k[0]] >= 1000])
add("ex-PIMCO Funds", [k for k in ALL if META[k][0] != "PIMCO Funds"])
add("ex-top-5 families", [k for k in ALL if META[k][0] not in
                          set(sorted(famclr, key=lambda r: -famclr[r][1])[:5])])
add("high-clearing families", A)
add("low-clearing families", B)
add("net assets >= median", C)
add("net assets < median", D)
add("2019-2022 only", [k for k in ALL if k[0] < "2023"])
add("2023-2026 only", [k for k in ALL if k[0] >= "2023"])
big = {k for k in ALL if sum(F[k]) > 0}
srt = sorted(big, key=lambda k: -sum(F[k]))
add("drop top 1% funds by notional", srt[len(srt)//100:])
add("drop top 5% funds by notional", srt[len(srt)//20:])

LOOSE = re.compile(r"(CLEAR|EXCHANGE|CME|LCH|BOARD OF TRADE|DTCC|EUREX|ICE\b)", re.I)
STRICT = re.compile(r"(LCH|CLEARNET|LONDON CLEARING|CME CLEARING|CHICAGO MERCANTILE"
                    r"|BOARD OF TRADE OF THE CITY|ICE CLEAR|OPTIONS CLEARING CORP"
                    r"|FIXED INCOME CLEARING|EUREX CLEARING|CLEARING HOUSE)", re.I)
for pat, lab in [(LOOSE, "CCP pattern: loose"), (STRICT, "CCP pattern: strict")]:
    fb = nb = 0.0
    for (per, isfx, was, nm), v in ENT.items():
        if pat.search(nm or ""):
            continue
        (fb := fb) if False else None
        if isfx: fb += v
        else:    nb += v
    specs.append((lab, 100 * fb / (fb + nb) if fb + nb else float("nan"),
                  float("nan")))

print(f"  {'specification':<36}{'FX %':>9}{'cleared %':>12}")
for lab, q, c in specs:
    print(f"  {lab:<36}{q:>9.1f}{c:>12.1f}" if c == c
          else f"  {lab:<36}{q:>9.1f}{'-':>12}")
qs = [q for _, q, _ in specs if q == q]
print(f"\n  FX share across {len(qs)} specifications: min {min(qs):.1f}  max {max(qs):.1f}  "
      f"median {st.median(qs):.1f}  sd {st.pstdev(qs):.1f}")
print(f"  specifications below the preregistered 15% kill threshold: "
      f"{sum(1 for q in qs if q < 15)}")

fig, ax = plt.subplots(figsize=(11, 7))
o = sorted(range(len(specs)), key=lambda i: specs[i][1])
ax.barh([specs[i][0] for i in o], [specs[i][1] for i in o],
        color=["#00798c" if specs[i][0].startswith("baseline") else "#d1495b" for i in o])
ax.axvline(15, ls="--", c="k", lw=1.2)
ax.text(16, 0.2, "preregistered kill threshold", fontsize=9)
ax.set_xlabel("FX forwards as % of uncleared notional")
ax.set_xlim(0, 100); ax.grid(axis="x", alpha=.3)
ax.set_title("Specification curve --- FX share across every discretionary choice", fontsize=12)
plt.tight_layout(); plt.savefig("data/speccurve.png", dpi=130)
print("\nchart -> data/speccurve.png")
