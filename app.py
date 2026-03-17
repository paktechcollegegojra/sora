import os
import requests
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

    # These are the magic settings you need in 2026 to beat Sora's security
    params = {
        'url': sora_url,
        'apikey': ZENROWS_API_KEY,
        'js_render': 'true',        # Runs Javascript to load the video player
        'premium_proxy': 'true',     # Uses a home IP to avoid being blocked
        'antibot': 'true',           # Automatically solves 'I am human' checks
        'wait_for': 'video'          # Waits until the video actually appears
    }

    try:
        # We tell ZenRows to go get the page for us
        response = requests.get('https://api.zenrows.com/v1/', params=params, timeout=30)
        html_content = response.text
        
        # We look for the video source in the code ZenRows sent back
        # Sora video links usually start with 'https://' and end with '.mp4'
        if 'src="' in html_content:
            # This is a simple way to pull the URL out of the HTML tags
            parts = html_content.split('src="')
            for p in parts:
                if 'https://' in p and '.mp4' in p:
                    video_url = p.split('"')[0]
                    return jsonify({"status": "success", "download_url": video_url})
        
        return jsonify({"error": "Could not find video. Try a different Sora link."}), 404

    except Exception as e:
        return jsonify({"error": "Connection to ZenRows failed."}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
