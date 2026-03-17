import os
import requests
import re
import tempfile
import uuid
import subprocess
import imageio_ffmpeg
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Your ZenRows Key
ZENROWS_API_KEY = "97a3341face7698dd0dccb24b16e385f0d826033"

# Setup a temporary folder on the Render server to hold the videos
TEMP_DIR = tempfile.gettempdir()

@app.route('/')
def index():
    return render_template('index.html')

# ROUTE: Serves the cleaned file to the user
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
        # 1. BYPASS CLOUDFLARE & SCRAPE
        response = requests.get('https://api.zenrows.com/v1/', params=params, timeout=60)
        clean_html = response.text.replace('\\/', '/').replace('\\u0026', '&')
        all_links = re.findall(r'(https?://[^\s"\'<>\[\]\{\}]+)', clean_html)
        
        # 2. ISOLATE THE SECURE AZURE LINK
        secure_video_links = []
        for link in all_links:
            if 'sig=' in link and 'se=' in link:
                if 'thumbnail' not in link.lower() and 'poster' not in link.lower() and '.jpg' not in link.lower() and '.png' not in link.lower():
                    secure_video_links.append(link)

        if not secure_video_links:
            return jsonify({"error": "Bypassed successfully, but couldn't find the secure video stream."}), 404

        best_link = max(secure_video_links, key=len)

        # 3. DOWNLOAD THE RAW VIDEO TO THE SERVER
        raw_filename = f"raw_{uuid.uuid4().hex}.mp4"
        clean_filename = f"clean_{uuid.uuid4().hex}.mp4"
        raw_path = os.path.join(TEMP_DIR, raw_filename)
        clean_path = os.path.join(TEMP_DIR, clean_filename)

        print("DEBUG: Downloading raw video from Azure...")
        vid_req = requests.get(best_link, stream=True)
        with open(raw_path, 'wb') as f:
            for chunk in vid_req.iter_content(chunk_size=8192):
                f.write(chunk)

        # 4. THE DYNAMIC BLUR (Advanced FFmpeg Filter)
        print("DEBUG: Applying dynamic blur to moving watermark...")
        
        # Get the FFmpeg engine path
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        # Box dimensions for the blur (Width=300px, Height=100px)
        w, h = 300, 100 

        # The Timeline Map: Moves the blur box based on the video's seconds (t)
        # These X and Y coordinates are estimated for a 1080x1920 video
        filter_complex = (
            f"[0:v]delogo=x=40:y=1750:w={w}:h={h}:enable='between(t,0,4)'[v1];"      # Bottom Left (0-4s)
            f"[v1]delogo=x=740:y=900:w={w}:h={h}:enable='between(t,4,8)'[v2];"       # Middle Right (4-8s)
            f"[v2]delogo=x=40:y=40:w={w}:h={h}:enable='between(t,8,12)'[v3];"        # Top Left (8-12s)
            f"[v3]delogo=x=740:y=1750:w={w}:h={h}:enable='between(t,12,15)'"         # Bottom Right (12-15s)
        )

        # Build the exact command for the engine
        command = [
            ffmpeg_exe, "-y", "-i", raw_path,
            "-filter_complex", filter_complex,
            "-c:a", "copy",          # Copy audio instantly to save CPU
            "-preset", "ultrafast",  # Force the server to work quickly
            clean_path
        ]

        # Fire the engine!
        subprocess.run(command, check=True)
        
        # Delete the raw video to save hard drive space
        os.remove(raw_path) 

        # 5. GIVE THE USER THE CLEAN LINK
        final_download_url = f"/download/{clean_filename}"
        
        return jsonify({"status": "success", "download_url": final_download_url})

    except subprocess.CalledProcessError as e:
        print(f"FFMPEG ERROR: {str(e)}")
        return jsonify({"error": "Failed to process the video watermark. Check Render logs."}), 500
    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        return jsonify({"error": f"Server Error: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
