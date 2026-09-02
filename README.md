# All or Nothing: Central Clearing in the US Fund Industry

Who clears derivatives, measured fund by fund from SEC Form N-PORT, 2019-2026.

**Headline.** Clearing adoption is close to binary at the level of the fund
complex. Of **168 fund families** with at least $30bn of derivative notional,
**52 clear less than a quarter** of it and **44 clear more than three quarters**;
mean 49.2%, sd 33.7. Direxion Shares ETF Trust clears **0.1%** of $1.62tn across
125 funds; Principal Funds clears **100%** of $1.07tn across 28. The dividing
line is not scale but **instrument eligibility**: families whose books are
concentrated in clearing-eligible instruments clear 61.3% against 37.0% for the
rest (24.3pp, se 4.88, *t* = 4.98), while the adoption-size gradient is
indistinguishable from zero (*t* = 0.21).

Panel: **10,893 funds, 105,604 fund-periods, 80 portfolio dates**, all 27
quarterly N-PORT archives.

## Reproducing

```bash
python src/build_panel.py           # downloads 27 archives, builds the fund panel
python src/maturity_correction.py   # maturity-weighted robustness
python src/make_figures.py          # figures + published CSVs
python src/falsification.py         # placebo, subsample splits, specification curve
python src/framework_simulation.py  # fixed-cost model, numerical verification
pdflatex main && pdflatex main
```

Each script streams archives one at a time and deletes each after processing, so
peak disk is about 1 GB rather than 10.

## Published data

| File | Contents |
|---|---|
| `data/counterparty_classification.csv` | All 756 counterparty names with CCP/bilateral classification and the matched pattern, so the classification can be audited rather than taken on trust. |
| `data/family_clearing.csv` | The 168-family panel: notional, cleared share, eligible share, fund count. |

## Read this before using N-PORT

`NPORT_PLUMBING.md` documents the dataset's traps, established from the filings
rather than from documentation. Three of them cost this project a rebuild each.

1. **Archives are organised by *filing* quarter, not report date.** One archive
   carries filings whose portfolio dates span about eleven months.
2. **`REPORT_DATE` and `REPORT_ENDING_PERIOD` are different things.**
   `REPORT_DATE` is the portfolio as-of date; `REPORT_ENDING_PERIOD` is the
   fund's *fiscal year end*. They differ on **69% of filings**. Keying on the
   fiscal field collapses distinct portfolio dates into one bucket and discards
   roughly two-thirds of the panel's time resolution: 36,484 fund-periods under
   the fiscal key against 105,604 under the correct one.
3. **Funds are `SERIES_ID`, not `ACCESSION_NUMBER`.** Accession is unique per
   filing, so under that key the fund overlap between consecutive periods is zero.

Also documented there: `ISSUER_CUSIP` usable on only 66.75% of holdings, ticker
on 11.5%, lending collateral fields populated on 0.13% and 0.00%, and
`DESC_REF_INDEX_COMPONENT` double-counting notional if naively summed.

## What did not survive

Section 6 of the paper reports a result we withdrew, because the withdrawal is
informative about the data.

FX forwards are **60.0% of uncleared gross notional**, and that figure is robust
across every specification tried. But FX forwards average **0.10 years to
maturity against 3.50 years for everything else**, a thirty-four-fold gap.
Weighting notional by maturity collapses their share to **3.3%**, or **19.8%**
under square-root scaling, across all 27 archives at 99% maturity coverage. The
exposure interpretation does not survive. Gross notional is the metric the
Uncleared Margin Rules are written in, which makes it relevant, but it is not
exposure, and reading it as exposure is wrong by roughly a factor of eighteen.

## Licence

- Code (`src/`) - MIT
- Paper and text (`main.tex`, `*.md`) - CC BY 4.0

No SEC data is redistributed. Everything is fetched at run time from the free
DERA archives.

## Citation

> Sahu, K. (2026). *All or Nothing: Central Clearing in the US Fund Industry.*
> Working paper.
