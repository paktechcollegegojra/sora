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
        # Increase timeout to 60s to allow ZenRows to solve the Cloudflare challenge
        response = requests.get('https://api.zenrows.com/v1/', params=params, timeout=60)
        
        # THE MAGIC TRICK: Un-escape the JSON!
        # This converts "https:\/\/sora..." back into standard "https://sora..." links
        clean_html = response.text.replace('\\/', '/')

        # Step 1: Find ALL links on the page using Regex
        all_links = re.findall(r'(https?://[^\s"\'<>\[\]\{\}]+)', clean_html)
        
        # Step 2: ANTI-JUNK FILTER (Block CSS, Javascript, Fonts, and standard Images)
        bad_stuff = ('.css', '.js', '.woff', '.woff2', '.png', '.jpg', '.jpeg', '.svg', '.map')
        clean_links = [link for link in all_links if not link.endswith(bad_stuff) and "_next/static" not in link]

        # Step 3: TARGET THE VIDEO (Look for mp4, m3u8, or OpenAI's hidden file vault)
        video_links = []
        for link in clean_links:
            if '.mp4' in link or '.m3u8' in link or 'files.oaiusercontent.com/file-' in link:
                video_links.append(link)

        if video_links:
            # Video URLs with secure access tokens attached are usually the longest strings.
            # We grab the longest link in the list to ensure it's the full, authorized video.
            best_link = max(video_links, key=len)
            return jsonify({"status": "success", "download_url": best_link})

        # If it gets here, it bypassed security but the video link was completely encrypted.
        return jsonify({"error": "Bypassed successfully, but couldn't find the media file."}), 404

    except Exception as e:
        return jsonify({"error": f"Server Error: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
