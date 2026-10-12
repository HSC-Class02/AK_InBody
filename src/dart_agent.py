"""OpenDART financial-data collector for InBody (041830).

The standard OpenDART financial-statement endpoints document coverage from 2015 onward.
The configured start_year remains 2010 so coverage checks are explicit; years before 2015
are recorded as unavailable from this endpoint rather than silently represented as zero.
"""
import csv
import io
import json
import os
import time
import zipfile
import xml.etree.ElementTree as ET
from calendar import isleap
from datetime import date
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://opendart.fss.or.kr/api"
ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
KEY = os.getenv("DART_API_KEY", "").strip()
API_FIRST_YEAR = int(CFG.get("api_first_year", 2015))
REPORTS = CFG["reports"]
FLOW_FIELDS = [
    "revenue", "cost_of_sales", "gross_profit", "sga", "operating_profit",
    "pretax_profit", "income_tax_expense", "net_income", "controlling_net_income",
    "depreciation_amortization", "interest_expense", "cfo", "cfi", "cff",
    "capex_ppe", "capex_intangible",
]

def spec(ids=(), names=(), statements=(), kind="flow"):
    return {"ids": tuple(ids), "names": tuple(names), "statements": set(statements), "kind": kind}

A = {
    "revenue": spec(("ifrs-full_Revenue", "ifrs_Revenue", "dart_Revenue"),
                    ("매출액", "수익(매출액)", "영업수익", "매출", "Revenue"), ("IS", "CIS")),
    "cost_of_sales": spec(("ifrs-full_CostOfSales", "ifrs_CostOfSales"),
                          ("매출원가", "매출원가(손실)", "Cost of sales"), ("IS", "CIS")),
    "gross_profit": spec(("ifrs-full_GrossProfit", "ifrs_GrossProfit"),
                         ("매출총이익", "매출총손익", "Gross profit"), ("IS", "CIS")),
    "sga": spec(("ifrs-full_SellingGeneralAndAdministrativeExpense", "ifrs_SellingGeneralAndAdministrativeExpense"),
                ("판매비와관리비", "판매비및관리비", "판매비와관리비(손실)", "Selling, general and administrative expenses"), ("IS", "CIS")),
    "operating_profit": spec(("dart_OperatingIncomeLoss", "ifrs-full_OperatingProfitLoss", "ifrs_OperatingIncomeLoss"),
                             ("영업이익", "영업이익(손실)", "영업손익", "Operating profit"), ("IS", "CIS")),
    "pretax_profit": spec(("ifrs-full_ProfitLossBeforeTax", "ifrs_ProfitLossBeforeTax"),
                          ("법인세비용차감전순이익", "법인세비용차감전순손익", "세전이익", "Profit before tax"), ("IS", "CIS")),
    "income_tax_expense": spec(("ifrs-full_IncomeTaxExpenseContinuingOperations", "ifrs-full_IncomeTaxExpense"),
                               ("법인세비용", "법인세비용(수익)", "법인세비용차감", "Income tax expense"), ("IS", "CIS")),
    "net_income": spec(("ifrs-full_ProfitLoss", "ifrs_ProfitLoss"),
                       ("당기순이익", "당기순이익(손실)", "분기순이익", "반기순이익", "당기순손익", "Profit (loss)"), ("IS", "CIS")),
    "controlling_net_income": spec(("ifrs-full_ProfitLossAttributableToOwnersOfParent", "ifrs_ProfitLossAttributableToOwnersOfParent"),
                                   ("지배기업의 소유주에게 귀속되는 당기순이익", "지배기업 소유주지분 순이익", "지배주주순이익"), ("IS", "CIS")),
    "depreciation_amortization": spec(("ifrs-full_DepreciationDepletionAndAmortisationExpense", "ifrs-full_DepreciationAndAmortisationExpense"),
                                     ("감가상각비및무형자산상각비", "감가상각비와무형자산상각비", "감가상각비", "무형자산상각비", "Depreciation and amortisation"), ("IS", "CIS", "CF")),
    "interest_expense": spec(("ifrs-full_InterestExpense", "ifrs_InterestExpense", "dart_InterestExpense"),
                             ("이자비용", "이자비용(금융원가)", "Interest expense"), ("IS", "CIS")),
    "assets": spec(("ifrs-full_Assets", "ifrs_Assets"), ("자산총계", "자산합계", "Total assets"), ("BS",), "balance"),
    "current_assets": spec(("ifrs-full_CurrentAssets", "ifrs_CurrentAssets"), ("유동자산", "Current assets"), ("BS",), "balance"),
    "cash": spec(("ifrs-full_CashAndCashEquivalents", "ifrs_CashAndCashEquivalents"),
                 ("현금및현금성자산", "현금 및 현금성자산", "Cash and cash equivalents"), ("BS",), "balance"),
    "receivables": spec(("ifrs-full_TradeAndOtherCurrentReceivables", "ifrs-full_TradeReceivables", "ifrs_TradeAndOtherCurrentReceivables"),
                        ("매출채권", "매출채권및기타유동채권", "매출채권 및 기타유동채권", "Trade receivables"), ("BS",), "balance"),
    "inventory": spec(("ifrs-full_Inventories", "ifrs_Inventories"), ("재고자산", "Inventories"), ("BS",), "balance"),
    "ppe": spec(("ifrs-full_PropertyPlantAndEquipment", "ifrs_PropertyPlantAndEquipment"),
                ("유형자산", "유형자산 순액", "Property, plant and equipment"), ("BS",), "balance"),
    "intangible_assets": spec(("ifrs-full_IntangibleAssetsOtherThanGoodwill", "ifrs_IntangibleAssets"),
                              ("무형자산", "무형자산 순액", "Intangible assets"), ("BS",), "balance"),
    "liabilities": spec(("ifrs-full_Liabilities", "ifrs_Liabilities"), ("부채총계", "부채합계", "Total liabilities"), ("BS",), "balance"),
    "current_liabilities": spec(("ifrs-full_CurrentLiabilities", "ifrs_CurrentLiabilities"), ("유동부채", "Current liabilities"), ("BS",), "balance"),
    "equity": spec(("ifrs-full_Equity", "ifrs_Equity"), ("자본총계", "자본합계", "Equity"), ("BS",), "balance"),
    "trade_payables": spec(("ifrs-full_TradePayables", "ifrs_TradePayables"),
                           ("매입채무", "매입채무및기타유동채무", "Trade payables"), ("BS",), "balance"),
    "short_term_borrowings": spec(("ifrs-full_ShorttermBorrowings", "ifrs_ShorttermBorrowings"),
                                  ("단기차입금", "단기차입부채", "Short-term borrowings"), ("BS",), "balance"),
    "long_term_borrowings": spec(("ifrs-full_LongtermBorrowings", "ifrs_LongtermBorrowings"),
                                 ("장기차입금", "장기차입부채", "Long-term borrowings"), ("BS",), "balance"),
    "current_portion_long_debt": spec(("ifrs-full_CurrentPortionOfLongtermBorrowings", "ifrs_CurrentPortionOfLongtermBorrowings"),
                                      ("유동성장기차입금", "유동성장기부채", "유동성 장기부채", "Current portion of long-term debt"), ("BS",), "balance"),
    "cfo": spec(("ifrs-full_CashFlowsFromUsedInOperatingActivities", "ifrs_CashFlowsFromUsedInOperatingActivities"),
                ("영업활동현금흐름", "영업활동으로 인한 현금흐름", "영업활동으로부터의 순현금흐름", "Net cash flows from operating activities"), ("CF",)),
    "cfi": spec(("ifrs-full_CashFlowsFromUsedInInvestingActivities", "ifrs_CashFlowsFromUsedInInvestingActivities"),
                ("투자활동현금흐름", "투자활동으로 인한 현금흐름", "투자활동으로부터의 순현금흐름", "Net cash flows from investing activities"), ("CF",)),
    "cff": spec(("ifrs-full_CashFlowsFromUsedInFinancingActivities", "ifrs_CashFlowsFromUsedInFinancingActivities"),
                ("재무활동현금흐름", "재무활동으로 인한 현금흐름", "재무활동으로부터의 순현금흐름", "Net cash flows from financing activities"), ("CF",)),
    "capex_ppe": spec(("ifrs-full_PurchaseOfPropertyPlantAndEquipment", "ifrs_PurchaseOfPropertyPlantAndEquipment"),
                      ("유형자산의 취득", "유형자산 취득", "유형자산의 취득으로 인한 현금유출", "유형자산취득", "Purchase of property, plant and equipment"), ("CF",)),
    "capex_intangible": spec(("ifrs-full_PurchaseOfIntangibleAssetsOtherThanGoodwill", "ifrs_PurchaseOfIntangibleAssets"),
                             ("무형자산의 취득", "무형자산 취득", "무형자산의 취득으로 인한 현금유출", "무형자산취득", "Purchase of intangible assets"), ("CF",)),
}
BALANCE_FIELDS = [k for k, v in A.items() if v["kind"] == "balance"]

def normalize(text):
    return "".join(str(text or "").lower().split()).replace("(", "").replace(")", "").replace("（", "").replace("）", "")

def number(value):
    if value is None:
        return None
    try:
        text = str(value).replace(",", "").strip()
        if not text or text in {"-", "—", "N/A"}:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None

session = requests.Session()
retries = Retry(total=4, connect=4, read=4, backoff_factor=1.0,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset(["GET"]))
session.mount("https://", HTTPAdapter(max_retries=retries))

def api(path, params=None):
    if not KEY:
        raise RuntimeError("DART_API_KEY is missing. Add it under Settings > Secrets and variables > Actions.")
    payload = {"crtfc_key": KEY}
    payload.update(params or {})
    response = session.get(f"{BASE}/{path}", params=payload, timeout=45)
    response.raise_for_status()
    result = response.json()
    status = str(result.get("status", "000"))
    if status == "013":
        return {"status": status, "list": []}
    if status != "000":
        # Fail fast for an invalid/suspended key, blocked IP, quota, or malformed request.
        raise RuntimeError(f"OpenDART API error {status}: {result.get('message', 'unknown error')}")
    return result

def find_corp_code():
    response = session.get(f"{BASE}/corpCode.xml", params={"crtfc_key": KEY}, timeout=45)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        xml_names = [name for name in archive.namelist() if name.lower().endswith(".xml")]
        if not xml_names:
            raise RuntimeError("OpenDART corpCode.xml response did not contain an XML file.")
        root = ET.fromstring(archive.read(xml_names[0]))
    stock_code = str(CFG["stock_code"]).zfill(6)
    for item in root.findall("list"):
        if (item.findtext("stock_code") or "").strip().zfill(6) == stock_code:
            code = (item.findtext("corp_code") or "").strip()
            if code:
                return code
    raise RuntimeError(f"Could not find corp_code for stock code {stock_code}.")

def account_value(rows, field, report_code):
    meta = A[field]
    eligible = [r for r in rows if not r.get("sj_div") or r.get("sj_div") in meta["statements"]]
    # Account IDs are the most reliable match; fall back to normalized labels for non-standard accounts.
    for alias in meta["ids"]:
        for row in eligible:
            if row.get("account_id") == alias:
                return read_amount(row, meta["kind"], report_code)
    wanted = {normalize(x) for x in meta["names"]}
    for row in eligible:
        if normalize(row.get("account_nm")) in wanted:
            return read_amount(row, meta["kind"], report_code)
    return None

def read_amount(row, kind, report_code):
    if kind == "balance" or report_code == "11011":
        keys = ("thstrm_amount", "thstrm_add_amount")
    else:
        # OpenDART defines thstrm_amount as the 3-month amount for interim IS/CIS,
        # and thstrm_add_amount as the year-to-date amount. Normalize intermediate
        # report flows to YTD here; standalone quarters are derived below.
        keys = ("thstrm_add_amount", "thstrm_amount")
    for key in keys:
        value = number(row.get(key))
        if value is not None:
            return value
    return None

def fetch_report(corp, year, report_label, report_code):
    for fs_div in ("CFS", "OFS"):
        result = api("fnlttSinglAcntAll.json", {
            "corp_code": corp, "bsns_year": str(year),
            "reprt_code": report_code, "fs_div": fs_div,
        })
        rows = result.get("list", []) or []
        if rows:
            record = {
                "year": year,
                "source_report": report_label,
                "reprt_code": report_code,
                "rcept_no": rows[0].get("rcept_no", ""),
                "fs_div": rows[0].get("fs_div", fs_div),
            }
            for field in A:
                record[field] = account_value(rows, field, report_code)
            # Revenue minus cost of sales is a transparent fallback when gross profit is not a reported line.
            if record["gross_profit"] is None and record["revenue"] is not None and record["cost_of_sales"] is not None:
                record["gross_profit"] = record["revenue"] - abs(record["cost_of_sales"])
            raw_path = ROOT / "data" / "raw" / f"{year}_{report_label}.json"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
            return record
    return None

def days_in_period(year, period, quarter=None):
    from datetime import date
    if period == "annual":
        return 366 if isleap(year) else 365
    if period == "half_year":
        return (date(year, 7, 1) - date(year, 1, 1)).days
    if quarter:
        starts = {1: date(year, 1, 1), 2: date(year, 4, 1), 3: date(year, 7, 1), 4: date(year, 10, 1)}
        ends = {1: date(year, 4, 1), 2: date(year, 7, 1), 3: date(year, 10, 1), 4: date(year + 1, 1, 1)}
        return (ends[quarter] - starts[quarter]).days
    return None

def build_period_rows(report_rows):
    by_year = {}
    for row in report_rows:
        by_year.setdefault(int(row["year"]), {})[row["source_report"]] = row
    result = []
    # Annual and half-year rows keep full-year and cumulative six-month flows, respectively.
    for year, reports in sorted(by_year.items()):
        for label, period in (("annual", "annual"), ("half_year", "half_year")):
            source = reports.get(label)
            if source:
                item = dict(source)
                item.update({"period": period, "quarter": "", "period_days": days_in_period(year, period)})
                result.append(item)
        # Use quarterly balance-sheet snapshots, and derive standalone quarterly flows from cumulative filings.
        quarter_specs = [
            (1, "q1", None),
            (2, "half_year", "q1"),
            (3, "q3", "half_year"),
            (4, "annual", "q3"),
        ]
        for quarter, current_label, previous_label in quarter_specs:
            current = reports.get(current_label)
            if not current:
                continue
            previous = reports.get(previous_label) if previous_label else None
            item = dict(current)
            item.update({
                "period": "quarterly",
                "quarter": f"Q{quarter}",
                "period_days": days_in_period(year, "quarterly", quarter),
                "source_report": current_label,
            })
            for field in FLOW_FIELDS:
                current_value = current.get(field)
                previous_value = previous.get(field) if previous else 0.0
                if current_value is None or (previous is not None and previous_value is None):
                    item[field] = None
                else:
                    item[field] = current_value - previous_value
            result.append(item)
    return result

def safe_div(numerator, denominator):
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator

def derive_metrics(rows):
    # Build matching-period references to calculate average balances and like-for-like growth.
    lookup = {}
    for row in rows:
        key = (int(row["year"]), row["period"], row.get("quarter", ""))
        lookup[key] = row
    for row in rows:
        year = int(row["year"])
        period = row["period"]
        quarter = row.get("quarter", "")
        previous_balance = None
        if period == "annual":
            previous_balance = lookup.get((year - 1, "annual", ""))
        elif period == "half_year":
            previous_balance = lookup.get((year - 1, "annual", ""))
        elif period == "quarterly":
            q_num = int(str(quarter).replace("Q", ""))
            previous_balance = lookup.get((year, "quarterly", f"Q{q_num - 1}")) if q_num > 1 else lookup.get((year - 1, "annual", ""))
        for name in ("cost_of_sales", "sga", "depreciation_amortization", "interest_expense"):
            if row.get(name) is not None:
                row[name] = abs(row[name])
        for name in ("capex_ppe", "capex_intangible"):
            if row.get(name) is not None:
                # Preserve sign until cumulative amounts have been differenced; use absolute outlay for ratios/FCF.
                row[name] = abs(row[name])
        # Some accounts report capex as outflows (negative); the absolute value above gives cash spent.
        capex_values = [row.get("capex_ppe"), row.get("capex_intangible")]
        row["capex"] = sum(v for v in capex_values if v is not None) if any(v is not None for v in capex_values) else None
        if row.get("gross_profit") is None and row.get("revenue") is not None and row.get("cost_of_sales") is not None:
            row["gross_profit"] = row["revenue"] - row["cost_of_sales"]
        row["ebitda"] = (
            row["operating_profit"] + row["depreciation_amortization"]
            if row.get("operating_profit") is not None and row.get("depreciation_amortization") is not None else None
        )
        borrow_fields = ["short_term_borrowings", "long_term_borrowings", "current_portion_long_debt"]
        found_borrowing = [row.get(f) for f in borrow_fields if row.get(f) is not None]
        row["interest_bearing_debt"] = sum(found_borrowing) if found_borrowing else None
        row["net_debt"] = (
            row["interest_bearing_debt"] - row["cash"]
            if row.get("interest_bearing_debt") is not None and row.get("cash") is not None else None
        )
        row["fcf"] = row["cfo"] - row["capex"] if row.get("cfo") is not None and row.get("capex") is not None else None
        row["avg_assets"] = (
            (row["assets"] + previous_balance["assets"]) / 2
            if row.get("assets") is not None and previous_balance and previous_balance.get("assets") is not None else None
        )
        row["avg_equity"] = (
            (row["equity"] + previous_balance["equity"]) / 2
            if row.get("equity") is not None and previous_balance and previous_balance.get("equity") is not None else None
        )
        row["avg_receivables"] = (
            (row["receivables"] + previous_balance["receivables"]) / 2
            if row.get("receivables") is not None and previous_balance and previous_balance.get("receivables") is not None else None
        )
        row["avg_inventory"] = (
            (row["inventory"] + previous_balance["inventory"]) / 2
            if row.get("inventory") is not None and previous_balance and previous_balance.get("inventory") is not None else None
        )
        row["avg_trade_payables"] = (
            (row["trade_payables"] + previous_balance["trade_payables"]) / 2
            if row.get("trade_payables") is not None and previous_balance and previous_balance.get("trade_payables") is not None else None
        )
        revenue = row.get("revenue")
        row["revenue_growth"] = None
        prior = lookup.get((year - 1, period, quarter))
        if revenue is not None and prior and prior.get("revenue") is not None and prior["revenue"] > 0:
            row["revenue_growth"] = revenue / prior["revenue"] - 1
        row["gross_margin"] = safe_div(row.get("gross_profit"), revenue)
        row["operating_margin"] = safe_div(row.get("operating_profit"), revenue)
        row["net_margin"] = safe_div(row.get("net_income"), revenue)
        row["ebitda_margin"] = safe_div(row.get("ebitda"), revenue)
        row["roa"] = safe_div(row.get("net_income"), row.get("avg_assets"))
        row["roe"] = safe_div(row.get("net_income"), row.get("avg_equity"))
        row["current_ratio"] = safe_div(row.get("current_assets"), row.get("current_liabilities"))
        quick_assets = row.get("current_assets") - row.get("inventory") if row.get("current_assets") is not None and row.get("inventory") is not None else None
        row["quick_ratio"] = safe_div(quick_assets, row.get("current_liabilities"))
        row["debt_to_equity"] = safe_div(row.get("liabilities"), row.get("equity"))
        row["equity_ratio"] = safe_div(row.get("equity"), row.get("assets"))
        row["debt_to_assets"] = safe_div(row.get("liabilities"), row.get("assets"))
        row["borrowing_to_assets"] = safe_div(row.get("interest_bearing_debt"), row.get("assets"))
        row["interest_coverage"] = safe_div(row.get("operating_profit"), row.get("interest_expense"))
        row["net_debt_to_ebitda"] = safe_div(row.get("net_debt"), row.get("ebitda"))
        row["asset_turnover"] = safe_div(revenue, row.get("avg_assets"))
        row["receivables_turnover"] = safe_div(revenue, row.get("avg_receivables"))
        row["dso_days"] = safe_div(row.get("period_days"), row.get("receivables_turnover"))
        row["inventory_turnover"] = safe_div(row.get("cost_of_sales"), row.get("avg_inventory"))
        row["dio_days"] = safe_div(row.get("period_days"), row.get("inventory_turnover"))
        row["dpo_days"] = None  # Credit purchases are not reliably disclosed as a single standardized account.
        row["ccc_days"] = None  # Not calculated unless DPO can be measured on a comparable basis.
        row["cfo_to_net_income"] = safe_div(row.get("cfo"), row.get("net_income"))
        # ROIC requires usable observed tax expense and invested capital. Do not substitute a guessed tax rate.
        tax_rate = safe_div(row.get("income_tax_expense"), row.get("pretax_profit"))
        invested_capital = (
            row.get("interest_bearing_debt") + row.get("equity") - row.get("cash")
            if row.get("interest_bearing_debt") is not None and row.get("equity") is not None and row.get("cash") is not None else None
        )
        prior_invested = None
        if previous_balance and previous_balance.get("interest_bearing_debt") is not None and previous_balance.get("equity") is not None and previous_balance.get("cash") is not None:
            prior_invested = previous_balance["interest_bearing_debt"] + previous_balance["equity"] - previous_balance["cash"]
        average_invested = (invested_capital + prior_invested) / 2 if invested_capital is not None and prior_invested is not None else None
        nopat = row["operating_profit"] * (1 - tax_rate) if row.get("operating_profit") is not None and tax_rate is not None and 0 <= tax_rate <= 1 else None
        row["roic"] = safe_div(nopat, average_invested)
    return rows

def main():
    if not KEY:
        raise SystemExit("DART_API_KEY is missing. Add it in repository Actions secrets.")
    corp = find_corp_code()
    today = date.today()
    first_year = int(CFG.get("start_year", 2010))
    report_rows = []
    coverage = {
        "company": CFG.get("company_name", "InBody"),
        "stock_code": CFG.get("stock_code", "041830"),
        "corp_code": corp,
        "configured_start_year": first_year,
        "standard_api_first_year": API_FIRST_YEAR,
        "run_date": today.isoformat(),
        "years_before_standard_api": list(range(first_year, min(API_FIRST_YEAR, today.year + 1))),
        "reports_found": [],
        "missing_reports": [],
        "note": "The standard OpenDART full-financial-statements endpoint documents data from 2015 onward. Earlier filings require a separate original-filing/XBRL parser and are not fabricated here.",
    }
    if first_year < API_FIRST_YEAR:
        print(f"INFO: {first_year}-{API_FIRST_YEAR - 1} are outside standard endpoint coverage; they are recorded as unavailable, not zero.")
    raw_dir = ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for year in range(max(first_year, API_FIRST_YEAR), today.year + 1):
        for label, code in REPORTS.items():
            try:
                rec = fetch_report(corp, year, label, code)
            except Exception as exc:
                # Authentication, quota, and systemic API errors should fail the workflow instead of being silently skipped.
                raise RuntimeError(f"Failed retrieving {year} {label}: {exc}") from exc
            if rec:
                report_rows.append(rec)
                coverage["reports_found"].append({"year": year, "report": label, "fs_div": rec.get("fs_div"), "rcept_no": rec.get("rcept_no")})
            else:
                coverage["missing_reports"].append({"year": year, "report": label, "reason": "No filing/data returned"})
            time.sleep(0.12)
    if not report_rows:
        raise SystemExit("No financial data was returned. Check DART_API_KEY and the OpenDART service status.")
    period_rows = derive_metrics(build_period_rows(report_rows))
    period_rows.sort(key=lambda r: (int(r["year"]), {"annual": 0, "half_year": 1, "quarterly": 2}.get(r["period"], 9), str(r.get("quarter", ""))))
    out_dir = ROOT / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    columns = list(dict.fromkeys(k for row in period_rows for k in row.keys()))
    with (out_dir / "financials.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(period_rows)
    coverage["period_rows"] = len(period_rows)
    coverage["available_years"] = sorted({int(r["year"]) for r in report_rows})
    (out_dir / "coverage.json").write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(period_rows)} normalized rows from {len(report_rows)} filings; corp_code={corp}.")
    print(f"Reports found: {len(coverage['reports_found'])}; missing report slots: {len(coverage['missing_reports'])}.")

if __name__ == "__main__":
    main()
