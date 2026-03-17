import os
import requests
import re
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Your ZenRows API Key
ZENROWS_API_KEY = "97a3341face7698dd0dccb24b16e385f0d826033"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
def process_video():
    data = request.json
    sora_url = data.get('url')
    
    if not sora_url:
        return jsonify({"error": "No URL provided"}), 400

    params = {
        'url': sora_url,
        'apikey': ZENROWS_API_KEY,
        'js_render': 'true',
        'premium_proxy': 'true',
        'antibot': 'true',
        'wait_for': 'video',          # Wait for the player
        'wait_browser': 'networkidle' # Wait for the video to start loading
    }

    try:
        # We increase timeout to 60 because Sora is slow to load
        response = requests.get('https://api.zenrows.com/v1/', params=params, timeout=60)
        html = response.text
        
        # --- IMPROVED SEARCHING ---
        # We look for ANY .mp4 link that looks like it belongs to OpenAI/Sora
        # This covers almost all the different link formats Sora uses.
        links = re.findall(r'(https?://[^\s"]+sora[^\s"]+\.mp4[^\s"]*)', html)
        
        if not links:
            # Fallback: Look for any high-quality mp4 link
            links = re.findall(r'(https?://[^\s"]+\.mp4[^\s"]*)', html)

        if links:
            # We found it! We take the first one found.
            return jsonify({"status": "success", "download_url": links[0]})
        
        return jsonify({"error": "Sora is being stubborn. Try the link again in a moment."}), 404

    except Exception as e:
        return jsonify({"error": "ZenRows timed out. Sora's servers might be busy."}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
