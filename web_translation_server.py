from flask import Flask, jsonify, render_template_string, request
import threading

app = Flask(__name__)

# Shared state for translation and user settings
data = {
    'translation': '',
    'bg_color': '#222222',
    'fg_color': '#f5f5f5',
}

def set_translation(text):
    data['translation'] = text

def set_colors(bg, fg):
    data['bg_color'] = bg
    data['fg_color'] = fg

def get_state():
    return data.copy()

@app.route('/')
def index():
    # Simple HTML/JS frontend
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Live Translation</title>
        <style>
            body {
                background: {{ bg_color }};
                color: {{ fg_color }};
                font-family: sans-serif;
                margin: 0; padding: 0;
            }
            #translation {
                margin: 40px auto;
                max-width: 700px;
                font-size: 2em;
                white-space: pre-wrap;
                background: rgba(0,0,0,0.1);
                border-radius: 10px;
                padding: 40px;
                box-shadow: 0 2px 10px #1118;
            }
        </style>
    </head>
    <body>
        <div id="translation">Loading...</div>
        <script>
        async function fetchTranslation() {
            const resp = await fetch('/api/state');
            const data = await resp.json();
            document.body.style.background = data.bg_color;
            document.body.style.color = data.fg_color;
            document.getElementById('translation').style.color = data.fg_color;
            document.getElementById('translation').textContent = data.translation || 'No translation yet.';
        }
        setInterval(fetchTranslation, 1000);
        fetchTranslation();
        </script>
    </body>
    </html>
    ''', bg_color=data['bg_color'], fg_color=data['fg_color'])

@app.route('/api/state')
def api_state():
    return jsonify(get_state())

@app.route('/api/update', methods=['POST'])
def api_update():
    payload = request.json
    if 'translation' in payload:
        set_translation(payload['translation'])
    if 'bg_color' in payload and 'fg_color' in payload:
        set_colors(payload['bg_color'], payload['fg_color'])
    return jsonify({'ok': True})

def run_server():
    app.run(host='127.0.0.1', port=8765, debug=False, use_reloader=False)

# If run directly, start server
if __name__ == '__main__':
    run_server()
