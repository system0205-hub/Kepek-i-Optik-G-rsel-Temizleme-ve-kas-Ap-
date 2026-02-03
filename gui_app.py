import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
from pathlib import Path
import json
from PIL import Image, ImageTk
import cv2
import numpy as np

# --- KONFİGÜRASYON VE SABİTLER ---
CONFIG_FILE = "ikas_config.json"
APP_TITLE = "Kepekçi Optik - Studio & İkas Manager"
APP_SIZE = "1000x700"
COLOR_BG = "#2b2b2b"
COLOR_FG = "#ffffff"
COLOR_ACCENT = "#007acc"
COLOR_ACCENT_HOVER = "#0098ff"
COLOR_SECONDARY = "#3c3c3c"

class ModernApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(APP_TITLE)
        self.geometry(APP_SIZE)
        self.configure(bg=COLOR_BG)
        # self.iconbitmap("icon.ico") # İkon varsa eklenebilir

        # Stil ayarları
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self._configure_styles()

        # Ana Container
        self.main_container = tk.Frame(self, bg=COLOR_BG)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # Sidebar (Sol Menü)
        self.sidebar = tk.Frame(self.main_container, bg=COLOR_SECONDARY, width=200)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # İçerik Alanı
        self.content_area = tk.Frame(self.main_container, bg=COLOR_BG)
        self.content_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Başlık
        self.title_label = tk.Label(self.sidebar, text="KEPEKÇİ\nOPTİK", 
                                    bg=COLOR_SECONDARY, fg=COLOR_FG, 
                                    font=("Segoe UI", 16, "bold"), pady=20)
        self.title_label.pack(fill=tk.X)

        # Menü Butonları
        self.btn_studio = self._create_sidebar_btn("📸 Stüdyo Modu", lambda: self.show_frame("studio"))
        self.btn_ikas = self._create_sidebar_btn("🚀 İkas Entegrasyon", lambda: self.show_frame("ikas"))
        self.btn_settings = self._create_sidebar_btn("⚙️ Ayarlar", lambda: self.show_frame("settings"))

        # Alt Bilgi
        self.version_label = tk.Label(self.sidebar, text="v1.0.0", bg=COLOR_SECONDARY, fg="#888888")
        self.version_label.pack(side=tk.BOTTOM, pady=10)

        # Sayfalar
        self.frames = {}
        for F in (StudioPage, IkasPage, SettingsPage):
            page_name = F.__name__
            frame = F(parent=self.content_area, controller=self)
            self.frames[page_name] = frame
            frame.place(relwidth=1, relheight=1) # Stack layout

        self.show_frame("studio")

    def _configure_styles(self):
        # Frame
        self.style.configure("TFrame", background=COLOR_BG)
        
        # Notebook (Tab)
        self.style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
        self.style.configure("TNotebook.Tab", background=COLOR_SECONDARY, foreground=COLOR_FG, padding=[10, 5])
        self.style.map("TNotebook.Tab", background=[("selected", COLOR_ACCENT)])

        # Label
        self.style.configure("TLabel", background=COLOR_BG, foreground=COLOR_FG, font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", font=("Segoe UI", 20, "bold"))
        self.style.configure("SubHeader.TLabel", font=("Segoe UI", 12), foreground="#aaaaaa")

        # Button
        self.style.configure("TButton", 
                             background=COLOR_ACCENT, 
                             foreground=COLOR_FG, 
                             borderwidth=0, 
                             focuscolor=COLOR_ACCENT,
                             font=("Segoe UI", 10, "bold"),
                             padding=10)
        self.style.map("TButton", 
                       background=[("active", COLOR_ACCENT_HOVER)],
                       foreground=[("active", COLOR_FG)])

        # Entry
        self.style.configure("TEntry", fieldbackground=COLOR_SECONDARY, foreground=COLOR_FG, borderwidth=0, padding=5)

        # Progressbar
        self.style.configure("TProgressbar", background=COLOR_ACCENT, troughcolor=COLOR_SECONDARY, borderwidth=0)

    def _create_sidebar_btn(self, text, command):
        btn = tk.Button(self.sidebar, text=text, command=command,
                        bg=COLOR_SECONDARY, fg=COLOR_FG, 
                        bd=0, font=("Segoe UI", 11), anchor="w", padx=20, pady=10,
                        activebackground=COLOR_ACCENT, activeforeground=COLOR_FG, cursor="hand2")
        btn.pack(fill=tk.X, pady=2)
        return btn

    def show_frame(self, page_alias):
        # Alias mapping
        mapping = {
            "studio": "StudioPage",
            "ikas": "IkasPage",
            "settings": "SettingsPage"
        }
        name = mapping.get(page_alias)
        if name:
            frame = self.frames[name]
            frame.tkraise()
            
            # Update sidebar active state (visual only)
            if page_alias == "studio":
                self.btn_studio.config(bg=COLOR_ACCENT)
                self.btn_ikas.config(bg=COLOR_SECONDARY)
                self.btn_settings.config(bg=COLOR_SECONDARY)
            elif page_alias == "ikas":
                self.btn_studio.config(bg=COLOR_SECONDARY)
                self.btn_ikas.config(bg=COLOR_ACCENT)
                self.btn_settings.config(bg=COLOR_SECONDARY)
            elif page_alias == "settings":
                self.btn_studio.config(bg=COLOR_SECONDARY)
                self.btn_ikas.config(bg=COLOR_SECONDARY)
                self.btn_settings.config(bg=COLOR_ACCENT)

class StudioPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=COLOR_BG)
        self.controller = controller
        
        # Header
        header = ttk.Label(self, text="Stüdyo Görsel İşleme", style="Header.TLabel")
        header.pack(anchor="w", pady=(0, 5))
        
        subheader = ttk.Label(self, text="Görselleri temizle, beyaz fon ekle ve organize et.", style="SubHeader.TLabel")
        subheader.pack(anchor="w", pady=(0, 20))

        # Input Area
        input_frame = tk.Frame(self, bg=COLOR_SECONDARY, padx=15, pady=15)
        input_frame.pack(fill=tk.X, pady=10)

        self.input_path = tk.StringVar(value=os.path.join(os.getcwd(), "input"))
        
        lbl_input = tk.Label(input_frame, text="Giriş Klasörü:", bg=COLOR_SECONDARY, fg=COLOR_FG, font=("Segoe UI", 10, "bold"))
        lbl_input.pack(anchor="w")
        
        input_row = tk.Frame(input_frame, bg=COLOR_SECONDARY)
        input_row.pack(fill=tk.X, pady=5)
        
        entry_input = tk.Entry(input_row, textvariable=self.input_path, bg="#555", fg="white", bd=0, font=("Consolas", 10))
        entry_input.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(0, 10))
        
        btn_browse = tk.Button(input_row, text="Gözat...", command=self._browse_input, bg="#444", fg="white", bd=0, padx=15)
        btn_browse.pack(side=tk.RIGHT)

        # Options
        options_frame = tk.Frame(self, bg=COLOR_BG)
        options_frame.pack(fill=tk.X, pady=10)
        
        self.var_organize = tk.BooleanVar(value=True)
        chk_organize = tk.Checkbutton(options_frame, text="Marka/Model Klasörlemesi Yap", 
                                      variable=self.var_organize, bg=COLOR_BG, fg=COLOR_FG, 
                                      selectcolor=COLOR_SECONDARY, activebackground=COLOR_BG, activeforeground=COLOR_FG)
        chk_organize.pack(side=tk.LEFT)

        # Actions
        btn_process = ttk.Button(self, text="▶ İŞLEMİ BAŞLAT", command=self._start_process)
        btn_process.pack(fill=tk.X, pady=20)

        # Log Area
        self.log_text = tk.Text(self, height=10, bg=COLOR_SECONDARY, fg=COLOR_FG, bd=0, font=("Consolas", 9), state="disabled")
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _browse_input(self):
        path = filedialog.askdirectory()
        if path:
            self.input_path.set(path)

    def _log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.update_idletasks()

    def _start_process(self):
        # İşlem ayrı bir thread'de çalışsın ki arayüz donmasın
        threading.Thread(target=self._process_logic, daemon=True).start()

    def _process_logic(self):
        input_dir = self.input_path.get()
        if not os.path.exists(input_dir):
            self._log("❌ Giriş klasörü bulunamadı!")
            return

        self._log("🔄 İşlem başlatılıyor...")
        
        # Output klasörü
        output_dir = os.path.join(os.path.dirname(input_dir), "output")
        os.makedirs(output_dir, exist_ok=True)

        # Desteklenen dosyalar
        exts = ('.jpg', '.jpeg', '.png', '.webp')
        
        # Rekürsif Arama (Alt klasörler dahil)
        all_files = []
        for root, dirs, files in os.walk(input_dir):
            for file in files:
                if file.lower().endswith(exts):
                    full_path = os.path.join(root, file)
                    all_files.append(full_path)
        
        if not all_files:
            self._log("⚠️ İşlenecek görsel bulunamadı.")
            return

        self._log(f"📁 {len(all_files)} görsel bulundu (Alt klasörler dahil).")

        # Arka plan temizleyici Başlat
        # Öncelik: transparent-background (SOTA) -> rembg (Stabil)
        remover = None
        remover_type = None
        ai_error_msg = ""
        
        # 1. InSPyReNet Dene
        try:
            from transparent_background import Remover
            self._log("🧠 AI Modeli yükleniyor (InSPyReNet)...")
            remover = Remover(mode='base', device='cpu')
            remover_type = "transparent-background"
            self._log("✅ InSPyReNet AI hazır (Yüksek Kalite).")
        except Exception as e:
            # self._log(f"⚠️ InSPyReNet Yükleme Hatası: {e}")
            pass

        # 2. Rembg Dene (Eğer ilki yoksa)
        if not remover:
            try:
                from rembg import remove, new_session
                self._log("🧠 Alternatif AI Modeli yükleniyor (Rembg)...")
                # Test import to verify dependencies like onnxruntime
                import onnxruntime
                remover_type = "rembg"
                self._log("✅ Rembg AI hazır (Standart Kalite).")
            except ImportError as e:
                ai_error_msg = str(e)
                if "onnxruntime" in str(e) and sys.version_info >= (3, 14):
                    ai_error_msg += "\n(Python 3.14, AI kütüphaneleriyle henüz uyumsuz.)"
                self._log(f"⚠️ AI Kütüphaneleri Eksik: {ai_error_msg}")
            except Exception as e:
                ai_error_msg = str(e)
                self._log(f"❌ Rembg Başlatma Hatası: {e}")
                
        if not remover_type:
            self._log("⚠️ DİKKAT: AI temizleme çalışmayacak. Sadece kırpma/yükleme yapılacak.")

        success_count = 0
        
        # Rembg fonksiyonunu güvenli import et
        rembg_remove = None
        if remover_type == "rembg":
             from rembg import remove as rembg_remove

        for i, input_path in enumerate(all_files, 1):
            filename = os.path.basename(input_path)
            try:
                self._log(f"[{i}/{len(all_files)}] İşleniyor: {filename}")
                
                # 1. Yükle (OpenCV)
                stream = open(input_path, "rb")
                bytes_data = bytearray(stream.read())
                numpyarray = np.asarray(bytes_data, dtype=np.uint8)
                cv_img = cv2.imdecode(numpyarray, cv2.IMREAD_COLOR)
                
                if cv_img is None:
                    self._log(f"  ❌ Okunamadı: {filename}")
                    continue

                # 2. Düzelt (Straighten)
                img_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
                img_pil = Image.fromarray(img_rgb)

                # 3. Arka Plan Temizle
                img_rgba = None
                
                if remover_type == "transparent-background" and remover:
                    try:
                        img_rgba = remover.process(img_pil, type='rgba')
                    except Exception as e:
                        self._log(f"  ⚠️ AI Hatası (TB): {e}")
                        
                elif remover_type == "rembg" and rembg_remove:
                    try:
                        img_rgba = rembg_remove(img_pil)
                    except Exception as e:
                         self._log(f"  ⚠️ AI Hatası (Rembg): {e}")

                # AI başarısızsa veya yoksa, orijinali kullan (Alpha kanalı ekle)
                if img_rgba is None:
                    img_rgba = img_pil.convert("RGBA")
                    # AI yoksa Step 4 (Studio) anlamsız olur çünkü arka plan silinmedi
                    # Bu yüzden sadece resize/crop yapıp kaydedelim veya Studio efektini yine de uygulayalım (belki beyaz fona koyar)
                    # Ama arka planı silinmemiş görseli beyaz fona koymak sadece kenar boşluğu ekler.
                
                # 4. Stüdyo Efekti (Beyaz fon + Gelişmiş Gölge)
                # Eğer AI çalışmadıysa gölge efekti "kare" görselin etrafına olur, pek hoş durmaz ama
                # "Sadece Kırpma" isteyenler için işe yarar.
                final_img = self._apply_studio_effect(img_rgba)

                # 5. Kaydet (Yapıyı koruyarak)
                try:
                    rel_path = os.path.relpath(os.path.dirname(input_path), input_dir)
                except ValueError:
                    rel_path = ""
                
                if self.var_organize.get():
                     save_dir = os.path.join(output_dir, rel_path)
                else:
                    save_dir = output_dir

                os.makedirs(save_dir, exist_ok=True)
                
                name_root, _ = os.path.splitext(filename)
                save_path = os.path.join(save_dir, f"studio_{name_root}.png")
                
                final_img.save(save_path, "PNG")
                self._log(f"  ✅ Kaydedildi")
                success_count += 1

            except Exception as e:
                self._log(f"  ❌ Hata: {e}")

        self._log(f"\n🎉 İşlem Tamamlandı! ({success_count} başarılı)")
        messagebox.showinfo("Bitti", "Tüm görseller işlendi.")

    def _apply_studio_effect(self, img_rgba):
        from PIL import ImageFilter
        
        # 1080x1080 Beyaz Fon
        target_size = (1080, 1080)
        canvas = Image.new("RGBA", target_size, (255, 255, 255, 255))
        
        # Kırp
        bbox = img_rgba.getbbox()
        if bbox:
            img_rgba = img_rgba.crop(bbox)

        # Boyutlandır (%85)
        # Daha estetik durması için %85 doluluk iyidir
        max_w = int(target_size[0] * 0.85)
        max_h = int(target_size[1] * 0.85)
        
        ratio = min(max_w / img_rgba.width, max_h / img_rgba.height)
        new_size = (int(img_rgba.width * ratio), int(img_rgba.height * ratio))
        img_resized = img_rgba.resize(new_size, Image.Resampling.LANCZOS)
        
        # Ortala
        x = (target_size[0] - new_size[0]) // 2
        y = (target_size[1] - new_size[1]) // 2
        
        # --- GELİŞMİŞ GÖLGE EFEKTİ ---
        # Ürünün maskesini al
        mask = img_resized.split()[3]
        
        # Gölge Katmanı Hazırla (Canvas boyutunda)
        shadow_layer = Image.new('RGBA', target_size, (0,0,0,0))
        
        # 1. Temas Gölgesi (Contact Shadow) - Keskin ve Koyu
        # Ürünün altına, çok az kaydırılmış
        s_contact = Image.new('RGBA', target_size, (0,0,0,0))
        contact_color = (0, 0, 0, 140) # Koyu gri
        s_contact.paste(contact_color, (x, y + 10), mask=mask)
        s_contact = s_contact.filter(ImageFilter.GaussianBlur(8))
        
        # 2. Ortam Gölgesi (Ambient Shadow) - Yayvan ve Açık
        s_ambient = Image.new('RGBA', target_size, (0,0,0,0))
        ambient_color = (0, 0, 0, 40) # Açık gri
        s_ambient.paste(ambient_color, (x, y + 30), mask=mask)
        s_ambient = s_ambient.filter(ImageFilter.GaussianBlur(30))
        
        # Gölgeleri birleştir
        shadow_layer = Image.alpha_composite(shadow_layer, s_ambient)
        shadow_layer = Image.alpha_composite(shadow_layer, s_contact)
        
        # Canvas'a sırayla ekle: Beyaz Fon -> Gölge -> Ürün
        canvas.paste(shadow_layer, (0, 0), mask=shadow_layer)
        canvas.paste(img_resized, (x, y), mask=img_resized)
        
        return canvas

class IkasPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=COLOR_BG)
        self.controller = controller
        
        header = ttk.Label(self, text="İkas Entegrasyonu", style="Header.TLabel")
        header.pack(anchor="w", pady=(0, 5))
        
        subheader = ttk.Label(self, text="Toplu ürün oluşturma ve görsel yükleme.", style="SubHeader.TLabel")
        subheader.pack(anchor="w", pady=(0, 20))

        # Step 1: Generate Excel
        step1_frame = tk.Frame(self, bg=COLOR_SECONDARY, padx=15, pady=15)
        step1_frame.pack(fill=tk.X, pady=10)
        
        lbl_step1 = tk.Label(step1_frame, text="ADIM 1: Excel Oluştur", bg=COLOR_SECONDARY, fg=COLOR_ACCENT, font=("Segoe UI", 12, "bold"))
        lbl_step1.pack(anchor="w")
        
        desc_step1 = tk.Label(step1_frame, text="'output' klasöründeki ürünleri İkas'a uygun Excel formatına getirir.", 
                              bg=COLOR_SECONDARY, fg="#aaaaaa", justify="left")
        desc_step1.pack(anchor="w", pady=(5, 10))
        
        btn_generate = ttk.Button(step1_frame, text="Excel Dosyası Oluştur", command=self._generate_excel)
        btn_generate.pack(anchor="w")

        # Step 2: Upload Images
        step2_frame = tk.Frame(self, bg=COLOR_SECONDARY, padx=15, pady=15)
        step2_frame.pack(fill=tk.X, pady=10)
        
        lbl_step2 = tk.Label(step2_frame, text="ADIM 2: Görsel Yükle", bg=COLOR_SECONDARY, fg=COLOR_ACCENT, font=("Segoe UI", 12, "bold"))
        lbl_step2.pack(anchor="w")
        
        desc_step2 = tk.Label(step2_frame, text="İkas'tan indirdiğiniz (ID'li) Excel dosyasını seçin.", 
                              bg=COLOR_SECONDARY, fg="#aaaaaa", justify="left")
        desc_step2.pack(anchor="w", pady=(5, 10))
        
        self.export_path = tk.StringVar()
        export_row = tk.Frame(step2_frame, bg=COLOR_SECONDARY)
        export_row.pack(fill=tk.X, pady=5)
        
        entry_export = tk.Entry(export_row, textvariable=self.export_path, bg="#555", fg="white", bd=0)
        entry_export.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(0, 10))
        
        btn_browse_excel = tk.Button(export_row, text="Seç...", command=self._browse_excel, bg="#444", fg="white", bd=0, padx=10)
        btn_browse_excel.pack(side=tk.RIGHT)
        
        btn_upload = ttk.Button(step2_frame, text="Görselleri Yükle", command=self._upload_images)
        btn_upload.pack(fill=tk.X, pady=(10, 0))

        # Log
        self.log_text = tk.Text(self, height=8, bg=COLOR_BG, fg="#aaaaaa", bd=0, font=("Consolas", 8), state="disabled")
        self.log_text.pack(side=tk.BOTTOM, fill=tk.BOTH, pady=10)

    def _log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"{msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.update_idletasks()

    def _generate_excel(self):
        import pandas as pd
        
        OUTPUT_DIR = "output"
        IMPORT_FILENAME = "ikas_import_new_products.xlsx"
        
        if not os.path.exists(OUTPUT_DIR):
            messagebox.showerror("Hata", "'output' klasörü bulunamadı!")
            return

        self._log("📂 Output klasörü taranıyor...")
        
        products = []
        for item in os.listdir(OUTPUT_DIR):
            item_path = os.path.join(OUTPUT_DIR, item)
            if os.path.isdir(item_path):
                product_name = item
                
                subfolders = [f for f in os.listdir(item_path) if os.path.isdir(os.path.join(item_path, f))]
                variants = []
                
                if subfolders:
                    for sub in subfolders:
                        # Varyant mantığı güncellendi: Klasör adının son kelimesi renk kodudur.
                        # Örn: "Venture 1205 C01" -> "C01"
                        parts = sub.split()
                        variant_val = parts[-1] if parts else sub
                        variant_val = variant_val.lstrip('0')
                        variants.append({"val": variant_val, "path": sub})
                else:
                    variants.append({"val": "Standart", "path": ""})

                brand = product_name.split()[0] if product_name else ""

                for var in variants:
                    products.append({
                        "Ürün Grup ID": "", 
                        "Varyant ID": "",   
                        "İsim": product_name,
                        "Açıklama": f"<p>{product_name}</p>",
                        "Satış Fiyatı": 0,
                        "İndirimli Fiyatı": "",
                        "Alış Fiyatı": "",
                        "Barkod Listesi": "",
                        "SKU": "", 
                        "Silindi mi?": False,
                        "Marka": brand,
                        "Kategoriler": "Güneş Gözlüğü",
                        "Etiketler": "Kilis Stok",
                        "Resim URL": "", 
                        "Metadata Başlık": "",
                        "Metadata Açıklama": "",
                        "Slug": "", 
                        "Stok:Kilis Stok": 1,
                        "Stok:İtalya Depo": 0, 
                        "Tip": "PHYSICAL",
                        "Varyant Tip 1": "Renk",
                        "Varyant Değer 1": var["val"],
                        "Varyant Tip 2": "",
                        "Varyant Değer 2": "",
                        "Desi": 1,
                        "HS Kod": "",
                        "Birim Ürün Miktarı": "",
                        "Ürün Birimi": "",
                        "Satılan Ürün Miktarı": "",
                        "Satılan Ürün Birimi": "",
                        "Google Ürün Kategorisi": "178",
                        "Tedarikçi": "",
                        "Stoğu Tükenince Satmaya Devam Et": False,
                        "Satış Kanalı:kepekcioptik": "VISIBLE",
                        "Satış Kanalı:Trendyol": "PASSIVE", 
                        "Sepet Başına Minimum Alma Adeti:kepekcioptik": "",
                        "Sepet Başına Maksimum Alma Adeti:kepekcioptik": "",
                        "Varyant Aktiflik": True
                    })

        if not products:
             # Boş şablon oluştur sorusu
             if messagebox.askyesno("Veri Bulunamadı", "Output klasöründe ürün bulunamadı. Boş bir şablon oluşturmak ister misiniz?"):
                 # Boş bir kayıt oluştur (Sütun yapılarını korumak için)
                 empty_record = {
                        "Ürün Grup ID": "", "Varyant ID": "", "İsim": "Yeni Ürün", "Açıklama": "",
                        "Satış Fiyatı": 0, "İndirimli Fiyatı": "", "Alış Fiyatı": "", "Barkod Listesi": "",
                        "SKU": "", "Silindi mi?": False, "Marka": "", "Kategoriler": "Güneş Gözlüğü",
                        "Etiketler": "", "Resim URL": "", "Metadata Başlık": "", "Metadata Açıklama": "",
                        "Slug": "", "Stok:Kilis Stok": 0, "Stok:İtalya Depo": 0, "Tip": "PHYSICAL",
                        "Varyant Tip 1": "Renk", "Varyant Değer 1": "", "Varyant Tip 2": "", "Varyant Değer 2": "",
                        "Desi": 1, "HS Kod": "", "Birim Ürün Miktarı": "", "Ürün Birimi": "",
                        "Satılan Ürün Miktarı": "", "Satılan Ürün Birimi": "", "Google Ürün Kategorisi": "178",
                        "Tedarikçi": "", "Stoğu Tükenince Satmaya Devam Et": False,
                        "Satış Kanalı:kepekcioptik": "VISIBLE", "Satış Kanalı:Trendyol": "PASSIVE", 
                        "Sepet Başına Minimum Alma Adeti:kepekcioptik": "",
                        "Sepet Başına Maksimum Alma Adeti:kepekcioptik": "", "Varyant Aktiflik": True
                 }
                 products.append(empty_record)
             else:
                 self._log("⚠️ İşlem iptal edildi.")
                 return

        # Preview Dialog Göster
        df = pd.DataFrame(products)
        # Tüm sütunları göster
        preview_cols = list(df.columns)
        preview_data = df.values.tolist()
        
        preview = PreviewDialog(self, "Excel Düzenleyici (Çift tıkla düzenle)", preview_cols, preview_data)
        self.wait_window(preview)
        
        if preview.result_data: # Eğer veri döndüyse
            try:
                # Modifiye edilmiş veriden yeni DataFrame oluştur
                new_df = pd.DataFrame(preview.result_data, columns=preview_cols)
                new_df.to_excel(IMPORT_FILENAME, index=False)
                self._log(f"✅ Dosya oluşturuldu: {IMPORT_FILENAME}")
                messagebox.showinfo("Başarılı", f"Dosya oluşturuldu:\n{IMPORT_FILENAME}\n\nİkas paneline yükleyebilirsiniz.")
            except Exception as e:
                self._log(f"❌ Hata: {e}")
                messagebox.showerror("Hata", str(e))
        else:
            self._log("⚠️ Excel oluşturma iptal edildi.")

    def _browse_excel(self):
        path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")])
        if path:
            self.export_path.set(path)

    def _upload_images(self):
        export_file = self.export_path.get()
        if not export_file:
            messagebox.showwarning("Uyarı", "Lütfen önce Excel dosyasını seçin.")
            return
            
        threading.Thread(target=self._upload_logic, args=(export_file,), daemon=True).start()

    def _upload_logic(self, export_file):
        import pandas as pd
        import requests
        import base64
        
        self._log("🚀 Yükleme başlatılıyor...")
        
        # Config yükle
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
        except Exception as e:
            self._log(f"❌ Config hatası: {e}")
            return

        # Token Al
        store_name = config.get("store_name", "kepekcioptik")
        auth_url = f"https://{store_name}.myikas.com/api/admin/oauth/token"
        
        try:
            r = requests.post(auth_url, json={
                "grant_type": "client_credentials",
                "client_id": config["client_id"],
                "client_secret": config["client_secret"]
            })
            r.raise_for_status()
            token = r.json().get("access_token")
            self._log("🔑 Token alındı.")
        except Exception as e:
            self._log(f"❌ Kimlik doğrulama hatası: {e}")
            return

        # Excel Oku
        try:
            df = pd.read_excel(export_file)
        except Exception as e:
            self._log(f"❌ Excel okuma hatası: {e}")
            return

        upload_url = "https://api.myikas.com/api/v1/admin/product/upload/image"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        OUTPUT_DIR = "output"

        for index, row in df.iterrows():
            if "Varyant ID" not in row or "İsim" not in row or pd.isna(row["Varyant ID"]):
                continue

            variant_id = row["Varyant ID"]
            product_name = row["İsim"]
            variant_val = str(row["Varyant Değer 1"]).strip().lstrip('0') if "Varyant Değer 1" in row else "Standart"
            
            # Klasör bul
            product_root = os.path.join(OUTPUT_DIR, str(product_name).strip())
            target_folder = None
            
            # Eğer output'ta klasör yoksa bile yükleme yapabilmesi için esneklik (Manuel Mod için)
            # Ancak manuel modda resimlerin nerede olduğu belirsiz.
            # Şimdilik sadece resim varsa yükle mantığını koruyoruz.
            
            if not os.path.exists(product_root):
                continue
                
            subfolders = [f for f in os.listdir(product_root) if os.path.isdir(os.path.join(product_root, f))]
            
            if subfolders:
                for sub in subfolders:
                    # Varyant mantığı güncellendi: Son kelimeyi al
                    parts = sub.split()
                    raw_color = parts[-1] if parts else sub
                    clean_color = raw_color.lstrip('0')
                    
                    if str(variant_val) == clean_color:
                        target_folder = os.path.join(product_root, sub)
                        break
            else:
                target_folder = product_root

            if not target_folder:
                continue

            self._log(f"📦 Yükleniyor: {product_name} ({variant_val})")
            
            images = list(Path(target_folder).glob("*.png")) + list(Path(target_folder).glob("*.jpg"))
            for i, img_path in enumerate(images):
                try:
                    with open(img_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("utf-8")
                    
                    payload = {
                        "productImage": {
                            "variantIds": [str(variant_id)],
                            "base64": b64,
                            "order": i,
                            "isMain": (i==0)
                        }
                    }
                    res = requests.post(upload_url, json=payload, headers=headers)
                    if res.status_code == 200:
                        self._log(f"   ✅ {img_path.name}")
                    else:
                        self._log(f"   ❌ Hata: {res.status_code}")
                except Exception as e:
                    self._log(f"   ❌ Hata: {e}")

        self._log("✨ İşlem Tamamlandı!")
        messagebox.showinfo("Bitti", "Yükleme tamamlandı.")

class PreviewDialog(tk.Toplevel):
    def __init__(self, parent, title, columns, data):
        super().__init__(parent)
        self.title(title)
        self.geometry("1000x600") # Genişletildi
        self.configure(bg=COLOR_BG)
        self.result_data = None # Geri dönecek veri
        self.columns = columns
        
        # Style
        style = ttk.Style()
        style.configure("Treeview", background="#333", foreground="white", fieldbackground="#333", borderwidth=0)
        style.configure("Treeview.Heading", background=COLOR_SECONDARY, foreground="black", font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", COLOR_ACCENT)])

        # Header
        lbl_info = tk.Label(self, text=f"Çift tıklayarak hücreleri düzenleyebilirsiniz.", bg=COLOR_BG, fg=COLOR_FG, pady=10)
        lbl_info.pack(fill=tk.X, padx=10)
        
        # Toolbar (Ekle/Sil)
        toolbar = tk.Frame(self, bg=COLOR_BG)
        toolbar.pack(fill=tk.X, padx=10, pady=5)
        
        btn_add = tk.Button(toolbar, text="➕ Satır Ekle", command=self._add_row, bg="#007acc", fg="white", bd=0, padx=10)
        btn_add.pack(side=tk.LEFT, padx=5)
        
        btn_del = tk.Button(toolbar, text="🗑️ Satır Sil", command=self._delete_row, bg="#dc3545", fg="white", bd=0, padx=10)
        btn_del.pack(side=tk.LEFT, padx=5)

        # Treeview
        tree_frame = tk.Frame(self, bg=COLOR_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        
        # Scrollbars
        y_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, minwidth=50) # Daraltıldı ki ekrana sığsın
            
        for row in data:
            self.tree.insert("", tk.END, values=row)

        # Bind Double Click
        self.tree.bind("<Double-1>", self._on_double_click)

        # Buttons
        btn_frame = tk.Frame(self, bg=COLOR_BG, pady=20)
        btn_frame.pack(fill=tk.X)
        
        btn_cancel = tk.Button(btn_frame, text="İptal", command=self.destroy, bg="#555", fg="white", bd=0, padx=20, pady=10)
        btn_cancel.pack(side=tk.RIGHT, padx=10)
        
        btn_confirm = tk.Button(btn_frame, text="✅ KAYDET ve OLUŞTUR", command=self._confirm, bg="#28a745", fg="white", bd=0, padx=20, pady=10, font=("Segoe UI", 10, "bold"))
        btn_confirm.pack(side=tk.RIGHT, padx=10)

    def _on_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
            
        column = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)
        
        if not row_id or not column:
            return
            
        # Sütun indexi (#1 -> 0)
        col_index = int(column.replace("#", "")) - 1
        
        # Mevcut Değer
        current_values = self.tree.item(row_id, "values")
        current_val = current_values[col_index]
        
        # Entry Widget Oluştur (Hücrenin üzerine)
        x, y, w, h = self.tree.bbox(row_id, column)
        
        entry = tk.Entry(self.tree, width=w)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, current_val)
        entry.focus()
        
        def save(event=None):
            new_val = entry.get()
            new_values = list(current_values)
            new_values[col_index] = new_val
            self.tree.item(row_id, values=new_values)
            entry.destroy()
            
        def cancel(event=None):
            entry.destroy()

        entry.bind("<Return>", save)
        entry.bind("<FocusOut>", save) # Odak değişince kaydet
        entry.bind("<Escape>", cancel)

    def _add_row(self):
        # Boş bir satır ekle
        empty_row = [""] * len(self.columns)
        self.tree.insert("", tk.END, values=empty_row)
        
    def _delete_row(self):
        selected_item = self.tree.selection()
        if selected_item:
            self.tree.delete(selected_item)

    def _confirm(self):
        # Treeview'daki tüm veriyi çek
        all_data = []
        for child in self.tree.get_children():
            row = self.tree.item(child)["values"]
            all_data.append(row)
            
        self.result_data = all_data
        self.destroy()

class SettingsPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=COLOR_BG)
        self.controller = controller
        
        header = ttk.Label(self, text="Ayarlar", style="Header.TLabel")
        header.pack(anchor="w", pady=(0, 20))

        # AI Settings
        ai_frame = tk.LabelFrame(self, text="AI Ayarları", bg=COLOR_BG, fg=COLOR_FG, font=("Segoe UI", 11, "bold"))
        ai_frame.pack(fill=tk.X, pady=10, ipady=5)
        
        self.var_ai_mode = tk.StringVar(value="local")
        
        rb_local = tk.Radiobutton(ai_frame, text="Yerel İşleme (Hızlı - InSPyReNet)", variable=self.var_ai_mode, value="local",
                                  bg=COLOR_BG, fg=COLOR_FG, selectcolor=COLOR_SECONDARY, activebackground=COLOR_BG, activeforeground=COLOR_FG)
        rb_local.pack(anchor="w", padx=10)
        
        rb_gemini = tk.Radiobutton(ai_frame, text="Google Gemini AI", variable=self.var_ai_mode, value="gemini",
                                  bg=COLOR_BG, fg=COLOR_FG, selectcolor=COLOR_SECONDARY, activebackground=COLOR_BG, activeforeground=COLOR_FG)
        rb_gemini.pack(anchor="w", padx=10)

        rb_openai = tk.Radiobutton(ai_frame, text="OpenAI (DALL-E / GPT Vision)", variable=self.var_ai_mode, value="openai",
                                  bg=COLOR_BG, fg=COLOR_FG, selectcolor=COLOR_SECONDARY, activebackground=COLOR_BG, activeforeground=COLOR_FG)
        rb_openai.pack(anchor="w", padx=10)
        
        rb_custom = tk.Radiobutton(ai_frame, text="Diğer (Custom API)", variable=self.var_ai_mode, value="custom",
                                  bg=COLOR_BG, fg=COLOR_FG, selectcolor=COLOR_SECONDARY, activebackground=COLOR_BG, activeforeground=COLOR_FG)
        rb_custom.pack(anchor="w", padx=10)

        # API Keys
        api_frame = tk.LabelFrame(self, text="API Anahtarları", bg=COLOR_BG, fg=COLOR_FG, font=("Segoe UI", 11, "bold"))
        api_frame.pack(fill=tk.X, pady=10, ipady=10)
        
        # Gemini Key
        tk.Label(api_frame, text="Gemini API Key:", bg=COLOR_BG, fg=COLOR_FG).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.entry_gemini = tk.Entry(api_frame, bg=COLOR_SECONDARY, fg=COLOR_FG, bd=0, width=40)
        self.entry_gemini.grid(row=0, column=1, padx=10, pady=5)
        
        # OpenAI Key
        tk.Label(api_frame, text="OpenAI API Key:", bg=COLOR_BG, fg=COLOR_FG).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.entry_openai = tk.Entry(api_frame, bg=COLOR_SECONDARY, fg=COLOR_FG, bd=0, width=40)
        self.entry_openai.grid(row=1, column=1, padx=10, pady=5)
        
        # Custom API
        tk.Label(api_frame, text="Custom API URL:", bg=COLOR_BG, fg=COLOR_FG).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.entry_custom = tk.Entry(api_frame, bg=COLOR_SECONDARY, fg=COLOR_FG, bd=0, width=40)
        self.entry_custom.grid(row=2, column=1, padx=10, pady=5)
        
        # Ikas Keys
        tk.Label(api_frame, text="İkas Client ID:", bg=COLOR_BG, fg=COLOR_FG).grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.entry_ikas_id = tk.Entry(api_frame, bg=COLOR_SECONDARY, fg=COLOR_FG, bd=0, width=40)
        self.entry_ikas_id.grid(row=3, column=1, padx=10, pady=5)
        
        tk.Label(api_frame, text="İkas Secret:", bg=COLOR_BG, fg=COLOR_FG).grid(row=4, column=0, padx=10, pady=5, sticky="w")
        self.entry_ikas_secret = tk.Entry(api_frame, bg=COLOR_SECONDARY, fg=COLOR_FG, bd=0, width=40, show="*")
        self.entry_ikas_secret.grid(row=4, column=1, padx=10, pady=5)
        
        tk.Label(api_frame, text="Mağaza Adı (örn: kepekcioptik):", bg=COLOR_BG, fg=COLOR_FG).grid(row=5, column=0, padx=10, pady=5, sticky="w")
        self.entry_store = tk.Entry(api_frame, bg=COLOR_SECONDARY, fg=COLOR_FG, bd=0, width=40)
        self.entry_store.grid(row=5, column=1, padx=10, pady=5)

        btn_save = ttk.Button(self, text="Ayarları Kaydet", command=self._save_settings)
        btn_save.pack(anchor="e", pady=20)
        
        self._load_settings()

    def _load_settings(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    
                self.entry_ikas_id.insert(0, data.get("client_id", ""))
                self.entry_ikas_secret.insert(0, data.get("client_secret", ""))
                self.entry_store.insert(0, data.get("store_name", "kepekcioptik"))
                self.entry_gemini.insert(0, data.get("gemini_api_key", ""))
                self.entry_openai.insert(0, data.get("openai_api_key", ""))
                self.entry_custom.insert(0, data.get("custom_api_url", ""))
                self.var_ai_mode.set(data.get("ai_mode", "local"))
            except Exception as e:
                print(f"Config yüklenemedi: {e}")

    def _save_settings(self):
        data = {
            "client_id": self.entry_ikas_id.get().strip(),
            "client_secret": self.entry_ikas_secret.get().strip(),
            "store_name": self.entry_store.get().strip(),
            "gemini_api_key": self.entry_gemini.get().strip(),
            "openai_api_key": self.entry_openai.get().strip(),
            "custom_api_url": self.entry_custom.get().strip(),
            "ai_mode": self.var_ai_mode.get()
        }
        
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(data, f, indent=4)
            messagebox.showinfo("Başarılı", "Ayarlar kaydedildi!")
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydedilemedi: {e}")

if __name__ == "__main__":
    app = ModernApp()
    app.mainloop()
