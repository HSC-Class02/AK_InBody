from pathlib import Path
import pandas as pd, json, html
import plotly.express as px
ROOT=Path(__file__).resolve().parents[1]; DOCS=ROOT/'docs'; DOCS.mkdir(exist_ok=True)
p=ROOT/'data/processed/financials.csv'
if not p.exists(): raise SystemExit('Run src/dart_agent.py first')
df=pd.read_csv(p); annual=df[df.period=='annual'].sort_values('year')
fig1=px.line(annual,x='year',y=['revenue','operating_profit','net_income'],markers=True,title='Annual Revenue & Profit Trend')
fig1.update_layout(template='plotly_white',legend_title_text='')
fig2=px.line(annual,x='year',y=['operating_margin','net_margin','roe','roa'],markers=True,title='Profitability & Capital Efficiency')
fig2.update_layout(template='plotly_white',legend_title_text='',yaxis_tickformat='.1%')
peer=pd.DataFrame([
 {'Company':'Selvas Healthcare','Ticker':'208370','Peer basis':'Body composition / medical devices; partial product overlap'},
 {'Company':'BIT Computer','Ticker':'032850','Peer basis':'Adjacent digital healthcare, not a direct body composition competitor'},
 {'Company':'i-SENS','Ticker':'099190','Peer basis':'Adjacent diagnostics / monitoring devices; glucose focus'},
])
metrics=['year','revenue','gross_profit','operating_profit','net_income','assets','cash','receivables','inventory','ppe','liabilities','equity','cfo','cfi','cff','revenue_growth','gross_margin','operating_margin','net_margin','roa','roe','current_ratio','debt_ratio','equity_ratio','cfo_to_net_income']
def table(x):
 x=x[[c for c in metrics if c in x]].copy().sort_values('year',ascending=False)
 for c in x.columns:
  if c in ['gross_margin','operating_margin','net_margin','roa','roe','revenue_growth','equity_ratio']: x[c]=x[c].map(lambda v:'' if pd.isna(v) else f'{v:.1%}')
  elif c!='year': x[c]=x[c].map(lambda v:'' if pd.isna(v) else (f'{v:,.0f}' if abs(v)>=100 else f'{v:.2f}'))
 return x.to_html(index=False,classes='data-table',border=0)
sections=[('Annual',df[df.period=='annual']),('Half-year',df[df.period=='half_year']),('Quarterly filing (Q1 YTD)',df[df.period=='q1']),('Quarterly filing (Q3 YTD)',df[df.period=='q3'])]
css="""body{font-family:Inter,system-ui,sans-serif;margin:0;background:#f4f7fb;color:#10233f}.hero{background:linear-gradient(135deg,#071d49,#0d6efd);color:white;padding:48px 7%}.wrap{max-width:1400px;margin:auto;padding:28px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.card{background:white;border-radius:18px;padding:20px;box-shadow:0 8px 28px #10233f14;margin-bottom:22px;overflow:auto}.data-table{border-collapse:collapse;width:100%;font-size:13px}.data-table th{background:#0d47a1;color:white;position:sticky;top:0}.data-table th,.data-table td{padding:10px;border-bottom:1px solid #e8eef7;text-align:right;white-space:nowrap}.data-table th:first-child,.data-table td:first-child{text-align:left}.note{color:#607089;font-size:13px}@media(max-width:900px){.grid{grid-template-columns:1fr}}"""
charts=fig1.to_html(full_html=False,include_plotlyjs='cdn')+fig2.to_html(full_html=False,include_plotlyjs=False)
body=''.join(f'<section class="card"><h2>{n}</h2>{table(x)}</section>' for n,x in sections)
peer_html=peer.to_html(index=False,classes='data-table',border=0)
page=f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>InBody Financial Dashboard</title><style>{css}</style></head><body><div class="hero"><h1>InBody Financial Intelligence Dashboard</h1><p>OpenDART periodic filings · automated monthly refresh · annual / half-year / quarterly</p></div><main class="wrap"><div class="grid"><div class="card">{fig1.to_html(full_html=False,include_plotlyjs='cdn')}</div><div class="card">{fig2.to_html(full_html=False,include_plotlyjs=False)}</div></div><p class="note">Amounts are raw KRW values returned by DART. Ratios are calculated from available standardized accounts. Missing metrics are not estimated.</p>{body}<section class="card"><h2>Domestic Peer Firms</h2>{peer_html}<p class="note">Peer group combines partial product overlap and adjacent Korean healthcare-device companies; not identical business models.</p></section></main></body></html>"""
(DOCS/'index.html').write_text(page,encoding='utf-8')
print('built',DOCS/'index.html')
