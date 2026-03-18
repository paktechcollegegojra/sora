import os
import requests
import re
import tempfile
import uuid
import subprocess
import html
import sys
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

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
        'wait': '10000'
    }

    try:
        print(f"--- STARTING PROCESS FOR: {sora_url} ---", flush=True)
        response = requests.get('https://api.zenrows.com/v1/', params=params, timeout=60)
        
        # 1. CLEAN THE CODE
        # We unescape twice to catch double-encoded OpenAI URLs
        raw_content = html.unescape(html.unescape(response.text)).replace('\\/', '/')
        
        # 2. THE AGGRESSIVE SEARCH
        # We look for ANY link that contains "oaiusercontent" or "openai" and looks like a media file
        links = re.findall(r'https?://[^\s"\'<>\[\]\{\}]+', raw_content)
        print(f"DEBUG: Found {len(links)} total links on page.", flush=True)

        secure_video_links = []
        for l in links:
            l_clean = l.replace('\\u0026', '&').replace('&amp;', '&').strip("\\'\"")
            l_low = l_clean.lower()
            
            # OpenAI storage keywords
            if 'oaiusercontent' in l_low or 'videos.openai' in l_low:
                # Exclude images and thumbnails
                if not any(x in l_low for x in ['.jpg', '.jpeg', '.png', '.webp', 'thumbnail', 'poster']):
                    secure_video_links.append(l_clean)

        if not secure_video_links:
            print("DEBUG ERROR: No video links found. Printing page sample...", flush=True)
            print(f"PAGE PREVIEW: {raw_content[:500]}", flush=True)
            return jsonify({"error": "Video link hidden. OpenAI updated their security."}), 404

        # Grab the longest link (usually the one with the security signature)
        best_link = max(secure_video_links, key=len)
        print(f"DEBUG: Success! Target found: {best_link[:80]}...", flush=True)

        # 3. VIDEO PROCESSING (FFmpeg)
        ffmpeg_exe = "ffmpeg"
        probe = subprocess.run([
            "ffprobe", "-user_agent", "Mozilla/5.0", "-i", best_link
        ], stderr=subprocess.PIPE, text=True)
        
        res_match = re.search(r'Video:.*?\s(\d+)x(\d+)', probe.stderr)
        V_W, V_H = (int(res_match.group(1)), int(res_match.group(2))) if res_match else (1080, 1920)

        # Dynamic Coordinates & Safety Clamp
        box_w, box_h = int(V_W * 0.35), int(V_H * 0.10)
        def clamp_x(val): return max(0, min(val, V_W - box_w - 5))
        def clamp_y(val): return max(0, min(val, V_H - box_h - 5))

        c = {
            "bl": (clamp_x(int(V_W * 0.05)), clamp_y(int(V_H * 0.85))), 
            "mr": (clamp_x(int(V_W * 0.65)), clamp_y(int(V_H * 0.45))), 
            "tl": (clamp_x(int(V_W * 0.05)), clamp_y(int(V_H * 0.05))), 
            "br": (clamp_x(int(V_W * 0.65)), clamp_y(int(V_H * 0.85)))  
        }

        filter_complex = (
            f"[0:v]delogo=x={c['bl'][0]}:y={c['bl'][1]}:w={box_w}:h={box_h}:enable='between(t,0,4)'[v1];"
            f"[v1]delogo=x={c['mr'][0]}:y={c['mr'][1]}:w={box_w}:h={box_h}:enable='between(t,4,8)'[v2];"
            f"[v2]delogo=x={c['tl'][0]}:y={c['tl'][1]}:w={box_w}:h={box_h}:enable='between(t,8,12)'[v3];"
            f"[v3]delogo=x={c['br'][0]}:y={c['br'][1]}:w={box_w}:h={box_h}:enable='between(t,12,15)'"
        )

        clean_filename = f"clean_{uuid.uuid4().hex}.mp4"
        clean_path = os.path.join(TEMP_DIR, clean_filename)
        
        command = [
            ffmpeg_exe, "-y", "-user_agent", "Mozilla/5.0", "-i", best_link,
            "-filter_complex", filter_complex, "-c:a", "copy", "-preset", "ultrafast", clean_path
        ]

        print("DEBUG: Applying Watermark Blurs...", flush=True)
        subprocess.run(command, check=True)

        return jsonify({"status": "success", "download_url": f"/download/{clean_filename}"})

    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}", flush=True)
        return jsonify({"error": f"Server error. See logs for details."}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
