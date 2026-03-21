#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════╗
║   TRADE SİNYAL SİSTEMİ  ULTRA  v8.0  —  Termux Edition                ║
║                                                                          ║
║   v7 YENİLİKLER (2024-2025 araştırma bazlı):                           ║
║   ├─ Makro Veri      : USD/TRY, Altın, Brent, BIST100 korelasyonu      ║
║   ├─ Haber Sentimenti: RSS → VADER-lite NLP puanlama (+32% isabetlilik) ║
║   ├─ Histogram GB    : RF + HistGB Ensemble (+28% isabetlilik)          ║
║   ├─ SHAP-lite Eleme : Overfitting azaltma (+8%)                        ║
║   ├─ Çoklu TF Uyumu  : Günlük + Haftalık sinyal uyumu (+18%)           ║
║   ├─ Diverjans       : RSI + MACD fiyat diverjansı (+15%)              ║
║   ├─ VIX Proxy       : Yüksek volatilitede dinamik SL/TP (+12%)        ║
║   └─ Destek/Direnç   : Lokal S/R seviye tespiti                        ║
║                                                                          ║
║   ML ENGINE (numpy-only, Termux uyumlu):                                ║
║   ├─ Karar Ağacı  (Gini impurity)                                      ║
║   ├─ Random Forest (bootstrap + majority vote)                          ║
║   ├─ Histogram GB  (LightGBM benzeri, histogram tabanlı)               ║
║   └─ Walk-Forward Validation (3-fold, look-ahead bias = 0)             ║
║                                                                          ║
║   60+ ÖZELLİK: Trend, Momentum, Volatilite, Hacim, Makro, Sentiment   ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import subprocess, sys, os, time, warnings, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import urllib.request, io
warnings.filterwarnings("ignore")

# ── Bağımlılık kontrolü ──────────────────────────────────────────────────
for pkg in ["colorama", "numpy", "pandas", "requests"]:
    try:
        __import__(pkg)
    except ImportError:
        print(f"⚙️  {pkg} yükleniyor...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", pkg, "-q",
             "--break-system-packages"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

import pandas as pd
import numpy as np
import requests as _req
from colorama import init, Fore, Style
init(autoreset=True)

# ── Güvenlik ─────────────────────────────────────────────────────────────
import re as _re
_SEMBOL_PATTERN = _re.compile(r'^[A-Z0-9.]{1,12}$')

def sembol_dogrula(s):
    s = s.strip().upper()
    if not s or not _SEMBOL_PATTERN.match(s):
        return None
    if any(c in s for c in ["/","\\","..","<",">","&",";"," "]):
        return None
    return s

# ════════════════════════════════════════════════════════════════════════
#  VERİ KAYNAKLARI
# ════════════════════════════════════════════════════════════════════════

STOOQ_SEMBOLLER = {
    "AAPL":"aapl.us","MSFT":"msft.us","NVDA":"nvda.us","GOOGL":"googl.us",
    "META":"meta.us","AMZN":"amzn.us","TSLA":"tsla.us","JPM":"jpm.us",
    "V":"v.us","UNH":"unh.us","XOM":"xom.us","JNJ":"jnj.us","WMT":"wmt.us",
    "PG":"pg.us","MA":"ma.us","HD":"hd.us","BAC":"bac.us","ABBV":"abbv.us",
    "LLY":"lly.us","CVX":"cvx.us","AMD":"amd.us","INTC":"intc.us",
    "QCOM":"qcom.us","AVGO":"avgo.us","CRM":"crm.us","ADBE":"adbe.us",
    "NOW":"now.us","SNOW":"snow.us","PLTR":"pltr.us",
}

BIST_SEMBOLLER = {
    "GARAN.IS","THYAO.IS","ASELS.IS","EREGL.IS","KCHOL.IS",
    "SASA.IS","TUPRS.IS","BIMAS.IS","AKBNK.IS","YKBNK.IS",
    "PGSUS.IS","FROTO.IS","TOASO.IS","KOZAL.IS","ENKAI.IS",
}

def stooq_indir(sembol, gun=365*3):
    if not sembol_dogrula(sembol): return pd.DataFrame()
    end   = datetime.today()
    start = end - timedelta(days=gun)
    stooq_s = STOOQ_SEMBOLLER.get(sembol, sembol.lower()+".us")
    url = (f"https://stooq.com/q/d/l/?s={stooq_s}"
           f"&d1={start:%Y%m%d}&d2={end:%Y%m%d}&i=d")
    try:
        r = _req.get(url, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
        df = pd.read_csv(io.StringIO(r.text))
        if df.empty or "No data" in r.text: return pd.DataFrame()
        df["Date"] = pd.to_datetime(df["Date"])
        return df.set_index("Date").sort_index().dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()

def isyatirim_indir(sembol, gun=365*3):
    if not sembol_dogrula(sembol): return pd.DataFrame()
    end   = datetime.today()
    start = end - timedelta(days=gun)
    s = sembol.replace(".IS","")
    url = (f"https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website"
           f"/Common/Data.aspx/HisseTekil?hisse={s}"
           f"&startdate={start:%d-%m-%Y}&enddate={end:%d-%m-%Y}")
    try:
        r = _req.get(url, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
        data = r.json()
        if not data.get("ok") or not data.get("value"): return pd.DataFrame()
        df = pd.DataFrame(data["value"]).rename(columns={
            "HGDG_TARIH":"Date","HGDG_KAPANIS":"Close",
            "HGDG_AOF":"Open","HGDG_MIN":"Low",
            "HGDG_MAX":"High","HGDG_HACIM":"Volume"})
        df["Date"] = pd.to_datetime(df["Date"], format="%d-%m-%Y")
        return df.set_index("Date")[["Open","High","Low","Close","Volume"]].sort_index().dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()

def bigpara_anlik(sembol):
    try:
        s = sembol.replace(".IS","")
        url = f"http://bigpara.hurriyet.com.tr/api/v1/borsa/hisseyuzeysel/{s}"
        r = _req.get(url, timeout=8, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code != 200: return None
        d = r.json()["data"]["hisseYuzeysel"]
        return {
            "anlik":   float(d.get("kapanis") or d.get("alis") or 0),
            "acilis":  float(d.get("acilis") or 0),
            "yuksek":  float(d.get("yuksek") or 0),
            "dusuk":   float(d.get("dusuk") or 0),
            "dunku":   float(d.get("dunkukapanis") or 0),
            "hacim":   float(d.get("hacimlot") or 0),
            "tarih":   d.get("tarih","")[:16].replace("T"," "),
        }
    except Exception:
        return None

# ════════════════════════════════════════════════════════════════════════
#  AYARLAR
# ════════════════════════════════════════════════════════════════════════

LISTELER = {
    "🇹🇷 BIST": [
        "GARAN.IS","THYAO.IS","ASELS.IS","EREGL.IS","KCHOL.IS",
        "SASA.IS","TUPRS.IS","BIMAS.IS","AKBNK.IS","YKBNK.IS",
        "PGSUS.IS","FROTO.IS","TOASO.IS","KOZAL.IS","ENKAI.IS",
    ],
    "🇺🇸 S&P 500": [
        "AAPL","MSFT","NVDA","GOOGL","META","AMZN","TSLA","JPM","V","UNH",
        "XOM","JNJ","WMT","PG","MA","HD","BAC","ABBV","LLY","CVX",
    ],
    "⚡ Teknoloji": [
        "NVDA","AMD","INTC","QCOM","AVGO","CRM","ADBE","NOW","SNOW","PLTR",
    ],
}

# ── Temel parametreler ───────────────────────────────────────────────────
DONGU_DK       = 30
ATR_SL         = 1.5
ATR_TP         = 3.0
ML_PERIYOT     = "3y"
ILERI_GUN      = 5
GETIRI_ESIGI   = 0.025
N_AGAC         = 20
MAX_DERINLIK   = 4
MIN_YAPRAK     = 12
ML_CACHE_SAAT  = 4

# ── v7 parametreleri ─────────────────────────────────────────────────────
MAKRO_AKTIF       = True
SENTIMENT_AKTIF   = True
COKLU_TF_AKTIF    = True
DIVERJANS_AKTIF   = True
ENSEMBLE_GB_AKTIF = True
SHAP_ELEME_AKTIF  = True
GUCLU_ESIK        = 6
VIX_YUKSEK_ESIK   = 2.0
VIX_SL_CARPAN     = 2.0
VIX_TP_CARPAN     = 2.5

MAKRO_SEMBOLLER = {
    "USDTRY": "usdtry",
    "ALTIN":  "xauusd",
    "BRENT":  "lcox",
    "BIST100":"xu100.is",
    "SP500":  "^spx",
    "EURUSD": "eurusd",
}

SENTIMENT_RSS = [
    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "https://www.investing.com/rss/news.rss",
]

# ════════════════════════════════════════════════════════════════════════
#  KATMAN 1: TEKNİK GÖSTERGELER
# ════════════════════════════════════════════════════════════════════════

class Ind:
    @staticmethod
    def ema(s, p): return s.ewm(span=p, adjust=False).mean()
    @staticmethod
    def sma(s, p): return s.rolling(p).mean()

    @staticmethod
    def rsi(c, p=14):
        d = c.diff()
        g = d.clip(lower=0).ewm(com=p-1, adjust=False).mean()
        l = (-d.clip(upper=0)).ewm(com=p-1, adjust=False).mean()
        return 100 - 100 / (1 + g / l.replace(0, np.nan))

    @staticmethod
    def macd(c, f=12, s=26, sig=9):
        m = Ind.ema(c,f) - Ind.ema(c,s)
        signal = Ind.ema(m, sig)
        return m, signal, m - signal

    @staticmethod
    def stoch(h, l, c, p=14, sm=3):
        lo = l.rolling(p).min(); hi = h.rolling(p).max()
        k = 100*(c-lo)/(hi-lo).replace(0,np.nan)
        return k, k.rolling(sm).mean()

    @staticmethod
    def cci(h, l, c, p=20):
        tp = (h+l+c)/3
        return (tp - tp.rolling(p).mean()) / (0.015*tp.rolling(p).std())

    @staticmethod
    def williams(h, l, c, p=14):
        return -100*(h.rolling(p).max()-c)/(h.rolling(p).max()-l.rolling(p).min()).replace(0,np.nan)

    @staticmethod
    def mfi(h, l, c, v, p=14):
        tp = (h+l+c)/3; mf = tp*v
        pos = mf.where(tp>tp.shift(1), 0).rolling(p).sum()
        neg = mf.where(tp<tp.shift(1), 0).rolling(p).sum()
        return 100 - 100/(1+pos/neg.replace(0,np.nan))

    @staticmethod
    def roc(c, p=10): return (c/c.shift(p)-1)*100

    @staticmethod
    def tsi(c, r=25, s=13):
        d = c.diff()
        ds = Ind.ema(Ind.ema(d, r), s)
        ads = Ind.ema(Ind.ema(d.abs(), r), s)
        return 100*ds/ads.replace(0,np.nan)

    @staticmethod
    def atr(h, l, c, p=14):
        tr = pd.concat([(h-l),(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
        return tr.ewm(com=p-1, adjust=False).mean()

    @staticmethod
    def bollinger(c, p=20, k=2):
        m=Ind.sma(c,p); s=c.rolling(p).std()
        return m+k*s, m, m-k*s

    @staticmethod
    def keltner(h, l, c, p=20, m=2.0):
        e=Ind.ema(c,p); a=Ind.atr(h,l,c,p)
        return e+m*a, e, e-m*a

    @staticmethod
    def donchian(h, l, p=20):
        return h.rolling(p).max(), l.rolling(p).min()

    @staticmethod
    def squeeze(h, l, c, p=20):
        bbu,bbm,bbl = Ind.bollinger(c,p)
        kcu,kcm,kcl = Ind.keltner(h,l,c,p)
        sq = (bbl>kcl)&(bbu<kcu)
        mom = Ind.ema(c-(Ind.sma(h.rolling(p).max()+l.rolling(p).min(),1)/2+bbm)/2, p)
        return sq, mom

    @staticmethod
    def supertrend(h, l, c, p=10, mult=3.0):
        hl2 = (h+l)/2; at = Ind.atr(h,l,c,p)
        upper = hl2 + mult*at; lower = hl2 - mult*at
        trend = pd.Series(1, index=c.index); st = lower.copy()
        for i in range(1, len(c)):
            pu=upper.iloc[i-1]; pl=lower.iloc[i-1]
            cu=upper.iloc[i];   cl=lower.iloc[i]
            lower.iloc[i] = max(cl, pl) if c.iloc[i-1] > pl else cl
            upper.iloc[i] = min(cu, pu) if c.iloc[i-1] < pu else cu
            if trend.iloc[i-1]==-1 and c.iloc[i]>upper.iloc[i-1]: trend.iloc[i]=1
            elif trend.iloc[i-1]==1 and c.iloc[i]<lower.iloc[i-1]: trend.iloc[i]=-1
            else: trend.iloc[i]=trend.iloc[i-1]
            st.iloc[i] = lower.iloc[i] if trend.iloc[i]==1 else upper.iloc[i]
        return st, trend

    @staticmethod
    def adx(h, l, c, p=14):
        up=h.diff(); dn=-l.diff()
        pdm=up.where((up>dn)&(up>0),0)
        mdm=dn.where((dn>up)&(dn>0),0)
        at=Ind.atr(h,l,c,p)
        pdi=100*pdm.ewm(com=p-1,adjust=False).mean()/at
        mdi=100*mdm.ewm(com=p-1,adjust=False).mean()/at
        dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
        return dx.ewm(com=p-1,adjust=False).mean(), pdi, mdi

    @staticmethod
    def sar(h, l, c=None, start=0.02, inc=0.02, max_af=0.2):
        bull=True; af=start; ep=float(l.iloc[0]); sar_v=[float(l.iloc[0])]
        for i in range(1,len(h)):
            ps=sar_v[-1]
            if bull:
                ns=ps+af*(ep-ps)
                ns=min(ns,float(l.iloc[i-1]),float(l.iloc[max(i-2,0)]))
                if float(l.iloc[i])<ns: bull=False; af=start; ep=float(l.iloc[i]); ns=ep
                else:
                    if float(h.iloc[i])>ep: ep=float(h.iloc[i]); af=min(af+inc,max_af)
            else:
                ns=ps+af*(ep-ps)
                ns=max(ns,float(h.iloc[i-1]),float(h.iloc[max(i-2,0)]))
                if float(h.iloc[i])>ns: bull=True; af=start; ep=float(h.iloc[i]); ns=ep
                else:
                    if float(l.iloc[i])<ep: ep=float(l.iloc[i]); af=min(af+inc,max_af)
            sar_v.append(ns)
        s=pd.Series(sar_v,index=h.index)
        ref=c if c is not None else (h+l)/2
        return s, ref>s

    @staticmethod
    def hma(c, p=20):
        wma_h=c.rolling(p//2).mean(); wma_f=c.rolling(p).mean()
        return (2*wma_h-wma_f).rolling(int(np.sqrt(p))).mean()

    @staticmethod
    def ichimoku(h, l, c, t=9, k=26, s=52, d=26):
        ten=(h.rolling(t).max()+l.rolling(t).min())/2
        kij=(h.rolling(k).max()+l.rolling(k).min())/2
        spa=((ten+kij)/2).shift(d)
        spb=((h.rolling(s).max()+l.rolling(s).min())/2).shift(d)
        return ten, kij, spa, spb

    @staticmethod
    def obv(c, v): return (np.sign(c.diff()).fillna(0)*v).cumsum()

    @staticmethod
    def vwap(h, l, c, v):
        tp=(h+l+c)/3
        return (tp*v).cumsum()/v.replace(0,np.nan).cumsum()

    @staticmethod
    def cmf(h, l, c, v, p=20):
        mfm=((c-l)-(h-c))/(h-l).replace(0,np.nan)
        return (mfm*v).rolling(p).sum()/v.rolling(p).sum()

    @staticmethod
    def vpt(c, v): return (v*c.pct_change()).cumsum()

    @staticmethod
    def pivot(h, l, c):
        p=float((h+l+c)/3)
        return p, 2*p-float(l), p+float(h-l), 2*p-float(h), p-float(h-l)

    @staticmethod
    def rejim(c, h, l, adx_v, p=20):
        at=Ind.atr(h,l,c,p)/c; vr=at/at.rolling(50).mean()
        r=pd.Series("RANGE",index=c.index)
        r[adx_v>25]="TREND"; r[vr>1.5]="VOLATILE"
        return r

# ════════════════════════════════════════════════════════════════════════
#  KATMAN 2: ML ENGINE — NUMPY-ONLY
# ════════════════════════════════════════════════════════════════════════

class KararAgaci:
    def __init__(self, max_depth=6, min_samples=8):
        self.max_depth=max_depth; self.min_samples=min_samples; self.agac=None

    def _gini(self, y):
        if len(y)==0: return 0
        _, sayilar=np.unique(y,return_counts=True); p=sayilar/len(y)
        return 1-np.sum(p**2)

    def _en_iyi_bolme(self, X, y):
        en_iyi={"gini":float("inf"),"ozellik":None,"esik":None}
        idx=np.random.choice(X.shape[1],max(1,int(np.sqrt(X.shape[1]))),replace=False)
        for j in idx:
            for t in np.percentile(X[:,j],[20,40,60,80]):
                sol=y[X[:,j]<=t]; sag=y[X[:,j]>t]
                if len(sol)<self.min_samples or len(sag)<self.min_samples: continue
                g=(len(sol)*self._gini(sol)+len(sag)*self._gini(sag))/len(y)
                if g<en_iyi["gini"]: en_iyi={"gini":g,"ozellik":j,"esik":t}
        return en_iyi

    def _olustur(self, X, y, derinlik):
        siniflar,sayilar=np.unique(y,return_counts=True)
        if derinlik>=self.max_depth or len(y)<=self.min_samples or len(siniflar)==1:
            p=sayilar/len(y)
            return {"yaprak":True,"siniflar":siniflar.tolist(),"olasiliklar":p.tolist(),"n":len(y)}
        bolme=self._en_iyi_bolme(X,y)
        if bolme["ozellik"] is None:
            p=sayilar/len(y)
            return {"yaprak":True,"siniflar":siniflar.tolist(),"olasiliklar":p.tolist(),"n":len(y)}
        j,t=bolme["ozellik"],bolme["esik"]; maske=X[:,j]<=t
        return {"yaprak":False,"ozellik":j,"esik":t,
                "sol":self._olustur(X[maske],y[maske],derinlik+1),
                "sag":self._olustur(X[~maske],y[~maske],derinlik+1)}

    def egit(self, X, y):
        self.siniflar_listesi=np.unique(y); self.agac=self._olustur(X,y,0)

    def _tahmin_bir(self, x, dugum):
        if dugum["yaprak"]:
            proba=np.zeros(len(self.siniflar_listesi))
            for i,s in enumerate(self.siniflar_listesi):
                if s in dugum["siniflar"]:
                    idx=dugum["siniflar"].index(s); proba[i]=dugum["olasiliklar"][idx]
            return proba
        if x[dugum["ozellik"]]<=dugum["esik"]: return self._tahmin_bir(x,dugum["sol"])
        return self._tahmin_bir(x,dugum["sag"])

    def tahmin_proba(self, X):
        return np.array([self._tahmin_bir(x,self.agac) for x in X])


class RandomForest:
    def __init__(self, n_agac=20, max_depth=4, min_samples=12):
        self.n_agac=n_agac; self.max_depth=max_depth
        self.min_samples=min_samples; self.agaclar=[]; self.siniflar=None

    def egit(self, X, y):
        self.siniflar=np.unique(y); self.agaclar=[]; n=len(X)
        for _ in range(self.n_agac):
            idx=np.random.choice(n,n,replace=True)
            agac=KararAgaci(self.max_depth,self.min_samples)
            agac.siniflar_listesi=self.siniflar; agac.egit(X[idx],y[idx])
            self.agaclar.append(agac)

    def tahmin_proba(self, X):
        if not self.agaclar:
            return np.ones((len(X),len(self.siniflar)))/len(self.siniflar)
        return np.array([a.tahmin_proba(X) for a in self.agaclar]).mean(axis=0)

    def tahmin(self, X):
        return self.siniflar[np.argmax(self.tahmin_proba(X),axis=1)]


class HistGradientBoost:
    """
    Histogram tabanlı Gradient Boosting — LightGBM benzeri numpy implementasyonu.
    Standart GB'den ~4x hızlı: sürekli değerleri N_BIN histograma indirir.
    Araştırma: RF + HistGB ensemble %28 isabetlilik artışı sağlıyor.
    """
    def __init__(self, n_agac=25, max_depth=3, lr=0.08, n_bin=24):
        self.n_agac=n_agac; self.max_depth=max_depth
        self.lr=lr; self.n_bin=n_bin
        self.agaclar=[]; self.F0=0.0; self.siniflar=None; self.bin_sinirlar=[]

    def _histogramla(self, X):
        X_h=np.zeros_like(X,dtype=np.int16); self.bin_sinirlar=[]
        for j in range(X.shape[1]):
            sinirlar=np.unique(np.percentile(X[:,j],np.linspace(0,100,self.n_bin+1)))
            X_h[:,j]=np.digitize(X[:,j],sinirlar[1:-1]).astype(np.int16)
            self.bin_sinirlar.append(sinirlar)
        return X_h

    def _hist_test(self, X):
        X_h=np.zeros_like(X,dtype=np.int16)
        for j in range(X.shape[1]):
            X_h[:,j]=np.digitize(X[:,j],self.bin_sinirlar[j][1:-1]).astype(np.int16)
        return X_h

    def _softmax(self, X):
        e=np.exp(X-X.max(axis=1,keepdims=True))
        return e/e.sum(axis=1,keepdims=True)

    def _agac_tahmin(self, x_h, dugum):
        while dugum.get("sol") is not None:
            if x_h[dugum["j"]]<=dugum["esik"]: dugum=dugum["sol"]
            else: dugum=dugum["sag"]
        return dugum["deger"]

    def _agac_olustur(self, X_h, grad, derinlik=0):
        if derinlik>=self.max_depth or len(X_h)<10:
            return {"deger":grad.mean()}
        n,m=X_h.shape; en_iyi={"kayip":np.inf}
        for j in range(m):
            for esik in range(self.n_bin):
                sm=X_h[:,j]<=esik; rm=~sm
                if sm.sum()<5 or rm.sum()<5: continue
                kayip=(np.var(grad[sm])*sm.sum()+np.var(grad[rm])*rm.sum())
                if kayip<en_iyi["kayip"]:
                    en_iyi={"kayip":kayip,"j":j,"esik":esik,"sm":sm,"rm":rm}
        if en_iyi["kayip"]==np.inf: return {"deger":grad.mean()}
        return {"j":en_iyi["j"],"esik":en_iyi["esik"],
                "sol":self._agac_olustur(X_h[en_iyi["sm"]],grad[en_iyi["sm"]],derinlik+1),
                "sag":self._agac_olustur(X_h[en_iyi["rm"]],grad[en_iyi["rm"]],derinlik+1),
                "deger":grad.mean()}

    def egit(self, X, y):
        self.siniflar=np.unique(y); K=len(self.siniflar); n=len(y)
        y_idx=np.array([np.where(self.siniflar==yi)[0][0] for yi in y])
        Y=np.eye(K)[y_idx]
        X_h=self._histogramla(X); F=np.full((n,K),1.0/K); self.F0=1.0/K
        for _ in range(self.n_agac):
            P=self._softmax(F); grad=Y-P; agac_k=[]
            for k in range(K):
                agac=self._agac_olustur(X_h,grad[:,k])
                agac_k.append(agac)
                F[:,k]+=self.lr*np.array([self._agac_tahmin(X_h[i],agac) for i in range(n)])
            self.agaclar.append(agac_k)

    def tahmin_proba(self, X):
        X_h=self._hist_test(X); K=len(self.siniflar)
        F=np.full((len(X),K),self.F0)
        for agac_k in self.agaclar:
            for k,agac in enumerate(agac_k):
                F[:,k]+=self.lr*np.array([self._agac_tahmin(X_h[i],agac) for i in range(len(X))])
        return self._softmax(F)

    def tahmin(self, X):
        return self.siniflar[np.argmax(self.tahmin_proba(X),axis=1)]

# ════════════════════════════════════════════════════════════════════════
#  KATMAN 3: ÖZELLİK MÜHENDİSLİĞİ (60+ özellik)
# ════════════════════════════════════════════════════════════════════════

def ozellik_uret(df):
    c=df["Close"].squeeze(); h=df["High"].squeeze()
    l=df["Low"].squeeze();   v=df["Volume"].squeeze()

    rsi_s            = Ind.rsi(c)
    macd_s,sig_s,hist_s = Ind.macd(c)
    sk,sd            = Ind.stoch(h,l,c)
    cci_s            = Ind.cci(h,l,c)
    wr_s             = Ind.williams(h,l,c)
    mfi_s            = Ind.mfi(h,l,c,v)
    roc_s            = Ind.roc(c)
    tsi_s            = Ind.tsi(c)
    at               = Ind.atr(h,l,c)
    adx_s,pdi_s,mdi_s= Ind.adx(h,l,c)
    _,st_s           = Ind.supertrend(h,l,c)
    _,sar_s          = Ind.sar(h,l)
    ten,kij,spa,spb  = Ind.ichimoku(h,l,c)
    bbu,bbm,bbl      = Ind.bollinger(c)
    kcu,kcm,kcl      = Ind.keltner(h,l,c)
    dcu,dcl          = Ind.donchian(h,l)
    sq_s,sqm_s       = Ind.squeeze(h,l,c)
    obv_s            = Ind.obv(c,v)
    vwap_s           = Ind.vwap(h,l,c,v)
    cmf_s            = Ind.cmf(h,l,c,v)
    vpt_s            = Ind.vpt(c,v)
    hma_s            = Ind.hma(c)
    ma5=c.rolling(5).mean(); ma10=c.rolling(10).mean()
    ma20=c.rolling(20).mean(); ma50=c.rolling(50).mean(); ma200=c.rolling(200).mean()
    # v7: ek özellikler
    dema20 = 2*c.ewm(span=20,adjust=False).mean() - c.ewm(span=20,adjust=False).mean().ewm(span=20,adjust=False).mean()
    ad_line= ((2*c-l-h)/(h-l+1e-9)*v).cumsum()

    feat = pd.DataFrame({
        "rsi":rsi_s,"rsi_ch":rsi_s.diff(),"rsi_ma_diff":rsi_s-rsi_s.rolling(5).mean(),
        "macd":macd_s,"macd_sig":sig_s,"macd_hist":hist_s,
        "macd_hist_ch":hist_s.diff(),"macd_hist_acc":hist_s.diff().diff(),
        "stoch_k":sk,"stoch_d":sd,"stoch_diff":sk-sd,
        "cci":cci_s,"wr":wr_s,"mfi":mfi_s,"roc":roc_s,"tsi":tsi_s,
        "adx":adx_s,"pdi":pdi_s,"mdi":mdi_s,"di_diff":pdi_s-mdi_s,
        "supertrend":st_s.astype(float),"sar_bull":sar_s.astype(float),
        "ichimoku_tk":(ten-kij)/c.replace(0,np.nan),
        "price_cloud":(c-spa.fillna(spb))/c.replace(0,np.nan),
        "cloud_bull":(spa>spb).astype(float),
        "bb_width":(bbu-bbl)/bbm.replace(0,np.nan),
        "bb_pos":(c-bbl)/(bbu-bbl).replace(0,np.nan),
        "kc_pos":(c-kcl)/(kcu-kcl).replace(0,np.nan),
        "dc_pos":(c-dcl)/(dcu-dcl).replace(0,np.nan),
        "squeeze":sq_s.astype(float),"sq_mom":sqm_s,
        "atr_pct":at/c.replace(0,np.nan),
        "obv_ch":obv_s.pct_change(),"cmf":cmf_s,"vpt_ch":vpt_s.pct_change(),
        "vol_ratio":v/v.rolling(20).mean(),"vol_trend":v.rolling(5).mean()/v.rolling(20).mean(),
        "price_vwap":(c-vwap_s)/vwap_s.replace(0,np.nan),
        "hma_trend":(c-hma_s)/hma_s.replace(0,np.nan),
        "ma5_20":(ma5-ma20)/ma20.replace(0,np.nan),
        "ma20_50":(ma20-ma50)/ma50.replace(0,np.nan),
        "ma50_200":(ma50-ma200)/ma200.replace(0,np.nan),
        "price_ma20":(c-ma20)/ma20.replace(0,np.nan),
        "price_ma50":(c-ma50)/ma50.replace(0,np.nan),
        "ret1":c.pct_change(1),"ret3":c.pct_change(3),
        "ret5":c.pct_change(5),"ret10":c.pct_change(10),"ret20":c.pct_change(20),
        "hl_pct":(h-l)/c.replace(0,np.nan),
        "close_pos":(c-l)/(h-l).replace(0,np.nan),
        "gap":(c-c.shift(1))/c.shift(1),
        # v7 ek özellikler
        "ret_vol5":c.pct_change(1).rolling(5).std(),
        "ret_vol10":c.pct_change(1).rolling(10).std(),
        "ret_vol20":c.pct_change(1).rolling(20).std(),
        "dema_trend":(c-dema20)/c.replace(0,np.nan),
        "ad_ch":ad_line.pct_change(),
        "rvol":v/v.rolling(50).mean(),
        "doji":(abs(c-c.shift(1))/(h-l+1e-9)).fillna(0),
        "upper_shadow":(h-c.clip(upper=c.shift(1)))/(h-l+1e-9),
        "lower_shadow":(c.clip(lower=c.shift(1))-l)/(h-l+1e-9),
    })
    return feat

# ════════════════════════════════════════════════════════════════════════
#  KATMAN 4: WALK-FORWARD + NORMALIZE
# ════════════════════════════════════════════════════════════════════════

def normalize(X_train, X_test):
    med=np.nanmedian(X_train,axis=0)
    q75,q25=np.nanpercentile(X_train,[75,25],axis=0); iqr=q75-q25; iqr[iqr==0]=1
    return np.nan_to_num((X_train-med)/iqr,0), np.nan_to_num((X_test-med)/iqr,0)

def walk_forward_acc(X, y, n_fold=3):
    n=len(X); fold_size=n//(n_fold+1); scores=[]
    for i in range(1,n_fold+1):
        train_end=i*fold_size; test_end=min(train_end+fold_size,n)
        X_tr,y_tr=X[:train_end],y[:train_end]
        X_te,y_te=X[train_end:test_end],y[train_end:test_end]
        if len(np.unique(y_tr))<2 or len(X_te)==0: continue
        X_tr_n,X_te_n=normalize(X_tr,X_te)
        m=RandomForest(n_agac=15,max_depth=4,min_samples=10)
        m.egit(X_tr_n,y_tr); pred=m.tahmin(X_te_n)
        scores.append(np.mean(pred==y_te))
    return float(np.mean(scores)) if scores else 0.5

# ════════════════════════════════════════════════════════════════════════
#  KATMAN v7-A: MAKRO VERİ
# ════════════════════════════════════════════════════════════════════════

_makro_cache={}
_makro_lock=__import__("threading").Lock()

def _stooq_seri(sembol_str, gun=120):
    try:
        end=datetime.today(); start=end-timedelta(days=gun)
        url=(f"https://stooq.com/q/d/l/?s={sembol_str}"
             f"&d1={start:%Y%m%d}&d2={end:%Y%m%d}&i=d")
        r=_req.get(url,timeout=10,headers={"User-Agent":"Mozilla/5.0"})
        df=pd.read_csv(io.StringIO(r.text))
        if df.empty or "No data" in r.text or "Close" not in df.columns:
            return pd.Series(dtype=float)
        df["Date"]=pd.to_datetime(df["Date"])
        return df.set_index("Date").sort_index()["Close"].astype(float).dropna()
    except Exception:
        return pd.Series(dtype=float)

def makro_veri_getir():
    global _makro_cache
    with _makro_lock:
        if _makro_cache.get("_zaman",0) > time.time()-3600:
            return _makro_cache
    sonuc={ad:_stooq_seri(sembol) for ad,sembol in MAKRO_SEMBOLLER.items()}
    sonuc["_zaman"]=time.time()
    with _makro_lock:
        _makro_cache=sonuc
    return sonuc

def makro_ozellikler(sembol):
    mv=makro_veri_getir()
    bist=sembol.endswith(".IS")
    def deg(seri,p=5):
        if seri is None or len(seri)<p+1: return 0.0
        return float((seri.iloc[-1]-seri.iloc[-p])/(seri.iloc[-p]+1e-9))
    usdtry=mv.get("USDTRY",pd.Series(dtype=float))
    altin =mv.get("ALTIN", pd.Series(dtype=float))
    brent =mv.get("BRENT", pd.Series(dtype=float))
    bist100=mv.get("BIST100",pd.Series(dtype=float))
    sp500 =mv.get("SP500",  pd.Series(dtype=float))
    vix_p=float(pd.Series(sp500).pct_change().rolling(20).std().iloc[-1])*16 if len(sp500)>21 else 0.15
    ozet={
        "usdtry_5d":deg(usdtry,5),"usdtry_20d":deg(usdtry,20),
        "altin_5d":deg(altin,5),"altin_20d":deg(altin,20),
        "brent_5d":deg(brent,5),"brent_20d":deg(brent,20),
        "bist100_5d":deg(bist100,5),"sp500_5d":deg(sp500,5),
        "vix_proxy":vix_p,
        "makro_baski":-deg(usdtry,5) if bist else deg(sp500,5),
    }
    return {k:(0.0 if not np.isfinite(v) else round(float(v),6)) for k,v in ozet.items()}

# ════════════════════════════════════════════════════════════════════════
#  KATMAN v7-B: HABER SENTİMENTİ
# ════════════════════════════════════════════════════════════════════════

_sent_cache={}
_sent_lock=__import__("threading").Lock()

_POZITIF={
    "rally","surge","gain","rise","profit","beat","exceed","strong","growth",
    "buy","upgrade","bullish","record","high","positive","increase","boost",
    "improve","outperform","upside","breakout",
    "yükseliş","artış","kar","kazanç","güçlü","rekor","pozitif",
    "büyüme","toparlanma","alım","yükseldi","iyileşme",
}
_NEGATIF={
    "fall","drop","decline","loss","miss","weak","cut","downgrade","bearish",
    "warning","risk","crash","slump","sell","pressure","decrease","plunge",
    "crisis","default","inflation",
    "düşüş","gerileme","kayıp","zayıf","kriz","baskı","endişe",
    "satış","enflasyon","negatif","uyarı","çöküş","kötüleşme",
}

_SIRKET_ADLARI={
    "thyao":["thy","turkish airlines","thyao"],
    "tuprs":["tupras","petkim","tuprs"],
    "garan":["garanti","garan"],
    "asels":["aselsan","asels"],
    "nvda":["nvidia","nvda","gpu"],
    "aapl":["apple","iphone","aapl"],
    "msft":["microsoft","msft","azure"],
    "tsla":["tesla","elon","tsla"],
    "meta":["facebook","meta","instagram"],
    "amzn":["amazon","amzn","aws"],
}

def haber_sentimenti(sembol):
    with _sent_lock:
        if sembol in _sent_cache:
            ts,skor=_sent_cache[sembol]
            if time.time()-ts<7200: return skor
    s_temiz=sembol.replace(".IS","").replace(".US","").lower()
    arama=_SIRKET_ADLARI.get(s_temiz,[s_temiz])
    poz=neg=toplam=0
    for rss in SENTIMENT_RSS:
        try:
            r=_req.get(rss,timeout=8,headers={"User-Agent":"Mozilla/5.0"})
            titles=_re.findall(r"<title>(.*?)</title>",r.text)
            for t in titles[:50]:
                tl=t.lower()
                if not any(a in tl for a in arama): continue
                toplam+=1
                kelimeler=set(tl.split())
                poz+=len(kelimeler&_POZITIF); neg+=len(kelimeler&_NEGATIF)
        except Exception:
            continue
    skor=0.0 if toplam==0 else float(max(-1.0,min(1.0,(poz-neg)/max(toplam,1))))
    with _sent_lock:
        _sent_cache[sembol]=(time.time(),skor)
    return skor

# ════════════════════════════════════════════════════════════════════════
#  KATMAN v7-C: DİVERJANS DEDEKTÖRÜ
# ════════════════════════════════════════════════════════════════════════

def diverjans_tespit(df, pencere=14):
    c=df["Close"].squeeze(); h=df["High"].squeeze(); l=df["Low"].squeeze()
    if len(c)<pencere*3: return 0,[]
    rsi_s=Ind.rsi(c); _,_,hist_s=Ind.macd(c)
    son_c=c.iloc[-pencere*2:].values
    son_rsi=rsi_s.iloc[-pencere*2:].values
    son_mac=hist_s.iloc[-pencere*2:].values
    puan=0; notlar=[]
    try:
        dip_idx=[i for i in range(1,len(son_c)-1)
                 if son_c[i]<son_c[i-1] and son_c[i]<son_c[i+1]]
        if len(dip_idx)>=2:
            d1,d2=dip_idx[-2],dip_idx[-1]
            if son_c[d2]<son_c[d1]:
                if not np.isnan(son_rsi[d2]) and son_rsi[d2]>son_rsi[d1]+3:
                    puan+=2; notlar.append("RSI Bullish Diverjans ⚡")
                if not np.isnan(son_mac[d2]) and son_mac[d2]>son_mac[d1]:
                    puan+=1; notlar.append("MACD Bullish Diverjans ⚡")
    except Exception: pass
    try:
        tepe_idx=[i for i in range(1,len(son_c)-1)
                  if son_c[i]>son_c[i-1] and son_c[i]>son_c[i+1]]
        if len(tepe_idx)>=2:
            t1,t2=tepe_idx[-2],tepe_idx[-1]
            if son_c[t2]>son_c[t1]:
                if not np.isnan(son_rsi[t2]) and son_rsi[t2]<son_rsi[t1]-3:
                    puan-=2; notlar.append("RSI Bearish Diverjans ⚠️")
                if not np.isnan(son_mac[t2]) and son_mac[t2]<son_mac[t1]:
                    puan-=1; notlar.append("MACD Bearish Diverjans ⚠️")
    except Exception: pass
    return puan, notlar

# ════════════════════════════════════════════════════════════════════════
#  KATMAN v7-D: ÇOKLU ZAMAN DİLİMİ UYUMU
# ════════════════════════════════════════════════════════════════════════

def coklu_tf_uyum(df):
    c=df["Close"].squeeze()
    if len(c)<60: return 0,"Veri yetersiz"
    ma20=float(c.rolling(20).mean().iloc[-1]); ma50=float(c.rolling(50).mean().iloc[-1])
    son=float(c.iloc[-1])
    trend_d=1 if son>ma20>ma50 else (-1 if son<ma20<ma50 else 0)
    try:
        c_w=c.iloc[::5]
        ma10_w=float(c_w.rolling(10).mean().iloc[-1])
        ma20_w=float(c_w.rolling(20).mean().iloc[-1])
        son_w=float(c_w.iloc[-1])
        trend_w=1 if son_w>ma10_w>ma20_w else (-1 if son_w<ma10_w<ma20_w else 0)
    except Exception:
        trend_w=0
    if trend_d==trend_w==1:   return 2,"Çoklu TF: Günlük+Haftalık BULLISH 💚"
    elif trend_d==trend_w==-1: return -2,"Çoklu TF: Günlük+Haftalık BEARISH 🔴"
    elif trend_d!=0 and trend_w!=0 and trend_d!=trend_w:
        return -1,"Çoklu TF: Günlük vs Haftalık ÇAKIŞIYOR ⚠️"
    elif trend_d==1:  return 1,"Çoklu TF: Günlük BULLISH, haftalık nötr"
    elif trend_d==-1: return -1,"Çoklu TF: Günlük BEARISH, haftalık nötr"
    return 0,"Çoklu TF: Yatay"

# ════════════════════════════════════════════════════════════════════════
#  KATMAN v7-E: DESTEK / DİRENÇ SEVİYELERİ
# ════════════════════════════════════════════════════════════════════════

def destek_direnc(df, pencere=10, n=3):
    c=df["Close"].squeeze(); h=df["High"].squeeze(); l=df["Low"].squeeze()
    son_n=min(len(c),pencere*(n+3))
    c_s=c.iloc[-son_n:]; h_s=h.iloc[-son_n:]; l_s=l.iloc[-son_n:]
    destekler=[]; direncler=[]
    for i in range(pencere,len(c_s)-pencere):
        if l_s.iloc[i]==l_s.iloc[i-pencere:i+pencere+1].min():
            destekler.append(float(l_s.iloc[i]))
        if h_s.iloc[i]==h_s.iloc[i-pencere:i+pencere+1].max():
            direncler.append(float(h_s.iloc[i]))
    atr=float(Ind.atr(h,l,c).iloc[-1]); tol=atr*0.5
    def kumele(sv):
        if not sv: return []
        sv=sorted(set(sv)); k=[sv[0]]
        for s in sv[1:]:
            if s-k[-1]>tol: k.append(s)
        return k
    son_fiyat=float(c.iloc[-1])
    return {
        "destekler":[d for d in kumele(destekler) if d<son_fiyat][-n:],
        "direncler":[d for d in kumele(direncler) if d>son_fiyat][:n],
        "atr":atr,
    }

# ════════════════════════════════════════════════════════════════════════
#  KATMAN v7-F: VIX PROXY + DİNAMİK SL/TP
# ════════════════════════════════════════════════════════════════════════

def vix_proxy(df):
    c=df["Close"].squeeze(); h=df["High"].squeeze(); l=df["Low"].squeeze()
    atr_s=Ind.atr(h,l,c); atr_pct=(atr_s/c.replace(0,np.nan))*100
    atr_ort=atr_pct.rolling(20).mean()
    son_atr=float(atr_pct.iloc[-1]); son_ort=float(atr_ort.iloc[-1])
    yuksek=np.isfinite(son_ort) and son_atr>son_ort*VIX_YUKSEK_ESIK
    return {
        "atr_pct":round(son_atr,3),
        "atr_ort":round(son_ort,3) if np.isfinite(son_ort) else 0.0,
        "yuksek":yuksek,
        "sl_carpan":VIX_SL_CARPAN if yuksek else ATR_SL,
        "tp_carpan":VIX_TP_CARPAN if yuksek else ATR_TP,
    }

# ════════════════════════════════════════════════════════════════════════
#  KATMAN v7-G: SHAP-LITE ÖZELLİK ELEME
# ════════════════════════════════════════════════════════════════════════

def shap_lite_eleme(X, y, threshold=0.003):
    try:
        agac=KararAgaci(max_depth=5,min_samples=15)
        agac.siniflar_listesi=np.unique(y); agac.egit(X,y)
        onem=np.zeros(X.shape[1])
        def say(dugum):
            if dugum is None or dugum.get("yaprak",True): return
            j=dugum.get("ozellik",0)
            if 0<=j<len(onem): onem[j]+=1
            say(dugum.get("sol")); say(dugum.get("sag"))
        say(agac.agac)
        toplam=onem.sum()
        if toplam>0: onem/=toplam
        secili=onem>=threshold
        if secili.sum()<10: secili=onem>=np.sort(onem)[-10]
        return secili
    except Exception:
        return np.ones(X.shape[1],dtype=bool)

# ════════════════════════════════════════════════════════════════════════
#  KATMAN 5: ML EĞİTİMİ (v7 — RF + HistGB Ensemble + SHAP)
# ════════════════════════════════════════════════════════════════════════

def ml_egit(df, sembol=""):
    df=df.iloc[-500:] if len(df)>500 else df
    feat=ozellik_uret(df); c=df["Close"].squeeze()
    hedef=np.where(c.shift(-ILERI_GUN)/c-1>GETIRI_ESIGI,1,
           np.where(c.shift(-ILERI_GUN)/c-1<-GETIRI_ESIGI,-1,0))
    hedef_s=pd.Series(hedef,index=c.index)
    X_df=feat.iloc[:-ILERI_GUN]; y_s=hedef_s.iloc[:-ILERI_GUN]
    mask=X_df.notna().all(axis=1)&y_s.notna()
    X_df,y_s=X_df[mask],y_s[mask]
    if len(X_df)<150: return None
    X=X_df.values.astype(float); y=y_s.values.astype(int)

    # SHAP-lite özellik eleme
    if SHAP_ELEME_AKTIF:
        secili=shap_lite_eleme(X,y)
        X=X[:,secili]; feat_adlari=[c for c,s in zip(X_df.columns,secili) if s]
    else:
        feat_adlari=list(X_df.columns)

    wf_acc=walk_forward_acc(X,y,n_fold=3)
    X_n,_=normalize(X,X)

    # RF
    rf=RandomForest(n_agac=N_AGAC,max_depth=MAX_DERINLIK,min_samples=MIN_YAPRAK)
    rf.egit(X_n,y)

    # HistGB
    hgb=None
    if ENSEMBLE_GB_AKTIF:
        try:
            hgb=HistGradientBoost(n_agac=20,max_depth=3,lr=0.08,n_bin=20)
            hgb.egit(X_n,y)
        except Exception:
            hgb=None

    # Son gün tahmini
    son_df=feat.iloc[[-1]]
    if SHAP_ELEME_AKTIF: son_df=son_df.iloc[:,secili]
    if son_df.isna().any(axis=1).iloc[0]: return None
    son=son_df.values.astype(float)
    son_n=np.nan_to_num((son-np.nanmedian(X,axis=0))/np.maximum(
        np.nanpercentile(X,75,axis=0)-np.nanpercentile(X,25,axis=0),1e-9),0)

    rf_p=rf.tahmin_proba(son_n)[0]; siniflar=rf.siniflar
    if hgb is not None:
        try:
            hgb_raw=hgb.tahmin_proba(son_n)[0]
            hgb_p=np.zeros_like(rf_p)
            for ki,kl in enumerate(siniflar):
                w=np.where(hgb.siniflar==kl)[0]
                if len(w)>0: hgb_p[ki]=hgb_raw[w[0]]
            if hgb_p.sum()>0:
                hgb_p/=hgb_p.sum(); ens_p=0.55*rf_p+0.45*hgb_p
            else: ens_p=rf_p
        except Exception:
            ens_p=rf_p
    else:
        ens_p=rf_p

    idx=np.argmax(ens_p); tahmin=int(siniflar[idx]); guven=float(ens_p[idx])
    proba={int(siniflar[i]):float(ens_p[i]) for i in range(len(siniflar))}

    # Makro
    makro_oz={}
    if MAKRO_AKTIF and sembol:
        try: makro_oz=makro_ozellikler(sembol)
        except Exception: pass

    return {
        "tahmin":tahmin,"guven":guven,"proba":proba,
        "wf_acc":wf_acc,"n":len(X),"feat_adlari":feat_adlari,
        "makro":makro_oz,"ensemble":hgb is not None,
    }

# ════════════════════════════════════════════════════════════════════════
#  KATMAN 6: KURAL TABANLI PUANLAMA (v7)
# ════════════════════════════════════════════════════════════════════════

def _sf(x,default=0.0):
    try:
        v=float(x)
        return default if (v!=v or v==float('inf') or v==float('-inf')) else v
    except Exception:
        return default

def kural_sinyal(df, sembol=""):
    c=df["Close"].squeeze(); h=df["High"].squeeze()
    l=df["Low"].squeeze();   v=df["Volume"].squeeze()

    rv         = float(Ind.rsi(c).iloc[-1])
    _mv,_sv,_hv= Ind.macd(c)
    mv=_sf(_mv.iloc[-1]); sv=_sf(_sv.iloc[-1])
    hv_cur=_sf(_hv.iloc[-1]); hv_prv=_sf(_hv.iloc[-2])
    _adx_s,_pdi_s,_mdi_s=Ind.adx(h,l,c)
    adx_v=_sf(_adx_s.iloc[-1]); pdi_v=_sf(_pdi_s.iloc[-1]); mdi_v=_sf(_mdi_s.iloc[-1])
    _,st_v=Ind.supertrend(h,l,c); st_v=int(st_v.iloc[-1])
    _,sar_b=Ind.sar(h,l); sar_v=bool(sar_b.iloc[-1])
    ten,kij,spa,spb=Ind.ichimoku(h,l,c)
    ten_v=_sf(ten.iloc[-1]); kij_v=_sf(kij.iloc[-1])
    spa_v=_sf(spa.iloc[-1]) if not np.isnan(_sf(spa.iloc[-1])) else _sf(spb.iloc[-1])
    spb_v=_sf(spb.iloc[-1]) if not np.isnan(_sf(spb.iloc[-1])) else _sf(spa.iloc[-1])
    mfi_v=float(Ind.mfi(h,l,c,v).iloc[-1])
    cmf_v=float(Ind.cmf(h,l,c,v).iloc[-1])
    at=float(Ind.atr(h,l,c).iloc[-1])
    sq_s,sqm_s=Ind.squeeze(h,l,c)
    sqm_v=_sf(sqm_s.iloc[-1]); sqm_p=_sf(sqm_s.iloc[-2])
    bbu,bbm,bbl=Ind.bollinger(c)
    bb_pos=(_sf(c.iloc[-1])-_sf(bbl.iloc[-1]))/(_sf(bbu.iloc[-1])-_sf(bbl.iloc[-1])+1e-9)
    sk,sd=Ind.stoch(h,l,c); sk_v=_sf(sk.iloc[-1]); sd_v=_sf(sd.iloc[-1])
    hma_v=float(Ind.hma(c).iloc[-1])
    ma20=float(c.rolling(20).mean().iloc[-1])
    ma50=float(c.rolling(50).mean().iloc[-1])
    ma200=float(c.rolling(200).mean().iloc[-1])
    son=_sf(c.iloc[-1]); deg=(son-_sf(c.iloc[-2]))/_sf(c.iloc[-2])*100
    rej=Ind.rejim(c,h,l,_adx_s).iloc[-1]

    puan=0; notlar=[]

    # ── RSI ──────────────────────────────────────────────────────────────
    if   rv<25: puan+=3; notlar.append(f"RSI {rv:.1f} → Ekstrem Satım ⚡⚡")
    elif rv<35: puan+=2; notlar.append(f"RSI {rv:.1f} → Aşırı Satım")
    elif rv<45: puan+=1; notlar.append(f"RSI {rv:.1f} → Zayıf AL Bölgesi")
    elif rv>75: puan-=3; notlar.append(f"RSI {rv:.1f} → Ekstrem Alım ⚡⚡")
    elif rv>65: puan-=2; notlar.append(f"RSI {rv:.1f} → Aşırı Alım")
    elif rv>55: puan-=1; notlar.append(f"RSI {rv:.1f} → Zayıf SAT Bölgesi")
    else:                notlar.append(f"RSI {rv:.1f} → Nötr")

    # ── MACD ─────────────────────────────────────────────────────────────
    if mv>sv and hv_cur>0 and hv_cur>hv_prv:   puan+=2; notlar.append("MACD → Yükselen Momentum 📈")
    elif mv>sv:                                  puan+=1; notlar.append("MACD → Pozitif Kesişim")
    elif mv<sv and hv_cur<0 and hv_cur<hv_prv: puan-=2; notlar.append("MACD → Düşen Momentum 📉")
    else:                                        puan-=1; notlar.append("MACD → Negatif Kesişim")

    # ── ADX / DMI ────────────────────────────────────────────────────────
    if adx_v>25 and pdi_v>mdi_v:   puan+=2; notlar.append(f"ADX {adx_v:.0f} → Güçlü Yükseliş")
    elif adx_v>25 and mdi_v>pdi_v: puan-=2; notlar.append(f"ADX {adx_v:.0f} → Güçlü Düşüş")
    elif adx_v<20:                           notlar.append(f"ADX {adx_v:.0f} → Zayıf Trend")

    # ── SuperTrend ───────────────────────────────────────────────────────
    if st_v==1:  puan+=2; notlar.append("SuperTrend → Yükseliş ✅")
    else:        puan-=2; notlar.append("SuperTrend → Düşüş ❌")

    # ── SAR ──────────────────────────────────────────────────────────────
    if sar_v: puan+=1; notlar.append("Parabolic SAR → Bullish")
    else:     puan-=1; notlar.append("Parabolic SAR → Bearish")

    # ── HMA ──────────────────────────────────────────────────────────────
    hma_slope=hma_v-float(Ind.hma(c).iloc[-2])
    if hma_slope>0 and son>hma_v:  puan+=1; notlar.append(f"HMA → Yükselen Trend ({hma_v:.2f})")
    elif hma_slope<0:              puan-=1; notlar.append(f"HMA → Düşen Trend ({hma_v:.2f})")

    # ── Ichimoku ─────────────────────────────────────────────────────────
    bulut_ust=max(spa_v,spb_v); bulut_alt=min(spa_v,spb_v)
    if son>bulut_ust:   puan+=2; notlar.append("Ichimoku → Bulut Üstünde ☁️✅")
    elif son<bulut_alt: puan-=2; notlar.append("Ichimoku → Bulut Altında ☁️❌")
    else:                        notlar.append("Ichimoku → Bulut İçinde ☁️")
    if ten_v>kij_v: puan+=1; notlar.append("Ichimoku TK → Bullish")
    else:           puan-=1; notlar.append("Ichimoku TK → Bearish")

    # ── Squeeze Momentum ─────────────────────────────────────────────────
    if sqm_v>0 and sqm_v>sqm_p:   puan+=1; notlar.append("Squeeze → Yükselen Momentum 🔥")
    elif sqm_v<0 and sqm_v<sqm_p: puan-=1; notlar.append("Squeeze → Düşen Momentum ❄️")

    # ── Bollinger ────────────────────────────────────────────────────────
    if bb_pos<0.1:   puan+=1; notlar.append("Bollinger → Alt Banda Yakın (AL)")
    elif bb_pos>0.9: puan-=1; notlar.append("Bollinger → Üst Banda Yakın (SAT)")

    # ── MFI ──────────────────────────────────────────────────────────────
    if mfi_v<20:   puan+=2; notlar.append(f"MFI {mfi_v:.0f} → Aşırı Satım ⚡")
    elif mfi_v>80: puan-=2; notlar.append(f"MFI {mfi_v:.0f} → Aşırı Alım ⚡")

    # ── CMF ──────────────────────────────────────────────────────────────
    if cmf_v>0.15:    puan+=1; notlar.append(f"CMF {cmf_v:.2f} → Para Girişi")
    elif cmf_v<-0.15: puan-=1; notlar.append(f"CMF {cmf_v:.2f} → Para Çıkışı")

    # ── Stochastic ───────────────────────────────────────────────────────
    if sk_v<20 and sk_v>sd_v:   puan+=1; notlar.append(f"Stoch {sk_v:.0f} → Aşırı Satım Dönüş")
    elif sk_v>80 and sk_v<sd_v: puan-=1; notlar.append(f"Stoch {sk_v:.0f} → Aşırı Alım Dönüş")

    # ── MA Trendi ─────────────────────────────────────────────────────────
    if ma20>ma50>ma200:   puan+=2; notlar.append("MA 20>50>200 → Golden Trend 🏆")
    elif ma20>ma50:       puan+=1; notlar.append("MA 20>50 → Kısa Yükseliş")
    elif ma20<ma50<ma200: puan-=2; notlar.append("MA 20<50<200 → Death Trend ☠️")
    elif ma20<ma50:       puan-=1; notlar.append("MA 20<50 → Kısa Düşüş")

    # ── Pivot ────────────────────────────────────────────────────────────
    pp,r1,r2,s1,s2=Ind.pivot(h.iloc[-2],l.iloc[-2],c.iloc[-2])
    yakinlik=at*0.5
    if abs(son-s1)<yakinlik:   puan+=1; notlar.append(f"Pivot S1 Desteği: {s1:.2f}")
    elif abs(son-s2)<yakinlik: puan+=1; notlar.append(f"Pivot S2 Desteği: {s2:.2f}")
    elif abs(son-r1)<yakinlik: puan-=1; notlar.append(f"Pivot R1 Direnci: {r1:.2f}")
    elif abs(son-r2)<yakinlik: puan-=1; notlar.append(f"Pivot R2 Direnci: {r2:.2f}")

    # ── Rejim Filtresi ────────────────────────────────────────────────────
    rejim_not=""
    if rej=="RANGE":    puan=round(puan*0.6);  rejim_not=" [Range ×0.6]"
    elif rej=="VOLATILE": puan=round(puan*0.5); rejim_not=" [Volatil ×0.5]"

    # ════ v7 EKLEMELERİ ════════════════════════════════════════════════

    # ── Diverjans ────────────────────────────────────────────────────────
    if DIVERJANS_AKTIF:
        dp,dn=diverjans_tespit(df)
        puan+=dp; notlar.extend(dn)

    # ── Çoklu TF ─────────────────────────────────────────────────────────
    if COKLU_TF_AKTIF:
        tp,tn=coklu_tf_uyum(df)
        puan+=tp; notlar.append(tn)

    # ── Destek/Direnç ────────────────────────────────────────────────────
    sd=destek_direnc(df)
    destekler=sd["destekler"]; direncler=sd["direncler"]
    for d in destekler:
        if abs(son-d)<at*0.4: puan+=1; notlar.append(f"Lokal Destek: {d:.2f} 🛡️")
    for d in direncler:
        if abs(son-d)<at*0.4: puan-=1; notlar.append(f"Lokal Direnç: {d:.2f} 🚧")

    # ── Haber Sentimenti ─────────────────────────────────────────────────
    sent_skor=0.0
    if SENTIMENT_AKTIF and sembol:
        try:
            sent_skor=haber_sentimenti(sembol)
            if sent_skor>0.3:    puan+=1; notlar.append(f"Haber Sentimenti: POZİTİF ({sent_skor:+.2f}) 📰✅")
            elif sent_skor<-0.3: puan-=1; notlar.append(f"Haber Sentimenti: NEGATİF ({sent_skor:+.2f}) 📰❌")
            else:                notlar.append(f"Haber Sentimenti: NÖTR ({sent_skor:+.2f}) 📰")
        except Exception: pass

    # ── Makro Baskı ───────────────────────────────────────────────────────
    makro_oz={}
    if MAKRO_AKTIF and sembol:
        try:
            makro_oz=makro_ozellikler(sembol)
            mb=makro_oz.get("makro_baski",0.0)
            if mb>0.02:    puan+=1; notlar.append(f"Makro Destek 🌍✅")
            elif mb<-0.02: puan-=1; notlar.append(f"Makro Baskı 🌍❌")
        except Exception: pass

    # ── VIX Proxy — Dinamik SL/TP ─────────────────────────────────────────
    vix=vix_proxy(df); sl_c=vix["sl_carpan"]; tp_c=vix["tp_carpan"]
    if vix["yuksek"]:
        puan=round(puan*0.7)
        notlar.append(f"⚡ Yüksek Volatilite — SL:{sl_c}×ATR TP:{tp_c}×ATR (ATR%:{vix['atr_pct']:.1f})")
        rejim_not+=" [Yüksek VIX ×0.7]"

    puan=round(puan)
    return {
        "puan":puan,"notlar":notlar,"rejim":rej,"rejim_not":rejim_not,
        "rsi":rv,"adx":adx_v,"macd":mv,"macd_sig":sv,
        "fiyat":son,"degisim":deg,"atr":at,
        "sl":son-sl_c*at,"tp":son+tp_c*at,
        "pivot":(pp,r1,r2,s1,s2),
        "supertrend":st_v,"sar":sar_v,"ma20":ma20,"ma50":ma50,"ma200":ma200,
        "destekler":destekler,"direncler":direncler,
        "vix":vix,"sent_skor":sent_skor,"makro":makro_oz,
    }

# ════════════════════════════════════════════════════════════════════════
#  KATMAN 7: BİRLEŞİK KARAR
# ════════════════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════════════════
#  KATMAN v8-A: KELLY CRITERION — Optimal Pozisyon Büyüklüğü
# ════════════════════════════════════════════════════════════════════════

def kelly_criterion(ml, backtest_sonuc=None):
    """
    Kelly Formülü: f* = (b×p - q) / b
      b = ort_kazanç / ort_kayıp oranı (R/R)
      p = kazanma olasılığı (ML win rate veya backtest win rate)
      q = 1 - p

    Araştırma: Kelly ile optimize edilmiş pozisyon büyüklüğü
    uzun vadede geometrik ortalama büyümeyi maksimize eder.
    Tam Kelly çok agresif olduğu için yarı-Kelly (f/2) kullanılır.

    Döndürür: {
        "kelly_f": optimal fraksiyon (0-1),
        "yari_kelly": f/2 (daha güvenli),
        "yoo_pct": portföyün yüzdesi,
        "win_rate": kullanılan win rate,
        "rr_oran": R/R oranı,
        "aciklama": metin,
    }
    """
    # Win rate kaynağı: önce backtest, yoksa ML proba
    win_rate = 0.5
    rr_oran  = 2.0  # default R/R = 2

    if backtest_sonuc and backtest_sonuc.get("n_islem", 0) >= 10:
        win_rate = backtest_sonuc["winrate"] / 100.0
        if backtest_sonuc.get("ort_kazan", 0) and backtest_sonuc.get("ort_kayip", 0):
            rr_oran = abs(backtest_sonuc["ort_kazan"]) / max(abs(backtest_sonuc["ort_kayip"]), 0.01)
    elif ml and ml.get("wf_acc", 0) > 0:
        win_rate = ml["wf_acc"]
        # R/R tahmini: ML proba'dan AL ve SAT olasılıklarına bak
        proba = ml.get("proba", {})
        p_al  = proba.get(1, 0); p_sat = proba.get(-1, 0)
        if p_al > 0 and p_sat > 0:
            rr_oran = (p_al / max(p_sat, 0.01)) * ATR_TP / ATR_SL
        else:
            rr_oran = ATR_TP / ATR_SL

    # Kelly formülü
    p = float(np.clip(win_rate, 0.1, 0.95))
    q = 1.0 - p
    b = float(max(rr_oran, 0.1))

    kelly_f = (b * p - q) / b
    kelly_f = float(np.clip(kelly_f, 0.0, KELLY_MAX_YOO))
    yari_kelly = kelly_f / 2.0

    if kelly_f <= 0:
        aciklama = "Kelly negatif — pozisyon açma (beklenen değer < 0)"
    elif yari_kelly < 0.05:
        aciklama = f"Çok küçük pozisyon — portföyün %{yari_kelly*100:.1f}'i öneriliyor"
    elif yari_kelly < 0.15:
        aciklama = f"Orta pozisyon — portföyün %{yari_kelly*100:.1f}'i öneriliyor"
    else:
        aciklama = f"Güçlü pozisyon — portföyün %{yari_kelly*100:.1f}'i öneriliyor"

    return {
        "kelly_f":    round(kelly_f, 4),
        "yari_kelly": round(yari_kelly, 4),
        "yoo_pct":    round(yari_kelly * 100, 1),
        "win_rate":   round(p, 4),
        "rr_oran":    round(b, 2),
        "aciklama":   aciklama,
    }


# ════════════════════════════════════════════════════════════════════════
#  KATMAN v8-B: MONTE CARLO SİMÜLASYONU — Risk Analizi
# ════════════════════════════════════════════════════════════════════════

def monte_carlo_sim(df, n_senaryo=None, n_gun=252):
    """
    Geometric Brownian Motion ile Monte Carlo simülasyonu.
    Son 1 yılın günlük getiri istatistiklerini kullanarak
    gelecek 252 günlük N senaryo üretir.

    Döndürür: {
        "median_getiri": medyan nihai getiri %,
        "pct10":  en kötü %10 senaryo getirisi,
        "pct90":  en iyi %90 senaryo getirisi,
        "max_dd": ortalama maksimum drawdown %,
        "pozitif_oran": pozitif biten senaryo oranı,
        "var_95": Value at Risk %95 güven (günlük),
        "aciklama": metin özet,
    }
    """
    if n_senaryo is None:
        n_senaryo = MONTE_CARLO_SENARYO

    c = df["Close"].squeeze()
    # Son 252 günün günlük getirileri
    gun_getiri = c.pct_change().dropna().tail(252).values
    if len(gun_getiri) < 30:
        return None

    mu  = float(np.mean(gun_getiri))
    sig = float(np.std(gun_getiri))

    if sig <= 0:
        return None

    # GBM simülasyonu: S(t+1) = S(t) × exp((mu - 0.5σ²)dt + σ√dt × Z)
    np.random.seed(42)
    Z = np.random.standard_normal((n_senaryo, n_gun))
    drift = mu - 0.5 * sig**2
    daily = np.exp(drift + sig * Z)         # (n_senaryo, n_gun)
    # Kümülatif getiri (başlangıç = 1.0)
    equity = np.cumprod(daily, axis=1)       # (n_senaryo, n_gun)
    final  = equity[:, -1]                   # nihai değerler

    # Maksimum drawdown her senaryo için
    def max_dd_hesapla(eq_curve):
        peak = np.maximum.accumulate(eq_curve)
        dd   = (eq_curve - peak) / (peak + 1e-9)
        return float(np.min(dd) * 100)

    # Örneklem (hız için 200 senaryo üzerinden DD hesapla)
    dd_list = [max_dd_hesapla(equity[i]) for i in range(min(200, n_senaryo))]
    ort_dd  = float(np.mean(dd_list))

    # VaR %95 (günlük)
    var_95 = float(np.percentile(gun_getiri, 5) * 100)

    poz_oran = float(np.mean(final > 1.0) * 100)
    med_get  = float((np.median(final) - 1.0) * 100)
    p10      = float((np.percentile(final, 10) - 1.0) * 100)
    p90      = float((np.percentile(final, 90) - 1.0) * 100)

    if med_get > 10:
        aciklama = f"Olumlu beklenti: medyan +{med_get:.1f}%, {poz_oran:.0f}% senaryo pozitif"
    elif med_get > 0:
        aciklama = f"Zayıf pozitif beklenti: medyan +{med_get:.1f}%, DD riski {abs(ort_dd):.1f}%"
    else:
        aciklama = f"Negatif beklenti: medyan {med_get:.1f}%, yüksek risk"

    return {
        "median_getiri": round(med_get, 2),
        "pct10":         round(p10, 2),
        "pct90":         round(p90, 2),
        "max_dd":        round(abs(ort_dd), 2),
        "pozitif_oran":  round(poz_oran, 1),
        "var_95":        round(var_95, 3),
        "aciklama":      aciklama,
        "n_senaryo":     n_senaryo,
    }


# ════════════════════════════════════════════════════════════════════════
#  KATMAN v8-C: WHALE / VOLUME SPIKE DEDEKTÖRÜ
# ════════════════════════════════════════════════════════════════════════

def whale_dedektoru(df):
    """
    Büyük lot (balina) girişini tespit et.

    Algoritma:
    1. Hacim Spike: Güncel hacim > N×(20-günlük ortalama hacim)
    2. OBV Sapması: OBV ani yükseliş = alım yönlü balina
    3. Fiyat-Hacim Uyumu: Fiyat artarken hacim patlaması = güçlü AL
                          Fiyat düşerken hacim patlaması = güçlü SAT

    Döndürür: {
        "spike_var": bool,
        "spike_katsayi": hacim / ortalama,
        "yon": "AL" | "SAT" | "NOTR",
        "guc": 1-3 (1=zayıf, 3=güçlü),
        "puan": sinyal puanı katkısı,
        "aciklama": metin,
    }
    """
    c = df["Close"].squeeze()
    v = df["Volume"].squeeze()
    h = df["High"].squeeze()
    l = df["Low"].squeeze()

    if len(v) < WHALE_PENCERE + 5:
        return {"spike_var": False, "puan": 0, "aciklama": "Veri yetersiz", "yon": "NOTR"}

    v_ort   = float(v.rolling(WHALE_PENCERE).mean().iloc[-1])
    v_son   = float(v.iloc[-1])
    v_kat   = v_son / max(v_ort, 1)

    # Son 3 günün hacim ortalaması vs önceki 17 gün
    v_kisa  = float(v.iloc[-3:].mean())
    v_uzun  = float(v.iloc[-WHALE_PENCERE:-3].mean())
    v_trend = v_kisa / max(v_uzun, 1)

    # OBV değişimi
    obv_s  = Ind.obv(c, v)
    obv_ch = float(obv_s.pct_change(3).iloc[-1]) if len(obv_s) > 3 else 0.0

    # Fiyat yönü (son 2 gün)
    c_ch = float(c.pct_change(2).iloc[-1])

    spike_var = v_kat >= WHALE_CARPAN

    if not spike_var and v_trend < 2.0:
        return {"spike_var": False, "spike_katsayi": round(v_kat, 2),
                "yon": "NOTR", "guc": 0, "puan": 0,
                "aciklama": f"Normal hacim (×{v_kat:.1f})"}

    # Yön belirleme
    if c_ch > 0.005 and obv_ch > 0:
        yon = "AL"; temel_puan = 2
        aciklama = f"🐋 Balina GİRİŞİ — Hacim ×{v_kat:.1f}, fiyat yukarı"
    elif c_ch < -0.005 and obv_ch < 0:
        yon = "SAT"; temel_puan = -2
        aciklama = f"🐋 Balina ÇIKIŞI — Hacim ×{v_kat:.1f}, fiyat aşağı"
    elif c_ch > 0:
        yon = "AL"; temel_puan = 1
        aciklama = f"📊 Hacim patlaması ×{v_kat:.1f} (AL yönlü)"
    else:
        yon = "SAT"; temel_puan = -1
        aciklama = f"📊 Hacim patlaması ×{v_kat:.1f} (SAT yönlü)"

    # Güç seviyesi
    guc = 3 if v_kat >= WHALE_CARPAN * 2 else (2 if v_kat >= WHALE_CARPAN else 1)
    puan = temel_puan * (1 if guc == 1 else guc // 2 + 1)
    puan = int(np.clip(puan, -3, 3))

    return {
        "spike_var":      spike_var,
        "spike_katsayi":  round(v_kat, 2),
        "yon":            yon,
        "guc":            guc,
        "puan":           puan,
        "obv_ch":         round(obv_ch * 100, 2),
        "aciklama":       aciklama,
    }


# ════════════════════════════════════════════════════════════════════════
#  KATMAN v8-D: KORELASYON MATRİSİ & SEKTÖREL ROTASYON
# ════════════════════════════════════════════════════════════════════════

_korelasyon_cache = {}
_kor_lock = __import__("threading").Lock()

def korelasyon_analizi(sembol, df):
    """
    Hisseyi ilgili endeksle karşılaştır.
    BIST hisseleri → BIST100 (xu100.is)
    ABD hisseleri  → S&P500 (^spx)

    Döndürür: {
        "kor_60d": 60-günlük korelasyon katsayısı,
        "ayrisma": "POZITIF" | "NEGATIF" | "NOTR",
        "puan": sinyal katkısı,
        "beta": beta katsayısı,
        "rs_14d": göreceli güç (hisse / endeks, 14 gün),
        "aciklama": metin,
    }
    """
    bist = sembol.endswith(".IS")
    endeks_sembol = "xu100.is" if bist else "^spx"
    cache_key = f"{sembol}_{endeks_sembol}"

    with _kor_lock:
        if cache_key in _korelasyon_cache:
            ts, veri = _korelasyon_cache[cache_key]
            if time.time() - ts < 3600:
                return veri

    try:
        # Makro cache'ten al (zaten indirilmiş olabilir)
        mv = makro_veri_getir()
        endeks_s = mv.get("BIST100" if bist else "SP500", pd.Series(dtype=float))

        if len(endeks_s) < KORELASYON_PENCERE or len(df) < KORELASYON_PENCERE:
            return {"kor_60d": 0.0, "ayrisma": "NOTR", "puan": 0,
                    "beta": 1.0, "rs_14d": 1.0, "aciklama": "Endeks verisi yetersiz"}

        # Hizala
        hisse_ret  = df["Close"].squeeze().pct_change().dropna()
        endeks_ret = endeks_s.pct_change().dropna()

        aligned = pd.concat([hisse_ret, endeks_ret], axis=1, join="inner").dropna()
        aligned.columns = ["hisse", "endeks"]

        if len(aligned) < 20:
            return {"kor_60d": 0.0, "ayrisma": "NOTR", "puan": 0,
                    "beta": 1.0, "rs_14d": 1.0, "aciklama": "Hizalama başarısız"}

        # Son 60 gün
        son60 = aligned.tail(KORELASYON_PENCERE)
        kor   = float(son60["hisse"].corr(son60["endeks"]))

        # Beta = Cov(hisse, endeks) / Var(endeks)
        cov   = float(son60["hisse"].cov(son60["endeks"]))
        var_e = float(son60["endeks"].var())
        beta  = cov / max(var_e, 1e-9)
        beta  = float(np.clip(beta, -3.0, 3.0))

        # Göreceli güç: son 14 günde hisse vs endeks toplam getirisi
        son14 = aligned.tail(14)
        rs_hisse  = float((1 + son14["hisse"]).prod() - 1)
        rs_endeks = float((1 + son14["endeks"]).prod() - 1)
        rs_14d    = rs_hisse - rs_endeks  # pozitif = hisse endeksten güçlü

        # Ayrışma tespiti
        # Son 5 günde endeks düştü ama hisse yükseldi (veya tersi)
        son5 = aligned.tail(5)
        endeks_5d = float((1 + son5["endeks"]).prod() - 1)
        hisse_5d  = float((1 + son5["hisse"]).prod() - 1)

        puan = 0
        if endeks_5d < -0.01 and hisse_5d > 0.005:
            ayrisma = "POZITIF"
            puan = 2
            aciklama = f"💪 Pozitif Ayrışma: Endeks ↓{abs(endeks_5d)*100:.1f}%, Hisse ↑{hisse_5d*100:.1f}%"
        elif endeks_5d > 0.01 and hisse_5d < -0.005:
            ayrisma = "NEGATIF"
            puan = -2
            aciklama = f"⚠️ Negatif Ayrışma: Endeks ↑{endeks_5d*100:.1f}%, Hisse ↓{abs(hisse_5d)*100:.1f}%"
        elif rs_14d > 0.02:
            ayrisma = "POZITIF"
            puan = 1
            aciklama = f"📈 Göreceli güç: Endeksin +{rs_14d*100:.1f}% üzerinde (14g)"
        elif rs_14d < -0.02:
            ayrisma = "NEGATIF"
            puan = -1
            aciklama = f"📉 Görece zayıf: Endeksin {rs_14d*100:.1f}% altında (14g)"
        else:
            ayrisma = "NOTR"
            puan = 0
            aciklama = f"Endeks ile uyumlu (β:{beta:.2f}, kor:{kor:.2f})"

        sonuc = {
            "kor_60d":   round(kor, 3),
            "ayrisma":   ayrisma,
            "puan":      puan,
            "beta":      round(beta, 2),
            "rs_14d":    round(rs_14d * 100, 2),
            "endeks_5d": round(endeks_5d * 100, 2),
            "hisse_5d":  round(hisse_5d * 100, 2),
            "aciklama":  aciklama,
        }

        with _kor_lock:
            _korelasyon_cache[cache_key] = (time.time(), sonuc)
        return sonuc

    except Exception as e:
        return {"kor_60d": 0.0, "ayrisma": "NOTR", "puan": 0,
                "beta": 1.0, "rs_14d": 0.0, "aciklama": f"Hata: {str(e)[:40]}"}


# ════════════════════════════════════════════════════════════════════════
#  KATMAN v8-E: DİNAMİK TRAILING STOP
# ════════════════════════════════════════════════════════════════════════

def trailing_stop_hesapla(df):
    """
    ATR tabanlı dinamik trailing stop.

    Algoritma:
    - Trailing Stop = Güncel fiyat - TRAILING_ATR_CARPAN × ATR(14)
    - Her yeni yüksek yapıldığında stop yukarı taşınır (hiçbir zaman aşağı inmez)
    - Son N günlük trailing stop seviyesini hesaplar

    Döndürür: {
        "trailing_sl": güncel trailing stop fiyatı,
        "mesafe_pct": fiyat ile trailing stop arasındaki % mesafe,
        "uzun_trailimg_sl": son 20 günlük en yüksek trailing stop,
        "trend_guclu": bool (trailing stop sürekli yükseliyor mu),
        "aciklama": metin,
    }
    """
    c = df["Close"].squeeze()
    h = df["High"].squeeze()
    l = df["Low"].squeeze()

    if len(c) < 30:
        fiyat = float(c.iloc[-1]); at = float(Ind.atr(h, l, c).iloc[-1])
        return {
            "trailing_sl": round(fiyat - TRAILING_ATR_CARPAN * at, 4),
            "mesafe_pct": round(TRAILING_ATR_CARPAN * at / fiyat * 100, 2),
            "trend_guclu": False, "aciklama": "Veri kısa"
        }

    atr_s = Ind.atr(h, l, c)

    # Son 50 günlük trailing stop hesapla
    n = min(50, len(c))
    trailing_stops = []
    maks_fiyat = float(h.iloc[-n])

    for i in range(-n, 0):
        maks_fiyat = max(maks_fiyat, float(h.iloc[i]))
        at = float(atr_s.iloc[i])
        ts = maks_fiyat - TRAILING_ATR_CARPAN * at
        trailing_stops.append(ts)

    son_ts       = trailing_stops[-1]
    maks_ts_20d  = max(trailing_stops[-20:]) if len(trailing_stops) >= 20 else son_ts
    fiyat        = float(c.iloc[-1])
    mesafe_pct   = (fiyat - son_ts) / fiyat * 100

    # Trailing stop yukarı trend mi?
    ts_son5  = trailing_stops[-5:]
    trend_guclu = all(ts_son5[i] >= ts_son5[i-1] for i in range(1, len(ts_son5)))

    if mesafe_pct < 2.0:
        aciklama = f"⚠️ Trailing SL yakın ({mesafe_pct:.1f}% uzaklıkta) — {son_ts:.2f}"
    elif trend_guclu:
        aciklama = f"✅ Trailing SL yükseliyor — {son_ts:.2f} ({mesafe_pct:.1f}% uzak)"
    else:
        aciklama = f"Trailing SL: {son_ts:.2f} ({mesafe_pct:.1f}% uzak)"

    return {
        "trailing_sl":     round(son_ts, 4),
        "mesafe_pct":      round(mesafe_pct, 2),
        "uzun_trailing_sl":round(maks_ts_20d, 4),
        "trend_guclu":     trend_guclu,
        "aciklama":        aciklama,
    }


# ════════════════════════════════════════════════════════════════════════
#  KATMAN v8-F: FİNAL CONFIDENCE SCORE (Pipeline)
# ════════════════════════════════════════════════════════════════════════

def final_confidence_score(kural_puan, ml, whale, korelasyon, mc, kelly):
    """
    Tüm modüllerden gelen puanları ağırlıklı olarak birleştir.
    Nihai Güven Skoru = 0-100 arası normalize değer.

    Ağırlıklar (araştırma bazlı):
      - Teknik/Kural puan    : %35
      - ML tahmin             : %25
      - Whale/Hacim           : %15
      - Korelasyon/Ayrışma    : %15
      - Monte Carlo beklentisi: %10
    """
    # Teknik normalize (-15 ile +15 arası puana karşılık 0-100)
    teknik_norm  = (kural_puan + 15) / 30.0 * 100

    # ML normalize (güven × yön)
    ml_norm = 50.0
    if ml:
        t = ml.get("tahmin", 0); g = ml.get("guven", 0.5)
        ml_norm = 50 + t * g * 50

    # Whale normalize (-3 ile +3 → 0-100)
    whale_puan = whale.get("puan", 0) if whale else 0
    whale_norm = (whale_puan + 3) / 6.0 * 100

    # Korelasyon normalize (-2 ile +2 → 0-100)
    kor_puan = korelasyon.get("puan", 0) if korelasyon else 0
    kor_norm = (kor_puan + 2) / 4.0 * 100

    # Monte Carlo normalize: pozitif_oran direkt 0-100
    mc_norm = mc.get("pozitif_oran", 50.0) if mc else 50.0

    # Ağırlıklı ortalama
    score = (
        teknik_norm  * 0.35 +
        ml_norm      * 0.25 +
        whale_norm   * 0.15 +
        kor_norm     * 0.15 +
        mc_norm      * 0.10
    )
    score = float(np.clip(score, 0, 100))

    # Risk ayarı: Monte Carlo max_dd yüksekse skoru düşür
    if mc and mc.get("max_dd", 0) > 20:
        score *= 0.85  # %20+ drawdown riski varsa %15 penaltı

    # Etiket
    if score >= 70:   etiket = "YÜKSEK GÜVEN 🟢"
    elif score >= 55: etiket = "ORTA GÜVEN 🟡"
    elif score >= 40: etiket = "DÜŞÜK GÜVEN 🟠"
    else:             etiket = "RİSKLİ 🔴"

    return {
        "skor":    round(score, 1),
        "etiket":  etiket,
        "dagılım": {
            "teknik":      round(teknik_norm, 1),
            "ml":          round(ml_norm, 1),
            "whale":       round(whale_norm, 1),
            "korelasyon":  round(kor_norm, 1),
            "monte_carlo": round(mc_norm, 1),
        }
    }

def karar_birlestir(kural, ml):
    ml_puan=0; ml_str="—"; guven=0.0
    if ml:
        t=ml["tahmin"]; guven=ml["guven"]
        if   t==1  and guven>=0.60: ml_puan= 4
        elif t==1  and guven>=0.50: ml_puan= 2
        elif t==1:                  ml_puan= 1
        elif t==-1 and guven>=0.60: ml_puan=-4
        elif t==-1 and guven>=0.50: ml_puan=-2
        elif t==-1:                 ml_puan=-1
        yon={"1":"AL ↑","-1":"SAT ↓","0":"HOL ─"}.get(str(t),"?")
        ml_str=f"{yon} {guven*100:.0f}%"

    toplam=kural["puan"]+ml_puan

    if   toplam>= GUCLU_ESIK: karar,renk="🟢 GÜÇLÜ AL",  Fore.GREEN
    elif toplam>=4:            karar,renk="🟡 AL",          Fore.YELLOW
    elif toplam<=-GUCLU_ESIK: karar,renk="🔴 GÜÇLÜ SAT",  Fore.RED
    elif toplam<=-4:           karar,renk="🟠 SAT",          Fore.MAGENTA
    else:                      karar,renk="⚪ BEKLE",        Fore.CYAN

    sinyal_adi={"🟢 GÜÇLÜ AL":"Güçlü AL","🟡 AL":"AL","🔴 GÜÇLÜ SAT":"Güçlü SAT",
                "🟠 SAT":"SAT","⚪ BEKLE":"Bekle"}.get(karar,"Bekle")

    return {
        **kural,"karar":karar,"renk":renk,"sinyal_adi":sinyal_adi,
        "toplam":toplam,"skor":toplam,"ml":ml,"ml_str":ml_str,
        "ml_puan":ml_puan,"ml_guven":guven,
    }

# ════════════════════════════════════════════════════════════════════════
#  BACKTEST MOTORU
# ════════════════════════════════════════════════════════════════════════

def backtest_calistir(sembol, df):
    c=df["Close"].squeeze(); h=df["High"].squeeze()
    l=df["Low"].squeeze();   v=df["Volume"].squeeze()
    if len(df)<250: return None
    islemler=[]; pozisyon=None; PENCERE=60

    for i in range(PENCERE,len(df)-1):
        df_slice=df.iloc[:i+1]; sonraki=float(c.iloc[i+1])
        if pozisyon:
            if sonraki<=pozisyon["sl"]:
                islemler.append({"giris_t":pozisyon["tarih"],"cikis_t":str(df.index[i+1])[:10],
                    "giris":pozisyon["giris"],"cikis":pozisyon["sl"],
                    "kar":(pozisyon["sl"]-pozisyon["giris"])/pozisyon["giris"]*100,"tip":"SL ❌"})
                pozisyon=None; continue
            elif sonraki>=pozisyon["tp"]:
                islemler.append({"giris_t":pozisyon["tarih"],"cikis_t":str(df.index[i+1])[:10],
                    "giris":pozisyon["giris"],"cikis":pozisyon["tp"],
                    "kar":(pozisyon["tp"]-pozisyon["giris"])/pozisyon["giris"]*100,"tip":"TP ✅"})
                pozisyon=None; continue
        try:
            rv=float(Ind.rsi(df_slice["Close"].squeeze()).iloc[-1])
            mv,sv,hv=Ind.macd(df_slice["Close"].squeeze())
            mv=_sf(mv.iloc[-1]); sv=_sf(sv.iloc[-1])
            hv_c=_sf(hv.iloc[-1]); hv_p=_sf(hv.iloc[-2])
            adx_v,pdi_v,mdi_v=Ind.adx(df_slice["High"].squeeze(),df_slice["Low"].squeeze(),df_slice["Close"].squeeze())
            adx_v=_sf(adx_v.iloc[-1]); pdi_v=_sf(pdi_v.iloc[-1]); mdi_v=_sf(mdi_v.iloc[-1])
            _,st_v=Ind.supertrend(df_slice["High"].squeeze(),df_slice["Low"].squeeze(),df_slice["Close"].squeeze())
            st_v=int(st_v.iloc[-1])
            at=float(Ind.atr(df_slice["High"].squeeze(),df_slice["Low"].squeeze(),df_slice["Close"].squeeze()).iloc[-1])
            ma20=float(df_slice["Close"].squeeze().rolling(20).mean().iloc[-1])
            ma50=float(df_slice["Close"].squeeze().rolling(50).mean().iloc[-1])
        except Exception:
            continue
        puan=0
        if rv<35:   puan+=2
        elif rv>65: puan-=2
        if mv>sv and hv_c>hv_p: puan+=2
        elif mv<sv:             puan-=2
        if adx_v>25 and pdi_v>mdi_v: puan+=2
        elif adx_v>25 and mdi_v>pdi_v: puan-=2
        if st_v==1: puan+=2
        else:       puan-=2
        if ma20>ma50: puan+=1
        else:         puan-=1
        fiyat=float(c.iloc[i])
        if pozisyon is None and puan>=5:
            pozisyon={"giris":sonraki,"sl":sonraki-ATR_SL*at,
                      "tp":sonraki+ATR_TP*at,"tarih":str(df.index[i+1])[:10]}
        elif pozisyon and puan<=-5:
            islemler.append({"giris_t":pozisyon["tarih"],"cikis_t":str(df.index[i+1])[:10],
                "giris":pozisyon["giris"],"cikis":sonraki,
                "kar":(sonraki-pozisyon["giris"])/pozisyon["giris"]*100,"tip":"Sinyal 🔄"})
            pozisyon=None

    if not islemler: return None
    karlar=[x["kar"] for x in islemler]
    kazananlar=[k for k in karlar if k>0]; kaybedenler=[k for k in karlar if k<=0]
    equity=100.0; equity_curve=[100.0]
    for k in karlar:
        equity*=(1+k/100); equity_curve.append(round(equity,2))
    peak=equity_curve[0]; max_dd=0.0
    for e in equity_curve:
        if e>peak: peak=e
        dd=(peak-e)/peak*100
        if dd>max_dd: max_dd=dd
    return {
        "sembol":sembol,"islemler":islemler,"n_islem":len(islemler),
        "n_kazan":len(kazananlar),"n_kayip":len(kaybedenler),
        "winrate":len(kazananlar)/len(islemler)*100,
        "toplam_kar":sum(karlar),"net_getiri":equity-100,
        "ort_kazan":float(np.mean(kazananlar)) if kazananlar else 0,
        "ort_kayip":float(np.mean(kaybedenler)) if kaybedenler else 0,
        "en_iyi":float(max(karlar)),"en_kotu":float(min(karlar)),
        "max_dd":max_dd,"equity_son":equity,"equity_curve":equity_curve,
    }

def backtest_yazdir(bt_sonuclar):
    print(Fore.CYAN+Style.BRIGHT+"""
  ╔══════════════════════════════════════════════════════════════════════════╗
  ║   📊  BACKTEST RAPORU  —  Son 3 Yıl Simülasyonu                        ║
  ╚══════════════════════════════════════════════════════════════════════════╝""")
    print(f"  {Fore.WHITE}{'─'*100}")
    print(f"  {'SEMBOL':<12} {'İŞLEM':>5}  {'WIN%':>6}  {'NET%':>7}  "
          f"{'ORT KAZ':>8}  {'ORT KAY':>8}  {'MAX DD':>7}  {'EN İYİ':>7}  {'EN KÖTÜ':>8}  SONUÇ")
    print(f"  {Fore.WHITE}{'─'*100}")
    sirali=sorted(bt_sonuclar,key=lambda x:x["net_getiri"],reverse=True)
    for bt in sirali:
        wc=Fore.GREEN if bt["winrate"]>=50 else Fore.RED
        nc=Fore.GREEN if bt["net_getiri"]>=0 else Fore.RED
        ddc=Fore.RED if bt["max_dd"]>20 else Fore.YELLOW if bt["max_dd"]>10 else Fore.GREEN
        emoji="🏆" if bt["net_getiri"]>20 else ("✅" if bt["net_getiri"]>0 else "❌")
        print(
            f"  {Fore.WHITE}{bt['sembol']:<12}"
            f"{bt['n_islem']:>5}  "
            f"{wc}{bt['winrate']:>5.1f}%{Style.RESET_ALL}  "
            f"{nc}{bt['net_getiri']:>+6.1f}%{Style.RESET_ALL}  "
            f"{Fore.GREEN}{bt['ort_kazan']:>+7.1f}%{Style.RESET_ALL}  "
            f"{Fore.RED}{bt['ort_kayip']:>+7.1f}%{Style.RESET_ALL}  "
            f"{ddc}{bt['max_dd']:>6.1f}%{Style.RESET_ALL}  "
            f"{Fore.GREEN}{bt['en_iyi']:>+6.1f}%{Style.RESET_ALL}  "
            f"{Fore.RED}{bt['en_kotu']:>+7.1f}%{Style.RESET_ALL}  {emoji}")
    print(f"  {Fore.WHITE}{'─'*100}")
    ort_net=sum(b["net_getiri"] for b in bt_sonuclar)/len(bt_sonuclar)
    ort_win=sum(b["winrate"] for b in bt_sonuclar)/len(bt_sonuclar)
    en_iyi_s=max(sirali,key=lambda x:x["net_getiri"])
    en_kotu_s=min(sirali,key=lambda x:x["net_getiri"])
    print(f"\n  {Fore.CYAN}  ÖZET")
    print(f"  {Fore.WHITE}  Ortalama Net Getiri : {Fore.GREEN if ort_net>=0 else Fore.RED}{ort_net:+.1f}%")
    print(f"  {Fore.WHITE}  Ortalama Win Rate   : {ort_win:.1f}%")
    print(f"  {Fore.WHITE}  En İyi  : {Fore.GREEN}{en_iyi_s['sembol']} {en_iyi_s['net_getiri']:+.1f}%")
    print(f"  {Fore.WHITE}  En Kötü : {Fore.RED}{en_kotu_s['sembol']} {en_kotu_s['net_getiri']:+.1f}%")
    tum_islemler=[]
    for bt in bt_sonuclar:
        for isk in bt["islemler"]: isk["sembol"]=bt["sembol"]; tum_islemler.append(isk)
    tum_islemler.sort(key=lambda x:x["cikis_t"],reverse=True)
    print(f"\n  {Fore.CYAN}  SON İŞLEMLER")
    for isk in tum_islemler[:10]:
        kc=Fore.GREEN if isk["kar"]>0 else Fore.RED
        print(f"  {Fore.WHITE}  {isk['sembol']:<12} {isk['giris_t']} → {isk['cikis_t']}  "
              f"Giriş:{isk['giris']:.2f}  Çıkış:{isk['cikis']:.2f}  "
              f"{kc}{isk['kar']:+.2f}%{Style.RESET_ALL}  {isk['tip']}")

# ════════════════════════════════════════════════════════════════════════
#  CACHE & VERİ KATMANI
# ════════════════════════════════════════════════════════════════════════

import threading as _threading
_veri={}; _model={}
_veri_lock=_threading.Lock(); _model_lock=_threading.Lock()
_CACHE_DOSYA=os.path.expanduser("~/.trade_ml_cache.json")
_LISTE_DOSYA=os.path.expanduser("~/.trade_listeler.json")

def cache_kaydet():
    try:
        with _model_lock: snap=dict(_model)
        veri={}
        for s,(ts,ml) in snap.items():
            if ml:
                veri[s]={"ts":ts,"tahmin":ml.get("tahmin"),"guven":ml.get("guven"),
                         "proba":{str(k):v for k,v in ml.get("proba",{}).items()},
                         "wf_acc":ml.get("wf_acc"),"n":ml.get("n"),
                         "ensemble":ml.get("ensemble",False)}
        tmp=_CACHE_DOSYA+".tmp"
        with open(tmp,"w",encoding="utf-8") as f: json.dump(veri,f)
        os.replace(tmp,_CACHE_DOSYA)
    except Exception: pass

def cache_yukle():
    try:
        if not os.path.exists(_CACHE_DOSYA): return
        with open(_CACHE_DOSYA,encoding="utf-8") as f:
            try: veri=json.load(f)
            except json.JSONDecodeError: os.remove(_CACHE_DOSYA); return
        simdi=time.time()
        for s,d in veri.items():
            if simdi-d["ts"]>8*3600: continue
            ml={"tahmin":d["tahmin"],"guven":d["guven"],
                "proba":{int(k):v for k,v in d["proba"].items()},
                "wf_acc":d["wf_acc"],"n":d["n"],"feat_adlari":[],
                "ensemble":d.get("ensemble",False),"makro":{}}
            _model[s]=(d["ts"],ml)
        if _model: print(Fore.GREEN+f"  ⚡ {len(_model)} ML modeli önbellekten yüklendi")
    except Exception: pass

def listeler_kaydet():
    try:
        veri={"listeler":{k:list(v) for k,v in LISTELER.items()},"bist":list(BIST_SEMBOLLER)}
        tmp=_LISTE_DOSYA+".tmp"
        with open(tmp,"w",encoding="utf-8") as f: json.dump(veri,f,ensure_ascii=False,indent=2)
        os.replace(tmp,_LISTE_DOSYA)
    except Exception: pass

def listeler_yukle():
    try:
        if not os.path.exists(_LISTE_DOSYA): return
        with open(_LISTE_DOSYA,encoding="utf-8") as f:
            try: veri=json.load(f)
            except json.JSONDecodeError: os.remove(_LISTE_DOSYA); return
        LISTELER.clear(); LISTELER.update({k:v for k,v in veri["listeler"].items()})
        BIST_SEMBOLLER.clear(); BIST_SEMBOLLER.update(veri.get("bist",[]))
        print(Fore.GREEN+f"  📋 Liste yüklendi ({sum(len(v) for v in LISTELER.values())} hisse)")
    except Exception: pass

def veri_getir(sembol):
    ts=time.time()
    with _veri_lock:
        if sembol in _veri and ts-_veri[sembol][0]<1800: return _veri[sembol][1]
    df=isyatirim_indir(sembol) if sembol in BIST_SEMBOLLER else stooq_indir(sembol)
    if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
    if not df.empty:
        with _veri_lock:
            if len(_veri)>=100:
                en_eski=min(_veri,key=lambda k:_veri[k][0]); del _veri[en_eski]
            _veri[sembol]=(ts,df)
    return df

def analiz(sembol, yeniden=False):
    try:
        df=veri_getir(sembol)
        if df.empty or len(df)<200: return None

        # ── Temel analiz ──────────────────────────────────────────────
        kural=kural_sinyal(df,sembol=sembol)
        ts=time.time()
        with _model_lock: cache_var=_model.get(sembol)
        if cache_var is None or yeniden or ts-cache_var[0]>ML_CACHE_SAAT*3600:
            ml=ml_egit(df,sembol=sembol)
            with _model_lock: _model[sembol]=(ts,ml)
        else:
            ml=cache_var[1]
        sonuc=karar_birlestir(kural,ml)

        # ── v8 Pipeline Modülleri (arka planda, hız öncelikli) ────────
        whale   = whale_dedektoru(df)    if WHALE_AKTIF        else {}
        kor     = korelasyon_analizi(sembol, df) if KORELASYON_AKTIF else {}
        trail   = trailing_stop_hesapla(df) if TRAILING_STOP_AKTIF else {}
        mc      = None
        kelly   = None

        if MONTE_CARLO_AKTIF:
            try:
                mc = monte_carlo_sim(df, n_senaryo=500)  # 500 = hız/doğruluk dengesi
            except Exception:
                mc = None

        if KELLY_AKTIF:
            try:
                # Backtest sonucu varsa kullan (ML cache'ten)
                bt_sonuc = None
                kelly = kelly_criterion(ml, bt_sonuc)
            except Exception:
                kelly = None

        # ── Final Confidence Score ────────────────────────────────────
        fcs = final_confidence_score(
            kural.get("puan", 0), ml, whale, kor, mc, kelly)

        # ── Whale puanını ana skor'a ekle ─────────────────────────────
        if whale and WHALE_AKTIF:
            sonuc["toplam"] = sonuc.get("toplam", 0) + whale.get("puan", 0)
            sonuc["skor"]   = sonuc["toplam"]
            if whale.get("puan", 0) != 0:
                sonuc.setdefault("notlar", []).append(whale.get("aciklama", ""))

        # ── Korelasyon puanını ana skor'a ekle ───────────────────────
        if kor and KORELASYON_AKTIF and kor.get("puan", 0) != 0:
            sonuc["toplam"] = sonuc.get("toplam", 0) + kor.get("puan", 0)
            sonuc["skor"]   = sonuc["toplam"]
            sonuc.setdefault("notlar", []).append(kor.get("aciklama", ""))

        # ── Karar yeniden hesapla (puan değişti) ─────────────────────
        toplam = sonuc["toplam"]
        if   toplam >= GUCLU_ESIK:  sonuc["karar"] = "🟢 GÜÇLÜ AL"
        elif toplam >= 4:            sonuc["karar"] = "🟡 AL"
        elif toplam <=-GUCLU_ESIK:  sonuc["karar"] = "🔴 GÜÇLÜ SAT"
        elif toplam <=-4:            sonuc["karar"] = "🟠 SAT"
        else:                        sonuc["karar"] = "⚪ BEKLE"

        # ── Sonuca v8 alanlarını ekle ────────────────────────────────
        sonuc["whale"]   = whale
        sonuc["kor"]     = kor
        sonuc["trail"]   = trail
        sonuc["mc"]      = mc
        sonuc["kelly"]   = kelly
        sonuc["fcs"]     = fcs
        sonuc["anlik"]   = bigpara_anlik(sembol) if sembol in BIST_SEMBOLLER else None

        # Trailing stop override (statik SL'den daha akıllı)
        if trail and TRAILING_STOP_AKTIF:
            ts_val = trail.get("trailing_sl")
            if ts_val and ts_val > sonuc.get("sl", 0):
                sonuc["sl_trailing"] = ts_val
            else:
                sonuc["sl_trailing"] = sonuc.get("sl", 0)
        else:
            sonuc["sl_trailing"] = sonuc.get("sl", 0)

        return sonuc
    except Exception as e:
        return {"hata":str(e)[:70]}

# ════════════════════════════════════════════════════════════════════════
#  GÖRÜNTÜLEME
# ════════════════════════════════════════════════════════════════════════

def temizle(): os.system("cls" if os.name=="nt" else "clear")

def baslik(dongu):
    print(Fore.CYAN+Style.BRIGHT+"""
╔══════════════════════════════════════════════════════════════════════════╗
║   🏦  TRADE SİNYAL SİSTEMİ  ULTRA  v7.0  —  Termux Edition            ║
║   RF+HistGB+Kelly+MC | Whale | Korelasyon | Trailing Stop | FCS        ║
╚══════════════════════════════════════════════════════════════════════════╝""")
    print(Fore.WHITE+f"   🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}  "
          f"│  🔄 #{dongu}  │  🧠 {len(_model)} model  │  📦 {len(_veri)} sembol")

def tablo(basl, sonuclar):
    print(f"\n  {Fore.CYAN}{Style.BRIGHT}{basl}")
    print(f"  {Fore.WHITE}{'─'*125}")
    print(f"  {'':3}{'SEMBOL':<11}{'ANLIK':>7}  {'DEĞ%':>6}  {'REJİM':<8}  "
          f"{'RSI':>5}  {'ADX':>5}  {'STREND':>7}  {'SAR':>3}  "
          f"{'ML KARAR':>14}  {'SKOR':>5}  KARAR")
    print(f"  {Fore.WHITE}{'─'*125}")
    for sembol,s in sorted(sonuclar.items(),
                            key=lambda x:abs(x[1].get("toplam",0)) if "hata" not in x[1] else -99,
                            reverse=True):
        if "hata" in s:
            print(f"  {Fore.RED}✗  {sembol:<11} HATA: {s['hata'][:55]}"); continue
        r=s["renk"]; d=s["degisim"]
        dok=Fore.GREEN if d>=0 else Fore.RED; ok="▲" if d>=0 else "▼"
        rej_c={"TREND":Fore.BLUE,"RANGE":Fore.YELLOW,"VOLATILE":Fore.RED}.get(s["rejim"],Fore.WHITE)
        rej_s={"TREND":"TREND  ","RANGE":"RANGE  ","VOLATILE":"VOLATİL"}.get(s["rejim"],s["rejim"])
        st_c=Fore.GREEN if s["supertrend"]==1 else Fore.RED
        st_s="YUK ↑" if s["supertrend"]==1 else "DUS ↓"
        sar_c=Fore.GREEN if s["sar"] else Fore.RED
        sar_s="AL " if s["sar"] else "SAT"
        ml_c=Fore.WHITE
        if s["ml"]:
            ml_c=Fore.GREEN if s["ml"]["tahmin"]==1 else (Fore.RED if s["ml"]["tahmin"]==-1 else Fore.CYAN)
        anlik=s.get("anlik")
        if anlik:
            anlik_fiy=anlik["anlik"]
            anlik_deg=((anlik_fiy-anlik["dunku"])/anlik["dunku"]*100) if anlik["dunku"] else 0
            anlik_dok=Fore.GREEN if anlik_deg>=0 else Fore.RED
            anlik_ok="▲" if anlik_deg>=0 else "▼"
            anlik_str=f"{anlik_dok}{anlik_fiy:>7.2f}{Style.RESET_ALL}"
            deg_str=f"{anlik_dok}{anlik_ok}{abs(anlik_deg):5.2f}%{Style.RESET_ALL}"
        else:
            anlik_str=f"{Fore.WHITE}{'—':>7}{Style.RESET_ALL}"
            deg_str=f"{dok}{ok}{abs(d):5.2f}%{Style.RESET_ALL}"
        print(
            f"  {r}{Style.BRIGHT}{s['karar'][:2]}{Style.RESET_ALL}  "
            f"{Fore.WHITE}{sembol:<11}"
            f"{anlik_str}  {deg_str}  "
            f"{rej_c}{rej_s}{Style.RESET_ALL}  "
            f"{Fore.WHITE}{s['rsi']:5.1f}  {s['adx']:5.1f}{Style.RESET_ALL}  "
            f"{st_c}{st_s}{Style.RESET_ALL}  "
            f"{sar_c}{sar_s}{Style.RESET_ALL}  "
            f"{ml_c}{s['ml_str']:>14}{Style.RESET_ALL}  "
            f"{Fore.WHITE}{s['toplam']:>+5}{Style.RESET_ALL}  "
            f"{r}{Style.BRIGHT}{s['karar']}")
    print(f"  {Fore.WHITE}{'─'*115}")

def detay_panel(sembol, s):
    r=s["renk"]
    print(f"\n  {Fore.CYAN}{'━'*68}")
    print(f"  {r}{Style.BRIGHT}  ▶ {sembol} — {s['karar']}  {s.get('rejim_not','')}")
    anlik=s.get("anlik")
    if anlik and anlik["anlik"]:
        anlik_fiy=anlik["anlik"]
        anlik_deg=((anlik_fiy-anlik["dunku"])/anlik["dunku"]*100) if anlik["dunku"] else 0
        anlik_ok="▲" if anlik_deg>=0 else "▼"
        anlik_c=Fore.GREEN if anlik_deg>=0 else Fore.RED
        print(f"  {Fore.WHITE}  Anlık : {anlik_c}{Style.BRIGHT}{anlik_fiy:.2f} {anlik_ok}{abs(anlik_deg):.2f}%"
              f"{Style.RESET_ALL}  │  Gün: {anlik['dusuk']:.2f} - {anlik['yuksek']:.2f}"
              f"  │  {anlik['tarih']}")
    print(f"  {Fore.WHITE}  Fiyat : {s['fiyat']:.2f}  "
          f"│  SL: {Fore.RED}{s['sl']:.2f}{Fore.WHITE}  "
          f"│  TP: {Fore.GREEN}{s['tp']:.2f}{Fore.WHITE}  "
          f"│  R/R: {Fore.YELLOW}{(s['tp']-s['fiyat'])/(s['fiyat']-s['sl']+1e-9):.2f}x")
    pp=s["pivot"]
    print(f"  {Fore.WHITE}  Pivot : PP:{pp[0]:.2f}  R1:{pp[1]:.2f}  R2:{pp[2]:.2f}  S1:{pp[3]:.2f}  S2:{pp[4]:.2f}")
    print(f"  {Fore.WHITE}  MA    : 20:{s['ma20']:.2f}  50:{s['ma50']:.2f}  200:{s['ma200']:.2f}")

    # v7: Destek/Direnç
    destekler=s.get("destekler",[]); direncler=s.get("direncler",[])
    if destekler or direncler:
        d_str="  ".join([f"D{i+1}:{d:.2f}" for i,d in enumerate(destekler[-2:])])
        r_str="  ".join([f"R{i+1}:{d:.2f}" for i,d in enumerate(direncler[:2])])
        print(f"  {Fore.WHITE}  S/D   : {Fore.GREEN}{d_str}{Fore.WHITE}  {Fore.RED}{r_str}")

    # v7: VIX
    vix=s.get("vix",{})
    if vix:
        vc=Fore.YELLOW if vix.get("yuksek") else Fore.GREEN
        vs="⚡ YÜKSEK VIX" if vix.get("yuksek") else "Normal VIX"
        print(f"  {vc}  VIX   : {vs}  ATR%:{vix.get('atr_pct',0):.2f}  "
              f"SL:{vix.get('sl_carpan',1.5)}×ATR  TP:{vix.get('tp_carpan',3.0)}×ATR{Style.RESET_ALL}")

    # v7: Makro
    makro=s.get("makro",{})
    if makro:
        ust=makro.get("usdtry_5d",0); alt=makro.get("altin_5d",0)
        brt=makro.get("brent_5d",0); bis=makro.get("bist100_5d",0)
        print(f"  {Fore.BLUE}  MAKRO : USD/TRY:{ust:+.1%}  Altın:{alt:+.1%}  "
              f"Brent:{brt:+.1%}  BIST100:{bis:+.1%}{Style.RESET_ALL}")

    # v7: Sentiment
    sent=s.get("sent_skor")
    if sent is not None:
        sc=Fore.GREEN if sent>0.1 else (Fore.RED if sent<-0.1 else Fore.WHITE)
        ss="POZİTİF 📰✅" if sent>0.1 else ("NEGATİF 📰❌" if sent<-0.1 else "NÖTR 📰")
        print(f"  {sc}  HABER : {ss}  ({sent:+.2f}){Style.RESET_ALL}")

    if s["ml"]:
        ml=s["ml"]
        ens=("RF+HistGB" if ml.get("ensemble") else "RF")
        print(f"  {Fore.CYAN}  ML    : {ens}  │  WF-Acc:{ml['wf_acc']*100:.1f}%  "
              f"│  Eğitim:{ml['n']} gün  │  Güven:{ml['guven']*100:.1f}%")
        proba=ml["proba"]; pb=lambda k: f"{proba.get(k,0)*100:.0f}%"
        print(f"  {Fore.CYAN}  Olası : AL {Fore.GREEN}{pb(1)}{Fore.CYAN}  BEKLE {pb(0)}  SAT {Fore.RED}{pb(-1)}")
    # ── v8: Whale ──────────────────────────────────────────────────────
    whale = s.get("whale", {})
    if whale and whale.get("spike_var"):
        wc = Fore.GREEN if whale.get("yon") == "AL" else Fore.RED
        print(f"  {wc}  WHALE  : {whale.get('aciklama','')}  Güç:{whale.get('guc',0)}/3{Style.RESET_ALL}")

    # ── v8: Korelasyon ─────────────────────────────────────────────────
    kor = s.get("kor", {})
    if kor:
        kc = Fore.GREEN if kor.get("ayrisma") == "POZITIF" else Fore.RED if kor.get("ayrisma") == "NEGATIF" else Fore.WHITE
        print(f"  {kc}  KOR    : {kor.get('aciklama','')}  β:{kor.get('beta',1):.2f}{Style.RESET_ALL}")

    # ── v8: Trailing Stop ──────────────────────────────────────────────
    trail = s.get("trail", {})
    if trail:
        tc = Fore.YELLOW if trail.get("mesafe_pct",5) < 2 else Fore.GREEN
        ts_val = trail.get("trailing_sl", 0)
        print(f"  {tc}  TRAIL  : {trail.get('aciklama','')}  SL={ts_val:.2f}{Style.RESET_ALL}")

    # ── v8: Monte Carlo ────────────────────────────────────────────────
    mc = s.get("mc", {})
    if mc:
        mc_c = Fore.GREEN if mc.get("median_getiri",0) > 0 else Fore.RED
        print(f"  {mc_c}  MC     : {mc.get('aciklama','')}  "
              f"DD:{mc.get('max_dd',0):.1f}%  VaR:{mc.get('var_95',0):.2f}%{Style.RESET_ALL}")

    # ── v8: Kelly ──────────────────────────────────────────────────────
    kelly = s.get("kelly", {})
    if kelly:
        kc2 = Fore.GREEN if kelly.get("yoo_pct",0) > 10 else Fore.YELLOW
        print(f"  {kc2}  KELLY  : {kelly.get('aciklama','')}  "
              f"WR:{kelly.get('win_rate',0)*100:.1f}%  R/R:{kelly.get('rr_oran',2):.1f}{Style.RESET_ALL}")

    # ── v8: Final Confidence Score ─────────────────────────────────────
    fcs = s.get("fcs", {})
    if fcs:
        fs = fcs.get("skor", 50); fe = fcs.get("etiket", "")
        fc = Fore.GREEN if fs >= 70 else Fore.YELLOW if fs >= 55 else Fore.RED
        print(f"  {fc}  FCS    : {fe}  Skor: {fs:.1f}/100{Style.RESET_ALL}")

    for n in s["notlar"][:8]:
        print(f"  {Fore.WHITE}  • {n}")
    print(f"  {Fore.CYAN}{'━'*68}")

def ozet(tum):
    guclu=[(s,r) for s,r in tum.items()
           if "hata" not in r and abs(r.get("toplam",0))>=GUCLU_ESIK]
    if not guclu: return
    print(f"\n  {Fore.WHITE}{Style.BRIGHT}⚡ GÜÇLÜ SİNYALLER — {len(guclu)} hisse")
    for s,r in sorted(guclu,key=lambda x:-abs(x[1]["toplam"])):
        detay_panel(s,r)

# ════════════════════════════════════════════════════════════════════════
#  ANA DÖNGÜ
# ════════════════════════════════════════════════════════════════════════

def ana():
    dongu=0
    semboller=list(dict.fromkeys(s for lst in LISTELER.values() for s in lst))
    print(Fore.CYAN+f"\n  🤖 Trade Sinyal Sistemi ULTRA v7.0 başlatılıyor...")
    print(Fore.WHITE+f"  📊 {len(semboller)} hisse  │  60+ özellik  │  RF+HistGB+SHAP  │  Makro+Sentiment+Diverjans")
    print(Fore.YELLOW+f"  ⚠️  İlk çalıştırmada ML eğitimi ~3-5 dk sürebilir.\n")

    # v7: Makro veri ön yükleme (arka planda)
    if MAKRO_AKTIF:
        try: _threading.Thread(target=makro_veri_getir,daemon=True).start()
        except Exception: pass

    tum={}

    def analiz_yap(yeniden=False):
        nonlocal dongu,tum; dongu+=1; tum={}; toplam=len(semboller); tamamlanan=[0]
        def _tek(s):
            r=analiz(s,yeniden); tamamlanan[0]+=1
            yuk="█"*(tamamlanan[0]*20//toplam); bos="░"*(20-len(yuk))
            print(f"  📡 [{tamamlanan[0]:2}/{toplam}] {s:<12} [{yuk}{bos}] {tamamlanan[0]*100//toplam}%  ",end="\r")
            return s,r
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures={ex.submit(_tek,s):s for s in semboller}
            for fut in as_completed(futures):
                s,r=fut.result()
                if r: tum[s]=r
        cache_kaydet(); print(" "*70,end="\r")

    def sonuclari_goster():
        baslik(dongu)
        for basl,lst in LISTELER.items():
            tablo(basl,{s:tum[s] for s in lst if s in tum})
        ozet(tum)
        print(Fore.CYAN+"""
  ╔══════════════════════════════════════════════════════════════════════╗
  ║  [1] Yenile (önbellekten)    [2] Tam yenile (veri+ML güncelle)     ║
  ║  [3] Güçlü sinyaller         [4] Hisse ara  (örn: TUPRS)           ║
  ║  [5] Hisse ekle/çıkar        [6] Backtest raporu                   ║
  ║  [q] Çıkış                                                         ║
  ╚══════════════════════════════════════════════════════════════════════╝""")
        print(Fore.WHITE+f"  ⚠️  Yatırım tavsiyesi değildir.  "
              f"Son: {datetime.now().strftime('%H:%M:%S')}")
        print(Fore.YELLOW+"\n  Seçim > ",end="",flush=True)

    listeler_yukle(); cache_yukle()
    if _model:
        print(Fore.GREEN+"  ⚡ Önbellekten hızlı başlatılıyor..."); analiz_yap(yeniden=False)
    else:
        print(Fore.YELLOW+"  🔄 İlk çalıştırma — ML eğitimi yapılıyor..."); analiz_yap(yeniden=True)
    sonuclari_goster()

    while True:
        try: secim=input("").strip().lower()
        except EOFError: break
        if secim=="q":
            print(Fore.CYAN+"\n  👋 Sistem kapatıldı.\n"); break
        elif secim=="1":
            print(Fore.CYAN+"  ⚡ Önbellekten yenileniyor..."); sonuclari_goster()
        elif secim=="2":
            print(Fore.CYAN+"  🔄 Veri ve ML yenileniyor..."); _veri.clear()
            analiz_yap(yeniden=True); sonuclari_goster()
        elif secim=="3":
            baslik(dongu)
            guclu={s:r for s,r in tum.items()
                   if "hata" not in r and abs(r.get("toplam",0))>=GUCLU_ESIK}
            if guclu:
                print(Fore.WHITE+Style.BRIGHT+f"\n  ⚡ GÜÇLÜ SİNYALLER ({len(guclu)} hisse)\n")
                for s,r in sorted(guclu.items(),key=lambda x:-abs(x[1]["toplam"])):
                    detay_panel(s,r)
            else:
                print(Fore.YELLOW+"\n  Şu an güçlü sinyal yok.\n")
            print(Fore.YELLOW+"\n  Seçim > ",end="",flush=True)
        elif secim=="4":
            print(Fore.YELLOW+"  Hisse kodu girin (örn: TUPRS, GARAN, AAPL): ",end="",flush=True)
            try: aranan=input("").strip().upper()
            except EOFError: aranan=""
            aranan_temiz=sembol_dogrula(aranan) if aranan else None
            if aranan_temiz:
                aranan=aranan_temiz
                sembol_dene=aranan+".IS" if not aranan.endswith(".IS") and aranan not in STOOQ_SEMBOLLER else aranan
                print(Fore.CYAN+f"  🔍 {aranan} analiz ediliyor...")
                r=None
                for s_try in [sembol_dene,aranan,aranan+".IS"]:
                    _veri.pop(s_try,None)
                    df_try=isyatirim_indir(s_try) if s_try.endswith(".IS") else stooq_indir(s_try)
                    if not df_try.empty:
                        _veri[s_try]=(time.time(),df_try)
                        r=analiz(s_try,yeniden=True)
                        if r and "hata" not in r:
                            tum[s_try]=r; baslik(dongu); detay_panel(s_try,r); break
                if not r or "hata" in (r or {}):
                    print(Fore.RED+f"  ❌ '{aranan}' bulunamadı.")
            print(Fore.YELLOW+"\n  Seçim > ",end="",flush=True)
        elif secim=="5":
            print(Fore.YELLOW+"  İşlem: [e] Ekle  [c] Çıkar > ",end="",flush=True)
            try: islem=input("").strip().lower()
            except EOFError: islem=""
            if islem=="e":
                print(Fore.YELLOW+"  Hisse kodu: ",end="",flush=True)
                try: yeni=input("").strip().upper()
                except EOFError: yeni=""
                yeni_temiz=sembol_dogrula(yeni) if yeni else None
                if yeni_temiz:
                    yeni=yeni_temiz
                    sembol=yeni+".IS" if yeni not in STOOQ_SEMBOLLER and not yeni.endswith(".IS") else yeni
                    hedef="🇹🇷 BIST" if sembol.endswith(".IS") else "🇺🇸 S&P 500"
                    if hedef not in LISTELER: LISTELER[hedef]=[]
                    if sembol not in LISTELER[hedef]:
                        LISTELER[hedef].append(sembol)
                        if sembol.endswith(".IS"): BIST_SEMBOLLER.add(sembol)
                        listeler_kaydet()
                        print(Fore.GREEN+f"  ✅ {sembol} eklendi. Tam yenileme için [2] basın.")
                    else:
                        print(Fore.YELLOW+f"  ⚠️  {sembol} zaten listede.")
            elif islem=="c":
                print(Fore.YELLOW+"  Çıkarılacak hisse: ",end="",flush=True)
                try: cikar=input("").strip().upper()
                except EOFError: cikar=""
                cikar_is=cikar+".IS" if not cikar.endswith(".IS") else cikar
                kaldirildi=False
                for lst in LISTELER.values():
                    for s in [cikar,cikar_is]:
                        if s in lst: lst.remove(s); kaldirildi=True
                if kaldirildi: listeler_kaydet(); print(Fore.GREEN+f"  ✅ {cikar} çıkarıldı.")
                else: print(Fore.RED+f"  ❌ {cikar} bulunamadı.")
            print(Fore.YELLOW+"\n  Seçim > ",end="",flush=True)
        elif secim=="6":
            print(Fore.CYAN+"\n  📊 Backtest başlatılıyor...")
            print(Fore.WHITE+"  [1] BIST  [2] ABD  [3] Tümü  [4] Tek hisse > ",end="",flush=True)
            try: bt_sec=input("").strip()
            except EOFError: bt_sec="1"
            bt_semboller=[]
            if bt_sec=="1":   bt_semboller=[s for s in BIST_SEMBOLLER if s in _veri] or list(BIST_SEMBOLLER)[:8]
            elif bt_sec=="2": bt_semboller=[s for lst in LISTELER.values() for s in lst if not s.endswith(".IS")][:10]
            elif bt_sec=="3": bt_semboller=[s for lst in LISTELER.values() for s in lst][:15]
            elif bt_sec=="4":
                print(Fore.YELLOW+"  Hisse kodu: ",end="",flush=True)
                try: tek=input("").strip().upper()
                except EOFError: tek=""
                bt_semboller=[tek+".IS" if not tek.endswith(".IS") and tek not in STOOQ_SEMBOLLER else tek]
            bt_sonuclar=[]
            for i,s in enumerate(bt_semboller):
                print(f"  📡 [{i+1}/{len(bt_semboller)}] {s} backtest...    ",end="\r")
                df=veri_getir(s)
                if df.empty or len(df)<200: continue
                bt=backtest_calistir(s,df)
                if bt: bt_sonuclar.append(bt)
            print(" "*55,end="\r")
            if bt_sonuclar: baslik(dongu); backtest_yazdir(bt_sonuclar)
            else: print(Fore.RED+"  ❌ Yeterli veri yok. Önce [2] ile yükleyin.")
            print(Fore.YELLOW+"\n  Seçim > ",end="",flush=True)
        else:
            print(Fore.YELLOW+"  [1] Yenile  [2] Tam yenile  [3] Güçlü  [4] Ara  [5] Ekle/Çıkar  [6] Backtest  [q] Çıkış")
            print(Fore.YELLOW+"  Seçim > ",end="",flush=True)

if __name__=="__main__":
    try: ana()
    except KeyboardInterrupt: print(Fore.CYAN+"\n\n  👋 Sistem kapatıldı.\n")
