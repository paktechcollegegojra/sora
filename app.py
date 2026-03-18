import os
import requests
import re
import tempfile
import uuid
import subprocess
import html
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Your ZenRows Key
ZENROWS_API_KEY = "97a3341face7698dd0dccb24b16e385f0d826033"
TEMP_DIR = tempfile.gettempdir()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download/<filename>')
def serve_video(filename):
    file_path = os.path.join(TEMP_DIR, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return "File not found or expired.", 404

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
        'wait': '10000' # Give the heavy JS page 10 full seconds to load
    }

    try:
        # 1. SCRAPE & CLEAN
        print(f"DEBUG: Processing URL: {sora_url}")
        response = requests.get('https://api.zenrows.com/v1/', params=params, timeout=60)
        
        # Unescape the HTML so regex can see through encoded characters
        raw_content = html.unescape(response.text).replace('\\/', '/')
        
        # Grab every single link starting with http
        all_links = re.findall(r'https?://[^\s"\'<>\[\]\{\}]+', raw_content)
        print(f"DEBUG: Scraped {len(all_links)} total links.")

        # 2. ULTRA-WIDE MEDIA FILTER
        secure_video_links = []
        media_keywords = ['oaiusercontent.com', 'videos.openai.com', 'cdn.openai.com', '.mp4', '.m3u8']
        junk_keywords = ['thumbnail', 'poster', '.jpg', '.jpeg', '.png', '.svg', '.woff', '.css', '.js', 'favicon']

        for link in all_links:
            # Deep cleaning the link formatting
            link_clean = link.replace('\\u0026', '&').replace('&amp;', '&').strip("\\'\"")
            l_low = link_clean.lower()
            
            # If it's from an OpenAI media domain and NOT an image or junk file
            if any(k in l_low for k in media_keywords):
                if not any(j in l_low for j in junk_keywords):
                    # We want the long links with security tokens
                    if len(link_clean) > 50:
                        secure_video_links.append(link_clean)

        if not secure_video_links:
            # LOG REPORTER: If we fail, show the first few links found to help us debug
            print(f"DEBUG ERROR: No video links found. Sample of detected links: {all_links[:5]}")
            return jsonify({"error": "Video link hidden."}), 404

        # The longest link is almost always the one with the full security signature
        best_link = max(secure_video_links, key=len)
        print(f"DEBUG: Targeted Link found!")

        # 3. RESOLUTION DETECTION
        ffmpeg_exe = "ffmpeg"
        probe = subprocess.run([
            "ffprobe", "-user_agent", "Mozilla/5.0", "-i", best_link
        ], stderr=subprocess.PIPE, text=True)
        
        res_match = re.search(r'Video:.*?\s(\d+)x(\d+)', probe.stderr)
        V_W, V_H = (int(res_match.group(1)), int(res_match.group(2))) if res_match else (1080, 1920)
        print(f"DEBUG: Video size is {V_W}x{V_H}")

        # 4. DYNAMIC BOX & SAFETY CLAMP
        box_w = int(V_W * 0.35)
        box_h = int(V_H * 0.10)

        def clamp_x(val): return max(0, min(val, V_W - box_w - 5))
        def clamp_y(val): return max(0, min(val, V_H - box_h - 5))

        coords = {
            "bl": (clamp_x(int(V_W * 0.05)), clamp_y(int(V_H * 0.85))), 
            "mr": (clamp_x(int(V_W * 0.65)), clamp_y(int(V_H * 0.45))), 
            "tl": (clamp_x(int(V_W * 0.05)), clamp_y(int(V_H * 0.05))), 
            "br": (clamp_x(int(V_W * 0.65)), clamp_y(int(V_H * 0.85)))  
        }

        filter_complex = (
            f"[0:v]delogo=x={coords['bl'][0]}:y={coords['bl'][1]}:w={box_w}:h={box_h}:enable='between(t,0,4)'[v1];"
            f"[v1]delogo=x={coords['mr'][0]}:y={coords['mr'][1]}:w={box_w}:h={box_h}:enable='between(t,4,8)'[v2];"
            f"[v2]delogo=x={coords['tl'][0]}:y={coords['tl'][1]}:w={box_w}:h={box_h}:enable='between(t,8,12)'[v3];"
            f"[v3]delogo=x={coords['br'][0]}:y={coords['br'][1]}:w={box_w}:h={box_h}:enable='between(t,12,15)'"
        )

        # 5. EXECUTE FFMPEG
        clean_filename = f"clean_{uuid.uuid4().hex}.mp4"
        clean_path = os.path.join(TEMP_DIR, clean_filename)
        
        command = [
            ffmpeg_exe, "-y", "-user_agent", "Mozilla/5.0", "-i", best_link,
            "-filter_complex", filter_complex, "-c:a", "copy", "-preset", "ultrafast", clean_path
        ]

        print("DEBUG: Processing video watermark blurs...")
        subprocess.run(command, check=True)

        return jsonify({"status": "success", "download_url": f"/download/{clean_filename}"})

    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        return jsonify({"error": f"Process Failed: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
