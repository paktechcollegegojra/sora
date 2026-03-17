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
        'wait': '8000' # Wait 8 seconds to ensure the JSON payload fully loads
    }

    try:
        response = requests.get('https://api.zenrows.com/v1/', params=params, timeout=60)
        
        # THE MAGIC TRICK: Un-escape the JSON!
        # This converts "https:\/\/sora..." back into "https://sora..."
        clean_html = response.text.replace('\\/', '/')

        # COMPETITOR LEVEL SEARCH 1: Hunt for the unhidden .mp4 or .m3u8 files
        video_links = re.findall(r'(https?://[^\s"\'<>\[\]\{\}]+\.(?:mp4|m3u8)[^\s"\'<>\[\]\{\}]*)', clean_html)
        
        # COMPETITOR LEVEL SEARCH 2: If Sora hid the .mp4 extension, hunt for their specific storage servers
        if not video_links:
            video_links = re.findall(r'(https?://[^\s"\'<>\[\]\{\}]*(?:oaiusercontent|openai-public|sora)[^\s"\'<>\[\]\{\}]*)', clean_html)

        if video_links:
            # We filter out junk links (like logos) to grab the actual heavy video file
            best_links = [l for l in video_links if 'video' in l.lower() or 'mp4' in l.lower() or 'oaiusercontent' in l.lower()]
            final_link = best_links[0] if best_links else video_links[0]
            
            return jsonify({"status": "success", "download_url": final_link})

        return jsonify({"error": "Cracked the JSON, but Sora might be using an encrypted stream today."}), 404

    except Exception as e:
        return jsonify({"error": f"Server Error: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
