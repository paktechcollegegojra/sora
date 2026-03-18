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
        # 1. SCRAPE & CLEAN
        response = requests.get('https://api.zenrows.com/v1/', params=params, timeout=60)
        clean_html = response.text.replace('\\/', '/')
        all_links = re.findall(r'(https?://[^\s"\'<>\[\]\{\}]+)', clean_html)
        
        secure_video_links = [l for l in all_links if ('sig=' in l and 'se=' in l) or '.mp4' in l or '.m3u8' in l]
        secure_video_links = [l for l in secure_video_links if 'thumbnail' not in l.lower() and '.jpg' not in l.lower()]

        if not secure_video_links:
            return jsonify({"error": "Video link hidden."}), 404

        best_link = html.unescape(max(secure_video_links, key=len))
        while "&amp;" in best_link or "\\u0026" in best_link:
            best_link = best_link.replace("\\u0026", "&").replace("&amp;", "&")
        best_link = best_link.strip("\\'\"<>[]{}()")

        # 2. RESOLUTION DETECTION
        ffmpeg_exe = "ffmpeg"
        probe = subprocess.run([
            "ffprobe", "-user_agent", "Mozilla/5.0", "-i", best_link
        ], stderr=subprocess.PIPE, text=True)
        
        res_match = re.search(r'Video:.*?\s(\d+)x(\d+)', probe.stderr)
        V_W, V_H = (int(res_match.group(1)), int(res_match.group(2))) if res_match else (1080, 1920)

        # 3. DYNAMIC BOX & SAFETY CLAMP
        box_w = int(V_W * 0.35)
        box_h = int(V_H * 0.10)

        def clamp_x(val): return max(0, min(val, V_W - box_w - 5))
        def clamp_y(val): return max(0, min(val, V_H - box_h - 5))

        # Calculate Coordinates
        coords = {
            "bl": (clamp_x(int(V_W * 0.05)), clamp_y(int(V_H * 0.85))), # 0-4s
            "mr": (clamp_x(int(V_W * 0.60)), clamp_y(int(V_H * 0.45))), # 4-8s
            "tl": (clamp_x(int(V_W * 0.05)), clamp_y(int(V_H * 0.05))), # 8-12s
            "br": (clamp_x(int(V_W * 0.60)), clamp_y(int(V_H * 0.85)))  # 12-15s
        }

        filter_complex = (
            f"[0:v]delogo=x={coords['bl'][0]}:y={coords['bl'][1]}:w={box_w}:h={box_h}:enable='between(t,0,4)'[v1];"
            f"[v1]delogo=x={coords['mr'][0]}:y={coords['mr'][1]}:w={box_w}:h={box_h}:enable='between(t,4,8)'[v2];"
            f"[v2]delogo=x={coords['tl'][0]}:y={coords['tl'][1]}:w={box_w}:h={box_h}:enable='between(t,8,12)'[v3];"
            f"[v3]delogo=x={coords['br'][0]}:y={coords['br'][1]}:w={box_w}:h={box_h}:enable='between(t,12,15)'"
        )

        # 4. EXECUTE
        clean_filename = f"clean_{uuid.uuid4().hex}.mp4"
        clean_path = os.path.join(TEMP_DIR, clean_filename)
        
        command = [
            ffmpeg_exe, "-y", "-user_agent", "Mozilla/5.0", "-i", best_link,
            "-filter_complex", filter_complex, "-c:a", "copy", "-preset", "ultrafast", clean_path
        ]

        subprocess.run(command, check=True)
        return jsonify({"status": "success", "download_url": f"/download/{clean_filename}"})

    except Exception as e:
        return jsonify({"error": f"Process Failed: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
