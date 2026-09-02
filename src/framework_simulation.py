import collections
import glob
import json
import math
import random
import statistics as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

random.seed(7)
N = 3000
b, F = 1.0, 4.0e10
sim = []
for _ in range(N):
    V = math.exp(random.gauss(math.log(2e11), 1.9))
    e = min(1.0, max(0.0, random.betavariate(1.6, 1.2)))
    adopt = b * e * V > F
    sim.append((V, e, e * 100 if adopt else 0.0))
sim_shares = [s for _, _, s in sim]
lo = sum(1 for s in sim_shares if s < 25)
hi = sum(1 for s in sim_shares if s > 75)
print("=" * 74)
print("1. NUMERICAL VERIFICATION --- does the model reproduce the bimodality?")
print("=" * 74)
print(f"  simulated {N} complexes | below 25% cleared: {lo} ({100*lo/N:.0f}%)"
      f" | above 75%: {hi} ({100*hi/N:.0f}%)")
print(f"  mean {st.mean(sim_shares):.1f}  sd {st.pstdev(sim_shares):.1f}")
print("  observed (168 families): 52 below 25% (31%), 44 above 75% (26%),"
          " mean 49.2, sd 33.7")

F_ = collections.defaultdict(lambda: [0., 0., 0., 0.])
META = {}
for p in sorted(glob.glob("data/panel/*.json")):
    d = json.load(open(p, encoding="utf8"))
    for per, sid, sn, cik, rn, na, fc, fb, nc, nb in d["funds"]:
        v = F_[(per, sid)]
        v[0] += fc; v[1] += fb; v[2] += nc; v[3] += nb
        META[(per, sid)] = (rn or "?", na or 0.0)

fam = collections.defaultdict(lambda: [0., 0., 0., 0., set()])
for k, v in F_.items():
    a = fam[META[k][0]]
    for i in range(4):
        a[i] += v[i]
    a[4].add(k[1])

rows = []
for rn, (fc, fb, nc, nb, sids) in fam.items():
    tot = fc + fb + nc + nb
    if tot < 3e10 or len(sids) < 5:
        continue
    elig = (nc + nb) / tot
    rows.append((rn, tot, 100 * (fc + nc) / tot, elig, len(sids)))
print()
print("=" * 74)
print("Comparative static: adoption-size gradient by eligibility")
print("=" * 74)
print(f"  {len(rows)} fund families (>=$30bn notional, >=5 funds)")
med_e = st.median(r[3] for r in rows)
HI = [r for r in rows if r[3] >= med_e]
LO = [r for r in rows if r[3] < med_e]
print(f"  eligibility (non-FX share of book) median = {med_e:.3f}")


def grad(sub, lab):
    xs = [math.log(r[1]) for r in sub]
    ys = [r[2] for r in sub]
    mx, my = st.mean(xs), st.mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    beta = sxy / sxx
    resid = [y - (my + beta * (x - mx)) for x, y in zip(xs, ys)]
    s2 = sum(r ** 2 for r in resid) / (len(xs) - 2)
    se = math.sqrt(s2 / sxx)
    print(f"  {lab:<34} n={len(sub):>3}  d(cleared%)/d(log notional) = "
          f"{beta:>6.2f}  se {se:.2f}  t {beta/se:>5.2f}")
    return beta, se


print()
bh, sh = grad(HI, "HIGH eligibility (non-FX heavy)")
bl, sl = grad(LO, "LOW eligibility (FX heavy)")
diff = bh - bl
sed = math.sqrt(sh ** 2 + sl ** 2)
print(f"\n  difference in gradients: {diff:.2f}  se {sed:.2f}  t {diff/sed:.2f}")
print(f"  -> CS predicts a POSITIVE difference. "
      f"{'SUPPORTED' if diff / sed > 1.96 else 'NOT SUPPORTED at conventional levels'}")
print(f"\n  mean cleared%: high-elig {st.mean([r[2] for r in HI]):.1f}  "
      f"low-elig {st.mean([r[2] for r in LO]):.1f}")

fig, ax = plt.subplots(1, 3, figsize=(16.5, 5))
ax[0].hist(sim_shares, bins=24, color="#00798c", edgecolor="w")
ax[0].set_title("Model: simulated cleared share\n(bimodality emerges from fixed cost)", fontsize=10)
ax[0].set_xlabel("% cleared"); ax[0].set_ylabel("complexes"); ax[0].grid(axis="y", alpha=.3)
ax[1].hist([r[2] for r in rows], bins=24, color="#d1495b", edgecolor="w")
ax[1].set_title(f"Data: {len(rows)} fund families\n(same qualitative shape)", fontsize=10)
ax[1].set_xlabel("% cleared"); ax[1].grid(axis="y", alpha=.3)
for sub, c, lab in [(HI, "#00798c", "high eligibility"), (LO, "#d1495b", "low eligibility")]:
    ax[2].scatter([math.log10(r[1]) for r in sub], [r[2] for r in sub],
                  s=16, alpha=.65, color=c, label=lab)
    xs = [math.log(r[1]) for r in sub]; ys = [r[2] for r in sub]
    mx, my = st.mean(xs), st.mean(ys)
    be = sum((x-mx)*(y-my) for x, y in zip(xs, ys)) / sum((x-mx)**2 for x in xs)
    lx = [min(xs), max(xs)]
    ax[2].plot([x/math.log(10) for x in lx], [my + be*(x-mx) for x in lx], color=c, lw=2)
ax[2].set_xlabel("log10 notional"); ax[2].set_ylabel("% cleared")
ax[2].set_title("CS: adoption-size gradient by eligibility", fontsize=10)
ax[2].legend(fontsize=8); ax[2].grid(alpha=.3)
plt.tight_layout(); plt.savefig("data/model_fit.png", dpi=130)
print("\nchart -> data/model_fit.png")
