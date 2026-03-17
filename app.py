import os
import time
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from seleniumbase import SB

app = Flask(__name__)
CORS(app)

# Create a folder to store the downloaded videos
DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

@app.route('/')
def index():
    # This looks for index.html inside the /templates folder
    return render_template('index.html')

@app.route('/api/process', methods=['POST'])
def process_video():
    data = request.json
    sora_url = data.get('url')
    
    if not sora_url:
        return jsonify({"error": "No URL provided"}), 400

    # STEP 1: BYPASS CLOUDFLARE
    video_src = ""
    try:
        # Using UC Mode to bypass Sora's security
        with SB(uc=True, headless=True) as sb:
            sb.activate_cdp_mode(sora_url)
            sb.sleep(5) 
            # Look for the video tag and grab the source link
            video_src = sb.get_attribute("video", "src", timeout=20)
    except Exception as e:
        return jsonify({"error": "Could not bypass Sora security. Please try again."}), 403

    # STEP 2: SIMULATE AI LOGO REMOVAL
    # Real AI inpainting requires a GPU. For now, we simulate the processing time.
    time.sleep(5) 
    
    return jsonify({
        "status": "success",
        "download_url": video_src  # In this version, we provide the direct Sora link
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)