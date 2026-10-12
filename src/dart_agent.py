import os, io, zipfile, requests, xml.etree.ElementTree as ET, json, time
from pathlib import Path
from datetime import date
import pandas as pd

BASE="https://opendart.fss.or.kr/api"
ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/'config.json').read_text(encoding='utf-8'))
KEY=os.getenv('DART_API_KEY','').strip()

ALIASES={
 'revenue':['ifrs-full_Revenue','ifrs_Revenue','Revenue','매출액','영업수익'],
 'gross_profit':['ifrs-full_GrossProfit','ifrs_GrossProfit','매출총이익'],
 'operating_profit':['dart_OperatingIncomeLoss','OperatingIncomeLoss','영업이익','영업이익(손실)'],
 'pretax_profit':['ifrs-full_ProfitLossBeforeTax','ProfitLossBeforeTax','법인세비용차감전순이익'],
 'net_income':['ifrs-full_ProfitLoss','ProfitLoss','당기순이익','당기순이익(손실)'],
 'assets':['ifrs-full_Assets','Assets','자산총계'], 'current_assets':['ifrs-full_CurrentAssets','CurrentAssets','유동자산'],
 'cash':['ifrs-full_CashAndCashEquivalents','CashAndCashEquivalents','현금및현금성자산'],
 'receivables':['ifrs-full_TradeAndOtherCurrentReceivables','TradeAndOtherCurrentReceivables','매출채권'],
 'inventory':['ifrs-full_Inventories','Inventories','재고자산'], 'ppe':['ifrs-full_PropertyPlantAndEquipment','PropertyPlantAndEquipment','유형자산'],
 'liabilities':['ifrs-full_Liabilities','Liabilities','부채총계'], 'current_liabilities':['ifrs-full_CurrentLiabilities','CurrentLiabilities','유동부채'],
 'equity':['ifrs-full_Equity','Equity','자본총계'],
 'cfo':['ifrs-full_CashFlowsFromUsedInOperatingActivities','CashFlowsFromUsedInOperatingActivities','영업활동현금흐름'],
 'cfi':['ifrs-full_CashFlowsFromUsedInInvestingActivities','CashFlowsFromUsedInInvestingActivities','투자활동현금흐름'],
 'cff':['ifrs-full_CashFlowsFromUsedInFinancingActivities','CashFlowsFromUsedInFinancingActivities','재무활동현금흐름'],
}
def api(path,params):
 if not KEY: raise SystemExit('DART_API_KEY is missing. Add it to GitHub Actions Secrets or environment.')
 p={'crtfc_key':KEY,**params}; r=requests.get(f'{BASE}/{path}',params=p,timeout=40); r.raise_for_status(); j=r.json()
 if j.get('status') not in (None,'000','013'): raise RuntimeError(f"DART {j.get('status')}: {j.get('message')}")
 return j

def corp_code():
 r=requests.get(f'{BASE}/corpCode.xml',params={'crtfc_key':KEY},timeout=40); r.raise_for_status()
 z=zipfile.ZipFile(io.BytesIO(r.content)); tree=ET.fromstring(z.read(z.namelist()[0]))
 for x in tree.findall('list'):
  if (x.findtext('stock_code') or '').strip()==CFG['stock_code']: return x.findtext('corp_code')
 raise RuntimeError('InBody corp_code not found')

def num(x):
 try:return float(str(x).replace(',',''))
 except:return None

def choose(rows,aliases):
 for a in aliases:
  for r in rows:
   if r.get('account_id')==a or r.get('account_nm')==a:
    v=num(r.get('thstrm_amount')); 
    if v is not None:return v
 return None

def fetch_year(corp,year,code,label):
 j=api('fnlttSinglAcntAll.json',{'corp_code':corp,'bsns_year':year,'reprt_code':code,'fs_div':'CFS'})
 rows=j.get('list',[]) or []
 if not rows:
  j=api('fnlttSinglAcntAll.json',{'corp_code':corp,'bsns_year':year,'reprt_code':code,'fs_div':'OFS'}); rows=j.get('list',[]) or []
 if not rows:return None,[]
 out={'year':year,'period':label,'reprt_code':code,'rcept_no':rows[0].get('rcept_no',''), 'fs_div': rows[0].get('fs_div','CFS')}
 for k,a in ALIASES.items(): out[k]=choose(rows,a)
 return out,rows

def enrich(df):
 df=df.sort_values(['period','year']).copy()
 for c in ['revenue','gross_profit','operating_profit','net_income','assets','equity','liabilities','current_assets','current_liabilities','cfo']:
  if c not in df: df[c]=None
 df['gross_margin']=df.gross_profit/df.revenue
 df['operating_margin']=df.operating_profit/df.revenue
 df['net_margin']=df.net_income/df.revenue
 df['current_ratio']=df.current_assets/df.current_liabilities
 df['debt_ratio']=df.liabilities/df.equity
 df['equity_ratio']=df.equity/df.assets
 df['cfo_to_net_income']=df.cfo/df.net_income
 # Period-appropriate growth; avoids mixing annual/half/quarter rows.
 df['revenue_growth']=df.groupby('period').revenue.pct_change(fill_method=None)
 # Average-balance ratios when adjacent comparable periods exist.
 avg_assets=(df.assets+df.groupby('period').assets.shift(1))/2
 avg_equity=(df.equity+df.groupby('period').equity.shift(1))/2
 df['roa']=df.net_income/avg_assets; df['roe']=df.net_income/avg_equity
 # For interim reports, net income is year-to-date; annualize only when appropriate.
 # Keep interim ROA/ROE blank to avoid misrepresenting YTD return as a full-year return.
 df.loc[df.period!='annual',['roa','roe']]=float('nan')
 # Do not calculate year-over-year growth across CFS/OFS changes.
 changed=df.fs_div.ne(df.groupby('period').fs_div.shift(1))
 df.loc[changed,'revenue_growth']=float('nan')
 # EBITDA, interest-bearing debt, CAPEX/FCF/ROIC require robust taxonomy mapping or notes; kept blank rather than guessed.
 return df

def main():
 corp=corp_code(); today=date.today(); records=[]
 rawdir=ROOT/'data/raw'; rawdir.mkdir(parents=True,exist_ok=True)
 for y in range(CFG['start_year'],today.year+1):
  for label,code in CFG['reports'].items():
   try:
    rec,rows=fetch_year(corp,y,code,label)
    if rec:
     records.append(rec); (rawdir/f'{y}_{label}.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
   except Exception as e: print('skip',y,label,e)
   time.sleep(.08)
 if not records: raise SystemExit('No financial data returned. Note: OpenDART standardized financial-statement APIs generally cover 2015 onward; 2010-2014 need filing/XBRL fallback.')
 df=enrich(pd.DataFrame(records)); out=ROOT/'data/processed'; out.mkdir(parents=True,exist_ok=True)
 df.to_csv(out/'financials.csv',index=False,encoding='utf-8-sig')
 print('saved',len(df),'periods; corp_code',corp)
if __name__=='__main__': main()
