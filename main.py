import tkinter as tk
from tkinter import ttk
import threading
import pyaudio
import wave
import whisper
from googletrans import Translator

#######################
# Globaller ve Ayarlar
#######################
recording = False  # Sürekli kayıt döngüsü çalışıyor mu?
record_thread = None

# Whisper modeli (base, small, medium vs. seçebilirsiniz)
model = whisper.load_model("base")

# Google Translate için translator nesnesi
translator = Translator()


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
    # İsterseniz language='en' ekleyerek İngilizce olduğunu sabitleyebilirsiniz:
    result = model.transcribe(audio_path)
    text = result["text"]
    print("Transkripsiyon tamamlandı.")
    return text
    if not text:
        text = ""
        return text


def translate_to_other(english_text):
    """
    İngilizce metni Google Translate ile Türkçeye çevirir.
    """
    print( language_combo.get() + "'e çeviriliyor...")
    translation = translator.translate(english_text, dest=language_combo.get())
    new_text = translation.text
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
        english_text = transcribe_audio(wav_file)
        if not english_text:
            english_text = "Transkripsiyon yapılamadı."

        # 3) Google Translate ile Türkçeye çevir
        if english_text == "Transkripsiyon yapılamadı.":
            new_text = ""
        else:
            new_text = translate_to_other(english_text)
        if not new_text:
            new_text = ""

        # 4) Arayüz label'ına ekle
        # Mevcut metnin sonuna yeni cümleyi ekleyebiliriz:
        current_text = output_label["text"]
        if new_text == "":
            updated_text = current_text
        else:
            updated_text = current_text + "\n" + new_text

        # Thread-safety açısından ideal olan root.after(...) kullanmaktır:
        root.after(0, lambda: output_label.config(text=updated_text))


def start_recording():
    """ Start düğmesi: Kayıt döngüsünü başlat. """
    global recording, record_thread
    if recording:
        return  # Zaten kayıt devam ediyorsa tekrar başlatma

    device_index = mic_devices[combo.current()][0]
    recording = True

    # Arka planda kayıt + transkripsiyon + çeviri yapan thread
    record_thread = threading.Thread(
        target=record_loop,
        args=(device_index,),
        daemon=True
    )
    record_thread.start()


def stop_recording():
    """ Stop düğmesi: Kayıt döngüsünü durdur. """
    global recording
    recording = False
    print("Kayıt durduruldu.")


#####################
# Tkinter Arayüzü
#####################
root = tk.Tk()
root.title("Sürekli Kayıt - Whisper - Google Translate")

# PyAudio üzerinden mikrofonları listele
mic_devices = []
audio = pyaudio.PyAudio()
for i in range(audio.get_device_count()):
    dev_info = audio.get_device_info_by_index(i)
    if dev_info.get('maxInputChannels', 0) > 0:
        mic_devices.append((i, dev_info['name']))
audio.terminate()

label = ttk.Label(root, text="Mikrofon seçin:")
label.pack(pady=5)

combo = ttk.Combobox(root, values=[f"{d[1]}" for d in mic_devices])
if mic_devices:
    combo.current(0)
combo.pack(pady=5)

select_language_label = ttk.Label(root, text="Çeviri dili seçin:")
select_language_label.pack(pady=5)

language_combo = ttk.Combobox(root, values=["fr", "de", "es", "it", "tr"])
combo.current(0)
language_combo.pack(pady=5)


start_button = ttk.Button(root, text="Start", command=start_recording)
start_button.pack(pady=5)

stop_button = ttk.Button(root, text="Stop", command=stop_recording)
stop_button.pack(pady=5)

output_label = ttk.Label(root, text="Çeviri metni burada görünecek.", wraplength=500)
output_label.pack(pady=20)

root.mainloop()
