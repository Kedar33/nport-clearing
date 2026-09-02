import collections
import csv
import io
import json
import os
import re
import zipfile

import requests

SEC = requests.Session()
SEC.headers["User-Agent"] = "Kedar Sahu independent research kedasahu@gmail.com"
OUT = "data/panel"
os.makedirs(OUT, exist_ok=True)
TMP = "data/cache/archive.zip"

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
MONTH = {"JAN": "01", "FEB": "02", "MAR": "03", "APR": "04", "MAY": "05",
         "JUN": "06", "JUL": "07", "AUG": "08", "SEP": "09", "OCT": "10",
         "NOV": "11", "DEC": "12"}

r = SEC.get("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/"
            "accounting/od/rates_of_exchange?fields=country_currency_desc,"
            "exchange_rate,record_date&filter=record_date:gte:2019-06-30"
            "&page[size]=10000", timeout=180)
FX = collections.defaultdict(dict)
for d in r.json()["data"]:
    FX[d["record_date"]][d["country_currency_desc"]] = float(d["exchange_rate"])
FX_DATES = sorted(FX)
print(f"FX: {len(FX_DATES)} dates", flush=True)


def iso_period(v):
    m = re.match(r"(\d{2})-([A-Z]{3})-(\d{4})", (v or "").strip().upper())
    return f"{m.group(3)}-{MONTH[m.group(2)]}" if m and m.group(2) in MONTH else None


def fx_rate(ccy, period):
    if ccy == "USD":
        return 1.0
    desc = ISO2TREAS.get(ccy)
    if not desc:
        return None
    tgt = period + "-28"
    for d in reversed(([x for x in FX_DATES if x <= tgt] or FX_DATES[:1])[-8:]):
        if desc in FX[d]:
            return FX[d][desc]
    return None


CONTRACTish = re.compile(
    r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s*-?\s*\d{2,4}\b"
    r"|\b(FUT|FUTURE|IDX|MINI|E-MINI)\b|\d{2}/\d{2}/\d{2}", re.I)
CCP_PAT = re.compile(
    r"\b(LCH\b|LCH\.|CLEARNET|LONDON CLEARING"
    r"|CHICAGO MERCANTILE EXCH|CME CLEARING|CME GROUP"
    r"|BOARD OF TRADE OF THE CITY OF CHICAGO|CHICAGO BOARD OF TRADE|\bCBOT\b"
    r"|ICE CLEAR|INTERCONTINENTAL EXCHANGE"
    r"|OPTIONS CLEARING CORP|FIXED INCOME CLEARING|\bFICC\b|\bNSCC\b|\bDTCC\b"
    r"|EUREX CLEARING|JAPAN SECURITIES CLEARING|\bJSCC\b"
    r"|NASDAQ CLEARING|CBOE CLEAR|EURONEXT CLEARING|ASX CLEAR"
    r"|CLEARING HOUSE|CLEARINGHOUSE|CENTRAL COUNTERPART"
    r"|NEW YORK MERCANTILE EXCH|\bCOMEX\b|\bNYMEX\b"
    r"|SINGAPORE EXCHANGE DERIV|HKFE CLEARING|SHANGHAI CLEARING"
    r"|MINNEAPOLIS GRAIN EXCH|MONTREAL EXCHANGE|CANADIAN DERIVATIVES CLEARING"
    r"|B3 S\.A|BM&FBOVESPA)", re.I)

SRC = [("FUT_FWD_NONFOREIGNCUR_CONTRACT.tsv", "NOTIONAL_AMOUNT", "CURRENCY_CODE", 0),
       ("NONFOREIGN_EXCHANGE_SWAP.tsv", "NOTIONAL_AMOUNT", "CURRENCY_CODE", 0),
       ("FWD_FOREIGNCUR_CONTRACT_SWAP.tsv", "CURRENCY_SOLD_AMOUNT",
        "DESC_CURRENCY_SOLD", 1),
       ("OTHER_DERIV_NOTIONAL_AMOUNT.tsv", "NOTIONAL_AMOUNT", "CURRENCY_CODE", 0)]


def tsv(z, name):
    if name not in z.namelist():
        return
    with z.open(name) as fh:
        for r_ in csv.DictReader(io.TextIOWrapper(fh, encoding="utf8",
                                                  errors="replace", newline=""),
                                 delimiter="\t"):
            yield r_


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

    acc_period = {}
    for r_ in tsv(z, "SUBMISSION.tsv"):
        p = iso_period(r_.get("REPORT_DATE"))
        if p:
            acc_period[r_["ACCESSION_NUMBER"]] = p

    acc_fund = {}
    for r_ in tsv(z, "FUND_REPORTED_INFO.tsv"):
        acc_fund[r_["ACCESSION_NUMBER"]] = (
            (r_.get("SERIES_ID") or "").strip(),
            (r_.get("SERIES_NAME") or "").strip()[:60],
            num(r_.get("NET_ASSETS")) or 0.0)

    acc_reg = {}
    for r_ in tsv(z, "REGISTRANT.tsv"):
        acc_reg[r_["ACCESSION_NUMBER"]] = (
            (r_.get("CIK") or "").strip(),
            (r_.get("REGISTRANT_NAME") or r_.get("NAME") or "").strip()[:60])

    cp = collections.defaultdict(list)
    for r_ in tsv(z, "DERIVATIVE_COUNTERPARTY.tsv"):
        cp[r_["HOLDING_ID"]].append(
            ((r_.get("DERIVATIVE_COUNTERPARTY_LEI") or "").strip(),
             re.sub(r"\s+", " ",
                    (r_.get("DERIVATIVE_COUNTERPARTY_NAME") or "").strip())))

    hold_acc = {}
    with z.open("FUND_REPORTED_HOLDING.tsv") as fh:
        t = io.TextIOWrapper(fh, encoding="utf8", errors="replace", newline="")
        t.readline()
        for line in t:
            i = line.find("\t"); j = line.find("\t", i + 1)
            hid = line[i + 1:j]
            if hid in cp:
                hold_acc[hid] = line[:i]

    F = collections.Counter()
    notional, meta = collections.defaultdict(float), {}
    votes = collections.defaultdict(collections.Counter)
    for fn, ncol, ccol, isfx in SRC:
        for r_ in tsv(z, fn):
            v = num(r_.get(ncol))
            if v is None: F["unparseable"] += 1; continue
            if v <= 0:    F["zero/neg"] += 1; continue
            hid = r_["HOLDING_ID"]
            acc = hold_acc.get(hid)
            if acc is None: F["no filer join"] += 1; continue
            per = acc_period.get(acc)
            if per is None: F["no period"] += 1; continue
            rate = fx_rate((r_.get(ccol) or "").strip().upper()[:3], per)
            if not rate: F["no FX rate"] += 1; continue
            usd = abs(v) / rate
            notional[(hid, isfx)] += usd
            meta[(hid, isfx)] = (per, acc)
            for lei, nm in cp[hid]:
                if lei: votes[lei][nm] += usd

    canon = {}
    for lei, vv in votes.items():
        clean = {k: s for k, s in vv.items() if not CONTRACTish.search(k)
                 and k.upper() not in ("N/A", "NA", "NONE", "")}
        canon[lei] = max(clean or vv, key=(clean or vv).get)

    fund = collections.defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
    ent = collections.defaultdict(float)
    for (hid, isfx), amt in notional.items():
        per, acc = meta[(hid, isfx)]
        sid, sname, na = acc_fund.get(acc, ("", "", 0.0))
        cik, rname = acc_reg.get(acc, ("", ""))
        cs = cp[hid]; share = amt / len(cs)
        for lei, nm in cs:
            cn = canon.get(lei, nm)
            if (cn or "").strip().upper() in ("N/A", "NA", "NONE", ""):
                F["N/A cp"] += 1; continue
            cleared = bool(CCP_PAT.search(cn or "") or CCP_PAT.search(nm or ""))
            idx = (0 if cleared else 1) + (0 if isfx else 2)
            fund[(per, sid or acc, sname, cik, rname, na)][idx] += share
            ent[(per, isfx, cleared, cn[:56])] += share

    recs = [[p, s, sn, ck, rn, na] + v
            for (p, s, sn, ck, rn, na), v in fund.items()]
    with open(f"{OUT}/{q}.json", "w", encoding="utf8") as f:
        json.dump({"archive": q, "funds": recs, "filters": dict(F),
                   "entities": sorted([[p, x, c, n, v]
                                       for (p, x, c, n), v in ent.items()],
                                      key=lambda r_: -r_[4])[:600]}, f)
    tot = sum(sum(v[6:]) if False else sum(v) for v in fund.values())
    fxb = sum(v[1] for v in fund.values()); fxc = sum(v[0] for v in fund.values())
    bil = sum(v[1] + v[3] for v in fund.values())
    sids = len({s for _, s, *_ in recs})
    print(f"  ${tot/1e12:.3f}tn | {len(recs):,} fund-periods | {sids:,} SERIES_IDs"
          f" | FX/bilat {100*fxb/bil if bil else 0:.1f}%"
          f" | FXclr {100*fxc/(fxc+fxb) if fxc+fxb else 0:.3f}% | {dict(F)}",
          flush=True)
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
