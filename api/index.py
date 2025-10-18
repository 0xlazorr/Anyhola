# -----------------------------------------------------------------------------
# IMPORTING NECESSARY LIBRARIES
# -----------------------------------------------------------------------------

from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp

# -----------------------------------------------------------------------------
# INITIALIZING THE FLASK APPLICATION
# -----------------------------------------------------------------------------

app = Flask(__name__)

# -----------------------------------------------------------------------------
# CONFIGURE CORS
# -----------------------------------------------------------------------------

CORS(app)

# -----------------------------------------------------------------------------
# DEFINE THE API ENDPOINT
# -----------------------------------------------------------------------------

@app.route('/api/download', methods=['POST'])
def download_video():
    # --- 4a. Get the data from the frontend ---
    # `request.get_json()` parses the incoming JSON request body into a Python dictionary.
    # The frontend sends a body like: {"videoUrl": "https://..."}
    data = request.get_json()
    # We extract the value associated with the key 'videoUrl'.
    video_url = data.get('videoUrl')

    # --- Validate the input ---
    if not video_url:
        return jsonify({'error': 'Video URL is required'}), 400

    # --- Process the URL with yt-dlp ---
    
    try:
        ydl_opts = {
            'quiet': True,        # Suppresses yt-dlp's own console output.
            'no_warnings': True,  # Hides warnings.
            'forcejson': True,    # Forces the output to be a single JSON line.
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            
            info = ydl.extract_info(video_url, download=False)
            
            # --- Prepare the response for the frontend ---
            formats_to_send = []
            if 'formats' in info:
                for f in info['formats']:
                    if f.get('url') and (f.get('resolution') or 'audio' in f.get('format_note', '')):
                        formats_to_send.append({
                            'format_id': f.get('format_id'),
                            'ext': f.get('ext'),
                            'resolution': f.get('resolution'),
                            'url': f.get('url'),
                            'filesize': f.get('filesize'),
                            'format_note': f.get('format_note'),
                        })
            
            # Structure the final JSON response that the frontend will receive.
            response_data = {
                'title': info.get('title'),
                'thumbnail': info.get('thumbnail'),
                'source': info.get('extractor_key'), # e.g., 'youtube', 'twitter', 'tiktok', 'instagram'.
                'formats': formats_to_send
            }
            return jsonify(response_data)

    except Exception as e:
        
        print(f"An error occurred: {e}")
        return jsonify({'error': 'Failed to fetch video information. The URL might be invalid or private.'}), 500

# -----------------------------------------------------------------------------
# THE FLASK SERVER
# -----------------------------------------------------------------------------

if __name__ == '__main__':
   
    app.run(debug=True)

