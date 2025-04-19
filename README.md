# VoiceToText

A real-time transcription and translation app using OpenAI Whisper and Google Translate, with a Tkinter GUI and a Flask web translation server.

## Features

- Continuous audio recording, transcription, and translation.
- Supports multiple target languages.
- Live subtitles overlay for streaming/OBS.
- Export transcripts to TXT, CSV, or PDF.
- Persistent settings (mic, language, Whisper model).
- Web view at http://127.0.0.1:8765.

## Requirements

Install Python 3.8+ and then:

```
pip install -r requirements.txt
```

## Running

### GUI

```
python main.py
```

### Web Server

```
python web_translation_server.py
```

### Live Subtitles Overlay

Click **Overlay** in the GUI to show a borderless subtitle window.

## Packaging

### PyInstaller

```
pyinstaller --onefile main.py
```

### Docker

Build and run the Flask server in Docker:

```
docker build -t voice2text-server .
docker run -p 8765:8765 voice2text-server
```

## Testing

API tests are provided using pytest. Run:

```
pytest
```
