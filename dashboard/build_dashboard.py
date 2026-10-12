"""Build the static, responsive InBody financial dashboard for GitHub Pages."""
import json
import html
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATA_PATH = ROOT / "data" / "processed" / "financials.csv"
COVERAGE_PATH = ROOT / "data" / "processed" / "coverage.json"
DOCS.mkdir(parents=True, exist_ok=True)

MONEY = {
    "revenue", "cost_of_sales", "gross_profit", "sga", "operating_profit", "pretax_profit",
    "net_income", "controlling_net_income", "ebitda", "assets", "current_assets", "cash",
    "receivables", "inventory", "ppe", "intangible_assets", "liabilities", "current_liabilities",
    "equity", "trade_payables", "interest_bearing_debt", "net_debt", "cfo", "cfi", "cff",
    "capex", "fcf",
}
PERCENT = {
    "revenue_growth", "gross_margin", "operating_margin", "net_margin", "ebitda_margin",
    "roa", "roe", "roic", "equity_ratio", "debt_to_assets", "borrowing_to_assets",
    "cfo_to_net_income",
}
PERCENT_100 = {"debt_to_equity"}
MULTIPLES = {
    "current_ratio", "quick_ratio", "interest_coverage", "net_debt_to_ebitda",
    "asset_turnover", "receivables_turnover", "inventory_turnover",
}
DAYS = {"dso_days", "dio_days", "dpo_days", "ccc_days"}
LABELS = {
    "year": "Year", "period": "Category", "quarter": "Quarter", "fs_div": "FS",
    "revenue": "Revenue", "cost_of_sales": "Cost of sales", "gross_profit": "Gross profit",
    "gross_margin": "Gross margin", "sga": "SG&A", "operating_profit": "Operating profit",
    "operating_margin": "Operating margin", "pretax_profit": "Pre-tax profit",
    "net_income": "Net income", "net_margin": "Net margin", "ebitda": "EBITDA",
    "ebitda_margin": "EBITDA margin", "assets": "Total assets", "cash": "Cash",
    "receivables": "Receivables", "inventory": "Inventory", "ppe": "PP&E",
    "intangible_assets": "Intangibles", "current_assets": "Current assets",
    "current_liabilities": "Current liabilities", "liabilities": "Total liabilities",
    "equity": "Equity", "trade_payables": "Trade payables", "interest_bearing_debt": "Interest-bearing debt",
    "net_debt": "Net debt", "cfo": "Operating cash flow", "cfi": "Investing cash flow",
    "cff": "Financing cash flow", "capex": "CAPEX", "fcf": "Free cash flow",
    "revenue_growth": "Revenue growth", "roa": "ROA", "roe": "ROE", "roic": "ROIC",
    "current_ratio": "Current ratio", "quick_ratio": "Quick ratio", "debt_to_equity": "Liabilities / equity",
    "equity_ratio": "Equity ratio", "debt_to_assets": "Liabilities / assets",
    "borrowing_to_assets": "Borrowings / assets", "interest_coverage": "Interest coverage",
    "net_debt_to_ebitda": "Net debt / EBITDA", "asset_turnover": "Asset turnover",
    "receivables_turnover": "Receivables turnover", "dso_days": "DSO (days)",
    "inventory_turnover": "Inventory turnover", "dio_days": "DIO (days)",
    "dpo_days": "DPO (days)", "ccc_days": "Cash conversion cycle (days)",
    "cfo_to_net_income": "CFO / net income",
}
TABLE_COLUMNS = [
    "year", "period", "quarter", "fs_div",
    "revenue", "cost_of_sales", "gross_profit", "gross_margin", "sga",
    "operating_profit", "operating_margin", "ebitda", "ebitda_margin", "net_income", "net_margin",
    "assets", "cash", "receivables", "inventory", "ppe", "current_assets", "current_liabilities",
    "liabilities", "equity", "interest_bearing_debt", "net_debt",
    "cfo", "cfi", "cff", "capex", "fcf",
    "revenue_growth", "roa", "roe", "roic", "current_ratio", "quick_ratio",
    "debt_to_equity", "equity_ratio", "debt_to_assets", "borrowing_to_assets",
    "interest_coverage", "net_debt_to_ebitda", "asset_turnover", "receivables_turnover",
    "dso_days", "inventory_turnover", "dio_days", "dpo_days", "ccc_days", "cfo_to_net_income",
]
PEERS = [
    ("셀바스헬스케어", "208370", "가장 가까운 국내 비교군", "체성분 분석기와 병원용 의료기기를 보유. 사업·규모 차이는 별도 확인 필요"),
    ("아이센스", "099190", "인접 의료기기", "혈당 측정 및 진단기기 중심. 체성분 분석기 직접 경쟁사는 아님"),
    ("비트컴퓨터", "032850", "인접 디지털 헬스케어", "의료정보·디지털 헬스케어 중심. 하드웨어 제품 구성이 다름"),
]

def is_missing(value):
    try:
        return value is None or pd.isna(value)
    except (TypeError, ValueError):
        return value is None

def fmt(value, key):
    if is_missing(value):
        return "—"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return html.escape(str(value))
    if key in MONEY:
        return f"{num / 100_000_000:,.1f}"
    if key in PERCENT or key in PERCENT_100:
        return f"{num * 100:,.1f}%"
    if key in MULTIPLES:
        return f"{num:,.2f}×"
    if key in DAYS:
        return f"{num:,.1f}"
    if key == "year":
        return str(int(num))
    if key == "quarter":
        return html.escape(str(value))
    return f"{num:,.2f}"

def period_label(row):
    year = int(row.get("year", 0))
    category = row.get("period", "")
    quarter = row.get("quarter", "")
    if category == "annual":
        return f"FY {year}"
    if category == "half_year":
        return f"H1 {year}"
    if category == "quarterly":
        return f"{quarter} {year}"
    return f"{year}"

def chart_html(df, name, traces, money_axis=False, percent_axis=False, include_js=False):
    fig = go.Figure()
    x = df["year"].astype(int).tolist() if not df.empty and "year" in df else []
    plotted = False
    for key, label in traces:
        if not df.empty and key in df.columns:
            values = pd.to_numeric(df[key], errors="coerce")
            if values.notna().any():
                if key in MONEY:
                    values = values / 100_000_000
                fig.add_trace(go.Scatter(
                    x=x, y=values.tolist(), mode="lines+markers", name=label,
                    connectgaps=False, hovertemplate="%{x}<br>" + label + ": %{y:,.2f}<extra></extra>",
                ))
                plotted = True
    if not plotted:
        fig.add_annotation(text="Waiting for the first successful DART data refresh",
                           x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False,
                           font={"size": 14, "color": "#64748b"})
    fig.update_layout(
        title={"text": name, "x": 0.02, "xanchor": "left"},
        template="plotly_white", height=350, margin={"l": 24, "r": 20, "t": 58, "b": 38},
        legend={"orientation": "h", "y": -0.25}, hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, system-ui, sans-serif", "color": "#172b4d"},
    )
    if money_axis:
        fig.update_yaxes(title="KRW 100 million")
    if percent_axis:
        fig.update_yaxes(tickformat=".0%")
    return fig.to_html(full_html=False, include_plotlyjs="cdn" if include_js else False, config={"responsive": True, "displaylogo": False})

def table_html(frame):
    if frame.empty:
        return '<div class="empty">No rows are available for this category yet. Run the “Monthly DART Update” workflow.</div>'
    frame = frame.copy()
    frame = frame.sort_values(["year", "quarter"] if "quarter" in frame.columns else ["year"], ascending=False, kind="stable")
    headers = []
    for key in TABLE_COLUMNS:
        if key in frame.columns:
            label = LABELS.get(key, key)
            if key in MONEY:
                label += " (₩100m)"
            headers.append(f"<th>{html.escape(label)}</th>")
    body_rows = []
    for _, row in frame.iterrows():
        cells = []
        report_ref = row.get("rcept_no", "")
        for key in TABLE_COLUMNS:
            if key not in frame.columns:
                continue
            value = row.get(key)
            if key == "period":
                label = html.escape(period_label(row))
                if not is_missing(report_ref) and str(report_ref).strip():
                    link = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + html.escape(str(report_ref), quote=True)
                    value_html = f'<a class="period-link" href="{link}" target="_blank" rel="noopener">{label}</a>'
                else:
                    value_html = label
                cells.append(f"<td class='period'>{value_html}</td>")
            elif key == "quarter":
                cells.append(f"<td>{html.escape(str(value)) if not is_missing(value) else ''}</td>")
            elif key == "fs_div":
                cells.append(f"<td><span class='basis'>{html.escape(str(value)) if not is_missing(value) else '—'}</span></td>")
            else:
                cells.append(f"<td>{fmt(value, key)}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    return "<div class='table-scroll'><table class='financial-table'><thead><tr>" + "".join(headers) + "</tr></thead><tbody>" + "".join(body_rows) + "</tbody></table></div>"

def kpi(value, label, key, subtext):
    return (
        "<article class='kpi'><div class='kpi-label'>" + html.escape(label) + "</div>"
        "<div class='kpi-value'>" + html.escape(fmt(value, key) if not is_missing(value) else "—") + "</div>"
        "<div class='kpi-note'>" + html.escape(subtext) + "</div></article>"
    )

def main():
    if DATA_PATH.exists():
        try:
            df = pd.read_csv(DATA_PATH)
        except pd.errors.EmptyDataError:
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()
    coverage = {}
    if COVERAGE_PATH.exists():
        try:
            coverage = json.loads(COVERAGE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            coverage = {}

    if not df.empty:
        for key in ("year", "period_days"):
            if key in df:
                df[key] = pd.to_numeric(df[key], errors="coerce")
        annual = df[df["period"] == "annual"].copy().sort_values("year")
        half = df[df["period"] == "half_year"].copy()
        quarter = df[df["period"] == "quarterly"].copy()
        latest = annual.iloc[-1] if not annual.empty else df.sort_values("year").iloc[-1]
        latest_period = period_label(latest)
        last_update = coverage.get("run_date", "Unknown")
    else:
        annual = half = quarter = pd.DataFrame()
        latest = {}
        latest_period = "No filing loaded"
        last_update = coverage.get("run_date", "Pending first run")

    metrics_html = "".join([
        kpi(latest.get("revenue") if hasattr(latest, "get") else None, "Revenue · " + latest_period, "revenue", "KRW 100 million"),
        kpi(latest.get("operating_margin") if hasattr(latest, "get") else None, "Operating margin", "operating_margin", "Operating profit / revenue"),
        kpi(latest.get("net_income") if hasattr(latest, "get") else None, "Net income", "net_income", "KRW 100 million"),
        kpi(latest.get("cfo") if hasattr(latest, "get") else None, "Operating cash flow", "cfo", "KRW 100 million"),
    ])
    revenue_chart = chart_html(
        annual, "Annual revenue and profit", [
            ("revenue", "Revenue"), ("operating_profit", "Operating profit"), ("net_income", "Net income")
        ], money_axis=True, include_js=True,
    )
    margins_chart = chart_html(
        annual, "Profitability and returns", [
            ("gross_margin", "Gross margin"), ("operating_margin", "Operating margin"),
            ("net_margin", "Net margin"), ("roa", "ROA"), ("roe", "ROE")
        ], percent_axis=True,
    )
    cash_chart = chart_html(
        annual, "Cash flow, CAPEX and free cash flow", [
            ("cfo", "Operating cash flow"), ("cfi", "Investing cash flow"),
            ("cff", "Financing cash flow"), ("fcf", "Free cash flow")
        ], money_axis=True,
    )
    peer_rows = "".join(
        "<tr><td><strong>" + html.escape(name) + "</strong></td><td>" + html.escape(code) +
        "</td><td>" + html.escape(basis) + "</td><td>" + html.escape(note) + "</td></tr>"
        for name, code, basis, note in PEERS
    )
    available_years = coverage.get("available_years", [])
    years_text = (str(min(available_years)) + "–" + str(max(available_years))) if available_years else "Waiting for first successful refresh"
    years_count = len(available_years)
    no_data_banner = ""
    if df.empty:
        no_data_banner = (
            "<div class='alert'><strong>Initial data refresh required.</strong> "
            "The repository has no validated financial-data CSV yet. After DART_API_KEY is available, "
            "run <em>Monthly DART Update</em> under Actions. The dashboard deliberately shows no invented values.</div>"
        )
    css = """
    :root{color-scheme:light;--navy:#0b1f43;--blue:#145ee8;--ink:#172b4d;--muted:#66758f;--line:#e4eaf3;--surface:#fff;--bg:#f3f6fb}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    a{color:#145ee8;text-decoration:none}a:hover{text-decoration:underline}
    .hero{background:radial-gradient(circle at 88% 5%,#315fbb 0,transparent 32%),linear-gradient(120deg,#071a3c,#123c82);color:#fff;padding:38px max(24px,calc((100vw - 1500px)/2))}
    .topline{display:flex;align-items:center;gap:12px;flex-wrap:wrap;font-size:12px;color:#d8e5ff;letter-spacing:.1em;text-transform:uppercase;font-weight:700}
    .dot{width:7px;height:7px;background:#51ddb2;border-radius:50%;display:inline-block}
    h1{font-size:clamp(30px,4vw,46px);letter-spacing:-.04em;line-height:1.1;margin:18px 0 10px}
    .hero p{margin:0;color:#d8e5ff;font-size:15px;max-width:850px;line-height:1.7}
    .hero-meta{margin-top:23px;display:flex;gap:8px;flex-wrap:wrap}
    .pill{border:1px solid #ffffff3b;border-radius:999px;padding:7px 11px;font-size:12px;color:#eaf1ff}
    .wrap{max-width:1540px;margin:0 auto;padding:26px 24px 52px}
    .section-heading{display:flex;align-items:end;justify-content:space-between;gap:16px;margin:30px 0 15px}
    h2{font-size:20px;letter-spacing:-.02em;margin:0;color:var(--navy)}
    .section-heading p{font-size:12px;color:var(--muted);margin:5px 0 0}
    .kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
    .kpi,.panel{background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:0 5px 18px #172b4d08}
    .kpi{padding:20px 21px;min-height:122px}.kpi-label{font-size:12px;color:var(--muted);font-weight:700}
    .kpi-value{font-size:27px;font-weight:750;letter-spacing:-.035em;margin-top:13px;color:var(--navy);font-variant-numeric:tabular-nums}
    .kpi-note{font-size:11px;color:#8290a6;margin-top:4px}
    .charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
    .panel{padding:14px;min-width:0}.panel.wide{grid-column:1/-1}
    .alert{background:#fff7e6;border:1px solid #f2d59b;color:#7a5013;border-radius:12px;padding:14px 16px;margin:16px 0;line-height:1.6;font-size:13px}
    .table-panel{padding:0;overflow:hidden}.table-title{padding:18px 20px 12px}
    .table-title p{margin:6px 0 0;font-size:12px;color:var(--muted);line-height:1.6}
    .table-scroll{overflow:auto;max-width:100%;border-top:1px solid var(--line)}
    .financial-table{border-collapse:separate;border-spacing:0;width:max-content;min-width:100%;font-size:12px;font-variant-numeric:tabular-nums}
    .financial-table th{position:sticky;top:0;background:#edf2fa;color:#263c5f;font-weight:750;text-align:right;white-space:nowrap}
    .financial-table td,.financial-table th{padding:11px 12px;border-bottom:1px solid #edf1f7;text-align:right;white-space:nowrap}
    .financial-table tbody tr:nth-child(even){background:#fafcff}.financial-table tbody tr:hover{background:#f0f6ff}
    .financial-table th:first-child,.financial-table td:first-child{text-align:left;position:sticky;left:0;background:#f8faff;z-index:1}
    .financial-table td.period{font-weight:750}.basis{font-size:10px;font-weight:700;background:#edf2fa;color:#455875;border-radius:5px;padding:3px 5px}
    .empty{padding:24px 20px;color:var(--muted);font-size:13px}
    .note{font-size:12px;line-height:1.7;color:var(--muted);margin:13px 2px}
    .peer-table{width:100%;border-collapse:collapse;font-size:13px}.peer-table th,.peer-table td{text-align:left;padding:12px;border-bottom:1px solid var(--line);vertical-align:top}
    .peer-table th{background:#edf2fa;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#415574}
    footer{border-top:1px solid var(--line);margin-top:40px;padding-top:20px;font-size:11px;color:#8390a4;line-height:1.7}
    @media(max-width:900px){.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.charts{grid-template-columns:1fr}.panel.wide{grid-column:auto}}
    @media(max-width:520px){.wrap{padding:18px 12px 36px}.hero{padding:28px 18px}.kpi{padding:15px}.kpi-value{font-size:22px}.kpis{gap:9px}.section-heading{align-items:start;flex-direction:column}}
    """
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="InBody financial statements and financial-ratio dashboard sourced from OpenDART.">
<title>InBody | Financial Intelligence Dashboard</title><style>{css}</style></head>
<body>
<header class="hero"><div class="topline"><span class="dot"></span> OpenDART · Financial intelligence</div>
<h1>InBody Financial Dashboard</h1><p>A statement-led view of growth, operating profitability, cash generation and balance-sheet resilience, based on periodic public filings.</p>
<div class="hero-meta"><span class="pill">Ticker · 041830</span><span class="pill">Coverage · {html.escape(years_text)}</span><span class="pill">Available years · {years_count}</span><span class="pill">Latest refresh · {html.escape(str(last_update))}</span></div></header>
<main class="wrap">
{no_data_banner}
<div class="section-heading"><div><h2>At a glance</h2><p>Latest annual filing where available; interim periods are shown separately below.</p></div></div>
<div class="kpis">{metrics_html}</div>
<div class="section-heading"><div><h2>Performance figures</h2><p>Annual trend charts use original DART reported amounts, scaled to KRW 100 million.</p></div></div>
<div class="charts"><section class="panel">{revenue_chart}</section><section class="panel">{margins_chart}</section><section class="panel wide">{cash_chart}</section></div>
<div class="section-heading"><div><h2>Financial statements & ratios</h2><p>Amounts are shown in KRW 100 million in tables. Scroll horizontally to view all fields.</p></div></div>
<section class="panel table-panel"><div class="table-title"><h2>Annual</h2><p>Full-year income and cash-flow items with year-end balance-sheet values.</p></div>{table_html(annual)}</section>
<section class="panel table-panel" style="margin-top:16px"><div class="table-title"><h2>Half-year</h2><p>First-half year-to-date income and cash flow; balance sheet as of the half-year reporting date. ROA/ROE are not annualized.</p></div>{table_html(half)}</section>
<section class="panel table-panel" style="margin-top:16px"><div class="table-title"><h2>Quarterly</h2><p>Q1–Q4 standalone income and cash-flow amounts derived from cumulative filings; balance-sheet values are the reported quarter-end snapshots. ROA/ROE are quarter-period, not annualized.</p></div>{table_html(quarter)}</section>
<p class="note"><strong>Methodology and coverage.</strong> CFS (consolidated) is preferred; OFS (separate) is used when the consolidated statement is unavailable. Always compare the “FS” field before interpreting trends. OpenDART documents the standardized full-statement endpoint from 2015 onward, so 2010–2014 are flagged as unavailable through that endpoint and are not filled with zeros. Gross profit may be derived as revenue less cost of sales if no matching reported line is found. EBITDA is shown only when operating profit and a mapped depreciation/amortization item are both available. CAPEX/FCF can be incomplete if investment-outflow accounts are not standardized in the source.</p>
<p class="note"><strong>Uncomputed indicators.</strong> DPO and the cash conversion cycle are left blank because a comparable credit-purchases denominator is not reliably available from standardized accounts. PER, PBR, EV/EBITDA and FCF yield require date-matched market prices, shares outstanding and/or enterprise value; these are not inferred from financial statements alone. Quick ratio uses (current assets − inventory) / current liabilities. Receivables turnover uses revenue as a proxy for credit sales.</p>
<div class="section-heading"><div><h2>Domestic peer firms</h2><p>Business adjacency, not a claim that each company is a direct substitute for InBody.</p></div></div>
<section class="panel table-panel"><div class="table-scroll"><table class="peer-table"><thead><tr><th>Company</th><th>Stock code</th><th>Peer category</th><th>Comparability note</th></tr></thead><tbody>{peer_rows}</tbody></table></div></section>
<footer>Source: Financial Supervisory Service OpenDART, single-company full financial statements API. This dashboard is for analytical and educational use and is not investment advice. Missing values are not estimated. <a href="https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020" target="_blank" rel="noopener">OpenDART API guide</a> · <a href="https://github.com/HSC-Class02/AK_InBody">Source repository</a></footer>
</main></body></html>"""
    (DOCS / "index.html").write_text(page, encoding="utf-8")
    print(f"Dashboard generated: {DOCS / 'index.html'} (rows={len(df)})")

if __name__ == "__main__":
    main()
