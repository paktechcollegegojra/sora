import os
import requests
import re
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Your ZenRows Key
ZENROWS_API_KEY = "97a3341face7698dd0dccb24b16e385f0d826033"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
def process_video():
    sora_url = request.json.get('url')
    
    if not sora_url:
        return jsonify({"error": "No URL provided"}), 400

    params = {
        'url': sora_url,
        'apikey': ZENROWS_API_KEY,
        'js_render': 'true',
        'premium_proxy': 'true',
        'antibot': 'true',
        'wait': '8000' # Waiting 8 seconds for the JSON to load
    }

    try:
        response = requests.get('https://api.zenrows.com/v1/', params=params, timeout=60)
        html = response.text
        
        # SEARCH 1: Hunt for any video file type (.mp4 or .m3u8)
        video_links = re.findall(r'(https?://[^\s"\'<>\[\]\{\}]+\.(?:mp4|m3u8)[^\s"\'<>\[\]\{\}]*)', html)
        
        if video_links:
            # We filter to make sure it's an OpenAI/Sora server link
            best_links = [l for l in video_links if 'openai' in l.lower() or 'sora' in l.lower() or 'oaiusercontent' in l.lower()]
            final_link = best_links[0] if best_links else video_links[0]
            return jsonify({"status": "success", "download_url": final_link})

        # SEARCH 2: The Diagnostic Output (Prints to your screen)
        char_count = len(html)
        if char_count < 5000:
            return jsonify({"error": f"BLOCKED! ZenRows only got {char_count} characters. Cloudflare stopped us."}), 404
        else:
            return jsonify({"error": f"INSIDE SORA! We got {char_count} characters of code, but the video link is hidden in JSON."}), 404

    except Exception as e:
        return jsonify({"error": f"Server Error: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
