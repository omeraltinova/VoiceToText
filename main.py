import tkinter as tk
from tkinter import ttk
import threading
import pyaudio
import wave
import whisper
from googletrans import Translator
import re
import tkinter.colorchooser
import requests
import webbrowser
import os
import json
import queue
import torch
from array import array
from tkinter import filedialog
import csv
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    defaults = {"last_device_index": 0, "language": "en", "model_size": "base"}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                conf = json.load(f)
            defaults.update(conf)
        except:
            pass
    return defaults

def save_config(conf):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(conf, f)
    except:
        pass

config = load_config()
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
model = whisper.load_model(config.get("model_size", "base"), device=DEVICE)
translator = Translator()
WEB_SERVER_URL = 'http://127.0.0.1:8765'

#######################
# Globaller ve Ayarlar
#######################
recording = False  # Sürekli kayıt döngüsü çalışıyor mu?
record_thread = None
audio_queue = None
worker_thread = None
detected_lang = ""
overlay_window = None
overlay_text_var = None
translation_popup = None
translation_text_popup = None
status_var = None

############################
# Ses Kaydı ve Transkripsiyon
############################
def record_audio(device_index, output_filename="output.wav", record_seconds=5, rate=44100, chunk=1024):
    """
    Belirtilen cihazdan 'record_seconds' kadar ses kaydı alır
    ve output_filename'e (WAV formatında) kaydeder.
    """
    audio_interface = pyaudio.PyAudio()
    stream = audio_interface.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=rate,
        input=True,
        input_device_index=device_index,
        frames_per_buffer=chunk
    )

    frames = []
    print("Kayıt başladı...")
    for i in range(int(rate / chunk * record_seconds)):
        data = stream.read(chunk)
        # audio level metering
        try:
            arr = array('h', data)
            peak = max(abs(s) for s in arr) if arr else 0
            normal = peak / 32767 * 100
            root.after(0, lambda v=normal: level_meter.config(value=v))
        except Exception:
            pass
        frames.append(data)
    print("Kayıt bitti.")

    # Kaydı durdur
    stream.stop_stream()
    stream.close()
    audio_interface.terminate()

    # WAV dosyasına yaz
    wf = wave.open(output_filename, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(audio_interface.get_sample_size(pyaudio.paInt16))
    wf.setframerate(rate)
    wf.writeframes(b''.join(frames))
    wf.close()

    return output_filename


def transcribe_audio(audio_path):
    """
    Verilen ses dosyasını Whisper ile transcribe eder.
    (Varsayılan olarak İngilizce kabul edip metin çıkarıyor.)
    """
    print("Whisper transkripsiyon yapılıyor...")
    try:
        result = model.transcribe(audio_path)
        text = result["text"]
        global detected_lang
        detected_lang = result.get("language", "")
    except Exception as e:
        print(f"Transcription error: {e}")
        text = ""
    print("Transkripsiyon tamamlandı.")
    return text


def translate_to_other(english_text):
    """
    İngilizce metni Google Translate ile seçili dile çevirir.
    """
    # Extract language code from combobox value
    lang_code = language_combo.get().split(" - ")[0]
    print(f"{lang_code}'e çeviriliyor...")
    try:
        translation = translator.translate(english_text, dest=lang_code)
        new_text = translation.text
    except Exception as e:
        print(f"Translation error: {e}")
        new_text = ""
    print("Çeviri tamamlandı.")
    return new_text


def record_loop(device_index):
    """
    Bu fonksiyon, recording=True olduğu sürece
    her 5 saniyelik kaydı alıp transcribe + çeviri yapar
    ve Tkinter arayüzünde gösterir.
    """
    global recording
    while recording:
        # 1) 5 saniye ses kaydı
        wav_file = record_audio(device_index=device_index, record_seconds=5)

        # 2) Whisper ile transcribe (İngilizce varsayılıyor)
        audio_queue.put(wav_file)
        root.after(0, lambda: status_var.set("Kayıt devam ediyor..."))


def worker_loop():
    while recording or (audio_queue and not audio_queue.empty()):
        try:
            wav_file = audio_queue.get(timeout=1)
        except queue.Empty:
            continue
        try:
            english_text = transcribe_audio(wav_file)
            if not english_text:
                english_text = "Transkripsiyon yapılamadı."
        except Exception:
            english_text = "Transkripsiyon yapılamadı."
        if english_text == "Transkripsiyon yapılamadı.":
            new_text = ""
        else:
            try:
                new_text = translate_to_other(english_text)
            except Exception:
                new_text = ""
        root.after(0, lambda e=english_text, n=new_text, dl=detected_lang: update_translation_widgets(e, n, dl))
    root.after(0, lambda: status_var.set("Hazır."))


def clear_transcripts():
    transcript_text.config(state="normal")
    transcript_text.delete(1.0, tk.END)
    transcript_text.config(state="disabled")
    translation_text.config(state="normal")
    translation_text.delete(1.0, tk.END)
    translation_text.config(state="disabled")
    if translation_popup and translation_popup.winfo_exists():
        translation_text_popup.config(state="normal")
        translation_text_popup.delete(1.0, tk.END)
        translation_text_popup.config(state="disabled")
    detected_label.config(text="Detected: --")


def export_transcripts():
    file_path = filedialog.asksaveasfilename(defaultextension='.txt', filetypes=[('Text','*.txt'),('CSV','*.csv'),('PDF','*.pdf')])
    if not file_path:
        return
    ext = file_path.rsplit('.',1)[-1].lower()
    try:
        if ext == 'txt':
            with open(file_path,'w',encoding='utf-8') as f:
                f.write('--- Transcript ---\n')
                f.write(transcript_text.get(1.0,'end-1c') + '\n')
                f.write('\n--- Translation ---\n')
                f.write(translation_text.get(1.0,'end-1c') + '\n')
        elif ext == 'csv':
            rows = list(zip(transcript_text.get(1.0,'end-1c').splitlines(), translation_text.get(1.0,'end-1c').splitlines()))
            with open(file_path,'w',newline='',encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Transcript','Translation'])
                writer.writerows(rows)
        elif ext == 'pdf':
            if FPDF is None:
                messagebox.showerror('Export Error','PDF export requires fpdf. Please install fpdf2 (pip install fpdf2)')
                return
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font('Arial','',12)
            pdf.multi_cell(0,10,'--- Transcript ---')
            for line in transcript_text.get(1.0,'end-1c').splitlines():
                pdf.multi_cell(0,10,line)
            pdf.multi_cell(0,10,'')
            pdf.multi_cell(0,10,'--- Translation ---')
            for line in translation_text.get(1.0,'end-1c').splitlines():
                pdf.multi_cell(0,10,line)
            pdf.output(file_path)
        messagebox.showinfo('Export', f'Exported to {file_path}')
    except Exception as e:
        messagebox.showerror('Export Error', str(e))


def update_translation_widgets(english_text, new_text, detected_lang):
    transcript_text.config(state="normal")
    transcript_text.insert(tk.END, english_text + "\n")
    transcript_text.config(state="disabled")
    transcript_text.see(tk.END)

    translation_text.config(state="normal")
    translation_text.insert(tk.END, new_text + "\n")
    translation_text.config(state="disabled")
    translation_text.see(tk.END)
    detected_label.config(text=f"Detected: {detected_lang}")
    # Insert into history
    history_tree.insert("", tk.END, values=(english_text, new_text))


def start_recording():
    """ Start düğmesi: Kayıt döngüsünü başlat. """
    global recording, record_thread
    if recording:
        return  # Zaten kayıt devam ediyorsa tekrar başlatma

    device_index = mic_devices[combo.current()][0]
    recording = True

    global audio_queue, worker_thread
    audio_queue = queue.Queue()
    worker_thread = threading.Thread(target=worker_loop, daemon=True)
    worker_thread.start()

    record_thread = threading.Thread(target=record_loop, args=(device_index,), daemon=True)
    record_thread.start()

def stop_recording():
    """ Stop düğmesi: Kayıt döngüsünü durdur. """
    global recording
    recording = False
    print("Kayıt durduruldu.")
    root.after(0, lambda: status_var.set("Hazır."))

def toggle_history():
    """Toggle visibility of the history panel."""
    if history_frame.winfo_ismapped():
        history_frame.pack_forget()
    else:
        history_frame.pack(fill=tk.BOTH, expand=True, pady=(10,0))

def open_overlay():
    global overlay_window, overlay_text_var
    if overlay_window and overlay_window.winfo_exists():
        overlay_window.lift()
        return
    overlay_window = tk.Toplevel(root)
    overlay_window.overrideredirect(True)
    overlay_window.attributes('-topmost', True)
    overlay_window.configure(bg=ACCENT_COLOR)
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    overlay_window.geometry(f"{sw}x100+0+{sh-100}")
    overlay_text_var = tk.StringVar()
    lbl = tk.Label(overlay_window, textvariable=overlay_text_var, bg=ACCENT_COLOR, fg=FG_COLOR, font=('Arial', 36))
    lbl.pack(fill=tk.BOTH, expand=True)
    def _upd():
        lines = translation_text.get(1.0, 'end-1c').splitlines()
        overlay_text_var.set(lines[-1] if lines else '')
        overlay_window.after(500, _upd)
    _upd()

def init_ui():
    # Menubar
    menubar = tk.Menu(root)
    file_menu = tk.Menu(menubar, tearoff=0)
    file_menu.add_command(label="Export", command=export_transcripts, accelerator="Ctrl+E")
    file_menu.add_command(label="Clear", command=clear_transcripts, accelerator="Ctrl+C")
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=root.quit)
    menubar.add_cascade(label="File", menu=file_menu)
    view_menu = tk.Menu(menubar, tearoff=0)
    view_menu.add_checkbutton(label="History Panel", command=toggle_history)
    menubar.add_cascade(label="View", menu=view_menu)
    root.config(menu=menubar)

    # Toolbar
    toolbar = tk.Frame(root, bg=ACCENT_COLOR)
    toolbar.pack(side=tk.TOP, fill=tk.X)
    EMOJI_FONT = ("Segoe UI Emoji", 16)
    # Buttons with icon and label
    for icon, label, cmd in [
        ("🎙️", "Start", start_recording),
        ("⏹️", "Stop", stop_recording),
        ("🗑️", "Clear", clear_transcripts),
        ("💾", "Export", export_transcripts),
    ]:
        btn = tk.Button(toolbar, text=f"{icon} {label}", command=cmd,
                       bg=ACCENT_COLOR, fg=FG_COLOR,
                       activebackground="#333333", bd=0, highlightthickness=0,
                       font=EMOJI_FONT)
        btn.pack(side=tk.LEFT, padx=4, pady=4)

    # Status Bar
    global status_var
    status_var = tk.StringVar(value="Hazır.")
    status_bar = ttk.Label(root, textvariable=status_var, relief=tk.SUNKEN, anchor=tk.W, padding=5, style="Dark.TLabel")
    status_bar.pack(side=tk.BOTTOM, fill=tk.X)

ACCENT_COLOR = "#222222"
FG_COLOR = "#FFFFFF"
root = tk.Tk()
root.title("Sürekli Kayıt - Whisper - Google Translate")
root.minsize(600, 400)
screen_w = root.winfo_screenwidth()
screen_h = root.winfo_screenheight()
width = int(screen_w * 0.5)
height = int(screen_h * 0.6)
x = int((screen_w - width) / 2)
y = int((screen_h - height) / 2)
root.geometry(f"{width}x{height}+{x}+{y}")
root.configure(bg="#181818")

# Dark combobox dropdown list styling
root.option_add('*TCombobox*Listbox.background', ACCENT_COLOR)
root.option_add('*TCombobox*Listbox.foreground', FG_COLOR)
root.option_add('*TCombobox*Listbox.selectBackground', '#333333')
root.option_add('*TCombobox*Listbox.selectForeground', FG_COLOR)

style = ttk.Style()
try:
    style.theme_use("clam")
except:
    pass
style.configure("Dark.TFrame", background="#181818")
style.configure("Dark.TLabelframe", background="#181818", foreground=FG_COLOR)
style.configure("Dark.TLabelframe.Label", background="#181818", foreground=FG_COLOR)
style.configure("Dark.TLabel", background="#181818", foreground=FG_COLOR)
style.configure("Dark.TButton", background=ACCENT_COLOR, foreground=FG_COLOR)
style.configure("Dark.TCombobox", fieldbackground=ACCENT_COLOR, background=ACCENT_COLOR, foreground=FG_COLOR)
style.map("Dark.TButton", background=[("active", "#333333")])
style.map("Dark.TCombobox",
    fieldbackground=[('readonly', ACCENT_COLOR)],
    background=[('readonly', ACCENT_COLOR)],
    selectbackground=[('readonly', ACCENT_COLOR)],
    foreground=[('readonly', FG_COLOR)],
    arrowcolor=[('!disabled', FG_COLOR)]
)
style.configure("Treeview", background=ACCENT_COLOR, fieldbackground=ACCENT_COLOR, foreground=FG_COLOR)
style.configure("Treeview.Heading", background=ACCENT_COLOR, foreground=FG_COLOR)
style.map("Treeview", background=[('selected', '#333333')], foreground=[('selected', FG_COLOR)])

main_frame = ttk.Frame(root, padding=10, style="Dark.TFrame")
main_frame.pack(fill=tk.BOTH, expand=True)

# Microphone Selection
mic_frame = ttk.LabelFrame(main_frame, text="Mikrofon Seçimi", padding=10, style="Dark.TLabelframe")
mic_frame.pack(fill=tk.X, pady=5)

mic_devices = []
audio = pyaudio.PyAudio()
def clean_device_name(name):
    if not isinstance(name, str):
        try:
            name = name.decode('utf-8', errors='replace')
        except Exception:
            name = str(name)
    name = re.sub(r'[^a-zA-Z0-9\s\.,!?-]', '?', name)
    return name.strip()
for i in range(audio.get_device_count()):
    dev_info = audio.get_device_info_by_index(i)
    if dev_info.get("maxInputChannels", 0) > 0:
        mic_devices.append((i, clean_device_name(dev_info['name'])))
audio.terminate()

mic_label = ttk.Label(mic_frame, text="Mikrofon:", style="Dark.TLabel")
mic_label.pack(side=tk.LEFT, padx=(0, 10))
combo = ttk.Combobox(mic_frame, values=[d[1] for d in mic_devices], state="readonly", width=40, style="Dark.TCombobox")
if mic_devices:
    combo.current(config.get("last_device_index", 0) % len(mic_devices))
combo.pack(side=tk.LEFT, padx=(0, 10))
combo.bind("<<ComboboxSelected>>", lambda e: (config.update({"last_device_index": combo.current()}), save_config(config)))

# Whisper Model Selection
model_frame = ttk.LabelFrame(main_frame, text="Model Seçimi", padding=10, style="Dark.TLabelframe")
model_frame.pack(fill=tk.X, pady=5)
model_label = ttk.Label(model_frame, text="Model:", style="Dark.TLabel")
model_label.pack(side=tk.LEFT, padx=(0,10))
MODEL_SIZES = ["tiny", "base", "small", "medium", "large"]
model_combo = ttk.Combobox(model_frame, values=MODEL_SIZES, state="readonly", width=10, style="Dark.TCombobox")
model_combo.current(MODEL_SIZES.index(config.get("model_size", "base")))
model_combo.pack(side=tk.LEFT, padx=(0,10))
def on_model_selected(event):
    config["model_size"] = model_combo.get()
    save_config(config)
    global model
    model = whisper.load_model(config["model_size"], device=DEVICE)
model_combo.bind("<<ComboboxSelected>>", on_model_selected)

# Language Selection
lang_frame = ttk.LabelFrame(main_frame, text="Çeviri Dili", padding=10, style="Dark.TLabelframe")
lang_frame.pack(fill=tk.X, pady=5)
lang_label = ttk.Label(lang_frame, text="Dil:", style="Dark.TLabel")
lang_label.pack(side=tk.LEFT, padx=(0,10))
LANGUAGES = [
    ("en", "English"), ("fr", "Français"), ("de", "Deutsch"), ("es", "Español"),
    ("it", "Italiano"), ("tr", "Türkçe"), ("ru", "Русский"), ("zh-cn", "中文 (简体)"),
    ("ja", "日本語"), ("ar", "العربية"), ("hi", "हिन्दी"), ("pt", "Português"),
    ("nl", "Nederlands"), ("sv", "Svenska"), ("pl", "Polski"), ("uk", "Українська"),
    ("ro", "Română"), ("ko", "한국어"), ("fa", "فارسی"),
]
language_combo = ttk.Combobox(lang_frame, values=[f"{c} - {n}" for c,n in LANGUAGES], state="readonly", width=20, style="Dark.TCombobox")
lang_index = next((i for i,(c,n) in enumerate(LANGUAGES) if c==config.get("language")), 0)
language_combo.current(lang_index)
language_combo.pack(side=tk.LEFT)
language_combo.bind("<<ComboboxSelected>>", lambda e: (config.update({"language": language_combo.get().split(" - ")[0]}), save_config(config)))

# Controls
control_frame = ttk.Frame(main_frame, style="Dark.TFrame")
control_frame.pack(fill=tk.X, pady=10)
start_button = ttk.Button(control_frame, text="Start", command=start_recording, style="Dark.TButton")
start_button.pack(side=tk.LEFT, padx=5)
stop_button = ttk.Button(control_frame, text="Stop", command=stop_recording, style="Dark.TButton")
stop_button.pack(side=tk.LEFT, padx=5)
open_window_button = ttk.Button(control_frame, text="Open Translation in New Window", style="Dark.TButton")
open_window_button.pack(side=tk.LEFT, padx=5)
see_in_web_button = ttk.Button(control_frame, text="See in a Web", style="Dark.TButton", command=lambda: webbrowser.open(WEB_SERVER_URL))
see_in_web_button.pack(side=tk.LEFT, padx=5)
clear_button = ttk.Button(control_frame, text="Clear", style="Dark.TButton", command=clear_transcripts)
clear_button.pack(side=tk.LEFT, padx=5)
export_button = ttk.Button(control_frame, text="Export", style="Dark.TButton", command=export_transcripts)
export_button.pack(side=tk.LEFT, padx=5)
#overlay_button = ttk.Button(control_frame, text="Overlay", style="Dark.TButton", command=open_overlay)
#overlay_button.pack(side=tk.LEFT, padx=5)
detected_label = ttk.Label(control_frame, text="Detected: --", style="Dark.TLabel")
detected_label.pack(side=tk.LEFT, padx=5)

# Audio level meter
level_frame = ttk.Frame(main_frame, style="Dark.TFrame")
level_frame.pack(fill=tk.X, pady=5)
level_label = ttk.Label(level_frame, text="Ses Seviyesi:", style="Dark.TLabel")
level_label.pack(side=tk.LEFT, padx=(0,10))
level_meter = ttk.Progressbar(level_frame, length=200, mode="determinate")
level_meter.pack(side=tk.LEFT)

# Separator
ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

# Output Areas
output_frame = ttk.Frame(main_frame, style="Dark.TFrame")
output_frame.pack(fill=tk.BOTH, expand=True)
transcript_label = ttk.Label(output_frame, text="Transkript:", style="Dark.TLabel")
transcript_label.pack(anchor=tk.W, pady=(0, 2))
transcript_text = tk.Text(output_frame, height=6, wrap=tk.WORD, state="disabled", bg=ACCENT_COLOR, fg=FG_COLOR, insertbackground=FG_COLOR)
transcript_text.pack(fill=tk.X, padx=5, pady=(0, 10))
translation_label = ttk.Label(output_frame, text="Çeviri:", style="Dark.TLabel")
translation_label.pack(anchor=tk.W, pady=(0, 2))
translation_text = tk.Text(output_frame, height=6, wrap=tk.WORD, state="disabled", bg=ACCENT_COLOR, fg=FG_COLOR, insertbackground=FG_COLOR)
translation_text.pack(fill=tk.BOTH, expand=True, padx=5)

# History panel (initially hidden)
history_frame = ttk.Frame(main_frame, style="Dark.TFrame")
history_tree = ttk.Treeview(history_frame, columns=("Transcript","Translation"), show="headings")
history_tree.heading("Transcript", text="Transcript")
history_tree.heading("Translation", text="Translation")
hscroll = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=history_tree.yview)
history_tree.configure(yscrollcommand=hscroll.set)
hscroll.pack(side=tk.RIGHT, fill=tk.Y)
history_tree.pack(fill=tk.BOTH, expand=True)

init_ui()
root.bind("<space>", lambda e: start_recording() if not recording else stop_recording())
root.bind("<Control-e>", lambda e: export_transcripts())
root.bind("<Control-c>", lambda e: clear_transcripts())

root.mainloop()
