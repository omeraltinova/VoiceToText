# Makefile for VoiceToText project (Windows)

.PHONY: all run server app

all: run

run: server app

server:
	start cmd /k ".venv\Scripts\activate && python web_translation_server.py"

app:
	start cmd /k ".venv\Scripts\activate && python main.py"
