import collections
import csv
import io
import os
import zipfile

Z = "data/cache/2026q1_nport.zip"
if not os.path.exists(Z):
    raise SystemExit(f"archive missing: {Z}")
z = zipfile.ZipFile(Z)
print(f"archive {os.path.getsize(Z)/1e6:.0f} MB, {len(z.namelist())} members\n")


def rows(name, limit=None):
    with z.open(name) as fh:
        rd = csv.DictReader(io.TextIOWrapper(fh, encoding="utf8",
                                             errors="replace", newline=""),
                            delimiter="\t")
        for i, r in enumerate(rd):
            if limit and i >= limit:
                break
            yield r


def cols(name):
    with z.open(name) as fh:
        return io.TextIOWrapper(fh, encoding="utf8").readline().rstrip("\n").split("\t")


def fill(name, limit=400000):
    c = cols(name)
    tot = 0
    nz = collections.Counter()
    for r in rows(name, limit):
        tot += 1
        for k in c:
            v = (r.get(k) or "").strip()
            if v and v.upper() not in ("N/A", "NA", "NONE"):
                nz[k] += 1
    return tot, {k: 100 * nz[k] / max(1, tot) for k in c}


print("=" * 84)
print("1. SUBMISSION --- filing types, amendments, periods")
print("=" * 84)
print("  cols:", ", ".join(cols("SUBMISSION.tsv")))
sub_type = collections.Counter()
last = collections.Counter()
per_acc = {}
rep_vs_end = collections.Counter()
for r in rows("SUBMISSION.tsv"):
    sub_type[(r.get("SUB_TYPE") or "").strip()] += 1
    last[(r.get("IS_LAST_FILING") or "").strip()] += 1
    per_acc[r["ACCESSION_NUMBER"]] = (r.get("REPORT_ENDING_PERIOD"),
                                      r.get("REPORT_DATE"))
    rep_vs_end[(r.get("REPORT_ENDING_PERIOD") == r.get("REPORT_DATE"))] += 1
print(f"  SUB_TYPE: {dict(sub_type)}")
print(f"  IS_LAST_FILING: {dict(last)}")
print(f"  REPORT_ENDING_PERIOD == REPORT_DATE: {dict(rep_vs_end)}")
print(f"  filings: {len(per_acc):,}")
ex = list(per_acc.items())[:3]
for a, (e, d) in ex:
    print(f"    {a}  ending={e}  report_date={d}")

print()
print("=" * 84)
print("2. Does ONE filing carry THREE months? (the frequency question)")
print("=" * 84)
mtr = collections.Counter()
mtr_cols = cols("MONTHLY_TOTAL_RETURN.tsv")
print("  MONTHLY_TOTAL_RETURN cols:", ", ".join(mtr_cols))
for r in rows("MONTHLY_TOTAL_RETURN.tsv", 300000):
    mtr[r["ACCESSION_NUMBER"]] += 1
d = collections.Counter(mtr.values())
print(f"  rows per accession: {dict(sorted(d.items())[:8])}")
print("  sample rows:")
for r in list(rows("MONTHLY_TOTAL_RETURN.tsv", 3)):
    print("   ", {k: r[k] for k in mtr_cols})

print()
print("=" * 84)
print("3. FUND_REPORTED_INFO --- flows, and what else is here")
print("=" * 84)
fri = cols("FUND_REPORTED_INFO.tsv")
print(f"  {len(fri)} columns:")
for i in range(0, len(fri), 4):
    print("   ", ", ".join(fri[i:i+4]))
tot, f = fill("FUND_REPORTED_INFO.tsv", 60000)
flowish = [c for c in fri if any(k in c.upper() for k in
           ("SALE", "REDEM", "REINVEST", "FLOW", "SUBSCR"))]
print(f"\n  flow-like columns and fill rate (n={tot:,}):")
for c in flowish:
    print(f"    {c:<42} {f[c]:6.1f}%")

print()
print("=" * 84)
print("4. SECURITIES_LENDING --- the field the paper depends on most")
print("=" * 84)
sl = cols("SECURITIES_LENDING.tsv")
print("  cols:", ", ".join(sl))
tot, f = fill("SECURITIES_LENDING.tsv", 500000)
for c in sl:
    print(f"    {c:<34} {f[c]:6.2f}% non-blank")
vals = collections.Counter()
loanvals = 0
nz_loan = 0
for r in rows("SECURITIES_LENDING.tsv", 500000):
    vals[(r.get("IS_LOAN_BY_FUND") or "").strip()] += 1
    v = (r.get("LOAN_VALUE") or "").strip()
    if v:
        loanvals += 1
        try:
            if float(v) > 0:
                nz_loan += 1
        except ValueError:
            pass
print(f"\n  IS_LOAN_BY_FUND values: {dict(vals)}")
print(f"  LOAN_VALUE present {loanvals:,}, strictly positive {nz_loan:,}")

print()
print("=" * 84)
print("5. FUND_REPORTED_HOLDING --- shorts, asset and derivative categories")
print("=" * 84)
frh = cols("FUND_REPORTED_HOLDING.tsv")
print("  cols:", ", ".join(frh))
pay, ac, dc, unit = (collections.Counter() for _ in range(4))
neg_bal = tot_h = 0
for r in rows("FUND_REPORTED_HOLDING.tsv", 600000):
    tot_h += 1
    pay[(r.get("PAYOFF_PROFILE") or "").strip()] += 1
    ac[(r.get("ASSET_CAT") or "").strip()] += 1
    dc[(r.get("DERIVATIVE_CAT") or "").strip()] += 1
    unit[(r.get("UNIT") or "").strip()] += 1
    b = (r.get("BALANCE") or "").strip()
    try:
        if float(b) < 0:
            neg_bal += 1
    except ValueError:
        pass
print(f"\n  scanned {tot_h:,} holdings")
print(f"  PAYOFF_PROFILE: {dict(pay.most_common(8))}")
print(f"  negative BALANCE rows: {neg_bal:,} ({100*neg_bal/tot_h:.2f}%)")
print(f"  ASSET_CAT: {dict(ac.most_common(12))}")
print(f"  DERIVATIVE_CAT: {dict(dc.most_common(10))}")
print(f"  UNIT: {dict(unit.most_common(6))}")

print()
print("=" * 84)
print("6. IDENTIFIERS --- can we join to CRSP/Compustat/13F?")
print("=" * 84)
idc = cols("IDENTIFIERS.tsv")
tot, f = fill("IDENTIFIERS.tsv", 400000)
for c in idc:
    print(f"    {c:<28} {f[c]:6.2f}%")
cus = blank_cus = 0
for r in rows("FUND_REPORTED_HOLDING.tsv", 400000):
    v = (r.get("ISSUER_CUSIP") or "").strip()
    cus += 1
    if not v or v.upper() in ("N/A", "NA", "000000000"):
        blank_cus += 1
print(f"\n  ISSUER_CUSIP usable on FUND_REPORTED_HOLDING: "
      f"{100*(cus-blank_cus)/cus:.2f}%  (n={cus:,})")

print()
print("=" * 84)
print("7. REGISTRANT")
print("=" * 84)
print("  cols:", ", ".join(cols("REGISTRANT.tsv")))
