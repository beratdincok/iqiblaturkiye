from __future__ import annotations
import re, csv, unicodedata
from pathlib import Path
from typing import Optional
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title='IQIBLA Türkiye Panel', layout='wide')
BASE=Path(__file__).resolve().parent
MANUAL=BASE/'manual_entries.csv'

st.markdown('''<style>.stApp{background:linear-gradient(135deg,#050505,#151515)}.block-container{max-width:1450px;padding-top:2rem}[data-testid="stMetric"]{background:rgba(255,255,255,.06);border:1px solid rgba(212,175,55,.25);border-radius:16px;padding:14px}</style>''', unsafe_allow_html=True)

def norm(x):
    if x is None or pd.isna(x): return ''
    s=str(x).lower().strip().translate(str.maketrans({'ı':'i','İ':'i','ş':'s','Ş':'s','ğ':'g','Ğ':'g','ç':'c','Ç':'c','ö':'o','Ö':'o','ü':'u','Ü':'u'}))
    s=unicodedata.normalize('NFKD',s); s=''.join(c for c in s if not unicodedata.combining(c)); s=re.sub(r'[^a-z0-9]+',' ',s)
    return re.sub(r'\s+',' ',s).strip()

def fnum(x):
    if x is None or pd.isna(x) or x=='': return 0.0
    if isinstance(x,(int,float)): return float(x)
    s=str(x).strip().replace('TL','').replace('TRY','').replace('₺','').replace('%','').replace('"','').replace('\xa0','').replace(' ','')
    if s.lower() in {'-','nan','none','null','n/a'}: return 0.0
    if ',' in s and '.' in s:
        s=s.replace('.','').replace(',','.') if s.rfind(',')>s.rfind('.') else s.replace(',','')
    elif ',' in s: s=s.replace('.','').replace(',','.')
    elif '.' in s:
        parts=s.split('.')
        if len(parts)>1 and all(p.isdigit() for p in parts) and all(len(p)==3 for p in parts[1:]): s=''.join(parts)
    try: return float(s)
    except: 
        try: return float(re.sub(r'[^0-9.\-]','',s))
        except: return 0.0

def money(v): return f'{float(v):,.2f} TL'
def div(a,b): return float(a)/float(b) if b else 0.0
def sku(x):
    if x is None or pd.isna(x): return ''
    s=str(x).strip().replace(' ','').replace("'",'')
    if s.startswith('6-'): s=s[2:]
    s=s.replace('-','')
    if re.fullmatch(r'\d+\.0',s): s=s[:-2]
    try:
        if 'e+' in s.lower(): s=str(int(float(s)))
    except: pass
    return s

def findcol(df,cands):
    mp={norm(c):c for c in df.columns}
    for c in cands:
        t=norm(c)
        for n,r in mp.items():
            if t==n: return r
    for c in cands:
        t=norm(c)
        for n,r in mp.items():
            if t and t in n: return r
    return None

def read_csv(path, skiprows=0):
    for enc in ['utf-8-sig','utf-8','cp1254','iso-8859-9','latin1']:
        for sep in [',',';','\t']:
            try:
                df=pd.read_csv(path,encoding=enc,sep=sep,dtype=str,low_memory=False,skiprows=skiprows)
                if df.shape[1]>1: return df,enc,sep
            except: pass
    return pd.DataFrame(),'',''

def read_table(path, skiprows=0):
    if path.suffix.lower() in ['.xlsx','.xls']:
        for sr in [skiprows,0,1,2,3,4,5]:
            try:
                df=pd.read_excel(path,dtype=str,skiprows=sr)
                if df.shape[1]>1: return df,'excel',f'skip={sr}'
            except: pass
        return pd.DataFrame(),'',''
    return read_csv(path,skiprows)

def read_shopify(path):
    df,e,s=read_csv(path)
    if not df.empty and {'Name','Created at','Lineitem name'}.issubset(set(df.columns)): return df,e,s
    return pd.DataFrame(),'',''

def files(): return [p for p in BASE.iterdir() if p.suffix.lower() in ['.csv','.xlsx','.xls'] and p.name!='manual_entries.csv']
def pfiles(platform):
    out=[]
    for p in files():
        n=norm(p.name)
        if platform=='Shopify' and any(x in n for x in ['shopify','orders export','fatura ozeti','zamana gore oturumlar']): out.append(p)
        if platform=='Trendyol' and any(x in n for x in ['trendyol','urun reklamlari raporum','magaza raporu','22 05']): out.append(p)
        if platform=='Hepsiburada' and 'hepsiburada' in n: out.append(p)
        if platform=='Kreatif' and any(x in n for x in ['adsiz rapor','kreatif','creative']): out.append(p)
    return out

def ensure_manual():
    if not MANUAL.exists(): MANUAL.write_text('date,platform,store_name,product_name,units_sold,order_count,total_revenue,ad_spend,notes\n',encoding='utf-8-sig')
def load_manual(platform=None):
    ensure_manual(); df=pd.read_csv(MANUAL,dtype=str)
    for c in ['units_sold','order_count','total_revenue','ad_spend']:
        if c not in df: df[c]=0.0
        df[c]=df[c].apply(fnum)
    return df[df['platform'].astype(str).str.lower()==platform.lower()].copy() if platform else df

def manual_form(platform):
    with st.expander('✍️ Manuel günlük giriş', expanded=False):
        with st.form('manual_'+platform):
            c1,c2,c3=st.columns(3)
            with c1:
                date=st.date_input('Tarih'); store=st.text_input('Mağaza/Kanal',value=platform); product=st.text_input('Ürün adı')
            with c2:
                units=st.number_input('Satılan ürün adedi',min_value=0,value=0); orders=st.number_input('Sipariş adedi',min_value=0,value=0); rev=st.number_input('Net ciro / Total Revenue',min_value=0.0,value=0.0,step=100.0)
            with c3:
                ad=st.number_input('Reklam harcaması',min_value=0.0,value=0.0,step=100.0); notes=st.text_area('Not')
            if st.form_submit_button('Ekle'):
                df=load_manual(); df=pd.concat([df,pd.DataFrame([{'date':str(date),'platform':platform,'store_name':store,'product_name':product,'units_sold':units,'order_count':orders,'total_revenue':rev,'ad_spend':ad,'notes':notes}])],ignore_index=True); df.to_csv(MANUAL,index=False,encoding='utf-8-sig'); st.success('Eklendi'); st.rerun()

def cost_table(platform):
    frames=[]
    for p in pfiles(platform):
        if 'maliyet' not in norm(p.name) and 'cost' not in norm(p.name): continue
        df,_,_=read_table(p)
        if df.empty: continue
        sc=findcol(df,['SKU','Barkod','Barcode','Stok Kodu']); co=findcol(df,['Maliyet','Maliyet Alış','Cost']); cm=findcol(df,['Komisyon','Commission']); sh=findcol(df,['Kargo','Shipping'])
        if not sc: continue
        frames.append(pd.DataFrame({'sku_key':df[sc].apply(sku),'unit_cost':df[co].apply(fnum) if co else 0.0,'commission_rate':df[cm].apply(fnum) if cm else 0.0,'unit_shipping':df[sh].apply(fnum) if sh else 0.0}))
    if not frames: return pd.DataFrame(columns=['sku_key','unit_cost','commission_rate','unit_shipping'])
    res=pd.concat(frames,ignore_index=True); res['commission_rate']=res['commission_rate'].apply(lambda x:x/100 if x>1 else x); return res[res.sku_key!=''].drop_duplicates('sku_key',keep='last')

def meta_billing(path):
    try:
        lines=path.read_text(encoding='utf-8-sig',errors='replace').splitlines(); idx=None
        for i,l in enumerate(lines):
            n=norm(l)
            if 'tarih' in n and 'tutar' in n and ('para birimi' in n or 'odeme' in n or 'islem' in n): idx=i; break
        if idx is not None:
            sec=[]
            for l in lines[idx:]:
                if not l.strip() and len(sec)>1: break
                if l.strip(): sec.append(l)
            rows=list(csv.reader(sec))
            if len(rows)>=2: return pd.DataFrame(rows[1:],columns=rows[0])
    except: pass
    df,_,_=read_csv(path); return df

def shopify_data():
    orders_raw=[]; spend=[]; debug=[]; costs=cost_table('Shopify')
    for p in pfiles('Shopify'):
        n=norm(p.name)
        if 'maliyet' in n or 'oturum' in n: continue
        if 'fatura' in n or 'billing' in n:
            df=meta_billing(p); amount=findcol(df,['Tutar','Amount','Total','Harcama','Spend'])
            if amount:
                tmp=pd.DataFrame({'ad_spend':df[amount].apply(fnum),'source_file':p.name}); tmp=tmp[tmp.ad_spend>0]; spend.append(tmp); debug.append({'file':p.name,'type':'meta_spend','status':'OK','rows':len(tmp)})
            continue
        df,e,s=read_shopify(p)
        if not df.empty: df['source_file']=p.name; orders_raw.append(df); debug.append({'file':p.name,'type':'orders','status':'OK','rows':len(df)})
    raw=pd.concat(orders_raw,ignore_index=True) if orders_raw else pd.DataFrame()
    ads=pd.concat(spend,ignore_index=True) if spend else pd.DataFrame(columns=['ad_spend','source_file'])
    if raw.empty: return pd.DataFrame(),pd.DataFrame(),costs,ads,pd.DataFrame(debug)
    for c in ['Total','Refunded Amount','Lineitem quantity','Lineitem price','Lineitem discount']:
        if c not in raw: raw[c]=0.0
        raw[c]=raw[c].apply(fnum)
    for c in ['Cancelled at','Financial Status','Lineitem sku','Lineitem name','Created at']:
        if c not in raw: raw[c]=''
    raw['order_name']=raw['Name'].astype(str); raw['order_date']=pd.to_datetime(raw['Created at'],errors='coerce',utc=True).dt.tz_localize(None); raw['financial_status']=raw['Financial Status'].astype(str).str.lower(); raw['cancelled_at']=pd.to_datetime(raw['Cancelled at'],errors='coerce',utc=True).dt.tz_localize(None)
    raw=raw.drop_duplicates(subset=[c for c in ['Name','Created at','Lineitem sku','Lineitem name','Lineitem quantity','Lineitem price','Total'] if c in raw],keep='first')
    orders=raw.groupby('order_name',as_index=False).agg(order_date=('order_date','first'),total=('Total','first'),refunded=('Refunded Amount','first'),cancelled_at=('cancelled_at','first'),financial_status=('financial_status','first'),source_file=('source_file','first'))
    orders['is_cancelled']=orders.cancelled_at.notna()|orders.financial_status.isin(['voided','cancelled','canceled']); orders['net_sales']=orders.total-orders.refunded; orders.loc[orders.is_cancelled,'net_sales']=0.0; orders['order_count']=(~orders.is_cancelled).astype(int)
    lines=raw.copy(); lines['sku_key']=lines['Lineitem sku'].apply(sku); lines['product_name']=lines['Lineitem name'].astype(str); lines['qty']=lines['Lineitem quantity']; lines['line_revenue']=lines['Lineitem price']*lines['qty']-lines['Lineitem discount']; lines=lines[['order_name','order_date','sku_key','product_name','qty','line_revenue','source_file']]
    return orders,lines,costs,ads,pd.DataFrame(debug)

def marketplace_data(platform):
    rows=[]; ads=[]; debug=[]; costs=cost_table(platform)
    for p in pfiles(platform):
        n=norm(p.name)
        if 'maliyet' in n: continue
        df,e,s=read_table(p)
        if df.empty: continue
        if any(x in n for x in ['reklam','ads','campaign']):
            sp=findcol(df,['Harcanan Tutar','Amount spent','Spend','Harcama','Tutar']); rv=findcol(df,['Reklam Geliri','Total Ad Revenue','Revenue','Dönüşüm değeri','Satış Tutarı']); pu=findcol(df,['Alışverişler','Purchases','Sipariş','Orders'])
            if sp: ads.append(pd.DataFrame({'ad_spend':df[sp].apply(fnum),'ad_revenue':df[rv].apply(fnum) if rv else 0.0,'ad_purchases':df[pu].apply(fnum) if pu else 0.0,'source_file':p.name})); debug.append({'file':p.name,'type':'ad','status':'OK','rows':len(df)}); continue
        date=findcol(df,['Sipariş Tarihi','Tarih','Order Date','Date']); order=findcol(df,['Sipariş Numarası','Sipariş No','Order Number','Order','Paket No']); prod=findcol(df,['Ürün Adı','Ürün Ad','Product Name','Product']); sk=findcol(df,['Barkod','Barcode','SKU','Stok Kodu']); qt=findcol(df,['Adet','Miktar','Quantity','Ürün Adedi','Satış Miktarı']); rev=findcol(df,['Faturalanacak Tutar','Net Satış Tutarı','Satış Tutarı','Ürün Tutarı','Sipariş Tutarı','Toplam Satış Tutarı','Mağazanın Brüt Cirosu','Ciro','Tutar','Amount','Revenue']); stat=findcol(df,['Sipariş Statüsü','Durum','Status'])
        if not rev: debug.append({'file':p.name,'type':'skip','status':'NO_REVENUE','rows':len(df)}); continue
        tmp=pd.DataFrame({'order_name':df[order].astype(str) if order else p.stem,'order_date':pd.to_datetime(df[date],errors='coerce',dayfirst=True) if date else pd.NaT,'product_name':df[prod].astype(str) if prod else platform+' Product','sku_key':df[sk].apply(sku) if sk else '', 'qty':df[qt].apply(fnum) if qt else 1.0,'line_revenue':df[rev].apply(fnum),'status':df[stat].astype(str) if stat else '', 'source_file':p.name})
        tmp['bad']=tmp.status.str.contains('iptal|iade|cancel|return|red|reddedildi',case=False,na=False); tmp.loc[tmp.bad,['qty','line_revenue']]=0.0; rows.append(tmp); debug.append({'file':p.name,'type':'sales','status':'OK','rows':len(tmp),'revenue_col':rev})
    lines=pd.concat(rows,ignore_index=True) if rows else pd.DataFrame(columns=['order_name','order_date','product_name','sku_key','qty','line_revenue','source_file'])
    adf=pd.concat(ads,ignore_index=True) if ads else pd.DataFrame(columns=['ad_spend','ad_revenue','ad_purchases','source_file'])
    orders=lines.groupby('order_name',as_index=False).agg(order_date=('order_date','first'),net_sales=('line_revenue','sum'),qty=('qty','sum'),source_file=('source_file','first')) if not lines.empty else pd.DataFrame(columns=['order_name','order_date','net_sales','qty','source_file'])
    if not orders.empty: orders['order_count']=orders.net_sales.gt(0).astype(int)
    return orders,lines,costs,adf,pd.DataFrame(debug)

def add_cost(lines,costs):
    if lines.empty: lines['gross_profit']=[]; lines['matched_cost']=[]; return lines
    lines=lines.merge(costs,on='sku_key',how='left')
    for c in ['unit_cost','unit_shipping','commission_rate']: lines[c]=lines[c].fillna(0.0)
    lines['matched_cost']=lines.unit_cost.gt(0); lines['gross_profit']=lines.line_revenue-((lines.unit_cost+lines.unit_shipping)*lines.qty)-(lines.line_revenue*lines.commission_rate); return lines

def metrics(platform):
    manual=load_manual(platform)
    if platform=='Shopify': orders,lines,costs,ads,debug=shopify_data(); ad_rev=0.0; ad_pur=0.0
    else: orders,lines,costs,ads,debug=marketplace_data(platform); ad_rev=ads.ad_revenue.sum() if 'ad_revenue' in ads else 0.0; ad_pur=ads.ad_purchases.sum() if 'ad_purchases' in ads else 0.0
    lines=add_cost(lines,costs)
    rev=(orders.net_sales.sum() if not orders.empty else 0.0)+(manual.total_revenue.sum() if not manual.empty else 0.0); oc=(orders.order_count.sum() if not orders.empty and 'order_count' in orders else 0.0)+(manual.order_count.sum() if not manual.empty else 0.0); units=(lines.qty.sum() if not lines.empty else 0.0)+(manual.units_sold.sum() if not manual.empty else 0.0); gp=(lines.gross_profit.sum() if not lines.empty else 0.0)+(manual.total_revenue.sum() if not manual.empty else 0.0); ad=(ads.ad_spend.sum() if not ads.empty and 'ad_spend' in ads else 0.0)+(manual.ad_spend.sum() if not manual.empty else 0.0)
    m={'total_revenue':rev,'order_count':oc,'units_sold':units,'aov':div(rev,oc),'gross_profit_before_ads':gp,'total_ad_spend':ad,'total_ad_revenue':ad_rev,'ad_purchases':ad_pur,'roas':div(ad_rev,ad),'net_profit_after_ads':gp-ad,'mer':div(rev,ad),'cost_match_rate':float(lines.matched_cost.mean()) if not lines.empty else 0.0}
    return m,orders,lines,ads,manual,debug

def cards(m,show_ad_rev=True):
    fields=[('Total Revenue','total_revenue','m'),('Order Count','order_count','i'),('Units Sold','units_sold','i'),('AOV','aov','m'),('Gross Profit Before Ads','gross_profit_before_ads','m'),('Total Ad Spend','total_ad_spend','m')]
    if show_ad_rev: fields.append(('Total Ad Revenue','total_ad_revenue','m'))
    fields += [('ROAS','roas','r'),('Net Profit After Ads','net_profit_after_ads','m'),('MER','mer','r'),('Cost Match Rate','cost_match_rate','p')]
    for i in range(0,len(fields),4):
        cols=st.columns(4)
        for col,(lab,key,t) in zip(cols,fields[i:i+4]):
            v=m.get(key,0)
            col.metric(lab, money(v) if t=='m' else (f'{v:,.0f}' if t=='i' else (f'{v:.2f}' if t=='r' and v else ('N/A' if t=='r' else f'{v:.1%}'))))

def show_platform(platform):
    st.header(platform); manual_form(platform); m,orders,lines,ads,manual,debug=metrics(platform); cards(m,show_ad_rev=(platform!='Shopify'))
    if platform=='Shopify': st.info('Shopify Ad Revenue kullanılmaz. Shopify sadece Total Ad Spend tarafında dahil edilir.')
    t1,t2,t3,t4,t5=st.tabs(['Satış','Ürün & Kâr','Reklam','Manuel','Debug'])
    with t1: st.dataframe(orders,use_container_width=True,hide_index=True)
    with t2: st.dataframe(lines,use_container_width=True,hide_index=True)
    with t3: st.dataframe(ads,use_container_width=True,hide_index=True)
    with t4: st.dataframe(manual,use_container_width=True,hide_index=True)
    with t5: st.dataframe(debug,use_container_width=True,hide_index=True); st.dataframe(pd.DataFrame([m]),use_container_width=True,hide_index=True)

def show_ai():
    st.header('Yapay Zeka / Toplam Rapor')
    sh,*_=metrics('Shopify'); tr,*_=metrics('Trendyol'); hb,*_=metrics('Hepsiburada')
    total_rev=sh['total_revenue']+tr['total_revenue']+hb['total_revenue']; ad=sh['total_ad_spend']+tr['total_ad_spend']+hb['total_ad_spend']; adrev=tr['total_ad_revenue']+hb['total_ad_revenue']; gp=sh['gross_profit_before_ads']+tr['gross_profit_before_ads']+hb['gross_profit_before_ads']; oc=sh['order_count']+tr['order_count']+hb['order_count']; units=sh['units_sold']+tr['units_sold']+hb['units_sold']
    m={'total_revenue':total_rev,'order_count':oc,'units_sold':units,'aov':div(total_rev,oc),'gross_profit_before_ads':gp,'total_ad_spend':ad,'total_ad_revenue':adrev,'roas':div(adrev,ad),'net_profit_after_ads':gp-ad,'mer':div(total_rev,ad),'cost_match_rate':0}
    cards(m)
    summary=pd.DataFrame([{'platform':'Shopify',**sh,'rule':'Shopify Ad Revenue kullanılmaz'},{'platform':'Trendyol',**tr},{'platform':'Hepsiburada',**hb}])
    st.dataframe(summary,use_container_width=True,hide_index=True)
    if st.button('Yorumu üret'):
        st.markdown(f'**Toplam ciro:** {money(total_rev)}  \n**Toplam reklam harcaması:** {money(ad)}  \n**Net kâr:** {money(gp-ad)}  \n**MER:** {div(total_rev,ad):.2f}  \n**ROAS:** {div(adrev,ad):.2f}  \n\nShopify Ad Revenue toplam dışı bırakıldı.')

st.title('IQIBLA Türkiye — Tek Dosya E-Ticaret Paneli')
st.caption('Klasör gerekmez. Bütün dosyaları GitHub ana dizinine yükle. Main file path: ana_sayfa.py')
page=st.sidebar.radio('Sayfa',['Ana Sayfa','Shopify','Trendyol','Hepsiburada','Yapay Zeka'])
if page=='Ana Sayfa': st.dataframe(pd.DataFrame({'file':[p.name for p in files()]}),use_container_width=True,hide_index=True)
elif page=='Shopify': show_platform('Shopify')
elif page=='Trendyol': show_platform('Trendyol')
elif page=='Hepsiburada': show_platform('Hepsiburada')
elif page=='Yapay Zeka': show_ai()
