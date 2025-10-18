from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp

# Vercel knows how to run this 'app' object
app = Flask(__name__)
CORS(app)

@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.get_json()
    video_url = data.get('videoUrl')

    if not video_url:
        return jsonify({'error': 'Video URL is required'}), 400

    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            formats_to_send = []
            if 'formats' in info:
                for f in info['formats']:
                    # Filter for useful formats with direct URLs
                    if f.get('url') and (f.get('vcodec') != 'none' or f.get('acodec') != 'none'):
                        formats_to_send.append({
                            'format_id': f.get('format_id'),
                            'ext': f.get('ext'),
                            'resolution': f.get('resolution'),
                            'url': f.get('url'),
                            'filesize': f.get('filesize'),
                            'format_note': f.get('format_note'),
                        })
            
            response_data = {
                'title': info.get('title', 'No title'),
                'thumbnail': info.get('thumbnail'),
                'source': info.get('extractor_key', 'N/A'),
                'formats': formats_to_send
            }
            return jsonify(response_data)

    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({'error': 'Failed to fetch video information. The URL might be invalid, private, or unsupported.'}), 500

# This part is for local development only
if __name__ == '__main__':
    app.run(debug=True, port=5000)