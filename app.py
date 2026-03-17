import os
import time
import random
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from seleniumbase import SB

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
def process_video():
    data = request.json
    sora_url = data.get('url')
    
    if not sora_url:
        return jsonify({"error": "No URL provided"}), 400

    # List of 2026 User Agents to rotate
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ]

    video_src = ""
    # UC=True + Incognito=True is the gold standard for 2026 bypass
    try:
        with SB(uc=True, headless=True, incognito=True, agent=random.choice(user_agents)) as sb:
            # 1. Use the 'reconnect' strategy which is better for Turnstile
            sb.uc_open_with_reconnect(sora_url, reconnect_time=7)
            
            # 2. Wait for the human check to clear
            sb.sleep(random.uniform(3.5, 6.2)) 
            
            # 3. Attempt to auto-click the 'Verify' button if it appears
            try:
                sb.uc_gui_click_captcha()
            except:
                pass

            # 4. Specifically wait for the Sora video player to render
            sb.wait_for_element("video", timeout=20)
            video_src = sb.get_attribute("video", "src")
            
            if not video_src:
                raise Exception("Video source not found in DOM")

    except Exception as e:
        print(f"Bypass Error: {e}")
        return jsonify({"error": "Security bypass failed. Sora's anti-bot is blocking the server."}), 403

    # Simulation for Logo Removal (Needs GPU for real)
    time.sleep(3) 
    
    return jsonify({
        "status": "success",
        "download_url": video_src 
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
