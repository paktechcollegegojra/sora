import os
import requests
import re
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Your exact ZenRows API Key
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
        'wait': '8000' # Wait 8 solid seconds for OpenAI to load the video in the background
    }

    try:
        # Increase timeout to 60s because ZenRows takes time to solve Cloudflare
        response = requests.get('https://api.zenrows.com/v1/', params=params, timeout=60)
        html = response.text
        
        print(f"DEBUG: Scraped {len(html)} characters from Sora.")

        # AGGRESSIVE DEEP SEARCH: Look for ANY link ending in .mp4
        # This catches hidden JSON data, React states, and standard HTML tags
        all_mp4_links = re.findall(r'(https?://[^\s"\'<>\[\]\{\}]+\.mp4[^\s"\'<>\[\]\{\}]*)', html)
        
        if all_mp4_links:
            # We filter for links that belong to OpenAI's actual storage servers
            openai_links = [link for link in all_mp4_links if "oaiusercontent" in link or "openai" in link or "sora" in link]
            
            if openai_links:
                # Give back the most secure OpenAI link found
                return jsonify({"status": "success", "download_url": openai_links[0]})
            else:
                # If no OpenAI specific link, just give the first mp4 we found
                return jsonify({"status": "success", "download_url": all_mp4_links[0]})

        return jsonify({"error": "Bypassed successfully, but OpenAI hid the video file too deep."}), 404

    except Exception as e:
        return jsonify({"error": f"Server timeout or error: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
