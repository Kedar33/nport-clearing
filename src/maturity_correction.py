import collections
import csv
import datetime as dt
import io
import json
import math
import os
import re
import zipfile

import requests

SEC = requests.Session()
SEC.headers["User-Agent"] = "Kedar Sahu independent research kedasahu@gmail.com"
OUT = "data/maturity"
os.makedirs(OUT, exist_ok=True)
TMP = "data/cache/archive_mat.zip"

ISO2TREAS = {
    "EUR": "Euro Zone-Euro", "JPY": "Japan-Yen", "GBP": "United Kingdom-Pound",
    "AUD": "Australia-Dollar", "CAD": "Canada-Dollar", "BRL": "Brazil-Real",
    "CHF": "Switzerland-Franc", "MXN": "Mexico-Peso", "SEK": "Sweden-Krona",
    "NOK": "Norway-Krone", "NZD": "New Zealand-Dollar", "SGD": "Singapore-Dollar",
    "HKD": "Hong Kong-Dollar", "KRW": "Korea-Won", "CNY": "China-Renminbi",
    "CNH": "China-Renminbi", "INR": "India-Rupee", "ZAR": "South Africa-Rand",
    "PLN": "Poland-Zloty", "DKK": "Denmark-Krone", "TWD": "Taiwan-Dollar",
    "THB": "Thailand-Baht", "ILS": "Israel-Shekel", "CZK": "Czech Republic-Koruna",
    "HUF": "Hungary-Forint", "TRY": "Turkey-New Lira", "CLP": "Chile-Peso",
    "COP": "Colombia-Peso", "PHP": "Philippines-Peso", "IDR": "Indonesia-Rupiah",
    "MYR": "Malaysia-Ringgit", "RUB": "Russia-Ruble", "PEN": "Peru-Sol",
    "RON": "Romania-New Leu", "AED": "United Arab Emirates-Dirham",
    "SAR": "Saudi Arabia-Riyal", "EGP": "Egypt-Pound", "NGN": "Nigeria-Naira",
    "VND": "Vietnam-Dong", "ARS": "Argentina-Peso", "UYU": "Uruguay-Peso",
}
MONTH = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6, "JUL": 7,
         "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}

r = SEC.get("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/"
            "accounting/od/rates_of_exchange?fields=country_currency_desc,"
            "exchange_rate,record_date&filter=record_date:gte:2019-06-30"
            "&page[size]=10000", timeout=180)
FX = collections.defaultdict(dict)
for d in r.json()["data"]:
    FX[d["record_date"]][d["country_currency_desc"]] = float(d["exchange_rate"])
FX_DATES = sorted(FX)
print(f"FX: {len(FX_DATES)} dates", flush=True)


def pdate(v):
    m = re.match(r"(\d{1,2})-([A-Z]{3})-(\d{4})", (v or "").strip().upper())
    if not m or m.group(2) not in MONTH:
        return None
    try:
        return dt.date(int(m.group(3)), MONTH[m.group(2)], int(m.group(1)))
    except ValueError:
        return None


def fx_rate(ccy, d):
    if ccy == "USD":
        return 1.0
    desc = ISO2TREAS.get(ccy)
    if not desc:
        return None
    tgt = d.isoformat()
    for x in reversed(([y for y in FX_DATES if y <= tgt] or FX_DATES[:1])[-8:]):
        if desc in FX[x]:
            return FX[x][desc]
    return None


CONTRACTish = re.compile(
    r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s*-?\s*\d{2,4}\b"
    r"|\b(FUT|FUTURE|IDX|MINI|E-MINI)\b|\d{2}/\d{2}/\d{2}", re.I)
CCP_PAT = re.compile(
    r"\b(LCH\b|LCH\.|CLEARNET|LONDON CLEARING|CHICAGO MERCANTILE EXCH"
    r"|CME CLEARING|CME GROUP|BOARD OF TRADE OF THE CITY OF CHICAGO"
    r"|CHICAGO BOARD OF TRADE|\bCBOT\b|ICE CLEAR|INTERCONTINENTAL EXCHANGE"
    r"|OPTIONS CLEARING CORP|FIXED INCOME CLEARING|\bFICC\b|\bNSCC\b|\bDTCC\b"
    r"|EUREX CLEARING|JAPAN SECURITIES CLEARING|\bJSCC\b|NASDAQ CLEARING"
    r"|CBOE CLEAR|EURONEXT CLEARING|ASX CLEAR|CLEARING HOUSE|CLEARINGHOUSE"
    r"|CENTRAL COUNTERPART|NEW YORK MERCANTILE EXCH|\bCOMEX\b|\bNYMEX\b"
    r"|MINNEAPOLIS GRAIN EXCH|MONTREAL EXCHANGE|B3 S\.A|BM&FBOVESPA)", re.I)

SRC = [("FUT_FWD_NONFOREIGNCUR_CONTRACT.tsv", "NOTIONAL_AMOUNT", None,
        "CURRENCY_CODE", None, "EXPIRATION_DATE", 0),
       ("NONFOREIGN_EXCHANGE_SWAP.tsv", "NOTIONAL_AMOUNT", None,
        "CURRENCY_CODE", None, "TERMINATION_DATE", 0),
       ("FWD_FOREIGNCUR_CONTRACT_SWAP.tsv", "CURRENCY_SOLD_AMOUNT",
        "CURRENCY_PURCHASED_AMOUNT", "DESC_CURRENCY_SOLD",
        "DESC_CURRENCY_PURCHASED", "SETTLEMENT_DATE", 1),
       ("OTHER_DERIV_NOTIONAL_AMOUNT.tsv", "NOTIONAL_AMOUNT", None,
        "CURRENCY_CODE", None, None, 0)]


def tsv(z, n):
    if n not in z.namelist():
        return
    with z.open(n) as fh:
        for x in csv.DictReader(io.TextIOWrapper(fh, encoding="utf8",
                                                 errors="replace", newline=""),
                                delimiter="\t"):
            yield x


def num(v):
    try:
        f = float(str(v).strip())
        return f if f == f else None
    except Exception:
        return None


def process(q, url):
    print(f"\n=== {q} ===", flush=True)
    if not os.path.exists(TMP):
        rr = SEC.get(url, timeout=2400, stream=True)
        if rr.status_code != 200:
            print(f"  HTTP {rr.status_code}"); return
        with open(TMP, "wb") as f:
            for c in rr.iter_content(1 << 21):
                f.write(c)
    z = zipfile.ZipFile(TMP)

    acc_date = {}
    for x in tsv(z, "SUBMISSION.tsv"):
        d = pdate(x.get("REPORT_DATE"))
        if d:
            acc_date[x["ACCESSION_NUMBER"]] = d

    cp = collections.defaultdict(list)
    for x in tsv(z, "DERIVATIVE_COUNTERPARTY.tsv"):
        cp[x["HOLDING_ID"]].append(
            ((x.get("DERIVATIVE_COUNTERPARTY_LEI") or "").strip(),
             re.sub(r"\s+", " ",
                    (x.get("DERIVATIVE_COUNTERPARTY_NAME") or "").strip())))

    hold_acc = {}
    with z.open("FUND_REPORTED_HOLDING.tsv") as fh:
        t = io.TextIOWrapper(fh, encoding="utf8", errors="replace", newline="")
        t.readline()
        for line in t:
            i = line.find("\t"); j = line.find("\t", i + 1)
            h = line[i + 1:j]
            if h in cp:
                hold_acc[h] = line[:i]

    votes = collections.defaultdict(collections.Counter)
    recs = []
    have = miss = 0
    for fn, c1, c2, cc1, cc2, dcol, isfx in SRC:
        for x in tsv(z, fn):
            v1 = num(x.get(c1))
            if v1 is None or v1 <= 0:
                continue
            h = x["HOLDING_ID"]
            acc = hold_acc.get(h)
            if acc is None or acc not in acc_date:
                continue
            d0 = acc_date[acc]
            r1 = fx_rate((x.get(cc1) or "").strip().upper()[:3], d0)
            if not r1:
                continue
            s = abs(v1) / r1
            if c2:
                v2 = num(x.get(c2))
                r2 = fx_rate((x.get(cc2) or "").strip().upper()[:3], d0)
                p_ = abs(v2) / r2 if (v2 and r2) else s
            else:
                p_ = s
            yrs = None
            if dcol:
                md = pdate(x.get(dcol))
                if md:
                    y = (md - d0).days / 365.25
                    if 0 <= y <= 50:
                        yrs = y
            have += (yrs is not None); miss += (yrs is None)
            recs.append((isfx, s, p_, yrs, h))
            for lei, nm in cp[h]:
                if lei:
                    votes[lei][nm] += s

    canon = {}
    for lei, vv in votes.items():
        cl = {k: n for k, n in vv.items() if not CONTRACTish.search(k)
              and k.upper() not in ("N/A", "NA", "NONE", "")}
        canon[lei] = max(cl or vv, key=(cl or vv).get)

    acc = collections.defaultdict(float)
    ymass = collections.defaultdict(float); nmass = collections.defaultdict(float)
    for isfx, s, p_, yrs, h in recs:
        cs = cp[h]
        if yrs is not None:
            ymass[isfx] += s * yrs; nmass[isfx] += s
        for lei, nm in cs:
            cn = canon.get(lei, nm)
            if (cn or "").strip().upper() in ("N/A", "NA", "NONE", ""):
                continue
            if CCP_PAT.search(cn or "") or CCP_PAT.search(nm or ""):
                continue
            acc[("sold", isfx)] += s / len(cs)
            acc[("purch", isfx)] += p_ / len(cs)
            if yrs is not None:
                acc[("matT", isfx)] += s * yrs / len(cs)
                acc[("matS", isfx)] += s * math.sqrt(yrs) / len(cs)

    out = {"q": q, "coverage": 100 * have / max(1, have + miss),
           "avg_mat_fx": ymass[1] / nmass[1] if nmass[1] else None,
           "avg_mat_nonfx": ymass[0] / nmass[0] if nmass[0] else None,
           "bilateral_fx_usd": acc[("sold", 1)],
           "bilateral_nonfx_usd": acc[("sold", 0)]}
    for m in ("sold", "purch", "matT", "matS"):
        f_, n_ = acc[(m, 1)], acc[(m, 0)]
        out[m] = 100 * f_ / (f_ + n_) if f_ + n_ else None
    with open(f"{OUT}/{q}.json", "w", encoding="utf8") as f:
        json.dump(out, f)
    print(f"  FX sold {out['sold']:.1f} | purch {out['purch']:.1f} | "
          f"xT {out['matT']:.1f} | xsqrtT {out['matS']:.1f} | "
          f"matFX {out['avg_mat_fx']:.2f}y nonFX {out['avg_mat_nonfx']:.2f}y | "
          f"cov {out['coverage']:.0f}%", flush=True)
    z.close(); os.remove(TMP)


def main():
    r_ = SEC.get("https://www.sec.gov/data-research/sec-markets-data/"
                 "form-n-port-data-sets", timeout=120)
    links = sorted(set(re.findall(
        r'href="([^"]*form-n-port-data-sets/(\d{4}q\d)_nport\.zip)"', r_.text)))
    print(f"{len(links)} archives", flush=True)
    for href, q in links:
        if os.path.exists(f"{OUT}/{q}.json"):
            print(f"=== {q} === done", flush=True); continue
        u = href if href.startswith("http") else "https://www.sec.gov" + href
        try:
            process(q, u)
        except Exception as e:
            print(f"  FAILED {q}: {type(e).__name__}: {e}", flush=True)
            if os.path.exists(TMP): os.remove(TMP)


if __name__ == "__main__":
    main()
