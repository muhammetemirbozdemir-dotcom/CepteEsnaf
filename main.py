import sys
import os
import datetime
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.core.window import Window
from kivy.clock import Clock

# Firebase kütüphaneleri
try:
    import firebase_admin
    from firebase_admin import credentials, db
except ImportError:
    print("HATA: 'pip install firebase-admin' yapman lazım reis!")

# PC Tarzı Lacivert Tema
Window.clearcolor = (0.17, 0.24, 0.31, 1)

# --- FIREBASE BAĞLANTISI (ZIRHLI) ---
firebase_ok = False
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(current_dir, "serviceAccountKey.json")
    
    if os.path.exists(json_path):
        if not firebase_admin._apps:
            cred = credentials.Certificate(json_path)
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://cepteesnaf-704fc-default-rtdb.europe-west1.firebasedatabase.app/'
            })
            firebase_ok = True
    else:
        print("⚠️ serviceAccountKey.json bulunamadı!")
except Exception as e:
    print(f"❌ Bağlantı Hatası: {e}")

# --- ANA MENÜ ---
class MainMenu(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        l = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Üst Bar
        top = BoxLayout(size_hint_y=0.15)
        top.add_widget(Label(text="CEPTE ESNAF", color=(0.18, 0.8, 0.44, 1), font_size=28, bold=True))
        biz_btn = Button(text="🏭 İŞLETMENİZ", background_color=(0.95, 0.77, 0.06, 1), size_hint_x=0.4, bold=True)
        biz_btn.bind(on_press=lambda x: setattr(self.manager, 'current', 'biz_view'))
        top.add_widget(biz_btn)
        l.add_widget(top)
        
        # Izgara Menü
        grid = GridLayout(cols=3, spacing=10)
        pages = [
            ("MÜŞTERİLER","cust"), ("TEDARİKÇİLER","supp"), ("ÜRÜNLER","prod"),
            ("SATIŞLAR","sale"), ("ALIŞLAR","buy"), ("MASRAFLAR","exp"),
            ("HESAPLAR","acc"), ("ÇALIŞANLAR","emp"), ("STOKLAR","stok"),
            ("RAPORLAR","rep"), ("TAKVİM","cal"), ("KATALOGLAR","cat")
        ]
        for t, s in pages:
            btn = Button(text=t, background_color=(0.2, 0.29, 0.37, 1), font_size=11)
            btn.bind(on_press=lambda x, sc=s: setattr(self.manager, 'current', sc))
            grid.add_widget(btn)
        l.add_widget(grid)
        self.add_widget(l)

# --- MODÜL ŞABLONU (ANLIK LİSTE GÜNCELLEMELİ) ---
class BaseModule(Screen):
    def __init__(self, db_key, fields, title, mode="simple", **kw):
        super().__init__(**kw)
        self.db_key, self.fields, self.mode = db_key, fields, mode
        self.layout = BoxLayout(orientation='vertical', padding=10, spacing=5)
        
        # Navigasyon
        nav = BoxLayout(size_hint_y=0.1)
        nav.add_widget(Button(text="⬅", size_hint_x=0.2, on_press=lambda x: setattr(self.manager, 'current', 'main')))
        nav.add_widget(Label(text=title, bold=True, color=(0.18, 0.8, 0.44, 1)))
        self.layout.add_widget(nav)

        # Giriş Alanları
        self.inputs = {}
        # Tarih (PC gibi)
        self.tarih_in = TextInput(text=datetime.date.today().strftime("%d.%m.%Y"), size_hint_y=None, height=40, multiline=False)
        self.layout.add_widget(Label(text="Tarih:", size_hint_y=None, height=15, font_size=11))
        self.layout.add_widget(self.tarih_in)

        for fid, fhint in fields:
            ti = TextInput(hint_text=fhint, multiline=False, size_hint_y=None, height=45)
            self.layout.add_widget(ti); self.inputs[fid] = ti
        
        btn_save = Button(text="KAYDET / HESAPLA", background_color=(0.18, 0.8, 0.44, 1), size_hint_y=None, height=50, bold=True)
        btn_save.bind(on_press=self.kaydet)
        self.layout.add_widget(btn_save)
        
        # Liste
        self.scroll_list = BoxLayout(orientation='vertical', size_hint_y=None)
        self.scroll_list.bind(minimum_height=self.scroll_list.setter('height'))
        scroll = ScrollView()
        scroll.add_widget(self.scroll_list)
        self.layout.add_widget(scroll)
        self.add_widget(self.layout)

    def on_enter(self): Clock.schedule_once(lambda dt: self.yenile(), 0.1)

    def kaydet(self, inst):
        if not firebase_ok: return
        data = {k: v.text for k, v in self.inputs.items()}
        data['tarih'] = self.tarih_in.text
        
        # PC Tipi Gelişmiş Hesaplama
        if self.mode == "calc":
            try:
                f, a = float(data.get('price', 0)), float(data.get('qty', 1))
                k, i = float(data.get('kdv', 20)), float(data.get('isk', 0))
                top = (f * a) * (1 + k/100) * (1 - i/100)
                data['borc'] = str(round(top, 2))
            except: data['borc'] = "0"
        elif self.mode == "product":
            data['borc'] = f"A:{data.get('alis','0')} S:{data.get('satis','0')}"

        db.reference(f"veriler/{self.db_key}").push(data)
        for i in self.inputs.values(): i.text = ""
        # ANLIK GÜNCELLEME: 0.3 sn sonra listeyi zorla yenile
        Clock.schedule_once(lambda dt: self.yenile(), 0.3)

    def yenile(self, *args):
        if not firebase_ok: return
        self.scroll_list.clear_widgets()
        veriler = db.reference(f"veriler/{self.db_key}").get()
        if veriler:
            # En yeni eklenen en üstte (reversed)
            for k, v in reversed(list(veriler.items())):
                row = BoxLayout(size_hint_y=None, height=75, padding=5, spacing=10)
                txt = f"[b]{v.get('ad','-')}[/b]\nTarih: {v.get('tarih','')} | [color=2ecc71]{v.get('borc', v.get('tutar','0'))} TL[/color]"
                lbl = Label(text=txt, markup=True, halign='left', font_size=13)
                lbl.bind(size=lbl.setter('text_size'))
                
                btn_x = Button(text="X", size_hint_x=0.2, background_color=(0.9, 0.3, 0.2, 1), bold=True)
                btn_x.bind(on_press=lambda x, key=k: self.sil(key))
                
                row.add_widget(lbl); row.add_widget(btn_x)
                self.scroll_list.add_widget(row)

    def sil(self, key):
        db.reference(f"veriler/{self.db_key}/{key}").delete()
        self.yenile()

# --- RAPORLAR ---
class Reports(Screen):
    def on_enter(self):
        if not firebase_ok: return
        v = db.reference('veriler').get() or {}
        c = sum(float(x.get('borc',0)) for x in (v.get('satislar') or {}).values() if str(x.get('borc')).replace('.','',1).isdigit())
        m = sum(float(x.get('borc',0)) for x in (v.get('masraflar') or {}).values() if str(x.get('borc')).replace('.','',1).isdigit())
        self.lbl.text = f"{datetime.date.today().strftime('%B %Y').upper()}\n\nCİRO: {c} TL\nMASRAF: {m} TL\nNET: {round(c-m,2)} TL"

    def __init__(self, **kw):
        super().__init__(**kw)
        l = BoxLayout(orientation='vertical', padding=40)
        l.add_widget(Button(text="⬅", size_hint_y=0.1, on_press=lambda x: setattr(self.manager, 'current', 'main')))
        self.lbl = Label(text="Yükleniyor...", font_size=24, bold=True, color=(0.18, 0.8, 0.44, 1))
        l.add_widget(self.lbl); self.add_widget(l)

# --- İŞLETMENİZ ---
class BizView(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        l = BoxLayout(orientation='vertical', padding=20, spacing=10)
        l.add_widget(Button(text="⬅ GERİ", size_hint_y=0.1, on_press=lambda x: setattr(self.manager, 'current', 'main')))
        self.ins = {}
        for label, key in [("İşletme Adı","ad"), ("Sahibi","sahip"), ("Vergi No","vergi"), ("Adres","adres")]:
            l.add_widget(Label(text=label, size_hint_y=None, height=20))
            ti = TextInput(multiline=False, size_hint_y=None, height=45)
            l.add_widget(ti); self.ins[key] = ti
        btn = Button(text="KAYDET", background_color=(0.95, 0.77, 0.06, 1), size_hint_y=0.15, bold=True)
        btn.bind(on_press=self.kaydet_biz); l.add_widget(btn); self.add_widget(l)

    def kaydet_biz(self, inst):
        if firebase_ok: db.reference('isletme_bilgileri').set({k: v.text for k, v in self.ins.items()})

class CepteEsnafApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(MainMenu(name='main'))
        sm.add_widget(BizView(name='biz_view'))
        sm.add_widget(Reports(name='rep'))
        # Modüller (PC Entegrasyonlu)
        sm.add_widget(BaseModule('musteriler', [('ad','Müşteri Adı'),('tel','Telefon'),('borc','Borç')], "MÜŞTERİLER", name='cust'))
        sm.add_widget(BaseModule('tedarikci', [('ad','Firma Adı'),('borc','Alacak')], "TEDARİKÇİLER", name='supp'))
        sm.add_widget(BaseModule('urunler', [('ad','Ürün Adı'),('alis','Alış Fiyatı'),('satis','Satış Fiyatı')], "ÜRÜNLER", mode="product", name='prod'))
        sm.add_widget(BaseModule('satislar', [('ad','Ürün'),('price','Birim Fiyat'),('qty','Miktar'),('kdv','KDV%'),('isk','İsk%')], "SATIŞLAR", mode="calc", name='sale'))
        sm.add_widget(BaseModule('alislar', [('ad','Ürün'),('price','Maliyet'),('qty','Adet'),('kdv','KDV%'),('isk','İsk%')], "ALIŞLAR", mode="calc", name='buy'))
        sm.add_widget(BaseModule('masraflar', [('ad','Başlık'),('borc','Tutar')], "MASRAFLAR", name='exp'))
        sm.add_widget(BaseModule('hesaplar', [('ad','Hesap Adı'),('borc','Bakiye')], "HESAPLAR", name='acc'))
        sm.add_widget(BaseModule('calisanlar', [('ad','İsim Soyisim'),('borc','Maaş')], "ÇALIŞANLAR", name='emp'))
        sm.add_widget(BaseModule('stoklar', [('ad','Ürün'),('borc','Adet')], "STOKLAR", name='stok'))
        sm.add_widget(BaseModule('takvim', [('ad','Not')], "TAKVİM", name='cal'))
        sm.add_widget(BaseModule('katalog', [('ad','Ürün'),('borc','Fiyat')], "KATALOGLAR", name='cat'))
        return sm

if __name__ == '__main__':
    CepteEsnafApp().run()
