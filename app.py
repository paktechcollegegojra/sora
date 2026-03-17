import os
import requests
import re
import tempfile
import uuid
import subprocess
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
        'wait': '8000'
    }

    try:
        # 1. SCRAPE THE LINKS
        response = requests.get('https://api.zenrows.com/v1/', params=params, timeout=60)
        clean_html = response.text.replace('\\/', '/').replace('\\u0026', '&')
        all_links = re.findall(r'(https?://[^\s"\'<>\[\]\{\}]+)', clean_html)
        
        # 2. BULLETPROOF VIDEO FILTER
        secure_video_links = []
        for link in all_links:
            if ('sig=' in link and 'se=' in link) or '.mp4' in link or '.m3u8' in link:
                if 'thumbnail' not in link.lower() and 'poster' not in link.lower() and '.jpg' not in link.lower() and '.png' not in link.lower():
                    secure_video_links.append(link)

        if not secure_video_links:
            return jsonify({"error": "Bypassed successfully, but the video link was totally hidden."}), 404

        best_link = max(secure_video_links, key=len)

        # 3. DIRECT STREAM TO FFMPEG (Fixes the moov atom text file crash!)
        clean_filename = f"clean_{uuid.uuid4().hex}.mp4"
        clean_path = os.path.join(TEMP_DIR, clean_filename)

        ffmpeg_exe = "ffmpeg"
        
        # Probe the URL directly for dimensions
        print("DEBUG: Probing video resolution directly from URL...")
        probe = subprocess.run(["ffprobe", "-i", best_link], stderr=subprocess.PIPE, text=True)
        res_match = re.search(r'Video:.*?\s(\d+)x(\d+)', probe.stderr)

        if res_match:
            V_W, V_H = int(res_match.group(1)), int(res_match.group(2))
            print(f"DEBUG: Resolution detected as {V_W}x{V_H}")
        else:
            V_W, V_H = 1080, 1920 
            print("DEBUG: Resolution scan failed, defaulting to 1080x1920")

        box_w = int(V_W * 0.30)
        box_h = int(V_H * 0.08)

        # The Coordinates Map
        bl_x, bl_y = int(V_W * 0.05), int(V_H * 0.88)
        mr_x, mr_y = int(V_W * 0.65), int(V_H * 0.45)
        tl_x, tl_y = int(V_W * 0.05), int(V_H * 0.05)
        br_x, br_y = int(V_W * 0.65), int(V_H * 0.88)

        mr_x = min(mr_x, V_W - box_w - 2)
        br_x = min(br_x, V_W - box_w - 2)

        filter_complex = (
            f"[0:v]delogo=x={bl_x}:y={bl_y}:w={box_w}:h={box_h}:enable='between(t,0,4)'[v1];"
            f"[v1]delogo=x={mr_x}:y={mr_y}:w={box_w}:h={box_h}:enable='between(t,4,8)'[v2];"
            f"[v2]delogo=x={tl_x}:y={tl_y}:w={box_w}:h={box_h}:enable='between(t,8,12)'[v3];"
            f"[v3]delogo=x={br_x}:y={br_y}:w={box_w}:h={box_h}:enable='between(t,12,15)'"
        )

        # We pass 'best_link' directly as the input (-i)
        command = [
            ffmpeg_exe, "-y", "-i", best_link,
            "-filter_complex", filter_complex,
            "-c:a", "copy",
            "-preset", "ultrafast",
            clean_path
        ]

        print("DEBUG: Streaming and applying dynamic blur via FFmpeg...")
        subprocess.run(command, check=True)

        # 4. SEND TO USER
        return jsonify({"status": "success", "download_url": f"/download/{clean_filename}"})

    except subprocess.CalledProcessError as e:
        return jsonify({"error": "FFmpeg Engine Failed. The video link might be dead or heavily encrypted."}), 500
    except Exception as e:
        return jsonify({"error": f"Server Error: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
