# -*- coding: utf-8 -*-
"""
Kepekçi Optik - Studio & İkas Manager
Ana GUI uygulaması.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import threading
import os
import sys
import time
import io
from pathlib import Path
import json
from PIL import Image, ImageTk
import cv2
import numpy as np
import requests
import re

# Yeni modüller
from config import load_config, save_config, get_timeout
from logging_utils import setup_logging, set_ui_widget, ui_log, log_info, log_warning, log_error, log_success
from net import create_session, request_with_retry, NetworkError
from wiro import run_nano_banana, validate_api_key, WiroError
from studio import apply_studio_effect, process_with_failure_policy, validate_image
from ikas import normalize_variant, validate_excel_columns, UploadReport, find_image_for_variant
from ikas_automation import (
    IkasAutomationRunner,
    AutomationError,
    FIT_GUIDE_MARKER,
    FIT_GUIDE_HTML,
    build_brand_specific_description,
    description_has_permanent_images,
    extract_brand_model_from_name,
)
from description import generate_product_description

# --- KONFİGÜRASYON VE SABİTLER ---
CONFIG_FILE = "ikas_config.json"
APP_TITLE = "Kepekçi Optik - Studio & İkas Manager"
APP_SIZE = "1000x700"

# Modern Canlı Renk Paleti
COLOR_BG = "#1a1a2e"           # Koyu lacivert arka plan
COLOR_FG = "#eaeaea"           # Açık beyaz metin
COLOR_ACCENT = "#00d4ff"       # Parlak cyan accent
COLOR_ACCENT_HOVER = "#00ffea" # Hover için neon yeşil-mavi
COLOR_SECONDARY = "#16213e"    # Koyu mavi sidebar
COLOR_SUCCESS = "#00ff88"      # Yeşil başarı
COLOR_WARNING = "#ffb800"      # Turuncu uyarı
COLOR_ERROR = "#ff4757"        # Kırmızı hata
COLOR_PURPLE = "#a855f7"       # Mor vurgu
COLOR_GRADIENT_START = "#667eea"  # Gradient başlangıç
COLOR_GRADIENT_END = "#764ba2"    # Gradient bitiş


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

        # Başlık - Gradient efektli görünüm
        self.title_label = tk.Label(self.sidebar, text="✨ KEPEKÇİ\n   OPTİK", 
                                    bg=COLOR_SECONDARY, fg=COLOR_ACCENT, 
                                    font=("Segoe UI", 18, "bold"), pady=25)
        self.title_label.pack(fill=tk.X)

        # Menü Butonları
        self.btn_studio = self._create_sidebar_btn("📸 Stüdyo Modu", lambda: self.show_frame("studio"))
        self.btn_ikas = self._create_sidebar_btn("🚀 İkas Entegrasyon", lambda: self.show_frame("ikas"))
        self.btn_mail = self._create_sidebar_btn("📧 Mail Watcher", lambda: self.show_frame("mail"))
        self.btn_settings = self._create_sidebar_btn("⚙️ Ayarlar", lambda: self.show_frame("settings"))
        self.btn_delete_panel = self._create_sidebar_btn("🗑️ Ürün Silme (Güvenli)", self._open_delete_panel_from_sidebar)
        self.btn_product_features_panel = self._create_sidebar_btn("📝 Ürün Özellikleri", self._open_product_features_panel_from_sidebar)
        self.btn_description_panel = self._create_sidebar_btn("🧩 Özel Alanlar", self._open_description_panel_from_sidebar)
        self.btn_help = self._create_sidebar_btn("❓ Yardım", lambda: self.show_frame("help"))

        # Alt Bilgi - Nano-banana versiyon
        self.version_label = tk.Label(self.sidebar, text="v2.0.0 🍌 Nano-Banana", 
                                      bg=COLOR_SECONDARY, fg=COLOR_WARNING, 
                                      font=("Segoe UI", 9))
        self.version_label.pack(side=tk.BOTTOM, pady=10)

        # Sayfalar
        self.frames = {}
        for F in (StudioPage, IkasPage, MailWatcherPage, SettingsPage, HelpPage):
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
                        bd=0, font=("Segoe UI", 11), anchor="w", padx=20, pady=12,
                        activebackground=COLOR_ACCENT, activeforeground=COLOR_FG, cursor="hand2")
        btn.pack(fill=tk.X, pady=2)
        
        # Hover efektleri
        def on_enter(e):
            btn.config(bg=COLOR_ACCENT, fg=COLOR_FG)
        def on_leave(e):
            btn.config(bg=COLOR_SECONDARY, fg=COLOR_FG)
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    def show_frame(self, page_alias):
        # Alias mapping
        mapping = {
            "studio": "StudioPage",
            "ikas": "IkasPage",
            "mail": "MailWatcherPage",
            "settings": "SettingsPage",
            "delete": "IkasPage",
            "product_features": "IkasPage",
            "description": "IkasPage",
            "help": "HelpPage"
        }
        name = mapping.get(page_alias)
        if name:
            frame = self.frames[name]
            frame.tkraise()
            
            # Reset all buttons
            all_btns = [
                self.btn_studio,
                self.btn_ikas,
                self.btn_mail,
                self.btn_settings,
                self.btn_delete_panel,
                self.btn_product_features_panel,
                self.btn_description_panel,
                self.btn_help,
            ]
            for btn in all_btns:
                btn.config(bg=COLOR_SECONDARY)
            
            # Highlight active
            btn_map = {
                "studio": self.btn_studio,
                "ikas": self.btn_ikas,
                "mail": self.btn_mail,
                "settings": self.btn_settings,
                "delete": self.btn_delete_panel,
                "product_features": self.btn_product_features_panel,
                "description": self.btn_description_panel,
                "help": self.btn_help
            }
            if page_alias in btn_map:
                btn_map[page_alias].config(bg=COLOR_ACCENT)

    def _open_delete_panel_from_sidebar(self):
        self.show_frame("delete")
        frame = self.frames.get("IkasPage")
        if frame and hasattr(frame, "_open_delete_popup"):
            self.after(120, frame._open_delete_popup)

    def _open_product_features_panel_from_sidebar(self):
        self.show_frame("product_features")
        frame = self.frames.get("IkasPage")
        if frame and hasattr(frame, "_open_product_features_popup"):
            self.after(120, frame._open_product_features_popup)

    def _open_description_panel_from_sidebar(self):
        self.show_frame("description")
        frame = self.frames.get("IkasPage")
        if frame and hasattr(frame, "_open_fitguide_popup"):
            self.after(120, frame._open_fitguide_popup)

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

        # Config'den AI modunu ve API key'i oku
        ai_mode = "local"
        wiro_api_key = ""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    ai_mode = config.get("ai_mode", "local")
                    wiro_api_key = config.get("wiro_api_key", "")
            except:
                pass

        # Wiro.ai API modundaysa
        if ai_mode == "wiro" and wiro_api_key:
            self._log("🌐 Wiro.ai API Modu Aktif")
            self._process_with_wiro_api(all_files, input_dir, output_dir, wiro_api_key)
            return

        # Yerel işleme modu
        self._log("💻 Yerel İşleme Modu Aktif")
        
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

    def _process_with_wiro_api(self, all_files, input_dir, output_dir, api_key):
        """Wiro.ai Nano-Banana (Gemini 2.5 Flash) API ile profesyonel stüdyo görseli oluşturma"""
        success_count = 0
        
        for i, input_path in enumerate(all_files, 1):
            filename = os.path.basename(input_path)
            try:
                self._log(f"[{i}/{len(all_files)}] 🍌 Wiro.ai Nano-Banana (Gemini): {filename}")
                
                # 1. Görseli Wiro.ai Nano-Banana API'sine gönder
                url = "https://api.wiro.ai/v1/Run/google/nano-banana"
                headers = {"x-api-key": api_key}

                
                with open(input_path, "rb") as img_file:
                    files = {"inputImage": (filename, img_file)}
                    data = {"prompt": "Remove the background completely and place this product on a pure white professional studio background with soft even lighting and subtle reflection below, product photography style for e-commerce"}
                    response = requests.post(url, headers=headers, files=files, data=data)

                
                if response.status_code != 200:
                    self._log(f"  ❌ API Hatası: {response.status_code}")
                    continue
                
                result = response.json()
                if not result.get("result"):
                    self._log(f"  ❌ API Hatası: {result.get('errors', 'Bilinmeyen hata')}")
                    continue
                
                task_token = result.get("socketaccesstoken")
                self._log(f"  ⏳ Task oluşturuldu, bekleniyor...")
                
                # 2. Sonucu bekle (polling)
                output_url = self._wait_for_wiro_result(api_key, task_token)
                
                if not output_url:
                    self._log(f"  ❌ Sonuç alınamadı")
                    continue
                
                # 3. Sonucu indir
                img_response = requests.get(output_url)
                if img_response.status_code != 200:
                    self._log(f"  ❌ İndirme hatası")
                    continue
                
                # Nano-banana zaten profesyonel stüdyo efekti uyguluyor
                # Ekstra _apply_studio_effect gerekli değil
                final_img = Image.open(io.BytesIO(img_response.content)).convert("RGBA")
                
                # 4. Kaydet
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

    def _wait_for_wiro_result(self, api_key, task_token, max_wait=120):
        """Wiro.ai task sonucunu bekle (polling)"""
        url = "https://api.wiro.ai/v1/Task/Detail"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key
        }
        payload = {"tasktoken": task_token}
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                response = requests.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("result") and data.get("tasklist"):
                        task = data["tasklist"][0]
                        status = task.get("status", "")
                        
                        if status == "task_postprocess_end":
                            # Tamamlandı
                            outputs = task.get("outputs", [])
                            if outputs:
                                return outputs[0].get("url")
                        elif status in ["task_error", "task_cancel"]:
                            # Hata oluştu
                            return None
                
                time.sleep(2)  # 2 saniye bekle
            except Exception as e:
                time.sleep(2)
        
        return None  # Timeout

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

        # Step 0: Full Automation
        step0_frame = tk.Frame(self, bg=COLOR_SECONDARY, padx=15, pady=15)
        step0_frame.pack(fill=tk.X, pady=10)

        lbl_step0 = tk.Label(
            step0_frame,
            text="ADIM 0: Tam Otomasyon",
            bg=COLOR_SECONDARY,
            fg=COLOR_ACCENT,
            font=("Segoe UI", 12, "bold"),
        )
        lbl_step0.pack(anchor="w")

        desc_step0 = tk.Label(
            step0_frame,
            text="Fiyat kural dosyasi + kanal secimi ile urun olusturma, varyant upsert ve gorsel yukleme tek adimda calisir.",
            bg=COLOR_SECONDARY,
            fg="#aaaaaa",
            justify="left",
            wraplength=820,
        )
        desc_step0.pack(anchor="w", pady=(5, 10))

        self.price_rules_path = tk.StringVar()
        price_row = tk.Frame(step0_frame, bg=COLOR_SECONDARY)
        price_row.pack(fill=tk.X, pady=5)

        entry_price = tk.Entry(price_row, textvariable=self.price_rules_path, bg="#555", fg="white", bd=0)
        entry_price.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(0, 10))

        btn_browse_price = tk.Button(
            price_row,
            text="Fiyat Excel Sec...",
            command=self._browse_price_rules,
            bg="#444",
            fg="white",
            bd=0,
            padx=10,
        )
        btn_browse_price.pack(side=tk.RIGHT)

        channel_row = tk.Frame(step0_frame, bg=COLOR_SECONDARY)
        channel_row.pack(fill=tk.X, pady=(5, 0))

        self.var_channel_storefront = tk.BooleanVar(value=True)
        self.var_channel_trendyol = tk.BooleanVar(value=False)

        chk_storefront = tk.Checkbutton(
            channel_row,
            text="Storefront (VISIBLE)",
            variable=self.var_channel_storefront,
            bg=COLOR_SECONDARY,
            fg=COLOR_FG,
            selectcolor=COLOR_BG,
            activebackground=COLOR_SECONDARY,
            activeforeground=COLOR_FG,
        )
        chk_storefront.pack(side=tk.LEFT, padx=(0, 20))

        chk_trendyol = tk.Checkbutton(
            channel_row,
            text="Trendyol (PASSIVE)",
            variable=self.var_channel_trendyol,
            bg=COLOR_SECONDARY,
            fg=COLOR_FG,
            selectcolor=COLOR_BG,
            activebackground=COLOR_SECONDARY,
            activeforeground=COLOR_FG,
        )
        chk_trendyol.pack(side=tk.LEFT)

        self.btn_full_automation = ttk.Button(
            step0_frame,
            text="Tam Otomasyonu Baslat",
            command=self._start_full_automation,
        )
        self.btn_full_automation.pack(fill=tk.X, pady=(10, 0))

        progress_box = tk.Frame(step0_frame, bg=COLOR_SECONDARY)
        progress_box.pack(fill=tk.X, pady=(10, 0))
        self.full_auto_progress_text = tk.StringVar(value="Hazır")
        lbl_progress = tk.Label(
            progress_box,
            textvariable=self.full_auto_progress_text,
            bg=COLOR_SECONDARY,
            fg=COLOR_WARNING,
            anchor="w",
        )
        lbl_progress.pack(fill=tk.X, pady=(0, 4))

        self.full_auto_progress = tk.DoubleVar(value=0.0)
        self.progress_full_auto = ttk.Progressbar(
            progress_box,
            orient="horizontal",
            mode="determinate",
            maximum=100,
            variable=self.full_auto_progress,
        )
        self.progress_full_auto.pack(fill=tk.X)

        # Aciklama iyilestirme popup durum degiskenleri
        self.fitguide_search_text = tk.StringVar()
        self.fitguide_progress_text = tk.StringVar(value="Hazır")
        self.fitguide_progress = tk.DoubleVar(value=0.0)
        self.btn_fitguide_sync = None
        self.fitguide_popup_window = None
        self.fitguide_popup_results = []
        self.fitguide_popup_selected = []
        self.fitguide_popup_list = None
        self.fitguide_popup_label = None
        self.fitguide_feature_frame = None
        self.fitguide_hint_label = None
        self.fitguide_attribute_id = ""

        self.product_features_search_text = tk.StringVar()
        self.product_features_template = tk.StringVar(value="Otomatik (Markayı üründen oku)")
        self.product_features_progress_text = tk.StringVar(value="Hazır")
        self.product_features_progress = tk.DoubleVar(value=0.0)
        self.btn_product_features_sync = None
        self.product_features_popup_window = None
        self.product_features_popup_results = []
        self.product_features_popup_selected = []
        self.product_features_popup_list = None
        self.product_features_popup_label = None
        self.product_features_feature_frame = None

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

        self._load_automation_defaults()

    def _log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"{msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        self.update_idletasks()

    def _set_full_auto_progress(self, value, text=None):
        try:
            value = max(0.0, min(100.0, float(value)))
        except Exception:
            value = 0.0
        self.full_auto_progress.set(value)
        if text is not None:
            self.full_auto_progress_text.set(str(text))
        self.update_idletasks()

    def _set_full_auto_running(self, running):
        state = "disabled" if running else "normal"
        try:
            self.btn_full_automation.config(state=state)
        except Exception:
            pass

    def _set_fitguide_sync_running(self, running):
        state = "disabled" if running else "normal"
        try:
            self.btn_fitguide_sync.config(state=state)
        except Exception:
            pass

    def _set_fitguide_sync_progress(self, value, text=None):
        try:
            value = max(0.0, min(100.0, float(value)))
        except Exception:
            value = 0.0
        self.fitguide_progress.set(value)
        if text is not None:
            self.fitguide_progress_text.set(str(text))
        self.update_idletasks()

    def _set_product_features_sync_running(self, running):
        state = "disabled" if running else "normal"
        try:
            self.btn_product_features_sync.config(state=state)
        except Exception:
            pass

    def _set_product_features_sync_progress(self, value, text=None):
        try:
            value = max(0.0, min(100.0, float(value)))
        except Exception:
            value = 0.0
        self.product_features_progress.set(value)
        if text is not None:
            self.product_features_progress_text.set(str(text))
        self.update_idletasks()

    def _on_automation_progress(self, payload):
        current = int(payload.get("current", 0) or 0)
        total = int(payload.get("total", 0) or 0)
        message = str(payload.get("message", "") or "")
        stage = str(payload.get("stage", "") or "")
        product_name = str(payload.get("product_name", "") or "")
        status = str(payload.get("status", "") or "")

        percent = 0.0
        if total > 0:
            percent = (current / total) * 100.0

        if stage == "product_start" and product_name:
            ui_text = f"İşleniyor ({current + 1}/{total}): {product_name}"
        elif stage == "product_done" and product_name:
            ui_text = f"Tamamlandı ({current}/{total}): {product_name} [{status}]"
        elif stage == "completed":
            ui_text = "Tam otomasyon bitti."
        else:
            ui_text = message or "Tam otomasyon çalışıyor..."

        self.after(0, lambda: self._set_full_auto_progress(percent, ui_text))

    def _load_automation_defaults(self):
        try:
            config = load_config()
            self.price_rules_path.set(config.get("ikas_price_rules_file", ""))
            defaults = config.get("ikas_sales_channel_defaults", {}) or {}
            self.var_channel_storefront.set(bool(defaults.get("storefront", True)))
            self.var_channel_trendyol.set(bool(defaults.get("trendyol", False)))
        except Exception as e:
            self._log(f"⚠️ Tam otomasyon varsayilanlari yuklenemedi: {e}")

    def _save_automation_defaults(self):
        try:
            data = {}
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data["ikas_price_rules_file"] = self.price_rules_path.get().strip()
            data["ikas_sales_channel_defaults"] = {
                "storefront": bool(self.var_channel_storefront.get()),
                "trendyol": bool(self.var_channel_trendyol.get()),
            }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self._log(f"⚠️ Varsayilanlar kaydedilemedi: {e}")

    def _browse_price_rules(self):
        path = filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")])
        if path:
            self.price_rules_path.set(path)

    def _start_full_automation(self):
        price_file = self.price_rules_path.get().strip()
        if not price_file:
            messagebox.showwarning("Uyarı", "Lütfen fiyat kural dosyasını seçin.")
            return
        if not os.path.exists(price_file):
            messagebox.showerror("Hata", f"Fiyat dosyası bulunamadı:\n{price_file}")
            return

        channel_preferences = {
            "storefront": bool(self.var_channel_storefront.get()),
            "trendyol": bool(self.var_channel_trendyol.get()),
        }
        if not channel_preferences["storefront"] and not channel_preferences["trendyol"]:
            messagebox.showwarning("Uyarı", "En az bir satış kanalı seçmelisiniz.")
            return

        self._save_automation_defaults()
        self._set_full_auto_running(True)
        self._set_full_auto_progress(0, "Tam otomasyon hazırlanıyor...")
        threading.Thread(
            target=self._full_automation_logic,
            args=(price_file, channel_preferences),
            daemon=True,
        ).start()

    def _full_automation_logic(self, price_file, channel_preferences):
        self._log("🚀 Tam otomasyon başlatılıyor...")
        try:
            config = load_config()
            runner = IkasAutomationRunner(
                config=config,
                price_rules_path=price_file,
                channel_preferences=channel_preferences,
                logger=self._log,
                progress_callback=self._on_automation_progress,
            )
            result = runner.run(output_dir="output")
            summary = result.get("summary", {})
            report_path = result.get("report_path", "")

            self._log("✅ Tam otomasyon tamamlandı.")
            self._log(
                "Özet => "
                f"Toplam: {summary.get('total_products', 0)} | "
                f"Oluşturulan: {summary.get('created_products', 0)} | "
                f"Güncellenen: {summary.get('updated_products', 0)} | "
                f"Atlanan: {summary.get('skipped_products', 0)} | "
                f"Hata: {summary.get('failed_products', 0)}"
            )
            self._log(
                "Varyant/Görsel => "
                f"Yüklenen görsel: {summary.get('uploaded_images', 0)} | "
                f"Görseli vardı (skip): {summary.get('skipped_has_images', 0)} | "
                f"Varyant hatası: {summary.get('variant_failures', 0)}"
            )

            if report_path:
                self._log(f"📄 Rapor: {report_path}")

            failed_total = int(summary.get("failed_products", 0)) + int(summary.get("variant_failures", 0))
            if failed_total > 0:
                messagebox.showwarning(
                    "Tam Otomasyon Bitti",
                    "İşlem tamamlandı ancak bazı hatalar var.\n"
                    f"Rapor dosyası:\n{report_path}",
                )
            else:
                messagebox.showinfo(
                    "Tam Otomasyon Başarılı",
                    "Tüm işlem başarıyla tamamlandı.\n"
                    f"Rapor dosyası:\n{report_path}",
                )
            self._set_full_auto_progress(100, "Tam otomasyon bitti.")

        except AutomationError as e:
            self._log(f"❌ Tam otomasyon hatası: {e}")
            self._set_full_auto_progress(
                self.full_auto_progress.get(),
                f"Hata: {e}",
            )
            messagebox.showerror("Tam Otomasyon Hatası", str(e))
        except Exception as e:
            self._log(f"❌ Beklenmeyen hata: {e}")
            self._set_full_auto_progress(
                self.full_auto_progress.get(),
                f"Hata: {e}",
            )
            messagebox.showerror("Tam Otomasyon Hatası", str(e))
        finally:
            self._set_full_auto_running(False)

    def _start_fitguide_sync(self):
        selected = list(getattr(self, "fitguide_popup_selected", []) or [])
        if not selected:
            messagebox.showwarning("Uyarı", "Lütfen listeden en az bir ürün seçin.")
            return

        update_items = []
        for p in selected:
            pid = str((p or {}).get("id") or "").strip()
            name = str((p or {}).get("name") or "-").strip()
            if not pid:
                continue
            update_items.append(
                {
                    "id": pid,
                    "name": name,
                    "attributes": list((p or {}).get("attributes") or []),
                }
            )

        if not update_items:
            messagebox.showerror("Hata", "Seçilen ürünlerde geçerli ürün ID bulunamadı.")
            return

        count = len(update_items)
        preview = "\n".join(f"- {x['name']}" for x in update_items[:8])
        if count > 8:
            preview += f"\n... ve {count - 8} ürün daha"
        ok = messagebox.askyesno(
            "Özel Alanlar Onayı",
            (
                f"Seçilen ürün sayısı: {count}\n\n{preview}\n\n"
                "Sadece ölçü rehberi eksik olan ürünler güncellenir.\n"
                "Devam etmek istiyor musunuz?"
            ),
        )
        if not ok:
            return

        self._set_fitguide_sync_running(True)
        self._set_fitguide_sync_progress(0, "Hazırlanıyor...")
        threading.Thread(
            target=self._sync_fitguide_logic,
            args=(update_items,),
            daemon=True,
        ).start()

    def _fold_text_tr(self, value):
        text = str(value or "").strip().lower()
        return (
            text.replace("ı", "i")
            .replace("ş", "s")
            .replace("ğ", "g")
            .replace("ç", "c")
            .replace("ö", "o")
            .replace("ü", "u")
        )

    def _resolve_fitguide_attribute_id(self, auth):
        if self.fitguide_attribute_id:
            return self.fitguide_attribute_id
        query = """
        query ListProductAttributes {
          listProductAttribute {
            id
            name
            type
          }
        }
        """
        data = self._ikas_graphql(auth, query)
        attrs = data.get("listProductAttribute") or []
        target_name = self._fold_text_tr("Ölçü Rehberi")
        selected_id = ""
        for item in attrs:
            name = self._fold_text_tr((item or {}).get("name"))
            attr_type = str((item or {}).get("type") or "").strip().upper()
            if name == target_name and attr_type == "HTML":
                selected_id = str((item or {}).get("id") or "").strip()
                break
        if not selected_id:
            for item in attrs:
                name = self._fold_text_tr((item or {}).get("name"))
                if name == target_name:
                    selected_id = str((item or {}).get("id") or "").strip()
                    break
        if not selected_id:
            raise Exception(
                "İkas'ta 'Ölçü Rehberi' özel alanı bulunamadı. "
                "Önce panelden bu özel alanı (HTML) oluşturmalısınız."
            )
        self.fitguide_attribute_id = selected_id
        self._log(f"ℹ️ Ölçü Rehberi özel alan ID bulundu: {selected_id}")
        return selected_id

    def _get_fitguide_value_from_attributes(self, attributes, attribute_id):
        target_id = str(attribute_id or "").strip()
        if not target_id:
            return ""
        for item in (attributes or []):
            pid = str((item or {}).get("productAttributeId") or "").strip()
            if pid != target_id:
                continue
            return str((item or {}).get("value") or "")
        return ""

    def _fitguide_value_exists(self, value):
        text = str(value or "")
        if not text.strip():
            return False
        if FIT_GUIDE_MARKER in text:
            return True
        lowered = self._fold_text_tr(re.sub(r"<[^>]+>", " ", text))
        return ("olcu rehberi" in lowered) or ("beden ve uyum kilavuzu" in lowered)

    def _search_products_for_fitguide_popup(self):
        if not self._fitguide_popup_is_alive():
            return
        search = self.fitguide_search_text.get().strip()
        if not search:
            messagebox.showwarning("Uyarı", "Lütfen ürün adı veya anahtar kelime girin.")
            return
        threading.Thread(
            target=self._search_products_for_fitguide_logic_popup,
            args=(search,),
            daemon=True,
        ).start()

    def _search_products_for_fitguide_logic_popup(self, search):
        self._log(f"🔎 Ölçü rehberi paneli arama: {search}")
        try:
            auth = self._get_ikas_auth_header()
            attribute_id = self._resolve_fitguide_attribute_id(auth)
            query = """
            query FindProducts($search: String!) {
              listProduct(search: $search, pagination: {page: 1, limit: 25}) {
                data {
                  id
                  name
                  attributes {
                    productAttributeId
                    value
                  }
                  variants {
                    id
                    variantValues {
                      variantTypeName
                      variantValueName
                    }
                    attributes {
                      productAttributeId
                      value
                    }
                  }
                }
              }
            }
            """
            data = self._ikas_graphql(auth, query, {"search": search})
            products = ((data.get("listProduct") or {}).get("data")) or []
            self.after(
                0,
                lambda: self._append_fitguide_popup_results(
                    products, search, attribute_id
                ),
            )
        except Exception as e:
            self._log(f"❌ Ölçü rehberi paneli arama hatası: {e}")
            self.after(0, lambda: messagebox.showerror("Arama Hatası", str(e)))

    def _append_fitguide_popup_results(self, products, search, attribute_id):
        if not self._fitguide_popup_is_alive():
            return
        if not products:
            self._log(f"ℹ️ Arama sonucu yok: {search}")
            return

        existing_ids = {
            str((p or {}).get("id") or "").strip()
            for p in (self.fitguide_popup_results or [])
        }
        added = 0
        for p in products:
            pid = str((p or {}).get("id") or "").strip()
            if not pid or pid in existing_ids:
                continue
            existing_ids.add(pid)
            attr_value = self._get_fitguide_value_from_attributes(
                (p or {}).get("attributes") or [],
                attribute_id,
            )
            has_fitguide = self._fitguide_value_exists(attr_value)
            p["_fitguide_has"] = has_fitguide
            self.fitguide_popup_results.append(p)
            name = str((p or {}).get("name") or "-")
            variants = (p or {}).get("variants") or []
            missing_variant_count = 0
            for v in variants:
                v_value = self._get_fitguide_value_from_attributes(
                    (v or {}).get("attributes") or [],
                    attribute_id,
                )
                if not self._fitguide_value_exists(v_value):
                    missing_variant_count += 1
            if variants:
                status_text = "VAR" if missing_variant_count == 0 else f"EKSIK({missing_variant_count} varyant)"
            else:
                status_text = "VAR" if has_fitguide else "YOK"
            self.fitguide_popup_list.insert(
                tk.END,
                f"{name} | ölçü rehberi:{status_text} | id:{pid}",
            )
            added += 1

        if added == 0:
            self._log(f"ℹ️ Arama sonucu zaten listede: {search}")
        else:
            self._log(f"✅ Listeye {added} ürün eklendi. (Arama: {search})")

    def _clear_fitguide_popup_list(self):
        if not self._fitguide_popup_is_alive():
            return
        self.fitguide_popup_results = []
        self.fitguide_popup_selected = []
        if self.fitguide_popup_list is not None:
            self.fitguide_popup_list.delete(0, tk.END)
        if self.fitguide_popup_label is not None:
            self.fitguide_popup_label.config(text="Seçili ürün sayısı: 0")
        self.fitguide_progress_text.set("Hazır")
        self.fitguide_progress.set(0.0)
        self._log("🧹 Ölçü rehberi listesi temizlendi.")

    def _on_fitguide_popup_select(self, _event=None):
        if not self._fitguide_popup_is_alive() or self.fitguide_popup_list is None:
            return
        indices = list(self.fitguide_popup_list.curselection())
        if not indices:
            self.fitguide_popup_selected = []
            if self.fitguide_popup_label is not None:
                self.fitguide_popup_label.config(text="Seçili ürün sayısı: 0")
            return

        selected = []
        for idx in indices:
            if idx < len(self.fitguide_popup_results):
                selected.append(self.fitguide_popup_results[idx])
        self.fitguide_popup_selected = selected

        count = len(selected)
        preview_names = [str((p or {}).get("name", "-")) for p in selected[:3]]
        more = "" if count <= 3 else f" (+{count - 3} ürün daha)"
        if self.fitguide_popup_label is not None:
            self.fitguide_popup_label.config(
                text=f"Seçili ürün sayısı: {count} | {', '.join(preview_names)}{more}"
            )

    def _sync_fitguide_logic(self, products):
        self._log("🧩 Özel Alanlar > Ölçü Rehberi işlemi başlatıldı...")
        try:
            auth = self._get_ikas_auth_header()
            attribute_id = self._resolve_fitguide_attribute_id(auth)
            total = len(products)
            if total == 0:
                self._set_fitguide_sync_progress(100, "Ürün bulunamadı.")
                self.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Bilgi",
                        "Güncellenecek ürün bulunamadı.",
                    ),
                )
                return

            self._log(f"🔎 Ölçü rehberi taraması başladı. Ürün sayısı: {total}")
            update_mutation = """
            mutation UpdateProductAndVariantAttributes($input: UpdateProductAndVariantAttributesInput!) {
              updateProductAndVariantAttributes(input: $input) {
                id
                name
              }
            }
            """

            updated = 0
            skipped = 0
            failed = 0

            for idx, product in enumerate(products, start=1):
                pid = str((product or {}).get("id") or "").strip()
                name = str((product or {}).get("name") or "-").strip()
                attributes = (product or {}).get("attributes") or []

                percent = (idx / total) * 100.0
                self._set_fitguide_sync_progress(
                    percent,
                    f"[{idx}/{total}] Kontrol ediliyor: {name}",
                )

                if not pid:
                    failed += 1
                    self._log(f"❌ Ürün id eksik, atlandı: {name}")
                    continue

                existing_value = self._get_fitguide_value_from_attributes(
                    attributes, attribute_id
                )
                product_needs_update = not self._fitguide_value_exists(existing_value)

                variants = (product or {}).get("variants") or []
                variant_inputs = []
                for variant in variants:
                    variant_id = str((variant or {}).get("id") or "").strip()
                    if not variant_id:
                        continue
                    variant_value = self._get_fitguide_value_from_attributes(
                        (variant or {}).get("attributes") or [],
                        attribute_id,
                    )
                    if self._fitguide_value_exists(variant_value):
                        continue
                    variant_inputs.append(
                        {
                            "variantId": variant_id,
                            "attributes": [
                                {
                                    "productAttributeId": attribute_id,
                                    "value": FIT_GUIDE_HTML,
                                }
                            ],
                        }
                    )

                if (not product_needs_update) and (len(variant_inputs) == 0):
                    skipped += 1
                    self._log(f"⏭️ Zaten var, atlandı: {name}")
                    continue

                try:
                    product_attrs_payload = []
                    if product_needs_update:
                        product_attrs_payload = [
                            {
                                "productAttributeId": attribute_id,
                                "value": FIT_GUIDE_HTML,
                            }
                        ]
                    data = self._ikas_graphql(
                        auth,
                        update_mutation,
                        {
                            "input": {
                                "productId": pid,
                                "productAttributes": product_attrs_payload,
                                "variantAttributes": variant_inputs,
                            }
                        },
                    )
                    updated_product = (data or {}).get("updateProductAndVariantAttributes")
                    if not updated_product:
                        raise Exception("Özel alan güncelleme yanıtı boş döndü.")
                    updated += 1
                    self._log(
                        f"✅ Ölçü rehberi özel alana yazıldı: {name} "
                        f"(ürün:{'evet' if product_needs_update else 'hayır'}, varyant:{len(variant_inputs)})"
                    )
                except Exception as e:
                    failed += 1
                    self._log(f"❌ Özel alan güncellenemedi: {name} -> {e}")

            summary_text = (
                f"İşlem tamamlandı.\n\n"
                f"Taranan ürün: {total}\n"
                f"Güncellenen: {updated}\n"
                f"Zaten vardı (atlandı): {skipped}\n"
                f"Hata: {failed}"
            )
            self._log(
                "📌 Ölçü rehberi özeti => "
                f"Taranan: {total} | Güncellenen: {updated} | Atlanan: {skipped} | Hata: {failed}"
            )
            self._set_fitguide_sync_progress(100, "Ölçü rehberi işlemi bitti.")
            self.after(0, lambda: messagebox.showinfo("İşlem Bitti", summary_text))
        except Exception as e:
            self._log(f"❌ Ölçü rehberi işlemi hatası: {e}")
            self._set_fitguide_sync_progress(
                self.fitguide_progress.get(),
                f"Hata: {e}",
            )
            self.after(0, lambda: messagebox.showerror("Hata", str(e)))
        finally:
            self._set_fitguide_sync_running(False)

    def _extract_variant_labels_from_product_variants(self, variants):
        labels = []
        seen = set()
        for variant in (variants or []):
            for value in ((variant or {}).get("variantValues") or []):
                label = str((value or {}).get("variantValueName") or "").strip().upper()
                if not label or label in seen:
                    continue
                seen.add(label)
                labels.append(label)
        labels.sort()
        return labels

    def _detect_product_signals_from_payload(self, product):
        text_parts = [str((product or {}).get("name") or "")]
        for tag in ((product or {}).get("tags") or []):
            text_parts.append(str((tag or {}).get("name") or ""))
        merged = self._fold_text_tr(" ".join(text_parts))
        is_child = any(k in merged for k in ("cocuk", "kids", "junior", "bebek"))
        is_polarized = any(k in merged for k in ("polarize", "polarized", "polarli", "polar"))
        return is_child, is_polarized

    def _build_meta_description_from_html(self, html_text, product_name):
        plain = re.sub(r"<[^>]+>", " ", str(html_text or ""))
        plain = re.sub(r"\s+", " ", plain).strip()
        if not plain:
            plain = f"{product_name} - Kepekçi Optik"
        return plain[:157] + "..." if len(plain) > 160 else plain

    def _search_products_for_product_features_popup(self):
        if not self._product_features_popup_is_alive():
            return
        search = self.product_features_search_text.get().strip()
        if not search:
            messagebox.showwarning("Uyarı", "Lütfen ürün adı veya anahtar kelime girin.")
            return
        threading.Thread(
            target=self._search_products_for_product_features_logic_popup,
            args=(search,),
            daemon=True,
        ).start()

    def _search_products_for_product_features_logic_popup(self, search):
        self._log(f"🔎 Ürün özellikleri paneli arama: {search}")
        try:
            auth = self._get_ikas_auth_header()
            query = """
            query FindProducts($search: String!) {
              listProduct(search: $search, pagination: {page: 1, limit: 25}) {
                data {
                  id
                  name
                  description
                  brand {
                    id
                    name
                  }
                  tags {
                    id
                    name
                  }
                  variants {
                    id
                    variantValues {
                      variantTypeName
                      variantValueName
                    }
                  }
                }
              }
            }
            """
            data = self._ikas_graphql(auth, query, {"search": search})
            products = ((data.get("listProduct") or {}).get("data")) or []
            self.after(
                0,
                lambda: self._append_product_features_popup_results(products, search),
            )
        except Exception as e:
            self._log(f"❌ Ürün özellikleri paneli arama hatası: {e}")
            self.after(0, lambda: messagebox.showerror("Arama Hatası", str(e)))

    def _append_product_features_popup_results(self, products, search):
        if not self._product_features_popup_is_alive():
            return
        if not products:
            self._log(f"ℹ️ Arama sonucu yok: {search}")
            return

        existing_ids = {
            str((p or {}).get("id") or "").strip()
            for p in (self.product_features_popup_results or [])
        }
        added = 0
        for p in products:
            pid = str((p or {}).get("id") or "").strip()
            if not pid or pid in existing_ids:
                continue
            existing_ids.add(pid)
            self.product_features_popup_results.append(p)
            name = str((p or {}).get("name") or "-")
            has_images = description_has_permanent_images((p or {}).get("description"))
            status_text = "VAR" if has_images else "YOK"
            self.product_features_popup_list.insert(
                tk.END,
                f"{name} | kalıcı görsel:{status_text} | id:{pid}",
            )
            added += 1

        if added == 0:
            self._log(f"ℹ️ Arama sonucu zaten listede: {search}")
        else:
            self._log(f"✅ Listeye {added} ürün eklendi. (Arama: {search})")

    def _clear_product_features_popup_list(self):
        if not self._product_features_popup_is_alive():
            return
        self.product_features_popup_results = []
        self.product_features_popup_selected = []
        if self.product_features_popup_list is not None:
            self.product_features_popup_list.delete(0, tk.END)
        if self.product_features_popup_label is not None:
            self.product_features_popup_label.config(text="Seçili ürün sayısı: 0")
        self.product_features_progress_text.set("Hazır")
        self.product_features_progress.set(0.0)
        self._log("🧹 Ürün özellikleri listesi temizlendi.")

    def _on_product_features_popup_select(self, _event=None):
        if not self._product_features_popup_is_alive() or self.product_features_popup_list is None:
            return
        indices = list(self.product_features_popup_list.curselection())
        if not indices:
            self.product_features_popup_selected = []
            if self.product_features_popup_label is not None:
                self.product_features_popup_label.config(text="Seçili ürün sayısı: 0")
            return

        selected = []
        for idx in indices:
            if idx < len(self.product_features_popup_results):
                selected.append(self.product_features_popup_results[idx])
        self.product_features_popup_selected = selected

        count = len(selected)
        preview_names = [str((p or {}).get("name", "-")) for p in selected[:3]]
        more = "" if count <= 3 else f" (+{count - 3} ürün daha)"
        if self.product_features_popup_label is not None:
            self.product_features_popup_label.config(
                text=f"Seçili ürün sayısı: {count} | {', '.join(preview_names)}{more}"
            )

    def _start_product_features_sync(self):
        selected = list(getattr(self, "product_features_popup_selected", []) or [])
        if not selected:
            messagebox.showwarning("Uyarı", "Lütfen listeden en az bir ürün seçin.")
            return
        template_brand = self._resolve_product_template_brand()
        template_text = template_brand or "Otomatik"

        update_items = []
        for p in selected:
            pid = str((p or {}).get("id") or "").strip()
            name = str((p or {}).get("name") or "").strip()
            if not (pid and name):
                continue
            update_items.append(
                {
                    "id": pid,
                    "name": name,
                    "brand": dict((p or {}).get("brand") or {}),
                    "description": str((p or {}).get("description") or ""),
                    "tags": list((p or {}).get("tags") or []),
                    "variants": list((p or {}).get("variants") or []),
                }
            )

        if not update_items:
            messagebox.showerror("Hata", "Seçilen ürünlerde geçerli ürün ID bulunamadı.")
            return

        count = len(update_items)
        preview = "\n".join(f"- {x['name']}" for x in update_items[:8])
        if count > 8:
            preview += f"\n... ve {count - 8} ürün daha"

        ok = messagebox.askyesno(
            "Ürün Özellikleri Onayı",
            (
                f"Seçilen ürün sayısı: {count}\n\n{preview}\n\n"
                "Seçili ürünlerin açıklamaları marka/model odaklı şablonla güncellenecek.\n"
                "Kalıcı görseller açıklama başında daima yer alacak.\n"
                f"Seçili şablon: {template_text}\n"
                "Devam etmek istiyor musunuz?"
            ),
        )
        if not ok:
            return

        self._set_product_features_sync_running(True)
        self._set_product_features_sync_progress(0, "Hazırlanıyor...")
        threading.Thread(
            target=self._sync_product_features_logic,
            args=(update_items, template_brand),
            daemon=True,
        ).start()

    def _sync_product_features_logic(self, products, template_brand=""):
        self._log("📝 Ürün Özellikleri işlemi başlatıldı...")
        if template_brand:
            self._log(f"🧩 Şablon markası: {template_brand}")
        else:
            self._log("🧩 Şablon markası: Otomatik")
        try:
            auth = self._get_ikas_auth_header()
            total = len(products)
            if total == 0:
                self._set_product_features_sync_progress(100, "Ürün bulunamadı.")
                self.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Bilgi",
                        "Güncellenecek ürün bulunamadı.",
                    ),
                )
                return

            self._log(f"🔎 Ürün özellikleri taraması başladı. Ürün sayısı: {total}")
            mutation = """
            mutation UpdateProductFeatures($input: UpdateProductInput!) {
              updateProduct(input: $input) {
                id
                name
                description
              }
            }
            """

            updated = 0
            failed = 0

            for idx, product in enumerate(products, start=1):
                pid = str((product or {}).get("id") or "").strip()
                name = str((product or {}).get("name") or "-").strip()
                brand_name = str((((product or {}).get("brand") or {}).get("name") or "")).strip()
                if not brand_name:
                    parsed_brand, _ = extract_brand_model_from_name(name)
                    brand_name = parsed_brand

                _, parsed_model = extract_brand_model_from_name(name)
                variant_labels = self._extract_variant_labels_from_product_variants(
                    (product or {}).get("variants") or []
                )
                is_child, is_polarized = self._detect_product_signals_from_payload(product)

                percent = (idx / total) * 100.0
                self._set_product_features_sync_progress(
                    percent,
                    f"[{idx}/{total}] Güncelleniyor: {name}",
                )

                if not pid:
                    failed += 1
                    self._log(f"❌ Ürün id eksik, atlandı: {name}")
                    continue

                try:
                    description = build_brand_specific_description(
                        product_name=name,
                        brand=brand_name,
                        model=parsed_model,
                        variant_labels=variant_labels,
                        is_child=is_child,
                        is_polarized=is_polarized,
                        template_brand=template_brand,
                    )
                    meta_description = self._build_meta_description_from_html(description, name)

                    data = self._ikas_graphql(
                        auth,
                        mutation,
                        {
                            "input": {
                                "id": pid,
                                "description": description,
                                "translations": [
                                    {
                                        "locale": "tr",
                                        "name": name,
                                        "description": description,
                                    }
                                ],
                                "metaData": {
                                    "pageTitle": name,
                                    "description": meta_description,
                                },
                            }
                        },
                    )
                    updated_product = (data or {}).get("updateProduct")
                    if not updated_product:
                        raise Exception("Ürün açıklama güncelleme yanıtı boş döndü.")
                    updated += 1
                    self._log(f"✅ Ürün özellikleri güncellendi: {name}")
                except Exception as e:
                    failed += 1
                    self._log(f"❌ Ürün özellikleri güncellenemedi: {name} -> {e}")

            summary_text = (
                f"İşlem tamamlandı.\n\n"
                f"Taranan ürün: {total}\n"
                f"Güncellenen: {updated}\n"
                f"Hata: {failed}"
            )
            self._log(
                "📌 Ürün özellikleri özeti => "
                f"Taranan: {total} | Güncellenen: {updated} | Hata: {failed}"
            )
            self._set_product_features_sync_progress(100, "Ürün özellikleri işlemi bitti.")
            self.after(0, lambda: messagebox.showinfo("İşlem Bitti", summary_text))
        except Exception as e:
            self._log(f"❌ Ürün özellikleri işlemi hatası: {e}")
            self._set_product_features_sync_progress(
                self.product_features_progress.get(),
                f"Hata: {e}",
            )
            self.after(0, lambda: messagebox.showerror("Hata", str(e)))
        finally:
            self._set_product_features_sync_running(False)

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
                        "Açıklama": generate_product_description(product_name, brand),
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

    def _normalize_name(self, value):
        return str(value or "").strip().lower()

    def _get_ikas_auth_header(self):
        config = load_config()
        mcp_token = str(config.get("ikas_mcp_token", "") or "").strip()
        if mcp_token:
            if mcp_token.lower().startswith("bearer "):
                return mcp_token
            return f"Bearer {mcp_token}"

        store_name = str(config.get("store_name", "")).strip()
        client_id = str(config.get("client_id", "")).strip()
        client_secret = str(config.get("client_secret", "")).strip()
        if not (store_name and client_id and client_secret):
            raise Exception("İkas kimlik bilgileri eksik. Ayarlar sayfasını kontrol edin.")

        auth_url = f"https://{store_name}.myikas.com/api/admin/oauth/token"
        res = requests.post(
            auth_url,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=(10, 120),
        )
        res.raise_for_status()
        access_token = (res.json() or {}).get("access_token")
        if not access_token:
            raise Exception("OAuth token alınamadı.")
        return f"Bearer {access_token}"

    def _ikas_graphql(self, auth_header, query, variables=None):
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        res = requests.post(
            "https://api.myikas.com/api/v2/admin/graphql",
            headers={"Authorization": auth_header, "Content-Type": "application/json"},
            json=payload,
            timeout=(10, 120),
        )
        if res.status_code != 200:
            raise Exception(f"GraphQL HTTP hatası: {res.status_code}")
        body = res.json()
        errors = body.get("errors") or []
        if errors:
            raise Exception(errors[0].get("message", "GraphQL hatası"))
        return body.get("data") or {}

    def _search_products_for_delete(self):
        search = self.delete_search_text.get().strip()
        if not search:
            messagebox.showwarning("Uyarı", "Lütfen ürün adı veya anahtar kelime girin.")
            return
        self.list_delete_results.delete(0, tk.END)
        self.delete_results = []
        self.delete_selected_product = None
        self.lbl_delete_selection.config(text="Seçili ürün: -")
        threading.Thread(target=self._search_products_for_delete_logic, args=(search,), daemon=True).start()

    def _search_products_for_delete_logic(self, search):
        self._log(f"🔎 Ürün aranıyor: {search}")
        try:
            auth = self._get_ikas_auth_header()
            query = """
            query FindProducts($search: String!) {
              listProduct(search: $search, pagination: {page: 1, limit: 25}) {
                data {
                  id
                  name
                  variants { id }
                }
              }
            }
            """
            data = self._ikas_graphql(auth, query, {"search": search})
            products = ((data.get("listProduct") or {}).get("data")) or []
            self.delete_results = products

            def _fill():
                self.list_delete_results.delete(0, tk.END)
                if not products:
                    self.list_delete_results.insert(tk.END, "Sonuç bulunamadı.")
                    return
                for p in products:
                    name = p.get("name", "-")
                    pid = p.get("id", "-")
                    vcount = len(p.get("variants") or [])
                    self.list_delete_results.insert(
                        tk.END, f"{name} | varyant:{vcount} | id:{pid}"
                    )

            self.after(0, _fill)
            self._log(f"✅ Arama tamamlandı. Sonuç: {len(products)} ürün")
        except Exception as e:
            self._log(f"❌ Ürün arama hatası: {e}")
            self.after(0, lambda: messagebox.showerror("Arama Hatası", str(e)))

    def _on_delete_result_select(self, _event=None):
        sel = self.list_delete_results.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx >= len(self.delete_results):
            return
        self.delete_selected_product = self.delete_results[idx]
        name = self.delete_selected_product.get("name", "-")
        pid = self.delete_selected_product.get("id", "-")
        self.lbl_delete_selection.config(text=f"Seçili ürün: {name} ({pid})")

    def _delete_selected_product(self):
        product = self.delete_selected_product
        if not product:
            messagebox.showwarning("Uyarı", "Lütfen önce listeden bir ürün seçin.")
            return

        name = str(product.get("name", "")).strip()
        pid = str(product.get("id", "")).strip()
        if not (name and pid):
            messagebox.showerror("Hata", "Seçilen ürün bilgisi eksik.")
            return

        ok = messagebox.askyesno(
            "Silme Onayı",
            f"Sadece bu ürün silinecek:\n\n{name}\n\nDevam etmek istiyor musunuz?",
        )
        if not ok:
            return

        typed = simpledialog.askstring(
            "Son Onay",
            f"Yanlışlıkla silmeyi önlemek için ürün adını aynen yazın:\n\n{name}",
            parent=self,
        )
        if typed is None:
            return
        if self._normalize_name(typed) != self._normalize_name(name):
            messagebox.showwarning("Uyarı", "Ürün adı eşleşmedi. Silme iptal edildi.")
            return

        threading.Thread(target=self._delete_selected_product_logic, args=(pid, name), daemon=True).start()

    def _delete_selected_product_logic(self, product_id, product_name):
        self._log(f"🗑️ Silme başlatıldı: {product_name}")
        try:
            auth = self._get_ikas_auth_header()
            mutation = """
            mutation DeleteProduct($idList: [String!]!) {
              deleteProductList(idList: $idList)
            }
            """
            self._ikas_graphql(auth, mutation, {"idList": [product_id]})
            self._log(f"✅ Ürün silindi: {product_name}")
            self.after(0, lambda: messagebox.showinfo("Başarılı", f"Ürün silindi:\n{product_name}"))

            # refresh list after delete
            search = self.delete_search_text.get().strip()
            if search:
                self.after(0, self._search_products_for_delete)
        except Exception as e:
            self._log(f"❌ Ürün silme hatası: {e}")
            self.after(0, lambda: messagebox.showerror("Silme Hatası", str(e)))

    def _fitguide_popup_is_alive(self):
        popup = getattr(self, "fitguide_popup_window", None)
        if not popup:
            return False
        try:
            return bool(popup.winfo_exists())
        except Exception:
            return False

    def _product_features_popup_is_alive(self):
        popup = getattr(self, "product_features_popup_window", None)
        if not popup:
            return False
        try:
            return bool(popup.winfo_exists())
        except Exception:
            return False

    def _resolve_product_template_brand(self):
        mapping = {
            "Ray-Ban Şablonu": "Ray-Ban",
            "Osse Şablonu": "Osse",
            "Venture Şablonu": "Venture",
        }
        selected = str(self.product_features_template.get() or "").strip()
        return mapping.get(selected, "")

    def _open_product_features_popup(self):
        if self._product_features_popup_is_alive():
            self.product_features_popup_window.lift()
            self.product_features_popup_window.focus_force()
            return

        popup = tk.Toplevel(self)
        popup.title("Ürün Özellikleri")
        popup.geometry("930x610")
        popup.configure(bg=COLOR_BG)
        popup.transient(self.winfo_toplevel())

        self.product_features_popup_window = popup
        self.product_features_popup_results = []
        self.product_features_popup_selected = []

        frame = tk.Frame(popup, bg=COLOR_BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        title = tk.Label(
            frame,
            text="Ürün Özellikleri",
            bg=COLOR_BG,
            fg=COLOR_ACCENT,
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        )
        title.pack(anchor="w")

        desc = tk.Label(
            frame,
            text=(
                "Eski ürünleri seçip toplu şekilde marka/model odaklı açıklama güncellemesi yapar.\n"
                "Kalıcı açıklama görselleri her ürüne otomatik eklenir."
            ),
            bg=COLOR_BG,
            fg="#d2d2d2",
            justify="left",
            wraplength=900,
            anchor="w",
        )
        desc.pack(anchor="w", fill=tk.X, pady=(6, 10))

        row = tk.Frame(frame, bg=COLOR_BG)
        row.pack(fill=tk.X)

        entry = tk.Entry(
            row,
            textvariable=self.product_features_search_text,
            bg="#555",
            fg="white",
            bd=0,
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 10))

        template_options = [
            "Otomatik (Markayı üründen oku)",
            "Ray-Ban Şablonu",
            "Osse Şablonu",
            "Venture Şablonu",
        ]
        current_template = str(self.product_features_template.get() or "").strip()
        if current_template not in template_options:
            self.product_features_template.set(template_options[0])

        cmb_template = ttk.Combobox(
            row,
            textvariable=self.product_features_template,
            values=template_options,
            width=30,
            state="readonly",
        )
        cmb_template.pack(side=tk.RIGHT, padx=(8, 0))

        btn_search = ttk.Button(
            row,
            text="Ürün Ara",
            command=self._search_products_for_product_features_popup,
        )
        btn_search.pack(side=tk.RIGHT, padx=(6, 0))

        btn_clear = ttk.Button(
            row,
            text="Listeyi Temizle",
            command=self._clear_product_features_popup_list,
        )
        btn_clear.pack(side=tk.RIGHT)

        list_wrap = tk.Frame(frame, bg=COLOR_SECONDARY)
        list_wrap.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.product_features_popup_list = tk.Listbox(
            list_wrap,
            height=12,
            selectmode=tk.EXTENDED,
            exportselection=False,
            bg=COLOR_BG,
            fg=COLOR_FG,
            selectbackground=COLOR_ACCENT,
            selectforeground=COLOR_FG,
            bd=0,
        )
        self.product_features_popup_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.product_features_popup_list.bind(
            "<<ListboxSelect>>", self._on_product_features_popup_select
        )

        scroll = tk.Scrollbar(list_wrap, command=self.product_features_popup_list.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.product_features_popup_list.config(yscrollcommand=scroll.set)

        self.product_features_popup_label = tk.Label(
            frame,
            text="Seçili ürün sayısı: 0",
            bg=COLOR_BG,
            fg=COLOR_WARNING,
            justify="left",
            anchor="w",
        )
        self.product_features_popup_label.pack(fill=tk.X, pady=(10, 6))

        self.btn_product_features_sync = ttk.Button(
            frame,
            text="Seçili Ürünlere Ürün Özellikleri Uygula",
            command=self._start_product_features_sync,
        )
        self.btn_product_features_sync.pack(fill=tk.X)

        status_label = tk.Label(
            frame,
            textvariable=self.product_features_progress_text,
            bg=COLOR_BG,
            fg=COLOR_WARNING,
            justify="left",
            wraplength=900,
            anchor="w",
        )
        status_label.pack(fill=tk.X, pady=(10, 4))

        progressbar = ttk.Progressbar(
            frame,
            orient="horizontal",
            mode="determinate",
            maximum=100,
            variable=self.product_features_progress,
        )
        progressbar.pack(fill=tk.X)

        def _on_close():
            self.btn_product_features_sync = None
            self.product_features_popup_window = None
            self.product_features_popup_results = []
            self.product_features_popup_selected = []
            self.product_features_popup_list = None
            self.product_features_popup_label = None
            try:
                popup.destroy()
            except Exception:
                pass

        popup.protocol("WM_DELETE_WINDOW", _on_close)

    def _open_fitguide_popup(self):
        if self._fitguide_popup_is_alive():
            self.fitguide_popup_window.lift()
            self.fitguide_popup_window.focus_force()
            return

        popup = tk.Toplevel(self)
        popup.title("Özel Alanlar")
        popup.geometry("930x610")
        popup.configure(bg=COLOR_BG)
        popup.transient(self.winfo_toplevel())
        self.fitguide_popup_window = popup
        self.fitguide_popup_results = []
        self.fitguide_popup_selected = []

        frame = tk.Frame(popup, bg=COLOR_BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        title = tk.Label(
            frame,
            text="Özel Alanlar",
            bg=COLOR_BG,
            fg=COLOR_ACCENT,
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        )
        title.pack(anchor="w")

        subtitle = tk.Label(
            frame,
            text="Özel Alan Seçimi",
            bg=COLOR_BG,
            fg=COLOR_WARNING,
            font=("Segoe UI", 11, "bold"),
            anchor="w",
        )
        subtitle.pack(anchor="w", pady=(2, 0))

        desc = tk.Label(
            frame,
            text=(
                "Aşağıdaki butonlardan bir özel alan seçin. "
                "Sonrasında o alana ait araçlar açılır.\n"
                "Aktif araç: Ölçü Rehberi HTML\n"
                "Ürün Özellikleri için sağ menüdeki ayrı butonu kullan."
            ),
            bg=COLOR_BG,
            fg="#d2d2d2",
            justify="left",
            wraplength=900,
            anchor="w",
        )
        desc.pack(anchor="w", fill=tk.X, pady=(6, 10))

        tools_row = tk.Frame(frame, bg=COLOR_BG)
        tools_row.pack(fill=tk.X, pady=(0, 8))

        btn_fitguide_tool = tk.Button(
            tools_row,
            text="Ölçü Rehberi HTML",
            command=self._show_fitguide_feature,
            bg=COLOR_SECONDARY,
            fg=COLOR_FG,
            bd=0,
            padx=10,
            pady=7,
            cursor="hand2",
        )
        btn_fitguide_tool.pack(side=tk.LEFT, padx=(0, 8))

        btn_product_features_tool = tk.Button(
            tools_row,
            text="Ürün Özellikleri (sağ menüden)",
            state="disabled",
            bg="#2d2d3f",
            fg="#909090",
            bd=0,
            padx=10,
            pady=7,
        )
        btn_product_features_tool.pack(side=tk.LEFT, padx=(0, 8))

        btn_future_tool = tk.Button(
            tools_row,
            text="XXX (Yakında)",
            state="disabled",
            bg="#2d2d3f",
            fg="#909090",
            bd=0,
            padx=10,
            pady=7,
        )
        btn_future_tool.pack(side=tk.LEFT)

        self.fitguide_hint_label = tk.Label(
            frame,
            text="İşleme devam etmek için üstten bir araç seç.",
            bg=COLOR_BG,
            fg="#9aa0b3",
            anchor="w",
            justify="left",
        )
        self.fitguide_hint_label.pack(fill=tk.X, pady=(4, 10))

        self.fitguide_feature_frame = tk.Frame(frame, bg=COLOR_SECONDARY, padx=12, pady=12)

        feature_title = tk.Label(
            self.fitguide_feature_frame,
            text="Ölçü Rehberi HTML",
            bg=COLOR_SECONDARY,
            fg=COLOR_ACCENT,
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        )
        feature_title.pack(fill=tk.X)

        feature_desc = tk.Label(
            self.fitguide_feature_frame,
            text=(
                "Ürün adıyla ara, sonuçları listeye ekle ve çoklu seçim yap. "
                "İşlem yalnızca seçtiğin ürünlerde çalışır."
            ),
            bg=COLOR_SECONDARY,
            fg="#d2d2d2",
            justify="left",
            wraplength=860,
            anchor="w",
        )
        feature_desc.pack(fill=tk.X, pady=(4, 10))

        row = tk.Frame(self.fitguide_feature_frame, bg=COLOR_SECONDARY)
        row.pack(fill=tk.X)

        entry = tk.Entry(
            row,
            textvariable=self.fitguide_search_text,
            bg="#555",
            fg="white",
            bd=0,
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 10))

        btn_search = ttk.Button(
            row,
            text="Ürün Ara",
            command=self._search_products_for_fitguide_popup,
        )
        btn_search.pack(side=tk.RIGHT, padx=(6, 0))

        btn_clear = ttk.Button(
            row,
            text="Listeyi Temizle",
            command=self._clear_fitguide_popup_list,
        )
        btn_clear.pack(side=tk.RIGHT)

        list_wrap = tk.Frame(self.fitguide_feature_frame, bg=COLOR_SECONDARY)
        list_wrap.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.fitguide_popup_list = tk.Listbox(
            list_wrap,
            height=12,
            selectmode=tk.EXTENDED,
            exportselection=False,
            bg=COLOR_BG,
            fg=COLOR_FG,
            selectbackground=COLOR_ACCENT,
            selectforeground=COLOR_FG,
            bd=0,
        )
        self.fitguide_popup_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.fitguide_popup_list.bind("<<ListboxSelect>>", self._on_fitguide_popup_select)

        scroll = tk.Scrollbar(list_wrap, command=self.fitguide_popup_list.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.fitguide_popup_list.config(yscrollcommand=scroll.set)

        self.fitguide_popup_label = tk.Label(
            self.fitguide_feature_frame,
            text="Seçili ürün sayısı: 0",
            bg=COLOR_SECONDARY,
            fg=COLOR_WARNING,
            justify="left",
            anchor="w",
        )
        self.fitguide_popup_label.pack(fill=tk.X, pady=(10, 6))

        self.btn_fitguide_sync = ttk.Button(
            self.fitguide_feature_frame,
            text="Seçili Ürünlere Ölçü Rehberi Ekle",
            command=self._start_fitguide_sync,
        )
        self.btn_fitguide_sync.pack(fill=tk.X)

        status_label = tk.Label(
            self.fitguide_feature_frame,
            textvariable=self.fitguide_progress_text,
            bg=COLOR_SECONDARY,
            fg=COLOR_WARNING,
            justify="left",
            wraplength=860,
            anchor="w",
        )
        status_label.pack(fill=tk.X, pady=(10, 4))

        progressbar = ttk.Progressbar(
            self.fitguide_feature_frame,
            orient="horizontal",
            mode="determinate",
            maximum=100,
            variable=self.fitguide_progress,
        )
        progressbar.pack(fill=tk.X)

        self.product_features_feature_frame = tk.Frame(
            frame, bg=COLOR_SECONDARY, padx=12, pady=12
        )

        pf_title = tk.Label(
            self.product_features_feature_frame,
            text="Ürün Özellikleri",
            bg=COLOR_SECONDARY,
            fg=COLOR_ACCENT,
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        )
        pf_title.pack(fill=tk.X)

        pf_desc = tk.Label(
            self.product_features_feature_frame,
            text=(
                "Ürün adıyla ara, sonuçları listeye ekle ve çoklu seçim yap. "
                "Seçilen ürünlerin açıklaması marka/model odaklı güncellenir. "
                "Açıklama başına kalıcı görseller otomatik eklenir."
            ),
            bg=COLOR_SECONDARY,
            fg="#d2d2d2",
            justify="left",
            wraplength=860,
            anchor="w",
        )
        pf_desc.pack(fill=tk.X, pady=(4, 10))

        pf_row = tk.Frame(self.product_features_feature_frame, bg=COLOR_SECONDARY)
        pf_row.pack(fill=tk.X)

        pf_entry = tk.Entry(
            pf_row,
            textvariable=self.product_features_search_text,
            bg="#555",
            fg="white",
            bd=0,
        )
        pf_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 10))

        pf_btn_search = ttk.Button(
            pf_row,
            text="Ürün Ara",
            command=self._search_products_for_product_features_popup,
        )
        pf_btn_search.pack(side=tk.RIGHT, padx=(6, 0))

        pf_btn_clear = ttk.Button(
            pf_row,
            text="Listeyi Temizle",
            command=self._clear_product_features_popup_list,
        )
        pf_btn_clear.pack(side=tk.RIGHT)

        pf_list_wrap = tk.Frame(self.product_features_feature_frame, bg=COLOR_SECONDARY)
        pf_list_wrap.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.product_features_popup_list = tk.Listbox(
            pf_list_wrap,
            height=12,
            selectmode=tk.EXTENDED,
            exportselection=False,
            bg=COLOR_BG,
            fg=COLOR_FG,
            selectbackground=COLOR_ACCENT,
            selectforeground=COLOR_FG,
            bd=0,
        )
        self.product_features_popup_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.product_features_popup_list.bind(
            "<<ListboxSelect>>", self._on_product_features_popup_select
        )

        pf_scroll = tk.Scrollbar(
            pf_list_wrap, command=self.product_features_popup_list.yview
        )
        pf_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.product_features_popup_list.config(yscrollcommand=pf_scroll.set)

        self.product_features_popup_label = tk.Label(
            self.product_features_feature_frame,
            text="Seçili ürün sayısı: 0",
            bg=COLOR_SECONDARY,
            fg=COLOR_WARNING,
            justify="left",
            anchor="w",
        )
        self.product_features_popup_label.pack(fill=tk.X, pady=(10, 6))

        self.btn_product_features_sync = ttk.Button(
            self.product_features_feature_frame,
            text="Seçili Ürünlere Ürün Özellikleri Uygula",
            command=self._start_product_features_sync,
        )
        self.btn_product_features_sync.pack(fill=tk.X)

        pf_status_label = tk.Label(
            self.product_features_feature_frame,
            textvariable=self.product_features_progress_text,
            bg=COLOR_SECONDARY,
            fg=COLOR_WARNING,
            justify="left",
            wraplength=860,
            anchor="w",
        )
        pf_status_label.pack(fill=tk.X, pady=(10, 4))

        pf_progressbar = ttk.Progressbar(
            self.product_features_feature_frame,
            orient="horizontal",
            mode="determinate",
            maximum=100,
            variable=self.product_features_progress,
        )
        pf_progressbar.pack(fill=tk.X)

        def _on_close():
            self.btn_fitguide_sync = None
            self.btn_product_features_sync = None
            self.fitguide_popup_window = None
            self.fitguide_popup_list = None
            self.fitguide_popup_label = None
            self.fitguide_feature_frame = None
            self.fitguide_hint_label = None
            self.product_features_popup_results = []
            self.product_features_popup_selected = []
            self.product_features_popup_list = None
            self.product_features_popup_label = None
            self.product_features_feature_frame = None
            self.fitguide_attribute_id = ""
            try:
                popup.destroy()
            except Exception:
                pass

        popup.protocol("WM_DELETE_WINDOW", _on_close)

    def _show_fitguide_feature(self):
        if not self._fitguide_popup_is_alive():
            return
        if self.fitguide_hint_label is not None:
            try:
                self.fitguide_hint_label.pack_forget()
            except Exception:
                pass
        if self.product_features_feature_frame is not None:
            try:
                self.product_features_feature_frame.pack_forget()
            except Exception:
                pass
        if self.fitguide_feature_frame is not None:
            self.fitguide_feature_frame.pack(fill=tk.BOTH, expand=True, pady=(2, 0))

    def _show_product_features_feature(self):
        if not self._fitguide_popup_is_alive():
            return
        if self.fitguide_hint_label is not None:
            try:
                self.fitguide_hint_label.pack_forget()
            except Exception:
                pass
        if self.fitguide_feature_frame is not None:
            try:
                self.fitguide_feature_frame.pack_forget()
            except Exception:
                pass
        if self.product_features_feature_frame is not None:
            self.product_features_feature_frame.pack(
                fill=tk.BOTH, expand=True, pady=(2, 0)
            )

    def _popup_is_alive(self):
        popup = getattr(self, "delete_popup_window", None)
        if not popup:
            return False
        try:
            return bool(popup.winfo_exists())
        except Exception:
            return False

    def _open_delete_popup(self):
        if self._popup_is_alive():
            self.delete_popup_window.lift()
            self.delete_popup_window.focus_force()
            return

        popup = tk.Toplevel(self)
        popup.title("İkas Ürün Silme (Güvenli)")
        popup.geometry("900x500")
        popup.configure(bg=COLOR_BG)
        popup.transient(self.winfo_toplevel())

        self.delete_popup_window = popup
        self.delete_popup_results = []
        self.delete_popup_selected = []
        self.delete_popup_search_text = tk.StringVar()

        frame = tk.Frame(popup, bg=COLOR_BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        title = tk.Label(
            frame,
            text="Ürün Silme (Çoklu Seçim + Güvenli)",
            bg=COLOR_BG,
            fg=COLOR_ERROR,
            font=("Segoe UI", 14, "bold"),
        )
        title.pack(anchor="w")

        desc = tk.Label(
            frame,
            text=(
                "Listeden bir veya birden fazla ürün seçebilirsiniz. "
                "Arama sonuçları listeye eklenir. Silmeden önce güçlü onay gerekir."
            ),
            bg=COLOR_BG,
            fg="#aaaaaa",
            justify="left",
            wraplength=840,
        )
        desc.pack(anchor="w", pady=(4, 12))

        row = tk.Frame(frame, bg=COLOR_BG)
        row.pack(fill=tk.X)

        entry = tk.Entry(
            row,
            textvariable=self.delete_popup_search_text,
            bg="#555",
            fg="white",
            bd=0,
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6, padx=(0, 10))

        btn_search = ttk.Button(
            row,
            text="Ürün Ara",
            command=self._search_products_for_delete_popup,
        )
        btn_search.pack(side=tk.RIGHT, padx=(6, 0))

        btn_clear = ttk.Button(
            row,
            text="Listeyi Temizle",
            command=self._clear_delete_popup_list,
        )
        btn_clear.pack(side=tk.RIGHT)

        list_wrap = tk.Frame(frame, bg=COLOR_BG)
        list_wrap.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.delete_popup_list = tk.Listbox(
            list_wrap,
            height=12,
            selectmode=tk.EXTENDED,
            exportselection=False,
            bg=COLOR_SECONDARY,
            fg=COLOR_FG,
            selectbackground=COLOR_ACCENT,
            selectforeground=COLOR_FG,
            bd=0,
        )
        self.delete_popup_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.delete_popup_list.bind("<<ListboxSelect>>", self._on_delete_popup_select)

        scroll = tk.Scrollbar(list_wrap, command=self.delete_popup_list.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.delete_popup_list.config(yscrollcommand=scroll.set)

        self.delete_popup_label = tk.Label(
            frame,
            text="Seçili ürün sayısı: 0",
            bg=COLOR_BG,
            fg=COLOR_WARNING,
            anchor="w",
        )
        self.delete_popup_label.pack(fill=tk.X, pady=(10, 8))

        btn_delete = tk.Button(
            frame,
            text="Seçili Ürünleri Sil",
            command=self._delete_selected_product_popup,
            bg=COLOR_ERROR,
            fg="white",
            bd=0,
            padx=12,
            pady=8,
        )
        btn_delete.pack(anchor="e")

    def _search_products_for_delete_popup(self):
        if not self._popup_is_alive():
            return
        search = self.delete_popup_search_text.get().strip()
        if not search:
            messagebox.showwarning("Uyarı", "Lütfen ürün adı veya anahtar kelime girin.")
            return
        threading.Thread(
            target=self._search_products_for_delete_logic_popup,
            args=(search,),
            daemon=True,
        ).start()

    def _search_products_for_delete_logic_popup(self, search):
        self._log(f"🔎 Silme paneli arama: {search}")
        try:
            auth = self._get_ikas_auth_header()
            query = """
            query FindProducts($search: String!) {
              listProduct(search: $search, pagination: {page: 1, limit: 25}) {
                data {
                  id
                  name
                  variants { id }
                }
              }
            }
            """
            data = self._ikas_graphql(auth, query, {"search": search})
            products = ((data.get("listProduct") or {}).get("data")) or []
            self.after(0, lambda: self._append_delete_popup_results(products, search))
        except Exception as e:
            self._log(f"❌ Silme paneli arama hatası: {e}")
            self.after(0, lambda: messagebox.showerror("Arama Hatası", str(e)))

    def _append_delete_popup_results(self, products, search):
        if not self._popup_is_alive():
            return
        if not products:
            self._log(f"ℹ️ Arama sonucu yok: {search}")
            return

        existing_ids = {
            str((p or {}).get("id") or "").strip()
            for p in (self.delete_popup_results or [])
        }
        added = 0
        for p in products:
            pid = str((p or {}).get("id") or "").strip()
            if not pid or pid in existing_ids:
                continue
            existing_ids.add(pid)
            self.delete_popup_results.append(p)
            name = p.get("name", "-")
            vcount = len(p.get("variants") or [])
            self.delete_popup_list.insert(
                tk.END, f"{name} | varyant:{vcount} | id:{pid}"
            )
            added += 1

        if added == 0:
            self._log(f"ℹ️ Arama sonucu zaten listede: {search}")
        else:
            self._log(f"✅ Listeye {added} ürün eklendi. (Arama: {search})")

    def _clear_delete_popup_list(self):
        if not self._popup_is_alive():
            return
        self.delete_popup_results = []
        self.delete_popup_selected = []
        self.delete_popup_list.delete(0, tk.END)
        self.delete_popup_label.config(text="Seçili ürün sayısı: 0")
        self._log("🧹 Silme paneli liste temizlendi.")

    def _on_delete_popup_select(self, _event=None):
        if not self._popup_is_alive():
            return
        indices = list(self.delete_popup_list.curselection())
        if not indices:
            self.delete_popup_selected = []
            self.delete_popup_label.config(text="Seçili ürün sayısı: 0")
            return
        selected = []
        for idx in indices:
            if idx < len(self.delete_popup_results):
                selected.append(self.delete_popup_results[idx])
        self.delete_popup_selected = selected
        count = len(selected)
        if count == 0:
            self.delete_popup_label.config(text="Seçili ürün sayısı: 0")
            return
        preview_names = [str((p or {}).get("name", "-")) for p in selected[:3]]
        more = "" if count <= 3 else f" (+{count - 3} ürün daha)"
        self.delete_popup_label.config(
            text=f"Seçili ürün sayısı: {count} | {', '.join(preview_names)}{more}"
        )

    def _delete_selected_product_popup(self):
        products = list(getattr(self, "delete_popup_selected", []) or [])
        if not products:
            messagebox.showwarning("Uyarı", "Lütfen listeden en az bir ürün seçin.")
            return

        delete_items = []
        for product in products:
            name = str((product or {}).get("name", "")).strip()
            pid = str((product or {}).get("id", "")).strip()
            if not (name and pid):
                continue
            delete_items.append({"id": pid, "name": name})

        if not delete_items:
            messagebox.showerror("Hata", "Seçili ürün bilgileri eksik.")
            return

        count = len(delete_items)
        preview = "\n".join(f"- {x['name']}" for x in delete_items[:10])
        if count > 10:
            preview += f"\n... ve {count - 10} ürün daha"
        ok = messagebox.askyesno(
            "Silme Onayı",
            f"Aşağıdaki {count} ürün silinecek:\n\n{preview}\n\nDevam etmek istiyor musunuz?",
        )
        if not ok:
            return

        typed = simpledialog.askstring(
            "Son Onay",
            f"Yanlışlıkla silmeyi önlemek için şu ifadeyi yazın:\n\nSIL {count}",
            parent=self,
        )
        if typed is None:
            return
        if self._normalize_name(typed) != self._normalize_name(f"SIL {count}"):
            messagebox.showwarning("Uyarı", "Doğrulama ifadesi eşleşmedi. Silme iptal edildi.")
            return

        threading.Thread(
            target=self._delete_selected_product_logic_popup,
            args=(delete_items,),
            daemon=True,
        ).start()

    def _delete_selected_product_logic_popup(self, delete_items):
        self._log(f"🗑️ Silme paneli toplu silme başlatıldı. Ürün sayısı: {len(delete_items)}")
        try:
            auth = self._get_ikas_auth_header()
            mutation = """
            mutation DeleteProduct($idList: [String!]!) {
              deleteProductList(idList: $idList)
            }
            """
            deleted = 0
            failed = []
            total = len(delete_items)
            for i, item in enumerate(delete_items, start=1):
                pid = item["id"]
                name = item["name"]
                self._log(f"⏳ [{i}/{total}] Siliniyor: {name}")
                try:
                    self._ikas_graphql(auth, mutation, {"idList": [pid]})
                    deleted += 1
                    self._log(f"✅ Silindi: {name}")
                except Exception as e:
                    failed.append((name, str(e)))
                    self._log(f"❌ Silinemedi: {name} -> {e}")

            if failed:
                msg = (
                    f"İşlem bitti.\n\nSilinen: {deleted}\nHata: {len(failed)}\n\n"
                    f"İlk hata: {failed[0][0]} -> {failed[0][1]}"
                )
                self.after(0, lambda: messagebox.showwarning("Silme Sonucu", msg))
            else:
                self.after(0, lambda: messagebox.showinfo("Başarılı", f"Tüm seçili ürünler silindi.\nAdet: {deleted}"))

            def _refresh():
                if self._popup_is_alive():
                    deleted_ids = {str(item.get("id")) for item in delete_items}
                    self.delete_popup_results = [
                        p for p in (self.delete_popup_results or [])
                        if str((p or {}).get("id") or "") not in deleted_ids
                    ]
                    self.delete_popup_selected = []
                    self.delete_popup_label.config(text="Seçili ürün sayısı: 0")
                    self.delete_popup_list.delete(0, tk.END)
                    for p in self.delete_popup_results:
                        name = p.get("name", "-")
                        pid = p.get("id", "-")
                        vcount = len(p.get("variants") or [])
                        self.delete_popup_list.insert(
                            tk.END, f"{name} | varyant:{vcount} | id:{pid}"
                        )

            self.after(0, _refresh)
        except Exception as e:
            self._log(f"❌ Silme paneli ürün silme hatası: {e}")
            self.after(0, lambda: messagebox.showerror("Silme Hatası", str(e)))

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
        
        rb_wiro = tk.Radiobutton(ai_frame, text="🌐 Wiro.ai API (Bulut - Yüksek Kalite)", variable=self.var_ai_mode, value="wiro",
                                  bg=COLOR_BG, fg=COLOR_FG, selectcolor=COLOR_SECONDARY, activebackground=COLOR_BG, activeforeground=COLOR_FG)
        rb_wiro.pack(anchor="w", padx=10)
        
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
        
        # Wiro.ai Key (ÖNCELİKLİ)
        tk.Label(api_frame, text="🌐 Wiro.ai API Key:", bg=COLOR_BG, fg=COLOR_FG, font=("Segoe UI", 10, "bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.entry_wiro = tk.Entry(api_frame, bg=COLOR_SECONDARY, fg=COLOR_FG, bd=0, width=40)
        self.entry_wiro.grid(row=0, column=1, padx=10, pady=5)
        
        # Gemini Key
        tk.Label(api_frame, text="Gemini API Key:", bg=COLOR_BG, fg=COLOR_FG).grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.entry_gemini = tk.Entry(api_frame, bg=COLOR_SECONDARY, fg=COLOR_FG, bd=0, width=40)
        self.entry_gemini.grid(row=1, column=1, padx=10, pady=5)
        
        # OpenAI Key
        tk.Label(api_frame, text="OpenAI API Key:", bg=COLOR_BG, fg=COLOR_FG).grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.entry_openai = tk.Entry(api_frame, bg=COLOR_SECONDARY, fg=COLOR_FG, bd=0, width=40)
        self.entry_openai.grid(row=2, column=1, padx=10, pady=5)
        
        # Custom API
        tk.Label(api_frame, text="Custom API URL:", bg=COLOR_BG, fg=COLOR_FG).grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.entry_custom = tk.Entry(api_frame, bg=COLOR_SECONDARY, fg=COLOR_FG, bd=0, width=40)
        self.entry_custom.grid(row=3, column=1, padx=10, pady=5)
        
        # Ikas Keys
        tk.Label(api_frame, text="İkas Client ID:", bg=COLOR_BG, fg=COLOR_FG).grid(row=4, column=0, padx=10, pady=5, sticky="w")
        self.entry_ikas_id = tk.Entry(api_frame, bg=COLOR_SECONDARY, fg=COLOR_FG, bd=0, width=40)
        self.entry_ikas_id.grid(row=4, column=1, padx=10, pady=5)
        
        tk.Label(api_frame, text="İkas Secret:", bg=COLOR_BG, fg=COLOR_FG).grid(row=5, column=0, padx=10, pady=5, sticky="w")
        self.entry_ikas_secret = tk.Entry(api_frame, bg=COLOR_SECONDARY, fg=COLOR_FG, bd=0, width=40, show="*")
        self.entry_ikas_secret.grid(row=5, column=1, padx=10, pady=5)
        
        tk.Label(api_frame, text="Mağaza Adı (örn: kepekcioptik):", bg=COLOR_BG, fg=COLOR_FG).grid(row=6, column=0, padx=10, pady=5, sticky="w")
        self.entry_store = tk.Entry(api_frame, bg=COLOR_SECONDARY, fg=COLOR_FG, bd=0, width=40)
        self.entry_store.grid(row=6, column=1, padx=10, pady=5)

        # Ikas Automation Metadata
        tk.Label(api_frame, text="İkas Google Kategori ID:", bg=COLOR_BG, fg=COLOR_FG).grid(row=7, column=0, padx=10, pady=5, sticky="w")
        self.entry_ikas_google_taxonomy = tk.Entry(api_frame, bg=COLOR_SECONDARY, fg=COLOR_FG, bd=0, width=40)
        self.entry_ikas_google_taxonomy.grid(row=7, column=1, padx=10, pady=5)

        self.var_ikas_ai_description_enabled = tk.BooleanVar(value=True)
        chk_ai_desc = tk.Checkbutton(
            api_frame,
            text="İkas ürün açıklamasını AI ile üret (OpenAI/Gemini)",
            variable=self.var_ikas_ai_description_enabled,
            bg=COLOR_BG,
            fg=COLOR_FG,
            selectcolor=COLOR_SECONDARY,
            activebackground=COLOR_BG,
            activeforeground=COLOR_FG,
        )
        chk_ai_desc.grid(row=8, column=0, columnspan=2, padx=10, pady=(8, 5), sticky="w")

        btn_save = ttk.Button(self, text="Ayarları Kaydet", command=self._save_settings)
        btn_save.pack(anchor="e", pady=20)
        
        self._load_settings()

    def _load_settings(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)

                self.entry_ikas_id.delete(0, tk.END)
                self.entry_ikas_secret.delete(0, tk.END)
                self.entry_store.delete(0, tk.END)
                self.entry_wiro.delete(0, tk.END)
                self.entry_gemini.delete(0, tk.END)
                self.entry_openai.delete(0, tk.END)
                self.entry_custom.delete(0, tk.END)
                self.entry_ikas_google_taxonomy.delete(0, tk.END)

                self.entry_ikas_id.insert(0, data.get("client_id", ""))
                self.entry_ikas_secret.insert(0, data.get("client_secret", ""))
                self.entry_store.insert(0, data.get("store_name", "kepekcioptik"))
                self.entry_wiro.insert(0, data.get("wiro_api_key", ""))
                self.entry_gemini.insert(0, data.get("gemini_api_key", ""))
                self.entry_openai.insert(0, data.get("openai_api_key", ""))
                self.entry_custom.insert(0, data.get("custom_api_url", ""))
                self.entry_ikas_google_taxonomy.insert(
                    0, str(data.get("ikas_google_taxonomy_id", "178") or "178")
                )
                self.var_ai_mode.set(data.get("ai_mode", "local"))
                self.var_ikas_ai_description_enabled.set(
                    bool(data.get("ikas_ai_description_enabled", True))
                )
            except Exception as e:
                print(f"Config yüklenemedi: {e}")

    def _save_settings(self):
        google_taxonomy_id = self.entry_ikas_google_taxonomy.get().strip() or "178"
        if not re.fullmatch(r"\d+", google_taxonomy_id):
            messagebox.showwarning(
                "Uyarı",
                "Google Kategori ID sadece rakamlardan oluşmalı (örn: 178).",
            )
            return

        data = {
            "client_id": self.entry_ikas_id.get().strip(),
            "client_secret": self.entry_ikas_secret.get().strip(),
            "store_name": self.entry_store.get().strip(),
            "wiro_api_key": self.entry_wiro.get().strip(),
            "gemini_api_key": self.entry_gemini.get().strip(),
            "openai_api_key": self.entry_openai.get().strip(),
            "custom_api_url": self.entry_custom.get().strip(),
            "ai_mode": self.var_ai_mode.get(),
            "ikas_google_taxonomy_id": google_taxonomy_id,
            "ikas_ai_description_enabled": bool(self.var_ikas_ai_description_enabled.get()),
        }
        
        try:
            existing = {}
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    existing = json.load(f)

            existing.update(data)

            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(existing, f, indent=4, ensure_ascii=False)
            messagebox.showinfo("Başarılı", "Ayarlar kaydedildi!")
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydedilemedi: {e}")


# ============================================
# MAIL WATCHER PAGE
# ============================================
class MailWatcherPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=COLOR_BG)
        self.controller = controller
        self.watcher_thread = None
        self.is_running = False
        self.stop_flag = False
        
        self._build_ui()
        self._load_config()
    
    def _build_ui(self):
        # Başlık
        header = ttk.Label(self, text="📧 Mail Watcher", style="Header.TLabel")
        header.pack(pady=(20, 5))
        
        subtitle = ttk.Label(self, text="Gmail'den otomatik fotoğraf indirme", style="SubHeader.TLabel")
        subtitle.pack(pady=(0, 20))
        
        # Ana container
        main_frame = tk.Frame(self, bg=COLOR_BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        # Sol Panel - Kontroller
        left_panel = tk.Frame(main_frame, bg=COLOR_SECONDARY, width=300)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        left_panel.pack_propagate(False)
        
        # Durum Göstergesi
        self.status_frame = tk.Frame(left_panel, bg=COLOR_SECONDARY)
        self.status_frame.pack(fill=tk.X, pady=20, padx=15)
        
        self.status_icon = tk.Label(self.status_frame, text="⏹️", font=("Segoe UI", 40), 
                                    bg=COLOR_SECONDARY, fg=COLOR_FG)
        self.status_icon.pack()
        
        self.status_label = tk.Label(self.status_frame, text="Durduruldu", 
                                     font=("Segoe UI", 14, "bold"), 
                                     bg=COLOR_SECONDARY, fg=COLOR_FG)
        self.status_label.pack(pady=5)
        
        # Başlat/Durdur Butonu
        self.toggle_btn = tk.Button(left_panel, text="▶️ BAŞLAT", 
                                    command=self._toggle_watcher,
                                    font=("Segoe UI", 12, "bold"),
                                    bg=COLOR_SUCCESS, fg="white",
                                    activebackground="#27ae60",
                                    relief=tk.FLAT, cursor="hand2",
                                    width=20, height=2)
        self.toggle_btn.pack(pady=15)
        
        # Ayırıcı
        tk.Frame(left_panel, bg="#333", height=1).pack(fill=tk.X, pady=15, padx=15)
        
        # İstatistikler
        stats_label = tk.Label(left_panel, text="📊 İstatistikler", 
                               font=("Segoe UI", 11, "bold"),
                               bg=COLOR_SECONDARY, fg=COLOR_ACCENT)
        stats_label.pack(anchor="w", padx=15)
        
        self.stats_text = tk.Label(left_panel, text="Son kontrol: -\nİndirilen: 0 dosya", 
                                   font=("Segoe UI", 10),
                                   bg=COLOR_SECONDARY, fg=COLOR_FG, justify="left")
        self.stats_text.pack(anchor="w", padx=15, pady=10)
        
        # Sağ Panel - Log
        right_panel = tk.Frame(main_frame, bg=COLOR_SECONDARY)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        log_header = tk.Label(right_panel, text="📋 Mail Watcher Log", 
                              font=("Segoe UI", 11, "bold"),
                              bg=COLOR_SECONDARY, fg=COLOR_ACCENT)
        log_header.pack(anchor="w", padx=15, pady=(15, 5))
        
        # Log Text
        log_frame = tk.Frame(right_panel, bg=COLOR_BG)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        self.log_text = tk.Text(log_frame, bg=COLOR_BG, fg=COLOR_FG, 
                                font=("Consolas", 9), wrap=tk.WORD,
                                relief=tk.FLAT, state="disabled")
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(self.log_text)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.log_text.yview)
        
        # Alt bilgi
        self.info_label = tk.Label(self, text="💡 Tedarikçi 'Güneş Gözlüğü' konulu mail atınca fotoğraflar otomatik indirilir", 
                                   font=("Segoe UI", 9),
                                   bg=COLOR_BG, fg="#888")
        self.info_label.pack(side=tk.BOTTOM, pady=10)
    
    def _load_config(self):
        """Mail watcher config'ini yükle."""
        try:
            config_path = os.path.join(os.path.dirname(__file__), "mail_watcher_config.json")
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
                self._log("✅ Konfigürasyon yüklendi")
            else:
                self.config = {}
                self._log("⚠️ mail_watcher_config.json bulunamadı")
        except Exception as e:
            self.config = {}
            self._log(f"❌ Config hatası: {e}")
    
    def _log(self, message):
        """Log mesajı ekle."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
    
    def _toggle_watcher(self):
        """Başlat/Durdur toggle."""
        if self.is_running:
            self._stop_watcher()
        else:
            self._start_watcher()
    
    def _start_watcher(self):
        """Mail watcher'ı başlat."""
        if not self.config.get("email_address") or not self.config.get("app_password"):
            messagebox.showwarning("Uyarı", "Lütfen mail_watcher_config.json dosyasını yapılandırın!")
            return
        
        self.is_running = True
        self.stop_flag = False
        
        self.status_icon.config(text="🟢")
        self.status_label.config(text="Çalışıyor", fg=COLOR_SUCCESS)
        self.toggle_btn.config(text="⏹️ DURDUR", bg=COLOR_ERROR)
        
        self._log("🚀 Mail Watcher başlatıldı")
        
        # Thread başlat
        self.watcher_thread = threading.Thread(target=self._watcher_loop, daemon=True)
        self.watcher_thread.start()
    
    def _stop_watcher(self):
        """Mail watcher'ı durdur."""
        self.stop_flag = True
        self.is_running = False
        
        self.status_icon.config(text="⏹️")
        self.status_label.config(text="Durduruldu", fg=COLOR_FG)
        self.toggle_btn.config(text="▶️ BAŞLAT", bg=COLOR_SUCCESS)
        
        self._log("🛑 Mail Watcher durduruldu")
    
    def _watcher_loop(self):
        """Mail kontrol döngüsü."""
        import imaplib
        import email
        from email.header import decode_header
        from pathlib import Path
        
        poll_interval = self.config.get("poll_interval_seconds", 60)
        download_count = 0
        
        while not self.stop_flag:
            try:
                self._log("🔍 Gmail kontrol ediliyor...")
                
                # IMAP bağlantısı
                mail = imaplib.IMAP4_SSL(
                    self.config.get("imap_server", "imap.gmail.com"),
                    self.config.get("imap_port", 993)
                )
                mail.login(self.config["email_address"], self.config["app_password"])
                mail.select("INBOX")
                
                # Okunmamış mailleri ara
                _, message_numbers = mail.search(None, "UNSEEN")
                msg_ids = message_numbers[0].split()
                
                if not msg_ids:
                    self._log("📭 Yeni mail yok")
                else:
                    keyword = self.config.get("subject_keyword", "Güneş Gözlüğü")
                    
                    for msg_id in msg_ids:
                        _, msg_data = mail.fetch(msg_id, "(RFC822)")
                        msg = email.message_from_bytes(msg_data[0][1])
                        
                        # Konu decode
                        subject_raw = msg["Subject"]
                        if subject_raw:
                            decoded = decode_header(subject_raw)
                            subject = ""
                            for part, charset in decoded:
                                if isinstance(part, bytes):
                                    subject += part.decode(charset or "utf-8", errors="replace")
                                else:
                                    subject += part
                        else:
                            subject = ""
                        
                        # Keyword kontrolü
                        if keyword.lower() in subject.lower():
                            self._log(f"📧 Mail bulundu: {subject[:40]}...")
                            
                            # Klasör yapısını ayrıştır (model/renk)
                            from mail_watcher import parse_subject_to_folders
                            main_folder, color_folder = parse_subject_to_folders(subject)
                            
                            if not main_folder or not color_folder:
                                self._log(f"  ⚠️ Konu formatı uygun değil")
                                mail.store(msg_id, "+FLAGS", "\\Seen")
                                continue
                            
                            download_root = self.config.get("download_root", "input")
                            target_folder = os.path.join(download_root, main_folder, color_folder)
                            Path(target_folder).mkdir(parents=True, exist_ok=True)
                            self._log(f"  📁 {main_folder}/{color_folder}/")
                            
                            # Ekleri indir
                            allowed_exts = self.config.get("save_attachments_exts", [".jpg", ".jpeg", ".png", ".webp"])
                            
                            for part in msg.walk():
                                if part.get_content_maintype() == "multipart":
                                    continue
                                
                                filename = part.get_filename()
                                if not filename:
                                    continue
                                
                                # Dosya adı decode
                                decoded_fn = decode_header(filename)
                                if decoded_fn[0][1]:
                                    filename = decoded_fn[0][0].decode(decoded_fn[0][1])
                                elif isinstance(decoded_fn[0][0], bytes):
                                    filename = decoded_fn[0][0].decode("utf-8", errors="replace")
                                else:
                                    filename = decoded_fn[0][0]
                                
                                _, ext = os.path.splitext(filename.lower())
                                if ext in allowed_exts:
                                    filepath = os.path.join(target_folder, filename)
                                    
                                    # Aynı isim varsa numara ekle
                                    counter = 1
                                    base, ext_orig = os.path.splitext(filepath)
                                    while os.path.exists(filepath):
                                        filepath = f"{base}_{counter}{ext_orig}"
                                        counter += 1
                                    
                                    with open(filepath, "wb") as f:
                                        f.write(part.get_payload(decode=True))
                                    
                                    download_count += 1
                                    self._log(f"  ✅ {filename}")
                            
                            # Maili işlenmiş olarak işaretle
                            try:
                                processed_folder = self.config.get("processed_folder", "Processed")
                                try:
                                    mail.create(processed_folder)
                                except:
                                    pass
                                mail.copy(msg_id, processed_folder)
                                mail.store(msg_id, "+FLAGS", "\\Deleted")
                            except:
                                mail.store(msg_id, "+FLAGS", "\\Seen")
                
                mail.expunge()
                mail.logout()
                
                # İstatistikleri güncelle
                from datetime import datetime
                self.stats_text.config(text=f"Son kontrol: {datetime.now().strftime('%H:%M:%S')}\nİndirilen: {download_count} dosya")
                
            except Exception as e:
                self._log(f"❌ Hata: {str(e)[:50]}")
            
            # Bekle
            for _ in range(poll_interval):
                if self.stop_flag:
                    break
                time.sleep(1)
        
        self._log("👋 Watcher döngüsü sonlandı")


class HelpPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, bg=COLOR_BG)
        self.controller = controller
        
        header = ttk.Label(self, text="Kullanım Talimatları", style="Header.TLabel")
        header.pack(pady=20, padx=20, anchor="w")
        
        # Scrollable Text
        text_frame = tk.Frame(self, bg=COLOR_BG)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.help_text = tk.Text(text_frame, bg="#333", fg="white", font=("Segoe UI", 11),
                                 borderwidth=0, padx=20, pady=20, state="normal",
                                 yscrollcommand=scrollbar.set)
        self.help_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.help_text.yview)
        
        # İçeriği Ekle
        content = """
# 🔬 Kepekçi Optik - Studio & İkas Manager

Bu yazılım, ürün görsellerini stüdyo kalitesinde temizlemek ve İkas'a yüklemek için geliştirilmiştir.

---

### 📸 1. Stüdyo Modu (Görsel Temizleme)
*   **Giriş Klasörü:** Temizlenecek ham fotoğrafların olduğu klasörü seçin.
*   **Model:** 'Otomatik' önerilir.
*   **Başlat:** Program, fotoğraflardaki arka planı siler, beyaz fon ve gölge ekler.
*   **Çıktı:** Temizlenen resimler 'output' klasörüne kaydedilir.

---

### 🚀 2. İkas Entegrasyonu
Bu modül ile ürünlerinizi İkas paneline hızlıca aktarabilirsiniz.

**A. Excel Oluştur & Düzenle**
1.  Butona bastığınızda 'output' klasöründeki ürünler listelenir.
2.  **Önizleme Penceresi:** Açılan tabloda fiyat, stok ve isimleri değiştirebilirsiniz.
    *   **Çift Tıkla:** Hücreyi düzenle.
    *   **➕ / 🗑️:** Satır ekle veya sil.
3.  **Kaydet:** Onayladığınızda masaüstüne bir Excel dosyası oluşturulur. Bunu İkas paneline yükleyin.

**B. Görsel Yükle**
1.  İkas panelinden ürünleri dışa aktarın (Excel olarak indirin).
2.  'Görsel Yükle' butonuna basıp o Excel dosyasını seçin.
3.  Program, ürün isimlerine göre eşleşen fotoğrafları otomatik yükler.

---

### 💡 İpuçları & Varyantlar
*   **Otomatik Renk Algılama:** Klasör isimlerinin son kelimesi renk kodu kabul edilir.
    *   Örn: "Rayban 1234 **C01**" -> Renk Kodu: **C01**
    *   İkas'taki renk kodu ile klasördeki renk kodu aynı olmalıdır.

### ⚙️ Ayarlar
*   İkas entegrasyonu için API anahtarlarını buradan girebilirsiniz.
*   Bilgisayarınız yavaşsa AI Modunu 'Local' yerine 'API' (Gemini/OpenAI) yapabilirsiniz.

Tüm işlemler bu kadar! Güle güle kullanın. 🧿
"""
        self.help_text.insert(tk.END, content.strip())
        self.help_text.config(state="disabled")

if __name__ == "__main__":
    app = ModernApp()
    app.mainloop()
