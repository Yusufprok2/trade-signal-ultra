"""
Trade Sinyal Sistemi ULTRA v8.0 — Kivy Android APK v2
Ozellikler:
  - Plotly Candlestick Grafik (WebView, SL/TP cizgili)
  - SQLite Portfolyo Takibi
  - WebSocket / Polling Canli Fiyat Akisi
  - Hizli Filtre Chips (Guclu AL, RSI<30 vb.)
  - Android Bildirim (plyer)
  - 3 Tema: Terminal | Glassmorphism | Dark Premium
"""

import threading, time, json, os, sqlite3, tempfile
from functools import partial

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line

try:
    from android.runnable import run_on_ui_thread
    from jnius import autoclass
    ANDROID = True
except ImportError:
    ANDROID = False

try:
    from plyer import notification
    PLYER_OK = True
except ImportError:
    PLYER_OK = False

# ════════════════════════════════════════════════════════════════════════
#  TEMA
# ════════════════════════════════════════════════════════════════════════

TEMALAR = {
    "terminal": {
        "ad":"Terminal","altyazi":"Bloomberg Tarzi",
        "bg":(0.04,0.04,0.04,1),"bg2":(0.08,0.08,0.08,1),"kart":(0.06,0.06,0.06,1),
        "ana":(0.0,1.0,0.255,1),"ikincil":(0.0,0.8,0.2,1),
        "yazi":(0.85,0.95,0.85,1),"yazi2":(0.5,0.7,0.5,1),
        "al":(0.0,1.0,0.255,1),"sat":(1.0,0.25,0.25,1),"bekle":(0.8,0.8,0.0,1),
        "font":"RobotoMono-Regular","font_baslik":"RobotoMono-Regular","kenar_r":2,
        "p_bg":"#0a0a0a","p_al":"#00FF41","p_sat":"#FF4444",
    },
    "glassmorphism": {
        "ad":"Glassmorphism","altyazi":"Modern Cam Efekti",
        "bg":(0.06,0.04,0.12,1),"bg2":(0.10,0.07,0.18,1),"kart":(0.12,0.08,0.22,0.85),
        "ana":(0.655,0.545,0.98,1),"ikincil":(0.22,0.74,0.98,1),
        "yazi":(0.93,0.90,1.0,1),"yazi2":(0.65,0.60,0.85,1),
        "al":(0.22,0.98,0.6,1),"sat":(0.98,0.35,0.45,1),"bekle":(0.655,0.545,0.98,1),
        "font":"Roboto-Regular","font_baslik":"Roboto-Bold","kenar_r":16,
        "p_bg":"#0f0a1e","p_al":"#38D98A","p_sat":"#F87171",
    },
    "dark_premium": {
        "ad":"Dark Premium","altyazi":"Luks Metal",
        "bg":(0.05,0.04,0.03,1),"bg2":(0.09,0.07,0.04,1),"kart":(0.10,0.08,0.05,1),
        "ana":(0.83,0.686,0.216,1),"ikincil":(0.604,0.69,0.784,1),
        "yazi":(0.95,0.92,0.85,1),"yazi2":(0.65,0.60,0.50,1),
        "al":(0.83,0.686,0.216,1),"sat":(0.72,0.20,0.15,1),"bekle":(0.604,0.69,0.784,1),
        "font":"Roboto-Regular","font_baslik":"Roboto-Bold","kenar_r":8,
        "p_bg":"#0d0b07","p_al":"#D4AF37","p_sat":"#B83232",
    },
}

_aktif_tema = "terminal"
def tema(): return TEMALAR[_aktif_tema]
def tema_sec(ad): global _aktif_tema; _aktif_tema = ad

def hx(rgba):
    return "#{:02x}{:02x}{:02x}".format(
        int(rgba[0]*255), int(rgba[1]*255), int(rgba[2]*255))

def hx2(rgba):
    return "{:02x}{:02x}{:02x}".format(
        int(rgba[0]*255), int(rgba[1]*255), int(rgba[2]*255))

# ════════════════════════════════════════════════════════════════════════
#  SQLite PORTFOLYO
# ════════════════════════════════════════════════════════════════════════

DB_YOLU = os.path.expanduser("~/.trade_portfolio.db")

def db_init():
    with sqlite3.connect(DB_YOLU) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sembol TEXT NOT NULL,
            adet REAL NOT NULL,
            alis_fiy REAL NOT NULL,
            tarih TEXT DEFAULT (date('now')),
            notlar TEXT DEFAULT ''
        )""")
        con.commit()

def portfolio_ekle(sembol, adet, alis_fiy):
    with sqlite3.connect(DB_YOLU) as con:
        con.execute("INSERT INTO portfolio (sembol,adet,alis_fiy) VALUES (?,?,?)",
                    (sembol.upper(), float(adet), float(alis_fiy)))
        con.commit()

def portfolio_sil(pid):
    with sqlite3.connect(DB_YOLU) as con:
        con.execute("DELETE FROM portfolio WHERE id=?", (pid,))
        con.commit()

def portfolio_listele():
    with sqlite3.connect(DB_YOLU) as con:
        return con.execute(
            "SELECT id,sembol,adet,alis_fiy,tarih FROM portfolio ORDER BY tarih DESC"
        ).fetchall()

db_init()

# ════════════════════════════════════════════════════════════════════════
#  PLOTLY HTML
# ════════════════════════════════════════════════════════════════════════

def plotly_html(df, sembol, sl, tp, sonuc):
    t = tema()
    try:
        son60 = df.tail(60)
        tarih = [str(d)[:10] for d in son60.index]
        ac    = [round(float(v),4) for v in son60["Open"]]
        yuk   = [round(float(v),4) for v in son60["High"]]
        dsk   = [round(float(v),4) for v in son60["Low"]]
        kap   = [round(float(v),4) for v in son60["Close"]]
        vol   = [round(float(v),0) for v in son60["Volume"]]
        karar = sonuc.get("karar","BEKLE")
        ml    = sonuc.get("ml") or {}
        guven = ml.get("guven",0)*100
        k_renk = t["p_al"] if "AL" in karar else t["p_sat"] if "SAT" in karar else "#aaaaaa"

        return f"""<!DOCTYPE html><html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
body{{margin:0;padding:0;background:{t['p_bg']};}}
#g{{width:100vw;height:72vh;}}
#b{{padding:6px 12px;font-family:monospace;font-size:11px;color:{hx(t['yazi2'])};display:flex;gap:12px;align-items:center;}}
.k{{color:{k_renk};font-weight:bold;font-size:13px;}}
</style></head><body>
<div id="g"></div>
<div id="b">
  <span class="k">{karar}</span>
  <span>SL: <b style="color:{t['p_sat']}">{sl:.2f}</b></span>
  <span>TP: <b style="color:{t['p_al']}">{tp:.2f}</b></span>
  <span>ML: <b style="color:{hx(t['ana'])}">{guven:.0f}%</b></span>
</div>
<script>
var x={json.dumps(tarih)};
var o={json.dumps(ac)};
var h={json.dumps(yuk)};
var l={json.dumps(dsk)};
var c={json.dumps(kap)};
var v={json.dumps(vol)};
Plotly.newPlot('g',[
  {{type:'candlestick',x:x,open:o,high:h,low:l,close:c,name:'{sembol.replace(".IS","")}',
    increasing:{{line:{{color:'{t['p_al']}',width:1}},fillcolor:'{t['p_al']}'}},
    decreasing:{{line:{{color:'{t['p_sat']}',width:1}},fillcolor:'{t['p_sat']}'}}}},
  {{type:'scatter',mode:'lines',x:[x[0],x[x.length-1]],y:[{sl:.4f},{sl:.4f}],
    line:{{color:'{t['p_sat']}',width:1.5,dash:'dash'}},name:'SL {sl:.2f}'}},
  {{type:'scatter',mode:'lines',x:[x[0],x[x.length-1]],y:[{tp:.4f},{tp:.4f}],
    line:{{color:'{t['p_al']}',width:1.5,dash:'dash'}},name:'TP {tp:.2f}'}},
  {{type:'bar',x:x,y:v,name:'Hacim',yaxis:'y2',
    marker:{{color:c.map((ci,i)=>ci>=o[i]?'{t['p_al']}33':'{t['p_sat']}33')}}}},
],{{
  paper_bgcolor:'{t['p_bg']}',plot_bgcolor:'{t['p_bg']}',
  font:{{color:'{hx(t['yazi2'])}',size:10}},
  margin:{{l:50,r:10,t:8,b:36}},
  xaxis:{{type:'category',showgrid:true,gridcolor:'{hx(t['yazi2'])}22',
          rangeslider:{{visible:false}},tickangle:-45,nticks:8}},
  yaxis:{{showgrid:true,gridcolor:'{hx(t['yazi2'])}22',side:'right',domain:[0.25,1]}},
  yaxis2:{{domain:[0,0.22],showgrid:false,showticklabels:false}},
  legend:{{orientation:'h',x:0,y:1.02,bgcolor:'rgba(0,0,0,0)',font:{{size:10}}}},
  hovermode:'x unified',dragmode:'pan',
}},{{scrollZoom:true,displayModeBar:false,responsive:true}});
</script></body></html>"""
    except Exception as e:
        return f"<html><body style='background:#000;color:#0f0;padding:20px;font-family:monospace'><p>Grafik hatasi: {e}</p></body></html>"

def html_kaydet(html):
    p = os.path.join(tempfile.gettempdir(), "trade_chart.html")
    with open(p,"w",encoding="utf-8") as f: f.write(html)
    return p

# ════════════════════════════════════════════════════════════════════════
#  WEBVIEW
# ════════════════════════════════════════════════════════════════════════

class GrafikView(RelativeLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._wv = None
        t = tema()
        self._ph = Label(text="Grafik yukleniyor...",
                         color=t["yazi2"], font_size=dp(13),
                         halign="center", valign="middle")
        self.add_widget(self._ph)

    def yukle(self, yol):
        if ANDROID:
            self._android(yol)
        else:
            self._ph.text = "[Plotly grafik APK'da goruntulenir]\n" + os.path.basename(yol)

    def _android(self, yol):
        try:
            from android.runnable import run_on_ui_thread
            from jnius import autoclass
            WebView = autoclass("android.webkit.WebView")
            PA = autoclass("org.kivy.android.PythonActivity")
            act = PA.mActivity

            @run_on_ui_thread
            def _f():
                if self._wv is None:
                    wv = WebView(act)
                    ws = wv.getSettings()
                    ws.setJavaScriptEnabled(True)
                    ws.setDomStorageEnabled(True)
                    ws.setBuiltInZoomControls(True)
                    ws.setDisplayZoomControls(False)
                    ws.setLoadWithOverviewMode(True)
                    ws.setUseWideViewPort(True)
                    wv.setBackgroundColor(0)
                    self._wv = wv
                self._wv.loadUrl(f"file://{yol}")
            _f()
        except Exception as e:
            self._ph.text = f"WebView hatasi:\n{e}"

# ════════════════════════════════════════════════════════════════════════
#  CANLI FİYAT
# ════════════════════════════════════════════════════════════════════════

class CanliFiyat:
    KRIPTO = {"BTCUSDT":"BTC","ETHUSDT":"ETH","BNBUSDT":"BNB"}
    BIST_LISTE = ["GARAN.IS","THYAO.IS","ASELS.IS","EREGL.IS","TUPRS.IS"]

    def __init__(self, cb):
        self._cb = cb
        self._on = False

    def baslat(self):
        if self._on: return
        self._on = True
        threading.Thread(target=self._kripto, daemon=True).start()
        threading.Thread(target=self._bist, daemon=True).start()

    def durdur(self):
        self._on = False

    def _kripto(self):
        import urllib.request
        while self._on:
            for s, ad in self.KRIPTO.items():
                try:
                    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={s}"
                    with urllib.request.urlopen(url, timeout=5) as r:
                        d = json.loads(r.read())
                    f = float(d["lastPrice"]); dg = float(d["priceChangePercent"])
                    Clock.schedule_once(lambda dt,a=ad,fv=f,dv=dg: self._cb(a,fv,dv))
                except Exception: pass
            time.sleep(6)

    def _bist(self):
        import urllib.request
        while self._on:
            for s in self.BIST_LISTE:
                try:
                    url = f"http://bigpara.hurriyet.com.tr/api/v1/borsa/hisseyuzeysel/{s.replace('.IS','')}"
                    with urllib.request.urlopen(url, timeout=6) as r:
                        d = json.loads(r.read())["data"]["hisseYuzeysel"]
                    f = float(d.get("kapanis") or d.get("alis") or 0)
                    dk = float(d.get("dunkukapanis") or f)
                    dg = (f-dk)/(dk+1e-9)*100
                    Clock.schedule_once(lambda dt,sv=s,fv=f,dv=dg: self._cb(sv,fv,dv))
                except Exception: pass
            time.sleep(15)

# ════════════════════════════════════════════════════════════════════════
#  BİLDİRİM
# ════════════════════════════════════════════════════════════════════════

_bildirim_gonderilen = set()
_bil_lock = threading.Lock()

def bildirim_gonder(sembol, karar, puan):
    if not PLYER_OK: return
    try:
        notification.notify(
            title=f"Trade Sinyal: {sembol}",
            message=f"{karar}  Puan: {puan:+d}",
            app_name="Trade Sinyal Ultra",
            timeout=8)
    except Exception: pass

def guclu_kontrol(sonuclar):
    with _bil_lock:
        for sem, s in sonuclar.items():
            if "hata" in s: continue
            top = s.get("toplam",0); kar = s.get("karar","")
            k = f"{sem}_{kar}"
            if abs(top) >= 9 and k not in _bildirim_gonderilen:
                _bildirim_gonderilen.add(k)
                threading.Thread(target=bildirim_gonder, args=(sem,kar,top), daemon=True).start()

# ════════════════════════════════════════════════════════════════════════
#  YARDIMCI BİLEŞENLER
# ════════════════════════════════════════════════════════════════════════

class RenkliKart(RelativeLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._ciz, size=self._ciz)

    def _ciz(self, *a):
        self.canvas.before.clear()
        t = tema()
        with self.canvas.before:
            Color(*t["kart"])
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(t["kenar_r"])])
            Color(*t["ana"][:3], 0.25)
            Line(rounded_rectangle=[self.x,self.y,self.width,self.height,dp(t["kenar_r"])], width=dp(0.8))


class GlowLabel(Label):
    def __init__(self, **kwargs):
        t = tema()
        kwargs.setdefault("color", t["ana"])
        kwargs.setdefault("font_name", t["font_baslik"])
        kwargs.setdefault("bold", True)
        super().__init__(**kwargs)


class TemaButon(Button):
    def __init__(self, ta, **kwargs):
        self.ta = ta
        td = TEMALAR[ta]
        kwargs["text"] = f"[b]{td['ad']}[/b]\n[size=12]{td['altyazi']}[/size]"
        kwargs["markup"] = True
        kwargs["size_hint_y"] = None
        kwargs["height"] = dp(68)
        kwargs["background_normal"] = ""
        kwargs["background_color"] = (0,0,0,0)
        kwargs["color"] = td["ana"]
        super().__init__(**kwargs)
        self.bind(pos=self._ciz, size=self._ciz)

    def _ciz(self, *a):
        self.canvas.before.clear()
        td = TEMALAR[self.ta]
        with self.canvas.before:
            Color(*td["kart"])
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])
            Color(*td["ana"][:3], 0.5)
            Line(rounded_rectangle=[self.x,self.y,self.width,self.height,dp(12)], width=dp(1.5))


class Chip(Button):
    def __init__(self, etiket, aktif=False, **kwargs):
        t = tema()
        kwargs["text"] = etiket
        kwargs["size_hint_y"] = None
        kwargs["height"] = dp(30)
        kwargs["size_hint_x"] = None
        kwargs["width"] = dp(len(etiket)*8+24)
        kwargs["background_normal"] = ""
        kwargs["background_color"] = (0,0,0,0)
        kwargs["font_size"] = dp(11)
        self._aktif = aktif
        super().__init__(**kwargs)
        self._renk()
        self.bind(pos=self._ciz, size=self._ciz)

    def _renk(self):
        t = tema()
        self.color = t["bg"] if self._aktif else t["ana"]

    def _ciz(self, *a):
        self.canvas.before.clear()
        t = tema()
        with self.canvas.before:
            Color(*t["ana"]) if self._aktif else Color(*t["ana"][:3], 0.15)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15)])

    def set_aktif(self, v):
        self._aktif = v
        self._renk()
        self._ciz()

# ════════════════════════════════════════════════════════════════════════
#  FİLTRELER
# ════════════════════════════════════════════════════════════════════════

FILTRELER = {
    "Tumu":        lambda s: True,
    "Guclu AL":    lambda s: s.get("toplam",0) >= 6,
    "AL":          lambda s: 3 <= s.get("toplam",0) < 6,
    "Guclu SAT":   lambda s: s.get("toplam",0) <= -6,
    "RSI<30":      lambda s: s.get("rsi",50) < 30,
    "RSI>70":      lambda s: s.get("rsi",50) > 70,
    "Diverjans":   lambda s: any("Diverjans" in n for n in s.get("notlar",[])),
}

# ════════════════════════════════════════════════════════════════════════
#  HİSSE SATIRI
# ════════════════════════════════════════════════════════════════════════

class HisseSatiri(BoxLayout):
    def __init__(self, sembol, sonuc, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=dp(58), spacing=dp(4), padding=[dp(6),dp(4)], **kwargs)
        self.sembol = sembol
        self.sonuc = sonuc
        self._ciz(sonuc)

    def _ciz(self, sonuc):
        self.clear_widgets()
        t = tema()
        karar  = sonuc.get("karar","BEKLE")
        toplam = sonuc.get("toplam",0)
        rsi    = sonuc.get("rsi",0)
        fiyat  = sonuc.get("fiyat",0)
        anlik  = sonuc.get("anlik")
        cf     = sonuc.get("_cf")
        cd     = sonuc.get("_cd")

        if cf:
            gf = cf; gd = cd if cd is not None else 0.0
        elif anlik and anlik.get("anlik"):
            gf = anlik["anlik"]
            gd = ((anlik["anlik"]-anlik["dunku"])/(anlik["dunku"]+1e-9)*100) if anlik.get("dunku") else 0
        else:
            gf = fiyat; gd = sonuc.get("degisim",0)

        if "AL" in karar:    kr = t["al"];   ks = "AL"
        elif "SAT" in karar: kr = t["sat"];  ks = "SAT"
        else:                kr = t["bekle"]; ks = "HOL"

        dr = t["al"] if gd>=0 else t["sat"]
        ok = "+" if gd>=0 else ""
        sr = t["al"] if toplam>0 else t["sat"] if toplam<0 else t["bekle"]

        with self.canvas.before:
            Color(*t["kart"])
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
        self.bind(pos=lambda *a: setattr(self._bg,"pos",self.pos),
                  size=lambda *a: setattr(self._bg,"size",self.size))

        self.add_widget(Label(text=f"[b]{self.sembol.replace('.IS','')}[/b]",
                              markup=True, color=t["yazi"], font_size=dp(13),
                              size_hint_x=0.22, halign="left", valign="middle"))
        self.add_widget(Label(
            text=f"[b]{gf:.2f}[/b]\n[color={hx2(dr)}]{ok}{gd:.1f}%[/color]",
            markup=True, color=t["yazi"], font_size=dp(12),
            size_hint_x=0.24, halign="center", valign="middle"))
        self.add_widget(Label(text=f"RSI\n{rsi:.0f}", color=t["yazi2"],
                              font_size=dp(11), size_hint_x=0.14,
                              halign="center", valign="middle"))
        self.add_widget(Label(
            text=f"[b][color={hx2(sr)}]{toplam:+d}[/color][/b]",
            markup=True, font_size=dp(14),
            size_hint_x=0.14, halign="center", valign="middle"))
        # FCS skoru + whale badge
        fcs   = sonuc.get("fcs", {})
        whale = sonuc.get("whale", {})
        fs    = fcs.get("skor", 0) if fcs else 0
        ws    = "🐋" if whale and whale.get("spike_var") else ""
        if fs >= 70:   fs_r = t["al"];   fs_t = f"{ws}{fs:.0f}✅"
        elif fs >= 50: fs_r = t["bekle"]; fs_t = f"{ws}{fs:.0f}"
        elif fs > 0:   fs_r = t["sat"];   fs_t = f"{ws}{fs:.0f}⚠"
        else:          fs_r = t["yazi2"]; fs_t = f"{ws}{ks}"

        self.add_widget(Label(
            text=f"[b][color={hx2(kr)}]{ks}[/color][/b]\n[color={hx2(fs_r)}]{fs_t}[/color]",
            markup=True, font_size=dp(10),
            size_hint_x=0.26, halign="right", valign="middle"))

    def guncelle_canli(self, f, d):
        self.sonuc["_cf"] = f
        self.sonuc["_cd"] = d
        self._ciz(self.sonuc)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            app = App.get_running_app()
            det = app.sm.get_screen("detay")
            det.yukle(self.sembol, self.sonuc)
            app.sm.transition = SlideTransition(direction="left")
            app.sm.current = "detay"
            return True
        return super().on_touch_down(touch)

# ════════════════════════════════════════════════════════════════════════
#  ANA EKRAN
# ════════════════════════════════════════════════════════════════════════

class AnaEkran(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sonuclar = {}
        self._yukleniyor = False
        self._aktif_tab = "BIST"
        self._aktif_filtre = "Tumu"
        self._satir_map = {}
        self._filtre_btns = {}
        self._tab_btns = {}
        self._canli = CanliFiyat(self._canli_cb)
        self._ticker = {}
        self._build()

    def _build(self):
        self.clear_widgets()
        self._satir_map = {}
        t = tema()

        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(*t["bg"])
            self._bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=lambda *a: setattr(self._bg,"pos",root.pos),
                  size=lambda *a: setattr(self._bg,"size",root.size))

        # Ust bar
        topbar = BoxLayout(size_hint_y=None, height=dp(54),
                           padding=[dp(12),dp(8)], spacing=dp(8))
        with topbar.canvas.before:
            Color(*t["bg2"]); Rectangle(pos=topbar.pos, size=topbar.size)
        topbar.bind(pos=lambda *a: self._rect(topbar, t["bg2"]),
                    size=lambda *a: self._rect(topbar, t["bg2"]))

        topbar.add_widget(GlowLabel(text="TRADE v7", font_size=dp(18),
                                    size_hint_x=0.4, halign="left", valign="middle"))
        self._durum_lbl = Label(text="Hazir", color=t["ana"], font_size=dp(11),
                                size_hint_x=0.3, halign="right", valign="middle")
        topbar.add_widget(self._durum_lbl)
        for ik, sc in [("P","portfolio"),("S","ayarlar")]:
            b = Button(text=ik, font_size=dp(16),
                       size_hint=(None,None), size=(dp(38),dp(38)),
                       background_normal="", background_color=(0,0,0,0), color=t["yazi2"])
            b.bind(on_press=partial(self._git, sc))
            topbar.add_widget(b)
        root.add_widget(topbar)

        # Tab bar
        tabbar = BoxLayout(size_hint_y=None, height=dp(36),
                           spacing=dp(4), padding=[dp(8),dp(2)])
        self._tab_btns = {}
        for et, k in [("BIST","BIST"),("S&P","SP"),("Tekno","TEKNO"),("Canli","CANLI")]:
            b = Button(text=et, font_size=dp(11), background_normal="",
                       background_color=(0,0,0,0), color=t["yazi2"])
            b.bind(on_press=partial(self._tab, k))
            self._tab_btns[k] = b
            tabbar.add_widget(b)
        root.add_widget(tabbar)

        # Filtre chipsleri
        fs = ScrollView(size_hint_y=None, height=dp(38), do_scroll_y=False)
        fb = BoxLayout(size_hint_x=None, spacing=dp(6), padding=[dp(8),dp(4)])
        fb.bind(minimum_width=fb.setter("width"))
        self._filtre_btns = {}
        for et in FILTRELER:
            c = Chip(et, aktif=(et == self._aktif_filtre))
            c.bind(on_press=partial(self._filtre, et))
            self._filtre_btns[et] = c
            fb.add_widget(c)
        fs.add_widget(fb)
        root.add_widget(fs)

        # Ticker
        self._ticker_lbl = Label(
            text="BTC: --   ETH: --   BNB: --",
            color=t["ana"], font_size=dp(11),
            size_hint_y=None, height=dp(22), halign="center")
        root.add_widget(self._ticker_lbl)

        # Liste
        sv = ScrollView(do_scroll_x=False)
        self._liste = GridLayout(cols=1, spacing=dp(4),
                                 padding=[dp(8),dp(4)], size_hint_y=None)
        self._liste.bind(minimum_height=self._liste.setter("height"))
        sv.add_widget(self._liste)
        root.add_widget(sv)

        # Alt bar
        alt = BoxLayout(size_hint_y=None, height=dp(50),
                        spacing=dp(8), padding=[dp(8),dp(6)])
        with alt.canvas.before:
            Color(*t["bg2"]); Rectangle(pos=alt.pos, size=alt.size)
        for txt, fn in [("Yenile",self._yenile),("Backtest",partial(self._git,"backtest"))]:
            b = Button(text=txt, font_size=dp(13), background_normal="",
                       background_color=(0,0,0,0), color=t["ana"], bold=True)
            b.bind(on_press=fn)
            b.bind(pos=lambda *a, btn=b: self._btn_ciz(btn),
                   size=lambda *a, btn=b: self._btn_ciz(btn))
            alt.add_widget(b)
        root.add_widget(alt)
        self.add_widget(root)

        self._tab_goster(self._aktif_tab)
        if self._sonuclar: self._liste_goster()

    def _rect(self, w, r, *a):
        w.canvas.before.clear()
        with w.canvas.before: Color(*r); Rectangle(pos=w.pos, size=w.size)

    def _btn_ciz(self, b, *a):
        b.canvas.before.clear()
        t = tema()
        with b.canvas.before:
            Color(*t["ana"][:3], 0.15)
            RoundedRectangle(pos=b.pos, size=b.size, radius=[dp(8)])

    def _tab(self, k, *a):
        self._aktif_tab = k
        self._tab_goster(k)
        self._liste_goster()

    def _tab_goster(self, aktif):
        t = tema()
        for k, b in self._tab_btns.items():
            b.color = t["ana"] if k == aktif else t["yazi2"]
            b.bold  = k == aktif

    def _filtre(self, et, *a):
        self._aktif_filtre = et
        for k, c in self._filtre_btns.items():
            c.set_aktif(k == et)
        self._liste_goster()

    def _liste_goster(self):
        self._liste.clear_widgets()
        self._satir_map = {}
        t = tema()

        if self._aktif_tab == "CANLI":
            self._liste.add_widget(Label(
                text="Canli kripto fiyatlari (Binance)\nBTC ETH BNB - yukarida guncellenir",
                color=t["yazi2"], font_size=dp(13),
                size_hint_y=None, height=dp(80), halign="center"))
            return

        tab_map = {
            "BIST":  [s for s in self._sonuclar if s.endswith(".IS")],
            "SP":    [s for s in self._sonuclar if not s.endswith(".IS")][:20],
            "TEKNO": [s for s in self._sonuclar
                      if s in {"NVDA","AMD","INTC","QCOM","AVGO","CRM","ADBE","NOW","SNOW","PLTR"}],
        }
        fn = FILTRELER.get(self._aktif_filtre, lambda s: True)
        liste = [s for s in tab_map.get(self._aktif_tab, [])
                 if s in self._sonuclar
                 and "hata" not in self._sonuclar[s]
                 and fn(self._sonuclar[s])]
        liste.sort(key=lambda s: abs(self._sonuclar[s].get("toplam",0)), reverse=True)

        if not liste:
            self._liste.add_widget(Label(
                text="Bu filtrede hisse yok", color=t["yazi2"],
                font_size=dp(13), size_hint_y=None, height=dp(60), halign="center"))
            return
        for s in liste:
            row = HisseSatiri(s, self._sonuclar[s])
            self._satir_map[s] = row
            self._liste.add_widget(row)

    @mainthread
    def _canli_cb(self, ad, f, d):
        if "/" in ad or ad in ("BTC","ETH","BNB"):
            self._ticker[ad] = f"{ad}:{f:,.0f}"
            self._ticker_lbl.text = "   ".join(self._ticker.values()) or "BTC:--  ETH:--"
            return
        if ad in self._satir_map:
            self._satir_map[ad].guncelle_canli(f, d)

    def _yenile(self, *a):
        if self._yukleniyor: return
        self._yukleniyor = True
        self._durum_lbl.text = "Yukleniyor..."; self._durum_lbl.color = tema()["bekle"]
        threading.Thread(target=self._cek, daemon=True).start()

    def _cek(self):
        try:
            import trade_v7 as tv
            from concurrent.futures import ThreadPoolExecutor, as_completed
            semboller = list(dict.fromkeys(s for lst in tv.LISTELER.values() for s in lst))
            sonuclar = {}
            with ThreadPoolExecutor(max_workers=4) as ex:
                futs = {ex.submit(tv.analiz, s, False): s for s in semboller}
                for f in as_completed(futs):
                    s = futs[f]
                    try:
                        r = f.result()
                        if r: sonuclar[s] = r
                    except Exception: pass
            Clock.schedule_once(lambda dt: self._tamam(sonuclar))
        except Exception as e:
            Clock.schedule_once(lambda dt: self._hata(str(e)))

    def _tamam(self, sonuclar):
        self._sonuclar = sonuclar
        self._yukleniyor = False
        t = tema()
        self._durum_lbl.text = f"{len(sonuclar)} hisse"
        self._durum_lbl.color = t["al"]
        self._liste_goster()
        guclu_kontrol(sonuclar)

    def _hata(self, e):
        self._yukleniyor = False
        self._durum_lbl.text = "Hata!"; self._durum_lbl.color = tema()["sat"]

    def _git(self, sc, *a):
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = sc

    def yenile(self):
        self._build(); self._yenile()

    def on_enter(self):
        self._canli.baslat()
        if not self._sonuclar and not self._yukleniyor:
            self._yenile()

# ════════════════════════════════════════════════════════════════════════
#  DETAY EKRANI
# ════════════════════════════════════════════════════════════════════════

class DetayEkran(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sem = ""; self._s = {}; self._df = None
        self._build()

    def yukle(self, sem, s):
        self._sem = sem; self._s = s; self._df = None
        self._build()
        threading.Thread(target=self._df_cek, daemon=True).start()

    def _df_cek(self):
        try:
            import trade_v7 as tv
            df = tv.veri_getir(self._sem)
            if not df.empty:
                self._df = df
                Clock.schedule_once(lambda dt: self._grafik())
        except Exception: pass

    def _grafik(self):
        if self._df is None or not hasattr(self, "_gv"): return
        sl = self._s.get("sl",0); tp = self._s.get("tp",0)
        html = plotly_html(self._df, self._sem, sl, tp, self._s)
        self._gv.yukle(html_kaydet(html))

    def _build(self):
        self.clear_widgets()
        t = tema(); s = self._s

        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(*t["bg"]); Rectangle(pos=root.pos, size=root.size)

        topbar = BoxLayout(size_hint_y=None, height=dp(54),
                           padding=[dp(8),dp(8)], spacing=dp(8))
        with topbar.canvas.before:
            Color(*t["bg2"]); Rectangle(pos=topbar.pos, size=topbar.size)
        geri = Button(text="<", font_size=dp(20),
                      size_hint=(None,None), size=(dp(42),dp(42)),
                      background_normal="", background_color=(0,0,0,0), color=t["ana"])
        geri.bind(on_press=self._geri)
        topbar.add_widget(geri)
        topbar.add_widget(GlowLabel(text=self._sem.replace(".IS",""),
                                    font_size=dp(20), halign="left", valign="middle"))
        ekle_b = Button(text="+Portfolyo", font_size=dp(11),
                        size_hint=(None,None), size=(dp(88),dp(34)),
                        background_normal="", background_color=(0,0,0,0),
                        color=t["ikincil"])
        ekle_b.bind(on_press=self._modal)
        topbar.add_widget(ekle_b)
        root.add_widget(topbar)

        if not s:
            root.add_widget(Label(text="Hisse secin", color=t["yazi2"]))
            self.add_widget(root); return

        sv = ScrollView(do_scroll_x=False)
        ic = GridLayout(cols=1, spacing=dp(8), padding=dp(10), size_hint_y=None)
        ic.bind(minimum_height=ic.setter("height"))

        karar  = s.get("karar","BEKLE"); toplam = s.get("toplam",0)
        fiyat  = s.get("fiyat",0); sl = s.get("sl",0); tp = s.get("tp",0)
        rsi    = s.get("rsi",0); adx = s.get("adx",0); atr = s.get("atr",0)
        ml     = s.get("ml"); anlik = s.get("anlik")

        # Grafik
        gk = RenkliKart(size_hint_y=None, height=dp(270))
        self._gv = GrafikView()
        gk.add_widget(self._gv)
        ic.add_widget(gk)

        # Karar
        kr = t["al"] if "AL" in karar else t["sat"] if "SAT" in karar else t["bekle"]
        kk = RenkliKart(size_hint_y=None, height=dp(68))
        kb = BoxLayout(orientation="vertical", padding=dp(10))
        kb.add_widget(Label(text=f"[b][color={hx2(kr)}]{karar}[/color][/b]",
                            markup=True, font_size=dp(20), size_hint_y=0.6))
        kb.add_widget(Label(text=f"Toplam Puan: [b]{toplam:+d}[/b]",
                            markup=True, color=t["yazi2"], font_size=dp(11), size_hint_y=0.4))
        kk.add_widget(kb); ic.add_widget(kk)

        # Fiyat
        if anlik and anlik.get("anlik"):
            gf = anlik["anlik"]
            gd = ((anlik["anlik"]-anlik["dunku"])/(anlik["dunku"]+1e-9)*100) if anlik.get("dunku") else 0
        else:
            gf = fiyat; gd = s.get("degisim",0)
        dr = t["al"] if gd>=0 else t["sat"]; ok = "+" if gd>=0 else ""
        rr = (tp-fiyat)/(fiyat-sl+1e-9)

        fk = RenkliKart(size_hint_y=None, height=dp(88))
        fg = GridLayout(cols=3, padding=dp(10), spacing=dp(6))
        for b2, d2 in [
            ("Fiyat", f"[b]{gf:.2f}[/b]"),
            ("Degisim", f"[color={hx2(dr)}]{ok}{gd:.2f}%[/color]"),
            ("ATR", f"{atr:.2f}"),
            (f"[color={hx2(t['sat'])}]SL[/color]", f"[color={hx2(t['sat'])}]{sl:.2f}[/color]"),
            (f"[color={hx2(t['al'])}]TP[/color]", f"[color={hx2(t['al'])}]{tp:.2f}[/color]"),
            ("R/R", f"{rr:.2f}x"),
        ]:
            cell = BoxLayout(orientation="vertical")
            cell.add_widget(Label(text=b2, markup=True, color=t["yazi2"], font_size=dp(10)))
            cell.add_widget(Label(text=d2, markup=True, color=t["yazi"], font_size=dp(13), bold=True))
            fg.add_widget(cell)
        fk.add_widget(fg); ic.add_widget(fk)

        # Gostergeler
        st = s.get("supertrend",0)
        ik2 = RenkliKart(size_hint_y=None, height=dp(68))
        ig = GridLayout(cols=4, padding=dp(8), spacing=dp(4))
        for b3, d3, rc in [
            ("RSI", f"{rsi:.0f}", t["al"] if rsi<40 else t["sat"] if rsi>60 else t["yazi"]),
            ("ADX", f"{adx:.0f}", t["ana"]),
            ("STrend", "UP" if st==1 else "DN", t["al"] if st==1 else t["sat"]),
            ("SAR", "AL" if s.get("sar") else "SAT", t["al"] if s.get("sar") else t["sat"]),
        ]:
            cell = BoxLayout(orientation="vertical")
            cell.add_widget(Label(text=b3, color=t["yazi2"], font_size=dp(10)))
            cell.add_widget(Label(text=f"[b][color={hx2(rc)}]{d3}[/color][/b]",
                                  markup=True, font_size=dp(14)))
            ig.add_widget(cell)
        ik2.add_widget(ig); ic.add_widget(ik2)

        # ML
        if ml:
            mk = RenkliKart(size_hint_y=None, height=dp(68))
            mb = BoxLayout(orientation="vertical", padding=dp(8))
            ens = "RF+HistGB" if ml.get("ensemble") else "RF"
            mb.add_widget(Label(
                text=f"[b]{ens}[/b]  WF:{ml.get('wf_acc',0)*100:.1f}%  N:{ml.get('n',0)}  Guven:{ml.get('guven',0)*100:.0f}%",
                markup=True, color=t["ana"], font_size=dp(11), halign="center"))
            pr = ml.get("proba",{})
            mb.add_widget(Label(
                text=f"AL {pr.get(1,0)*100:.0f}%  BEKLE {pr.get(0,0)*100:.0f}%  SAT {pr.get(-1,0)*100:.0f}%",
                color=t["yazi2"], font_size=dp(12), halign="center"))
            mk.add_widget(mb); ic.add_widget(mk)

        # ── v8: Whale ────────────────────────────────────────────────────
        whale = s.get("whale", {})
        if whale and whale.get("spike_var"):
            wk = RenkliKart(size_hint_y=None, height=dp(52))
            wb = BoxLayout(orientation="vertical", padding=dp(8))
            wc = t["al"] if whale.get("yon") == "AL" else t["sat"]
            wb.add_widget(Label(
                text=f"[b][color={hx2(wc)}]🐋 {whale.get('aciklama','')}[/color][/b]",
                markup=True, font_size=dp(12), halign="center"))
            wb.add_widget(Label(
                text=f"Hacim ×{whale.get('spike_katsayi',0):.1f}  OBV:%{whale.get('obv_ch',0):+.1f}  Güç:{whale.get('guc',1)}/3",
                color=t["yazi2"], font_size=dp(10), halign="center"))
            wk.add_widget(wb); ic.add_widget(wk)

        # ── v8: Korelasyon ───────────────────────────────────────────────
        kor = s.get("kor", {})
        if kor and kor.get("kor_60d") != 0:
            kork = RenkliKart(size_hint_y=None, height=dp(52))
            korb = BoxLayout(orientation="vertical", padding=dp(8))
            korc = t["al"] if kor.get("ayrisma") == "POZITIF" else t["sat"] if kor.get("ayrisma") == "NEGATIF" else t["yazi2"]
            korb.add_widget(Label(
                text=f"[b][color={hx2(korc)}]{kor.get('aciklama','')}[/color][/b]",
                markup=True, font_size=dp(12), halign="center"))
            korb.add_widget(Label(
                text=f"β:{kor.get('beta',1):.2f}  Kor:{kor.get('kor_60d',0):.2f}  RS14g:{kor.get('rs_14d',0):+.1f}%",
                color=t["yazi2"], font_size=dp(10), halign="center"))
            kork.add_widget(korb); ic.add_widget(kork)

        # ── v8: Trailing Stop ────────────────────────────────────────────
        trail = s.get("trail", {})
        if trail:
            sl_trail = trail.get("trailing_sl", 0)
            sl_stat  = s.get("sl", 0)
            trk = RenkliKart(size_hint_y=None, height=dp(52))
            trb = BoxLayout(orientation="horizontal", padding=dp(8), spacing=dp(10))
            trc = t["sat"] if trail.get("mesafe_pct", 5) < 2 else t["al"]
            for lb, val in [("Trailing SL", f"{sl_trail:.2f}"),
                            ("Statik SL",  f"{sl_stat:.2f}"),
                            ("Mesafe",     f"{trail.get('mesafe_pct',0):.1f}%")]:
                cell = BoxLayout(orientation="vertical")
                cell.add_widget(Label(text=lb, color=t["yazi2"], font_size=dp(10)))
                cell.add_widget(Label(text=f"[b][color={hx2(trc)}]{val}[/color][/b]",
                                      markup=True, font_size=dp(13)))
                trb.add_widget(cell)
            trk.add_widget(trb); ic.add_widget(trk)

        # ── v8: Monte Carlo ──────────────────────────────────────────────
        mc = s.get("mc", {})
        if mc:
            mck = RenkliKart(size_hint_y=None, height=dp(72))
            mcb = BoxLayout(orientation="vertical", padding=dp(8))
            mcc = t["al"] if mc.get("median_getiri", 0) > 0 else t["sat"]
            mcb.add_widget(Label(
                text=f"Monte Carlo  {mc.get('n_senaryo',1000)} Senaryo",
                color=t["ana"], font_size=dp(12), bold=True, halign="center"))
            mcg = GridLayout(cols=4, size_hint_y=None, height=dp(38))
            for lb, vl, vc in [
                ("Med.Get", f"{mc.get('median_getiri',0):+.1f}%", mcc),
                ("P10",     f"{mc.get('pct10',0):+.1f}%",         t["sat"]),
                ("P90",     f"{mc.get('pct90',0):+.1f}%",         t["al"]),
                ("MaxDD",   f"{mc.get('max_dd',0):.1f}%",         t["sat"]),
            ]:
                cell = BoxLayout(orientation="vertical")
                cell.add_widget(Label(text=lb, color=t["yazi2"], font_size=dp(9)))
                cell.add_widget(Label(text=f"[b][color={hx2(vc)}]{vl}[/color][/b]",
                                      markup=True, font_size=dp(12)))
                mcg.add_widget(cell)
            mcb.add_widget(mcg)
            mck.add_widget(mcb); ic.add_widget(mck)

        # ── v8: Kelly + FCS ──────────────────────────────────────────────
        kelly = s.get("kelly", {})
        fcs   = s.get("fcs", {})
        if kelly or fcs:
            kfk = RenkliKart(size_hint_y=None, height=dp(80))
            kfb = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(4))
            if kelly:
                kc2 = t["al"] if kelly.get("yoo_pct",0) > 10 else t["bekle"]
                kfb.add_widget(Label(
                    text=f"Kelly: {kelly.get('aciklama','')}",
                    color=kc2, font_size=dp(12), halign="center"))
                kfb.add_widget(Label(
                    text=f"Yarı-Kelly: %{kelly.get('yoo_pct',0):.1f}  WR:{kelly.get('win_rate',0)*100:.0f}%  R/R:{kelly.get('rr_oran',2):.1f}",
                    color=t["yazi2"], font_size=dp(11), halign="center"))
            if fcs:
                fs = fcs.get("skor", 50)
                fc = t["al"] if fs >= 70 else t["bekle"] if fs >= 50 else t["sat"]
                kfb.add_widget(Label(
                    text=f"Final Confidence Score: [b][color={hx2(fc)}]{fs:.1f}/100  {fcs.get('etiket','')}[/color][/b]",
                    markup=True, font_size=dp(13), halign="center"))
            kfk.add_widget(kfb); ic.add_widget(kfk)

        # Makro
        makro = s.get("makro",{})
        if makro:
            mak = RenkliKart(size_hint_y=None, height=dp(56))
            mb2 = BoxLayout(orientation="vertical", padding=dp(8))
            mb2.add_widget(Label(
                text=(f"USD/TRY:{makro.get('usdtry_5d',0):+.1%}  "
                      f"Altin:{makro.get('altin_5d',0):+.1%}  "
                      f"Brent:{makro.get('brent_5d',0):+.1%}  "
                      f"BIST:{makro.get('bist100_5d',0):+.1%}"),
                color=t["ikincil"], font_size=dp(10), halign="center"))
            vix = s.get("vix",{})
            if vix:
                vc = t["sat"] if vix.get("yuksek") else t["al"]
                mb2.add_widget(Label(
                    text=f"{'Yuksek VIX' if vix.get('yuksek') else 'Normal VIX'}  ATR%:{vix.get('atr_pct',0):.2f}",
                    color=vc, font_size=dp(10), halign="center"))
            mak.add_widget(mb2); ic.add_widget(mak)

        # Notlar
        notlar = s.get("notlar",[])
        if notlar:
            nk = RenkliKart(size_hint_y=None, height=dp(22*min(len(notlar),10)+14))
            nb = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(2))
            for n in notlar[:10]:
                nb.add_widget(Label(text=f"* {n}", color=t["yazi2"],
                                    font_size=dp(11), halign="left", valign="middle",
                                    size_hint_y=None, height=dp(20),
                                    text_size=(Window.width-dp(40), None)))
            nk.add_widget(nb); ic.add_widget(nk)

        sv.add_widget(ic); root.add_widget(sv)
        self.add_widget(root)

    def _modal(self, *a):
        if not self._sem: return
        t = tema()
        modal = ModalView(size_hint=(0.86, 0.42), background_color=t["bg"])
        box = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        with modal.canvas.before:
            Color(*t["bg2"])
            RoundedRectangle(pos=modal.pos, size=modal.size, radius=[dp(14)])

        box.add_widget(GlowLabel(text=f"+ {self._sem.replace('.IS','')} Portfolyo",
                                 font_size=dp(15), size_hint_y=None, height=dp(34)))
        adet_i = TextInput(hint_text="Adet (100)", multiline=False,
                           size_hint_y=None, height=dp(42),
                           background_color=t["kart"], foreground_color=t["yazi"],
                           hint_text_color=t["yazi2"], font_size=dp(14),
                           padding=[dp(10),dp(10)])
        fiyat_i = TextInput(
            hint_text=f"Alis Fiyati ({self._s.get('fiyat',0):.2f})",
            multiline=False, size_hint_y=None, height=dp(42),
            background_color=t["kart"], foreground_color=t["yazi"],
            hint_text_color=t["yazi2"], font_size=dp(14),
            padding=[dp(10),dp(10)])
        box.add_widget(adet_i); box.add_widget(fiyat_i)

        row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        ip = Button(text="Iptal", background_normal="",
                    background_color=t["kart"], color=t["yazi2"])
        ip.bind(on_press=modal.dismiss)
        ky = Button(text="Kaydet", background_normal="",
                    background_color=t["al"][:3]+(0.2,), color=t["al"], bold=True)

        def _kd(*x):
            try:
                portfolio_ekle(self._sem, float(adet_i.text.replace(",",".")),
                               float(fiyat_i.text.replace(",",".")))
                modal.dismiss()
            except ValueError:
                fiyat_i.hint_text = "Gecerli sayi girin"

        ky.bind(on_press=_kd)
        row.add_widget(ip); row.add_widget(ky)
        box.add_widget(row)
        modal.add_widget(box); modal.open()

    def _geri(self, *a):
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = "ana"

# ════════════════════════════════════════════════════════════════════════
#  PORTFOLYO EKRANI
# ════════════════════════════════════════════════════════════════════════

class PortfolioEkran(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()

    def on_enter(self):
        self._build()

    def _build(self):
        self.clear_widgets()
        t = tema()
        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(*t["bg"]); Rectangle(pos=root.pos, size=root.size)

        topbar = BoxLayout(size_hint_y=None, height=dp(54), padding=[dp(8),dp(8)])
        with topbar.canvas.before:
            Color(*t["bg2"]); Rectangle(pos=topbar.pos, size=topbar.size)
        geri = Button(text="<", font_size=dp(20),
                      size_hint=(None,None), size=(dp(42),dp(42)),
                      background_normal="", background_color=(0,0,0,0), color=t["ana"])
        geri.bind(on_press=self._geri)
        topbar.add_widget(geri)
        topbar.add_widget(GlowLabel(text="PORTFOYUm", font_size=dp(18),
                                    halign="left", valign="middle"))
        root.add_widget(topbar)

        sv = ScrollView(do_scroll_x=False)
        self._ic = GridLayout(cols=1, spacing=dp(6), padding=dp(10), size_hint_y=None)
        self._ic.bind(minimum_height=self._ic.setter("height"))
        sv.add_widget(self._ic)
        root.add_widget(sv)

        self._top_lbl = Label(text="", color=t["ana"], font_size=dp(13),
                              size_hint_y=None, height=dp(36), halign="center")
        root.add_widget(self._top_lbl)
        self.add_widget(root)
        threading.Thread(target=self._yukle, daemon=True).start()

    def _yukle(self):
        kayitlar = portfolio_listele()
        if not kayitlar:
            Clock.schedule_once(lambda dt: self._bos())
            return
        try:
            import trade_v7 as tv
            satirlar = []
            toplam_kz = 0.0
            for pid, sem, adet, alis, tarih in kayitlar:
                try:
                    df = tv.veri_getir(sem)
                    gun = float(df["Close"].iloc[-1]) if not df.empty else alis
                except Exception:
                    gun = alis
                kzp = (gun-alis)/(alis+1e-9)*100
                kzt = (gun-alis)*adet
                toplam_kz += kzt
                satirlar.append((pid, sem, adet, alis, gun, kzp, kzt, tarih))
            Clock.schedule_once(lambda dt: self._goster(satirlar, toplam_kz))
        except Exception as e:
            Clock.schedule_once(lambda dt: self._hata(str(e)))

    def _bos(self):
        self._ic.clear_widgets()
        t = tema()
        self._ic.add_widget(Label(
            text="Portfolyo bos.\nDetay ekranindan hisse ekleyin.",
            color=t["yazi2"], font_size=dp(13),
            size_hint_y=None, height=dp(80), halign="center"))

    def _goster(self, satirlar, tkz):
        self._ic.clear_widgets()
        t = tema()
        for pid, sem, adet, alis, gun, kzp, kzt, tarih in satirlar:
            kart = RenkliKart(size_hint_y=None, height=dp(78))
            box  = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(4))
            kr   = t["al"] if kzp>=0 else t["sat"]
            ok   = "+" if kzp>=0 else ""
            box.add_widget(Label(
                text=f"[b]{sem.replace('.IS','')}[/b]   Adet:{adet:.0f}   Alis:{alis:.2f}",
                markup=True, color=t["yazi"], font_size=dp(13), halign="left"))
            box.add_widget(Label(
                text=(f"Guncel: [b]{gun:.2f}[/b]   "
                      f"[color={hx2(kr)}]{ok}{kzp:.2f}%   {ok}{abs(kzt):.0f}[/color]"),
                markup=True, color=t["yazi2"], font_size=dp(12), halign="left"))
            sil = Button(text="X", font_size=dp(14),
                         size_hint=(None,None), size=(dp(32),dp(32)),
                         background_normal="", background_color=(0,0,0,0),
                         color=t["sat"])
            sil.bind(on_press=partial(self._sil, pid))
            rl = RelativeLayout(size_hint_y=None, height=dp(78))
            rl.add_widget(kart); rl.add_widget(box)
            sil.pos_hint = {"right":0.98,"top":0.95}
            rl.add_widget(sil)
            self._ic.add_widget(rl)
        kr2 = t["al"] if tkz>=0 else t["sat"]
        ok2 = "+" if tkz>=0 else ""
        self._top_lbl.text = f"Toplam K/Z: {ok2}{tkz:.2f}"
        self._top_lbl.color = kr2

    def _hata(self, e):
        self._ic.clear_widgets()
        t = tema()
        self._ic.add_widget(Label(text=f"Hata: {e[:50]}", color=t["sat"],
                                  size_hint_y=None, height=dp(50)))

    def _sil(self, pid, *a):
        portfolio_sil(pid)
        self._ic.clear_widgets()
        threading.Thread(target=self._yukle, daemon=True).start()

    def _geri(self, *a):
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = "ana"

# ════════════════════════════════════════════════════════════════════════
#  BACKTEST EKRANI
# ════════════════════════════════════════════════════════════════════════

class BacktestEkran(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()

    def _build(self):
        self.clear_widgets()
        t = tema()
        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(*t["bg"]); Rectangle(pos=root.pos, size=root.size)

        topbar = BoxLayout(size_hint_y=None, height=dp(54), padding=[dp(8),dp(8)])
        with topbar.canvas.before:
            Color(*t["bg2"]); Rectangle(pos=topbar.pos, size=topbar.size)
        geri = Button(text="<", font_size=dp(20),
                      size_hint=(None,None), size=(dp(42),dp(42)),
                      background_normal="", background_color=(0,0,0,0), color=t["ana"])
        geri.bind(on_press=self._geri)
        topbar.add_widget(geri)
        topbar.add_widget(GlowLabel(text="BACKTEST", font_size=dp(20),
                                    halign="left", valign="middle"))
        root.add_widget(topbar)

        sv = ScrollView(do_scroll_x=False)
        ic = GridLayout(cols=1, spacing=dp(8), padding=dp(12), size_hint_y=None)
        ic.bind(minimum_height=ic.setter("height"))

        for txt, tip in [("BIST Backtest","bist"),("ABD Backtest","abd")]:
            b = Button(text=txt, font_size=dp(15), size_hint_y=None, height=dp(50),
                       background_normal="", background_color=(0,0,0,0),
                       color=t["ana"], bold=True)
            b.bind(on_press=partial(self._calistir, tip))
            b.bind(pos=lambda *a, btn=b: self._btn_ciz(btn),
                   size=lambda *a, btn=b: self._btn_ciz(btn))
            ic.add_widget(b)

        self._sk = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        self._sk.bind(minimum_height=self._sk.setter("height"))
        ic.add_widget(self._sk)
        sv.add_widget(ic); root.add_widget(sv)
        self.add_widget(root)

    def _btn_ciz(self, b, *a):
        b.canvas.before.clear()
        t = tema()
        with b.canvas.before:
            Color(*t["ana"][:3], 0.15)
            RoundedRectangle(pos=b.pos, size=b.size, radius=[dp(10)])

    def _calistir(self, tip, *a):
        t = tema()
        self._sk.clear_widgets()
        self._sk.add_widget(Label(text="Hesaplaniyor...", color=t["bekle"],
                                  font_size=dp(13), size_hint_y=None, height=dp(36)))
        threading.Thread(target=self._hesapla, args=(tip,), daemon=True).start()

    def _hesapla(self, tip):
        try:
            import trade_v7 as tv
            sems = (list(tv.BIST_SEMBOLLER)[:8] if tip=="bist"
                    else [s for lst in tv.LISTELER.values()
                          for s in lst if not s.endswith(".IS")][:8])
            res = []
            for s in sems:
                df = tv.veri_getir(s)
                if df.empty or len(df)<200: continue
                bt = tv.backtest_calistir(s, df)
                if bt: res.append(bt)
            Clock.schedule_once(lambda dt: self._goster(res))
        except Exception as e:
            Clock.schedule_once(lambda dt: self._hata(str(e)))

    def _goster(self, res):
        t = tema()
        self._sk.clear_widgets()
        if not res:
            self._sk.add_widget(Label(text="Veri yetersiz", color=t["sat"],
                                      font_size=dp(13), size_hint_y=None, height=dp(36)))
            return
        for bt in sorted(res, key=lambda x: x["net_getiri"], reverse=True):
            k = RenkliKart(size_hint_y=None, height=dp(68))
            box = BoxLayout(orientation="vertical", padding=dp(10))
            nc = t["al"] if bt["net_getiri"]>=0 else t["sat"]
            wc = t["al"] if bt["winrate"]>=50 else t["sat"]
            em = "WIN" if bt["net_getiri"]>20 else ("OK" if bt["net_getiri"]>0 else "LOSS")
            box.add_widget(Label(
                text=f"[b]{bt['sembol'].replace('.IS','')}[/b]  {em}",
                markup=True, color=t["yazi"], font_size=dp(14), halign="left"))
            box.add_widget(Label(
                text=(f"Net:[color={hx2(nc)}]{bt['net_getiri']:+.1f}%[/color]  "
                      f"Win:[color={hx2(wc)}]{bt['winrate']:.0f}%[/color]  "
                      f"N:{bt['n_islem']}  DD:{bt['max_dd']:.1f}%"),
                markup=True, color=t["yazi2"], font_size=dp(11), halign="left"))
            k.add_widget(box); self._sk.add_widget(k)

    def _hata(self, e):
        self._sk.clear_widgets()
        t = tema()
        self._sk.add_widget(Label(text=f"Hata:{e[:50]}", color=t["sat"],
                                  size_hint_y=None, height=dp(36)))

    def _geri(self, *a):
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = "ana"

# ════════════════════════════════════════════════════════════════════════
#  AYARLAR EKRANI
# ════════════════════════════════════════════════════════════════════════

class AyarlarEkran(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()

    def _build(self):
        self.clear_widgets()
        t = tema()
        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(*t["bg"]); Rectangle(pos=root.pos, size=root.size)

        topbar = BoxLayout(size_hint_y=None, height=dp(54), padding=[dp(8),dp(8)])
        with topbar.canvas.before:
            Color(*t["bg2"]); Rectangle(pos=topbar.pos, size=topbar.size)
        geri = Button(text="<", font_size=dp(20),
                      size_hint=(None,None), size=(dp(42),dp(42)),
                      background_normal="", background_color=(0,0,0,0), color=t["ana"])
        geri.bind(on_press=self._geri)
        topbar.add_widget(geri)
        topbar.add_widget(GlowLabel(text="AYARLAR", font_size=dp(20),
                                    halign="left", valign="middle"))
        root.add_widget(topbar)

        sv = ScrollView(do_scroll_x=False)
        ic = BoxLayout(orientation="vertical", spacing=dp(10),
                       padding=dp(14), size_hint_y=None)
        ic.bind(minimum_height=ic.setter("height"))

        ic.add_widget(GlowLabel(text="TEMA SEC", font_size=dp(13),
                                size_hint_y=None, height=dp(26), halign="left"))
        for ta in TEMALAR:
            b = TemaButon(ta)
            b.bind(on_press=partial(self._tema, ta))
            ic.add_widget(b)

        ic.add_widget(GlowLabel(text="v7 PARAMETRELER", font_size=dp(13),
                                size_hint_y=None, height=dp(34), halign="left"))
        try:
            import trade_v7 as tv
            params = [
                ("ATR SL", f"{tv.ATR_SL}x"),("ATR TP", f"{tv.ATR_TP}x"),
                ("ML Ileri Gun", str(tv.ILERI_GUN)),
                ("Getiri Esigi", f"{tv.GETIRI_ESIGI*100:.1f}%"),
                ("Guclu Esik", str(tv.GUCLU_ESIK)),
                ("Makro", "ON" if tv.MAKRO_AKTIF else "OFF"),
                ("Sentiment", "ON" if tv.SENTIMENT_AKTIF else "OFF"),
                ("HistGB", "ON" if tv.ENSEMBLE_GB_AKTIF else "OFF"),
                ("SHAP", "ON" if tv.SHAP_ELEME_AKTIF else "OFF"),
            ]
        except Exception:
            params = [("trade_v7.py", "Yuklenemedi")]

        pk = RenkliKart(size_hint_y=None, height=dp(len(params)*28+16))
        pg = GridLayout(cols=2, padding=dp(10), spacing=dp(4))
        for k, v in params:
            pg.add_widget(Label(text=k, color=t["yazi2"], font_size=dp(12), halign="left"))
            pg.add_widget(Label(text=v, color=t["ana"], font_size=dp(12),
                                halign="right", bold=True))
        pk.add_widget(pg); ic.add_widget(pk)

        if PLYER_OK:
            tb = Button(text="Bildirim Testi", font_size=dp(13),
                        size_hint_y=None, height=dp(42),
                        background_normal="", background_color=(0,0,0,0),
                        color=t["ikincil"])
            tb.bind(on_press=lambda *a: bildirim_gonder("TEST","GUCLU AL",12))
            ic.add_widget(tb)

        sv.add_widget(ic); root.add_widget(sv)
        self.add_widget(root)

    def _tema(self, ta, *a):
        tema_sec(ta)
        app = App.get_running_app()
        for en in ["ana","detay","backtest","ayarlar","portfolio"]:
            try: app.sm.get_screen(en)._build()
            except Exception: pass
        self._build()

    def _geri(self, *a):
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = "ana"

# ════════════════════════════════════════════════════════════════════════
#  SPLASH + TEMA SECİCİ
# ════════════════════════════════════════════════════════════════════════

class SplashEkran(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        t = tema()
        lay = FloatLayout()
        with lay.canvas.before:
            Color(*t["bg"])
            self._bg = Rectangle(pos=lay.pos, size=lay.size)
        lay.bind(pos=lambda *a: setattr(self._bg,"pos",lay.pos),
                 size=lambda *a: setattr(self._bg,"size",lay.size))
        box = BoxLayout(orientation="vertical", spacing=dp(8),
                        size_hint=(0.8,0.38), pos_hint={"center_x":0.5,"center_y":0.56})
        box.add_widget(GlowLabel(text="Trade Sinyal\nULTRA v8.0",
                                 font_size=dp(24), halign="center",
                                 size_hint_y=None, height=dp(70)))
        box.add_widget(Label(text="Plotly | SQLite | Canlı | Kelly | Monte Carlo | Whale | FCS",
                             color=t["yazi2"], font_size=dp(11),
                             size_hint_y=None, height=dp(22)))
        lay.add_widget(box)
        self.add_widget(lay)

    def on_enter(self):
        Clock.schedule_once(lambda dt: setattr(self.manager, "current", "tema_secici"), 1.0)


class TemaSeciciEkran(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()

    def _build(self):
        self.clear_widgets()
        t = tema()
        lay = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(12))
        with lay.canvas.before:
            Color(*t["bg"])
            self._bg = Rectangle(pos=lay.pos, size=lay.size)
        lay.bind(pos=lambda *a: setattr(self._bg,"pos",lay.pos),
                 size=lambda *a: setattr(self._bg,"size",lay.size))
        lay.add_widget(GlowLabel(text="TEMA SEC", font_size=dp(28),
                                 size_hint_y=None, height=dp(48), halign="center"))
        lay.add_widget(Label(text="Uygulamanin gorununumunu belirle",
                             color=t["yazi2"], font_size=dp(13),
                             size_hint_y=None, height=dp(26), halign="center"))
        for ta in TEMALAR:
            b = TemaButon(ta)
            b.bind(on_press=partial(self._sec, ta))
            lay.add_widget(b)
        lay.add_widget(Label())
        self.add_widget(lay)

    def _sec(self, ta, *a):
        tema_sec(ta)
        app = App.get_running_app()
        app.sm.get_screen("ana").yenile()
        app.sm.transition = SlideTransition(direction="left")
        app.sm.current = "ana"

# ════════════════════════════════════════════════════════════════════════
#  UYGULAMA
# ════════════════════════════════════════════════════════════════════════

class TradeApp(App):
    def build(self):
        Window.clearcolor = tema()["bg"]
        self.sm = ScreenManager()
        self.sm.add_widget(SplashEkran(name="splash"))
        self.sm.add_widget(TemaSeciciEkran(name="tema_secici"))
        self.sm.add_widget(AnaEkran(name="ana"))
        self.sm.add_widget(DetayEkran(name="detay"))
        self.sm.add_widget(BacktestEkran(name="backtest"))
        self.sm.add_widget(AyarlarEkran(name="ayarlar"))
        self.sm.add_widget(PortfolioEkran(name="portfolio"))
        return self.sm

    def get_application_name(self):
        return "Trade Sinyal Ultra"

    def on_pause(self): return True
    def on_resume(self): pass


if __name__ == "__main__":
    TradeApp().run()
