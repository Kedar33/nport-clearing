# Working notes on Form N-PORT

Everything below was established by reading an actual archive
(`2026q1_nport.zip`, 463 MB, 32 tables) rather than the form instructions. Run
`src/nport_plumbing_probe.py` against any archive to reproduce the counts.

I wrote these up because I got three things wrong before catching them, and each
cost a full rebuild of the panel. If you are starting with this data, read
sections 2 and 3 first.

---

## 1. Distribution

Quarterly ZIP archives from SEC DERA at
`sec.gov/files/dera/data/form-n-port-data-sets/{YYYY}q{N}_nport.zip`.
27 archives cover 2019 Q4 to 2026 Q2, 240 to 724 MB each. The index page has to
be scraped; the URLs are consistent but the listing is the safe way to enumerate.

Thirty-two tab-separated tables. The joins are `ACCESSION_NUMBER` for the filing
and `HOLDING_ID` for the position.

## 2. The two date fields

`SUBMISSION.tsv` carries two dates and they are not the same thing.

| Field | What it is |
|---|---|
| `REPORT_DATE` | the as-of date of the portfolio |
| `REPORT_ENDING_PERIOD` | the fund's **fiscal year end** |

They disagree on **69% of filings**. Typical rows:

```
ending = 31-DEC-2025   report_date = 31-DEC-2025
ending = 31-OCT-2026   report_date = 31-JAN-2026
ending = 30-SEP-2026   report_date = 31-DEC-2025
```

An `ending` later than the `report_date` is the tell. Keying a panel on the
fiscal field collapses distinct portfolio dates into one bucket: the same
filings give 36,484 fund-periods on the fiscal key against 105,604 on
`REPORT_DATE`.

Compounding this, **archives are organised by filing quarter, not by portfolio
date**. One archive holds filings whose as-of dates span about eleven months.

## 3. Fund identity

Funds are `SERIES_ID`. `ACCESSION_NUMBER` is unique to a filing, so keying funds
on it gives zero overlap between any two periods, which looks like complete
turnover and is not.

## 4. Filing frequency and disclosure

Historically quarterly, each filing covering three months. Confirmed in the data:
`MONTHLY_TOTAL_RETURN` has `MONTHLY_TOTAL_RETURN1/2/3` per share class, and
`FUND_REPORTED_INFO` carries `..._MON1/MON2/MON3` for flows and gains. Holdings
themselves appear as of the third month only, so monthly granularity exists for
returns and flows but not for portfolios.

The 2024 amendments were effective 17 November 2025 and move filing to monthly
within 30 days of month end, public after a 60-day delay. A February 2026
proposal would roll public disclosure back to quarterly before that takes effect;
unresolved as of writing.

Amendments are rare. `SUB_TYPE` is `NPORT-P` on 13,110 filings and `NPORT-P/A`
on 38. `IS_LAST_FILING` is `Y` on 58, so neither field cleanly identifies a
definitive record.

Liquidity classifications under Rule 22e-4 remain non-public and appear nowhere
in the tables.

## 5. What is actually populated

Counts from 600,000 scanned holdings unless noted.

**`FUND_REPORTED_HOLDING`** (983 MB uncompressed)

- `PAYOFF_PROFILE`: Long 558,935, N/A 36,685, Short 2,791, blank 1,589. Shorts
  are 0.47% of positions and the N/A share is large enough that you cannot read
  direction from this field alone. Negative `BALANCE` on 1.27% is a second,
  partly inconsistent signal.
- `ASSET_CAT`: EC 245,542, DBT 176,031, ABS-MBS 54,611, LON 52,700, DE 16,578,
  DFE 12,969, then ABS-O, ABS-CBDO, DIR, OTHER, STIV, EP.
- `DERIVATIVE_CAT`: blank on 94%, then SWP 19,018, FWD 12,284, FUT 3,353,
  OPT 2,504, SWO 860, WAR 506, OTH 69.

**`SECURITIES_LENDING`** — `IS_LOAN_BY_FUND` is `Y` on 2.74% of positions and
`LOAN_VALUE` is populated on those. But `CASH_COLLATERAL_AMOUNT` is populated on
0.13% and `NON_CASH_COLLATERAL_VALUE` on 0.00%. Position-level lending is usable;
collateral is not.

**`FUND_REPORTED_INFO`** — 47 columns. `SALES_FLOW_MON1/2/3`,
`REINVESTMENT_FLOW_MON1/2/3` and `REDEMPTION_FLOW_MON1/2/3` are populated on
99.4 to 100%. Also monthly realised and unrealised non-derivative gains, total
and net assets, borrowings by tenor, and a credit-spread grid.

**Identifiers** — this is the binding constraint on joining to anything else.
`ISSUER_CUSIP` is usable on 66.75% of holdings, `IDENTIFIER_ISIN` on 51.2%,
`IDENTIFIER_TICKER` on 11.5%. A third of positions cannot be matched to CRSP or
Compustat without falling back on name or LEI.

**Derivative notional** lives in separate per-instrument tables:
`FUT_FWD_NONFOREIGNCUR_CONTRACT`, `NONFOREIGN_EXCHANGE_SWAP`,
`FWD_FOREIGNCUR_CONTRACT_SWAP`, `OTHER_DERIV_NOTIONAL_AMOUNT` and
`SWAPTION_OPTION_WARNT_DERIV`. `DESC_REF_INDEX_COMPONENT` also carries a notional
column but it is component-level within baskets and will double-count if summed
with the others.

**`DERIVATIVE_COUNTERPARTY`** carries both name and LEI. LEI is present on 93.7%
of rows. The name field is badly fragmented: 1,778 distinct spellings resolve to
376 entities, with one LEI absorbing 23 spellings and another 24. Resolve on LEI
and take the notional-weighted modal spelling for display.

## 6. Who files what

Registered investment companies file N-PORT: open-end funds, ETFs, closed-end
funds. Money market funds file N-MFP instead. The annual census is N-CEN. Hedge
funds, pensions and bank trading books file none of these.

## 7. Defects, collected

1. `REPORT_ENDING_PERIOD` is the fiscal year end, not the portfolio date.
2. Archives are keyed by filing quarter and span about eleven months of as-of dates.
3. `ISSUER_CUSIP` usable on 66.75% of holdings.
4. `IDENTIFIER_TICKER` on 11.5%.
5. Lending collateral fields empty in practice.
6. `PAYOFF_PROFILE` is N/A on 6% of rows; direction is not reliably readable.
7. `DESC_REF_INDEX_COMPONENT` double-counts notional.
8. Counterparty names are free text and heavily fragmented.
9. Liquidity classifications absent.
10. Neither `SUB_TYPE` nor `IS_LAST_FILING` cleanly marks the definitive record.
