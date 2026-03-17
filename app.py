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
        
        # THE AZURE SIGNATURE FILTER:
        # Secure OpenAI videos ALWAYS have a signature ('sig=') and an expiration time ('se=').
        # Fonts, CSS, and basic images do not have these security tags.
        secure_video_links = [link for link in all_links if 'sig=' in link and 'se=' in link]

        if secure_video_links:
            # The video file will be the longest link because of the massive security tokens.
            best_link = max(secure_video_links, key=len)
            return jsonify({"status": "success", "download_url": best_link})

        # If it gets here, it bypassed security but couldn't find an Azure signature.
        return jsonify({"error": "Bypassed successfully, but the secure video signature is missing."}), 404

    except Exception as e:
        return jsonify({"error": f"Server Error: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
