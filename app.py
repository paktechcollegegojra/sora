import os
import requests
import re
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Your ZenRows API Key
ZENROWS_API_KEY = "97a3341face7698dd0dccb24b16e385f0d826033"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
def process_video():
    sora_url = request.json.get('url')
    
    if not sora_url:
        return jsonify({"error": "No URL provided"}), 400

    # ZenRows Bypass Settings
    params = {
        'url': sora_url,
        'apikey': ZENROWS_API_KEY,
        'js_render': 'true',
        'premium_proxy': 'true',
        'antibot': 'true',
        'wait': '8000' # Wait 8 seconds to ensure the JSON payload fully loads
    }

    try:
        # Pushing timeout to 60s to allow ZenRows to solve Cloudflare
        response = requests.get('https://api.zenrows.com/v1/', params=params, timeout=60)
        
        # Un-escape the JSON (fixes hidden slashes and broken parameters)
        clean_html = response.text.replace('\\/', '/').replace('\\u0026', '&')

        # Find ALL links on the page using Regex
        all_links = re.findall(r'(https?://[^\s"\'<>\[\]\{\}]+)', clean_html)
        
        # THE AZURE SIGNATURE FILTER (Now with Thumbnail Blocker!)
        secure_video_links = []
        for link in all_links:
            # 1. Must have Azure security passwords
            if 'sig=' in link and 'se=' in link:
                # 2. MUST NOT be the thumbnail, poster, or a standard image file
                if 'thumbnail' not in link.lower() and 'poster' not in link.lower() and '.jpg' not in link.lower() and '.png' not in link.lower():
                    secure_video_links.append(link)

        if secure_video_links:
            # Now the longest remaining link is guaranteed to be the actual video stream!
            best_link = max(secure_video_links, key=len)
            return jsonify({"status": "success", "download_url": best_link})

        return jsonify({"error": "Bypassed successfully, but couldn't separate the video from the thumbnail."}), 404

    except Exception as e:
        return jsonify({"error": f"Server Error: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
