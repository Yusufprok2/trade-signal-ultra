"""
Trade Sinyal Sistemi ULTRA v7.0 — Kivy Android APK
3 Tema: Terminal (Siber Yeşil) | Glassmorphism (Violet) | Dark Premium (Altın)
"""

import threading
import time
from functools import partial

from kivy.app import App
from kivy.clock import Clock
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
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.animation import Animation

# ════════════════════════════════════════════════════════════════════════
#  TEMA SİSTEMİ
# ════════════════════════════════════════════════════════════════════════

TEMALAR = {
    "terminal": {
        "ad":          "Terminal",
        "altyazi":     "Bloomberg Tarzı",
        "bg":          (0.04, 0.04, 0.04, 1),
        "bg2":         (0.08, 0.08, 0.08, 1),
        "kart":        (0.06, 0.06, 0.06, 1),
        "ana":         (0.0,  1.0,  0.255, 1),    # Siber Yeşil #00FF41
        "ikincil":     (0.0,  0.8,  0.2,  1),
        "yazi":        (0.85, 0.95, 0.85, 1),
        "yazi2":       (0.5,  0.7,  0.5,  1),
        "al":          (0.0,  1.0,  0.255, 1),
        "sat":         (1.0,  0.25, 0.25, 1),
        "bekle":       (0.7,  0.7,  0.0,  1),
        "font":        "RobotoMono-Regular",
        "font_baslik": "RobotoMono-Regular",
        "kenar_r":     2,
    },
    "glassmorphism": {
        "ad":          "Glassmorphism",
        "altyazi":     "Modern Cam Efekti",
        "bg":          (0.06, 0.04, 0.12, 1),
        "bg2":         (0.10, 0.07, 0.18, 1),
        "kart":        (0.12, 0.08, 0.22, 0.85),
        "ana":         (0.655, 0.545, 0.98,  1),  # Violet #A78BFA
        "ikincil":     (0.22, 0.74, 0.98,  1),   # Ocean #38BDF8
        "yazi":        (0.93, 0.90, 1.0,   1),
        "yazi2":       (0.65, 0.60, 0.85,  1),
        "al":          (0.22, 0.98, 0.6,   1),
        "sat":         (0.98, 0.35, 0.45,  1),
        "bekle":       (0.655, 0.545, 0.98, 1),
        "font":        "Roboto-Regular",
        "font_baslik": "Roboto-Bold",
        "kenar_r":     16,
    },
    "dark_premium": {
        "ad":          "Dark Premium",
        "altyazi":     "Lüks Metal",
        "bg":          (0.05, 0.04, 0.03, 1),
        "bg2":         (0.09, 0.07, 0.04, 1),
        "kart":        (0.10, 0.08, 0.05, 1),
        "ana":         (0.83, 0.686, 0.216, 1),   # Altın #D4AF37
        "ikincil":     (0.604, 0.69, 0.784, 1),  # Gümüş #9AB0C8
        "yazi":        (0.95, 0.92, 0.85, 1),
        "yazi2":       (0.65, 0.60, 0.50, 1),
        "al":          (0.83, 0.686, 0.216, 1),
        "sat":         (0.72, 0.20, 0.15, 1),
        "bekle":       (0.604, 0.69, 0.784, 1),
        "font":        "Roboto-Regular",
        "font_baslik": "Roboto-Bold",
        "kenar_r":     8,
    },
}

_aktif_tema = "terminal"

def tema():
    return TEMALAR[_aktif_tema]

def tema_sec(ad):
    global _aktif_tema
    _aktif_tema = ad

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
            Color(*t["ana"][:3], 0.3)
            Line(rounded_rectangle=[self.x, self.y, self.width, self.height,
                                    dp(t["kenar_r"])], width=dp(1))


class GlowLabel(Label):
    """Ana renkte parlayan başlık etiketi."""
    def __init__(self, glow=True, **kwargs):
        t = tema()
        kwargs.setdefault("color", t["ana"])
        kwargs.setdefault("font_name", t["font_baslik"])
        kwargs.setdefault("bold", True)
        super().__init__(**kwargs)
        self.glow = glow


class KararBadge(Label):
    """AL / SAT / BEKLE rozeti."""
    def __init__(self, karar="BEKLE", **kwargs):
        t = tema()
        if "GÜÇLÜ AL" in karar or karar == "AL":
            renk = t["al"]
        elif "GÜÇLÜ SAT" in karar or karar == "SAT":
            renk = t["sat"]
        else:
            renk = t["bekle"]
        kwargs["text"] = karar
        kwargs["color"] = renk
        kwargs["bold"] = True
        kwargs["font_name"] = t["font"]
        super().__init__(**kwargs)
        self.bind(pos=self._ciz, size=self._ciz)

    def _ciz(self, *a):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.color[:3], 0.15)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(6)])


class TemaButon(Button):
    def __init__(self, tema_ad, **kwargs):
        self.tema_ad = tema_ad
        t_data = TEMALAR[tema_ad]
        kwargs["text"] = f"[b]{t_data['ad']}[/b]\n[size=12]{t_data['altyazi']}[/size]"
        kwargs["markup"] = True
        kwargs["size_hint_y"] = None
        kwargs["height"] = dp(80)
        kwargs["background_normal"] = ""
        kwargs["background_color"] = (0, 0, 0, 0)
        kwargs["color"] = t_data["ana"]
        super().__init__(**kwargs)
        self.bind(pos=self._ciz, size=self._ciz)

    def _ciz(self, *a):
        self.canvas.before.clear()
        t_data = TEMALAR[self.tema_ad]
        with self.canvas.before:
            Color(*t_data["kart"])
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])
            Color(*t_data["ana"][:3], 0.5)
            Line(rounded_rectangle=[self.x, self.y, self.width, self.height, dp(12)], width=dp(1.5))


# ════════════════════════════════════════════════════════════════════════
#  EKRANLAR
# ════════════════════════════════════════════════════════════════════════

class SplashEkran(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()

    def _build(self):
        self.clear_widgets()
        t = tema()
        layout = FloatLayout()
        with layout.canvas.before:
            Color(*t["bg"])
            self._bg_rect = Rectangle(pos=layout.pos, size=layout.size)
        layout.bind(pos=lambda *a: setattr(self._bg_rect, "pos", layout.pos),
                    size=lambda *a: setattr(self._bg_rect, "size", layout.size))

        # Logo kutusu
        logo_box = BoxLayout(orientation="vertical", spacing=dp(8),
                             size_hint=(0.8, 0.35),
                             pos_hint={"center_x": 0.5, "center_y": 0.55})

        logo_box.add_widget(GlowLabel(
            text="🏦", font_size=dp(64), size_hint_y=None, height=dp(80)))
        logo_box.add_widget(GlowLabel(
            text="TRADE SİNYAL\nULTRA v7.0",
            font_size=dp(22), halign="center", valign="middle",
            size_hint_y=None, height=dp(60)))
        logo_box.add_widget(Label(
            text="RF+HistGB | Makro | Sentiment",
            color=t["yazi2"], font_size=dp(12),
            size_hint_y=None, height=dp(24)))

        layout.add_widget(logo_box)

        # Yükleniyor
        self._yukleniyor = Label(
            text="Başlatılıyor...", color=t["yazi2"],
            font_size=dp(13), size_hint=(1, None), height=dp(32),
            pos_hint={"center_x": 0.5, "y": 0.15})
        layout.add_widget(self._yukleniyor)

        self.add_widget(layout)

    def on_enter(self):
        Clock.schedule_once(self._gecis, 0.5)

    def _gecis(self, dt):
        self.manager.current = "tema_secici"


class TemaSeciciEkran(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()

    def _build(self):
        self.clear_widgets()
        t = tema()
        layout = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(16))
        with layout.canvas.before:
            Color(*t["bg"])
            self._bg = Rectangle(pos=layout.pos, size=layout.size)
        layout.bind(pos=lambda *a: setattr(self._bg, "pos", layout.pos),
                    size=lambda *a: setattr(self._bg, "size", layout.size))

        layout.add_widget(GlowLabel(
            text="TEMA SEÇ", font_size=dp(28),
            size_hint_y=None, height=dp(50), halign="center"))
        layout.add_widget(Label(
            text="Uygulamanın görünümünü belirle",
            color=t["yazi2"], font_size=dp(13),
            size_hint_y=None, height=dp(28), halign="center"))

        for tema_ad in TEMALAR:
            btn = TemaButon(tema_ad)
            btn.bind(on_press=partial(self._sec, tema_ad))
            layout.add_widget(btn)

        layout.add_widget(Label())  # spacer
        self.add_widget(layout)

    def _sec(self, tema_ad, *a):
        tema_sec(tema_ad)
        App.get_running_app().sm.get_screen("ana").yenile()
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = "ana"


class HisseSatiri(BoxLayout):
    def __init__(self, sembol, sonuc, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=dp(52), spacing=dp(4), **kwargs)
        t = tema()
        self.sembol = sembol
        self.sonuc = sonuc

        karar = sonuc.get("karar", "⚪ BEKLE")
        toplam = sonuc.get("toplam", 0)
        rsi = sonuc.get("rsi", 0)
        fiyat = sonuc.get("fiyat", 0)
        degisim = sonuc.get("degisim", 0)
        anlik = sonuc.get("anlik")

        if anlik and anlik.get("anlik"):
            goster_fiyat = anlik["anlik"]
            goster_deg = ((anlik["anlik"] - anlik["dunku"]) / (anlik["dunku"] + 1e-9) * 100) if anlik.get("dunku") else 0
        else:
            goster_fiyat = fiyat
            goster_deg = degisim

        if "GÜÇLÜ AL" in karar or "AL" in karar:
            k_renk = t["al"]
            k_kisa = "🟢 AL"
        elif "GÜÇLÜ SAT" in karar or "SAT" in karar:
            k_renk = t["sat"]
            k_kisa = "🔴 SAT"
        else:
            k_renk = t["bekle"]
            k_kisa = "⚪ HOL"

        deg_renk = t["al"] if goster_deg >= 0 else t["sat"]
        deg_ok = "▲" if goster_deg >= 0 else "▼"

        # Arkaplan
        with self.canvas.before:
            Color(*t["kart"])
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8)])
        self.bind(pos=lambda *a: setattr(self._bg, "pos", self.pos),
                  size=lambda *a: setattr(self._bg, "size", self.size))

        # Sembol
        self.add_widget(Label(
            text=f"[b]{sembol.replace('.IS','')}[/b]",
            markup=True, color=t["yazi"],
            font_name=t["font"], font_size=dp(13),
            size_hint_x=0.22, halign="left", valign="middle",
            text_size=(None, None)))

        # Fiyat + değişim
        self.add_widget(Label(
            text=f"[b]{goster_fiyat:.2f}[/b]\n[color={self._hex(deg_renk)}]{deg_ok}{abs(goster_deg):.1f}%[/color]",
            markup=True, color=t["yazi"],
            font_size=dp(12), size_hint_x=0.22,
            halign="center", valign="middle"))

        # RSI
        self.add_widget(Label(
            text=f"RSI\n{rsi:.0f}",
            color=t["yazi2"], font_size=dp(11),
            size_hint_x=0.14, halign="center", valign="middle"))

        # Skor
        skor_renk = t["al"] if toplam > 0 else t["sat"] if toplam < 0 else t["bekle"]
        self.add_widget(Label(
            text=f"[b][color={self._hex(skor_renk)}]{toplam:+d}[/color][/b]",
            markup=True, font_size=dp(14),
            size_hint_x=0.14, halign="center", valign="middle"))

        # Karar badge
        self.add_widget(Label(
            text=f"[b][color={self._hex(k_renk)}]{k_kisa}[/color][/b]",
            markup=True, font_size=dp(12),
            size_hint_x=0.28, halign="right", valign="middle"))

    def _hex(self, rgba):
        return "{:02x}{:02x}{:02x}".format(
            int(rgba[0]*255), int(rgba[1]*255), int(rgba[2]*255))

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            app = App.get_running_app()
            detay = app.sm.get_screen("detay")
            detay.yukle(self.sembol, self.sonuc)
            app.sm.transition = SlideTransition(direction="left")
            app.sm.current = "detay"
            return True
        return super().on_touch_down(touch)


class AnaEkran(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sonuclar = {}
        self._yukleniyor = False
        self._build()

    def _build(self):
        self.clear_widgets()
        t = tema()

        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(*t["bg"])
            self._bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=lambda *a: setattr(self._bg, "pos", root.pos),
                  size=lambda *a: setattr(self._bg, "size", root.size))

        # ── Üst bar ──
        topbar = BoxLayout(size_hint_y=None, height=dp(56),
                           padding=[dp(12), dp(8)], spacing=dp(8))
        with topbar.canvas.before:
            Color(*t["bg2"])
            Rectangle(pos=topbar.pos, size=topbar.size)
        topbar.bind(pos=lambda *a: self._ciz_topbar(topbar),
                    size=lambda *a: self._ciz_topbar(topbar))

        topbar.add_widget(GlowLabel(
            text="🏦 TRADE v7", font_size=dp(18),
            size_hint_x=0.5, halign="left", valign="middle"))

        self._durum_lbl = Label(
            text="●  Hazır", color=t["ana"],
            font_size=dp(11), size_hint_x=0.3, halign="right", valign="middle")
        topbar.add_widget(self._durum_lbl)

        ayar_btn = Button(text="⚙", font_size=dp(20),
                          size_hint=(None, None), size=(dp(44), dp(44)),
                          background_normal="", background_color=(0,0,0,0),
                          color=t["yazi2"])
        ayar_btn.bind(on_press=self._ayarlara_git)
        topbar.add_widget(ayar_btn)
        root.add_widget(topbar)

        # ── Tab bar ──
        tabbar = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(4),
                           padding=[dp(8), dp(4)])
        self._tab_btns = {}
        for etiket in ["🇹🇷 BIST", "🇺🇸 S&P", "⚡ Tekno"]:
            btn = Button(text=etiket, font_size=dp(12),
                         background_normal="", background_color=(0,0,0,0),
                         color=t["yazi2"], bold=False)
            btn.bind(on_press=partial(self._tab_sec, etiket))
            self._tab_btns[etiket] = btn
            tabbar.add_widget(btn)
        root.add_widget(tabbar)
        self._aktif_tab = "🇹🇷 BIST"
        self._tab_sec("🇹🇷 BIST")

        # ── Liste ──
        scroll = ScrollView(do_scroll_x=False)
        self._liste = GridLayout(cols=1, spacing=dp(4),
                                 padding=[dp(8), dp(4)],
                                 size_hint_y=None)
        self._liste.bind(minimum_height=self._liste.setter("height"))
        scroll.add_widget(self._liste)
        root.add_widget(scroll)

        # ── Alt butonlar ──
        altbar = BoxLayout(size_hint_y=None, height=dp(56),
                           spacing=dp(8), padding=[dp(8), dp(6)])
        with altbar.canvas.before:
            Color(*t["bg2"])
            Rectangle(pos=altbar.pos, size=altbar.size)

        for metin, handler in [("🔄 Yenile", self._yenile), ("📊 Backtest", self._backtest_git)]:
            btn = Button(text=metin, font_size=dp(13),
                         background_normal="", background_color=(0,0,0,0),
                         color=t["ana"], bold=True)
            btn.bind(pos=lambda *a, b=btn: self._ciz_btn(b),
                     size=lambda *a, b=btn: self._ciz_btn(b))
            btn.bind(on_press=handler)
            altbar.add_widget(btn)

        root.add_widget(altbar)
        self.add_widget(root)

        if self._sonuclar:
            self._liste_guncelle()

    def _ciz_topbar(self, w, *a):
        w.canvas.before.clear()
        t = tema()
        with w.canvas.before:
            Color(*t["bg2"])
            Rectangle(pos=w.pos, size=w.size)

    def _ciz_btn(self, btn, *a):
        btn.canvas.before.clear()
        t = tema()
        with btn.canvas.before:
            Color(*t["ana"][:3], 0.15)
            RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(8)])

    def _tab_sec(self, etiket, *a):
        t = tema()
        self._aktif_tab = etiket
        for k, b in self._tab_btns.items():
            if k == etiket:
                b.color = t["ana"]; b.bold = True
            else:
                b.color = t["yazi2"]; b.bold = False
        self._liste_guncelle()

    def _liste_guncelle(self):
        self._liste.clear_widgets()
        t = tema()
        if not self._sonuclar:
            self._liste.add_widget(Label(
                text="Veri yükleniyor...", color=t["yazi2"],
                font_size=dp(14), size_hint_y=None, height=dp(60)))
            return

        # Tab filtreleme
        tab_map = {"🇹🇷 BIST": ".IS", "🇺🇸 S&P": "", "⚡ Tekno": ""}
        tab_semboller = {
            "🇹🇷 BIST":  [s for s in self._sonuclar if s.endswith(".IS")],
            "🇺🇸 S&P":   [s for s in self._sonuclar if not s.endswith(".IS")][:20],
            "⚡ Tekno":  ["NVDA","AMD","INTC","QCOM","AVGO","CRM","ADBE","NOW","SNOW","PLTR"],
        }
        liste = tab_semboller.get(self._aktif_tab, list(self._sonuclar.keys()))

        # Skor'a göre sırala
        liste = sorted([s for s in liste if s in self._sonuclar],
                       key=lambda s: abs(self._sonuclar[s].get("toplam", 0)),
                       reverse=True)

        if not liste:
            self._liste.add_widget(Label(
                text="Bu listede hisse yok", color=t["yazi2"],
                font_size=dp(13), size_hint_y=None, height=dp(60)))
            return

        for sembol in liste:
            s = self._sonuclar[sembol]
            if "hata" in s:
                continue
            self._liste.add_widget(HisseSatiri(sembol, s))

    def _yenile(self, *a):
        if self._yukleniyor:
            return
        self._yukleniyor = True
        self._durum_lbl.text = "●  Yükleniyor..."
        self._durum_lbl.color = tema()["bekle"]
        threading.Thread(target=self._veri_cek, daemon=True).start()

    def _veri_cek(self):
        try:
            import trade_v7 as tv
            from concurrent.futures import ThreadPoolExecutor, as_completed
            semboller = list(dict.fromkeys(s for lst in tv.LISTELER.values() for s in lst))
            sonuclar = {}
            with ThreadPoolExecutor(max_workers=4) as ex:
                futures = {ex.submit(tv.analiz, s, False): s for s in semboller}
                for fut in as_completed(futures):
                    s = futures[fut]
                    try:
                        r = fut.result()
                        if r:
                            sonuclar[s] = r
                    except Exception:
                        pass
            Clock.schedule_once(lambda dt: self._veri_tamam(sonuclar))
        except Exception as e:
            Clock.schedule_once(lambda dt: self._veri_hata(str(e)))

    def _veri_tamam(self, sonuclar):
        self._sonuclar = sonuclar
        self._yukleniyor = False
        t = tema()
        self._durum_lbl.text = f"●  {len(sonuclar)} hisse"
        self._durum_lbl.color = t["al"]
        self._liste_guncelle()

    def _veri_hata(self, hata):
        self._yukleniyor = False
        self._durum_lbl.text = "●  Hata!"
        self._durum_lbl.color = tema()["sat"]

    def _ayarlara_git(self, *a):
        self.manager.transition = SlideTransition(direction="up")
        self.manager.current = "ayarlar"

    def _backtest_git(self, *a):
        self.manager.transition = SlideTransition(direction="left")
        self.manager.current = "backtest"

    def yenile(self):
        self._build()
        self._yenile()

    def on_enter(self):
        if not self._sonuclar and not self._yukleniyor:
            self._yenile()


class DetayEkran(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sembol = ""
        self._sonuc = {}
        self._build()

    def yukle(self, sembol, sonuc):
        self._sembol = sembol
        self._sonuc = sonuc
        self._build()

    def _build(self):
        self.clear_widgets()
        t = tema()
        s = self._sonuc

        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(*t["bg"])
            Rectangle(pos=root.pos, size=root.size)

        # ── Üst bar ──
        topbar = BoxLayout(size_hint_y=None, height=dp(56),
                           padding=[dp(8), dp(8)], spacing=dp(8))
        with topbar.canvas.before:
            Color(*t["bg2"])
            Rectangle(pos=topbar.pos, size=topbar.size)

        geri_btn = Button(text="←", font_size=dp(22),
                          size_hint=(None, None), size=(dp(44), dp(44)),
                          background_normal="", background_color=(0,0,0,0),
                          color=t["ana"])
        geri_btn.bind(on_press=self._geri)
        topbar.add_widget(geri_btn)
        topbar.add_widget(GlowLabel(
            text=self._sembol.replace(".IS", ""),
            font_size=dp(20), halign="left", valign="middle"))
        root.add_widget(topbar)

        if not s:
            root.add_widget(Label(text="Hisse seçin", color=t["yazi2"]))
            self.add_widget(root)
            return

        scroll = ScrollView(do_scroll_x=False)
        icerik = GridLayout(cols=1, spacing=dp(8), padding=dp(12),
                            size_hint_y=None)
        icerik.bind(minimum_height=icerik.setter("height"))

        karar = s.get("karar","⚪ BEKLE"); toplam = s.get("toplam",0)
        fiyat = s.get("fiyat",0); sl = s.get("sl",0); tp = s.get("tp",0)
        rsi = s.get("rsi",0); adx = s.get("adx",0); atr = s.get("atr",0)
        ml = s.get("ml")
        anlik = s.get("anlik")

        # ── Karar kartı ──
        karar_kart = RenkliKart(size_hint_y=None, height=dp(90))
        k_box = BoxLayout(orientation="vertical", padding=dp(12))

        if "AL" in karar: k_renk = t["al"]
        elif "SAT" in karar: k_renk = t["sat"]
        else: k_renk = t["bekle"]

        k_box.add_widget(Label(
            text=f"[b][color={self._hex(k_renk)}]{karar}[/color][/b]",
            markup=True, font_size=dp(22), size_hint_y=0.6))
        k_box.add_widget(Label(
            text=f"Toplam Puan: [b]{toplam:+d}[/b]",
            markup=True, color=t["yazi2"], font_size=dp(13), size_hint_y=0.4))
        karar_kart.add_widget(k_box)
        icerik.add_widget(karar_kart)

        # ── Fiyat kartı ──
        fiyat_kart = RenkliKart(size_hint_y=None, height=dp(100))
        f_grid = GridLayout(cols=3, padding=dp(10), spacing=dp(6))
        if anlik and anlik.get("anlik"):
            gf = anlik["anlik"]
            gd = ((anlik["anlik"] - anlik["dunku"]) / (anlik["dunku"] + 1e-9) * 100) if anlik.get("dunku") else 0
        else:
            gf = fiyat; gd = s.get("degisim", 0)
        deg_renk = t["al"] if gd >= 0 else t["sat"]
        ok = "▲" if gd >= 0 else "▼"

        for baslik_m, deger_m in [
            ("Fiyat", f"[b]{gf:.2f}[/b]"),
            ("Değişim", f"[color={self._hex(deg_renk)}]{ok}{abs(gd):.2f}%[/color]"),
            ("ATR", f"{atr:.2f}"),
            (f"[color={self._hex(t['sat'])}]SL[/color]", f"[color={self._hex(t['sat'])}]{sl:.2f}[/color]"),
            (f"[color={self._hex(t['al'])}]TP[/color]", f"[color={self._hex(t['al'])}]{tp:.2f}[/color]"),
            ("R/R", f"{(tp-fiyat)/(fiyat-sl+1e-9):.2f}x"),
        ]:
            cell = BoxLayout(orientation="vertical")
            cell.add_widget(Label(text=baslik_m, markup=True,
                                  color=t["yazi2"], font_size=dp(10)))
            cell.add_widget(Label(text=deger_m, markup=True,
                                  color=t["yazi"], font_size=dp(13), bold=True))
            f_grid.add_widget(cell)
        fiyat_kart.add_widget(f_grid)
        icerik.add_widget(fiyat_kart)

        # ── Göstergeler kartı ──
        ind_kart = RenkliKart(size_hint_y=None, height=dp(80))
        ind_grid = GridLayout(cols=4, padding=dp(10), spacing=dp(4))
        st = s.get("supertrend", 0)
        st_renk = t["al"] if st == 1 else t["sat"]
        for b, d, rc in [
            ("RSI", f"{rsi:.0f}", t["al"] if rsi < 40 else t["sat"] if rsi > 60 else t["yazi"]),
            ("ADX", f"{adx:.0f}", t["ana"]),
            ("SuperTrend", "↑" if st == 1 else "↓", st_renk),
            ("SAR", "AL" if s.get("sar") else "SAT",
             t["al"] if s.get("sar") else t["sat"]),
        ]:
            cell = BoxLayout(orientation="vertical")
            cell.add_widget(Label(text=b, color=t["yazi2"], font_size=dp(10)))
            cell.add_widget(Label(text=f"[b][color={self._hex(rc)}]{d}[/color][/b]",
                                  markup=True, font_size=dp(14)))
            ind_grid.add_widget(cell)
        ind_kart.add_widget(ind_grid)
        icerik.add_widget(ind_kart)

        # ── ML kartı ──
        if ml:
            ml_kart = RenkliKart(size_hint_y=None, height=dp(80))
            ml_box = BoxLayout(orientation="vertical", padding=dp(10))
            ens = "RF+HistGB" if ml.get("ensemble") else "RF"
            ml_box.add_widget(Label(
                text=f"[b]{ens} Ensemble[/b]  •  WF-Acc: {ml.get('wf_acc',0)*100:.1f}%  •  Eğitim: {ml.get('n',0)} gün",
                markup=True, color=t["ana"], font_size=dp(12), halign="center"))
            proba = ml.get("proba", {})
            al_p = proba.get(1, 0); sat_p = proba.get(-1, 0); hol_p = proba.get(0, 0)
            ml_box.add_widget(Label(
                text=f"AL {al_p*100:.0f}%   BEKLE {hol_p*100:.0f}%   SAT {sat_p*100:.0f}%",
                color=t["yazi2"], font_size=dp(12), halign="center"))
            ml_kart.add_widget(ml_box)
            icerik.add_widget(ml_kart)

        # ── Makro kartı ──
        makro = s.get("makro", {})
        if makro:
            makro_kart = RenkliKart(size_hint_y=None, height=dp(70))
            mb = BoxLayout(orientation="vertical", padding=dp(8))
            ust = makro.get("usdtry_5d", 0); alt = makro.get("altin_5d", 0)
            brt = makro.get("brent_5d", 0); bis = makro.get("bist100_5d", 0)
            mb.add_widget(Label(
                text=f"USD/TRY: {ust:+.1%}   Altın: {alt:+.1%}   Brent: {brt:+.1%}   BIST100: {bis:+.1%}",
                color=t["ikincil"], font_size=dp(11), halign="center"))
            vix = s.get("vix", {})
            if vix:
                vc = t["sat"] if vix.get("yuksek") else t["al"]
                vs = "⚡ Yüksek VIX" if vix.get("yuksek") else "✅ Normal VIX"
                mb.add_widget(Label(
                    text=f"{vs}  ATR%: {vix.get('atr_pct',0):.2f}",
                    color=vc, font_size=dp(11), halign="center"))
            makro_kart.add_widget(mb)
            icerik.add_widget(makro_kart)

        # ── Notlar ──
        notlar = s.get("notlar", [])
        if notlar:
            notlar_kart = RenkliKart(size_hint_y=None,
                                     height=dp(24 * min(len(notlar), 10) + 20))
            nb = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(2))
            for n in notlar[:10]:
                nb.add_widget(Label(
                    text=f"• {n}", color=t["yazi2"],
                    font_size=dp(11), halign="left", valign="middle",
                    size_hint_y=None, height=dp(22),
                    text_size=(Window.width - dp(60), None)))
            notlar_kart.add_widget(nb)
            icerik.add_widget(notlar_kart)

        scroll.add_widget(icerik)
        root.add_widget(scroll)
        self.add_widget(root)

    def _hex(self, rgba):
        return "{:02x}{:02x}{:02x}".format(
            int(rgba[0]*255), int(rgba[1]*255), int(rgba[2]*255))

    def _geri(self, *a):
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = "ana"


class BacktestEkran(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()

    def _build(self):
        self.clear_widgets()
        t = tema()
        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(*t["bg"])
            Rectangle(pos=root.pos, size=root.size)

        topbar = BoxLayout(size_hint_y=None, height=dp(56),
                           padding=[dp(8), dp(8)])
        with topbar.canvas.before:
            Color(*t["bg2"])
            Rectangle(pos=topbar.pos, size=topbar.size)
        geri_btn = Button(text="←", font_size=dp(22),
                          size_hint=(None, None), size=(dp(44), dp(44)),
                          background_normal="", background_color=(0,0,0,0),
                          color=t["ana"])
        geri_btn.bind(on_press=self._geri)
        topbar.add_widget(geri_btn)
        topbar.add_widget(GlowLabel(text="BACKTEST", font_size=dp(20),
                                    halign="left", valign="middle"))
        root.add_widget(topbar)

        scroll = ScrollView(do_scroll_x=False)
        icerik = GridLayout(cols=1, spacing=dp(8), padding=dp(12),
                            size_hint_y=None)
        icerik.bind(minimum_height=icerik.setter("height"))

        icerik.add_widget(Label(
            text="Backtest başlatmak için BIST veya ABD seçin:",
            color=t["yazi2"], font_size=dp(13),
            size_hint_y=None, height=dp(40), halign="center"))

        for metin, handler in [("🇹🇷 BIST Backtest", partial(self._calistir, "bist")),
                                ("🇺🇸 ABD Backtest",  partial(self._calistir, "abd"))]:
            btn = Button(text=metin, font_size=dp(15),
                         size_hint_y=None, height=dp(56),
                         background_normal="", background_color=(0,0,0,0),
                         color=t["ana"], bold=True)
            btn.bind(pos=lambda *a, b=btn: self._ciz_btn(b),
                     size=lambda *a, b=btn: self._ciz_btn(b))
            btn.bind(on_press=handler)
            icerik.add_widget(btn)

        self._sonuc_kutu = GridLayout(cols=1, spacing=dp(6),
                                      size_hint_y=None)
        self._sonuc_kutu.bind(minimum_height=self._sonuc_kutu.setter("height"))
        icerik.add_widget(self._sonuc_kutu)

        scroll.add_widget(icerik)
        root.add_widget(scroll)
        self.add_widget(root)

    def _ciz_btn(self, btn, *a):
        btn.canvas.before.clear()
        t = tema()
        with btn.canvas.before:
            Color(*t["ana"][:3], 0.15)
            RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(10)])

    def _calistir(self, tip, *a):
        t = tema()
        self._sonuc_kutu.clear_widgets()
        self._sonuc_kutu.add_widget(Label(
            text="Backtest çalışıyor...", color=t["bekle"],
            font_size=dp(14), size_hint_y=None, height=dp(40)))
        threading.Thread(target=self._hesapla, args=(tip,), daemon=True).start()

    def _hesapla(self, tip):
        try:
            import trade_v7 as tv
            if tip == "bist":
                semboller = list(tv.BIST_SEMBOLLER)[:8]
            else:
                semboller = [s for lst in tv.LISTELER.values()
                             for s in lst if not s.endswith(".IS")][:8]
            sonuclar = []
            for s in semboller:
                df = tv.veri_getir(s)
                if df.empty or len(df) < 200:
                    continue
                bt = tv.backtest_calistir(s, df)
                if bt:
                    sonuclar.append(bt)
            Clock.schedule_once(lambda dt: self._goster(sonuclar))
        except Exception as e:
            Clock.schedule_once(lambda dt: self._hata(str(e)))

    def _goster(self, sonuclar):
        t = tema()
        self._sonuc_kutu.clear_widgets()
        if not sonuclar:
            self._sonuc_kutu.add_widget(Label(
                text="Veri yetersiz", color=t["sat"],
                font_size=dp(13), size_hint_y=None, height=dp(40)))
            return
        sirali = sorted(sonuclar, key=lambda x: x["net_getiri"], reverse=True)
        for bt in sirali:
            kart = RenkliKart(size_hint_y=None, height=dp(72))
            box = BoxLayout(orientation="vertical", padding=dp(8))
            nc = t["al"] if bt["net_getiri"] >= 0 else t["sat"]
            wc = t["al"] if bt["winrate"] >= 50 else t["sat"]
            emoji = "🏆" if bt["net_getiri"] > 20 else ("✅" if bt["net_getiri"] > 0 else "❌")
            box.add_widget(Label(
                text=f"[b]{bt['sembol'].replace('.IS','')}[/b]  {emoji}",
                markup=True, color=t["yazi"], font_size=dp(14), halign="left"))
            box.add_widget(Label(
                text=(f"Net: [color={self._hex(nc)}]{bt['net_getiri']:+.1f}%[/color]  "
                      f"Win: [color={self._hex(wc)}]{bt['winrate']:.0f}%[/color]  "
                      f"İşlem: {bt['n_islem']}  MaxDD: {bt['max_dd']:.1f}%"),
                markup=True, color=t["yazi2"], font_size=dp(11), halign="left"))
            kart.add_widget(box)
            self._sonuc_kutu.add_widget(kart)

    def _hata(self, hata):
        self._sonuc_kutu.clear_widgets()
        self._sonuc_kutu.add_widget(Label(
            text=f"Hata: {hata[:60]}", color=tema()["sat"],
            font_size=dp(12), size_hint_y=None, height=dp(40)))

    def _hex(self, rgba):
        return "{:02x}{:02x}{:02x}".format(
            int(rgba[0]*255), int(rgba[1]*255), int(rgba[2]*255))

    def _geri(self, *a):
        self.manager.transition = SlideTransition(direction="right")
        self.manager.current = "ana"


class AyarlarEkran(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build()

    def _build(self):
        self.clear_widgets()
        t = tema()
        root = BoxLayout(orientation="vertical")
        with root.canvas.before:
            Color(*t["bg"])
            Rectangle(pos=root.pos, size=root.size)

        topbar = BoxLayout(size_hint_y=None, height=dp(56), padding=[dp(8), dp(8)])
        with topbar.canvas.before:
            Color(*t["bg2"])
            Rectangle(pos=topbar.pos, size=topbar.size)
        geri_btn = Button(text="←", font_size=dp(22),
                          size_hint=(None, None), size=(dp(44), dp(44)),
                          background_normal="", background_color=(0,0,0,0),
                          color=t["ana"])
        geri_btn.bind(on_press=self._geri)
        topbar.add_widget(geri_btn)
        topbar.add_widget(GlowLabel(text="AYARLAR", font_size=dp(20),
                                    halign="left", valign="middle"))
        root.add_widget(topbar)

        scroll = ScrollView(do_scroll_x=False)
        icerik = BoxLayout(orientation="vertical", spacing=dp(12),
                           padding=dp(16), size_hint_y=None)
        icerik.bind(minimum_height=icerik.setter("height"))

        # Tema seçici
        icerik.add_widget(GlowLabel(
            text="TEMA", font_size=dp(14),
            size_hint_y=None, height=dp(30), halign="left"))

        for tema_ad in TEMALAR:
            td = TEMALAR[tema_ad]
            btn = TemaButon(tema_ad)
            btn.bind(on_press=partial(self._tema_degistir, tema_ad))
            icerik.add_widget(btn)

        # Aktif parametreler
        icerik.add_widget(GlowLabel(
            text="MEVCUT AYARLAR", font_size=dp(14),
            size_hint_y=None, height=dp(40), halign="left"))
        try:
            import trade_v7 as tv
            params = [
                ("ATR SL Çarpanı", str(tv.ATR_SL)),
                ("ATR TP Çarpanı", str(tv.ATR_TP)),
                ("ML İleri Gün", str(tv.ILERI_GUN)),
                ("Getiri Eşiği", f"{tv.GETIRI_ESIGI*100:.1f}%"),
                ("Güçlü Sinyal Eşiği", str(tv.GUCLU_ESIK)),
                ("Makro Aktif", "✅" if tv.MAKRO_AKTIF else "❌"),
                ("Sentiment Aktif", "✅" if tv.SENTIMENT_AKTIF else "❌"),
                ("HistGB Ensemble", "✅" if tv.ENSEMBLE_GB_AKTIF else "❌"),
                ("SHAP Eleme", "✅" if tv.SHAP_ELEME_AKTIF else "❌"),
            ]
        except Exception:
            params = [("trade_v7.py", "Yüklenemedi")]

        param_kart = RenkliKart(size_hint_y=None,
                                height=dp(len(params) * 32 + 16))
        param_grid = GridLayout(cols=2, padding=dp(12), spacing=dp(4))
        for k, v in params:
            param_grid.add_widget(Label(text=k, color=t["yazi2"],
                                        font_size=dp(12), halign="left"))
            param_grid.add_widget(Label(text=v, color=t["ana"],
                                        font_size=dp(12), halign="right", bold=True))
        param_kart.add_widget(param_grid)
        icerik.add_widget(param_kart)

        scroll.add_widget(icerik)
        root.add_widget(scroll)
        self.add_widget(root)

    def _tema_degistir(self, tema_ad, *a):
        tema_sec(tema_ad)
        app = App.get_running_app()
        for ekran_ad in ["ana", "detay", "backtest", "ayarlar"]:
            try:
                app.sm.get_screen(ekran_ad)._build()
            except Exception:
                pass
        self._build()

    def _geri(self, *a):
        self.manager.transition = SlideTransition(direction="down")
        self.manager.current = "ana"


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
        return self.sm

    def get_application_name(self):
        return "Trade Sinyal Ultra"


if __name__ == "__main__":
    TradeApp().run()
