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
        response = requests.get('https://api.zenrows.com/v1/', params=params, timeout=60)
        
        # THE MAGIC TRICK 2.0: Clean up the messy JSON characters
        # Fixes hidden slashes
        clean_html = response.text.replace('\\/', '/')
        # Fixes broken URL parameters (Converts \u0026 back to &)
        clean_html = clean_html.replace('\\u0026', '&') 

        # Step 1: Find ALL links on the page using Regex
        all_links = re.findall(r'(https?://[^\s"\'<>\[\]\{\}]+)', clean_html)
        
        # Step 2: ANTI-JUNK FILTER (Block CSS, JS, Fonts, and standard Images)
        bad_stuff = ('.css', '.js', '.woff', '.woff2', '.png', '.jpg', '.jpeg', '.svg', '.map', '.ico')
        clean_links = [link for link in all_links if not link.endswith(bad_stuff) and "_next/static" not in link]

        # Step 3: THE "CATCH-ALL" OPENAI FILTER
        # We stop looking for .mp4. We just look for their raw content servers.
        video_links = []
        for link in clean_links:
            # Look for OpenAI's specific file storage domains
            if 'oaiusercontent.com' in link or 'cdn.openai.com' in link:
                # Make sure it's not just a link back to another Sora webpage
                if '/p/s_' not in link:
                    video_links.append(link)

        if video_links:
            # The video file is ALWAYS the longest URL because it has massive 
            # security signatures attached to it (e.g. ?sig=12345&se=2026...).
            best_link = max(video_links, key=len)
            return jsonify({"status": "success", "download_url": best_link})

        # If it gets here, OpenAI completely cloaked the media domain today.
        return jsonify({"error": "Bypassed successfully, but OpenAI completely cloaked the media domain."}), 404

    except Exception as e:
        return jsonify({"error": f"Server Error: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
