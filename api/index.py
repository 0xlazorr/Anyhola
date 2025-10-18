from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
from yt_dlp.utils import DownloadError

app = Flask(__name__)
CORS(app)


@app.route("/api/download", methods=["POST"])
def download_video():
    data = request.get_json()
    video_url = data.get("videoUrl")

    if not video_url:
        return jsonify({"error": "Video URL is required"}), 400

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "extract_flat": True,  # This is fast for checking playlists
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info. 'extract_flat': True makes this very fast for playlists.
            info = ydl.extract_info(video_url, download=False)

            # --- PLAYLIST LOGIC ---
            # Check if it's a playlist by looking for the 'entries' key
            if "entries" in info:
                video_list = []
                for entry in info["entries"]:
                    video_list.append(
                        {
                            "title": entry.get("title"),
                            "url": entry.get(
                                "url"
                            ),  # This is the URL to the video's page
                            "thumbnail": entry.get("thumbnail"),
                            "duration": entry.get("duration"),
                        }
                    )

                response_data = {
                    "is_playlist": True,
                    "playlist_title": info.get("title"),
                    "source": info.get("extractor_key", "N/A"),
                    "videos": video_list,
                }
                return jsonify(response_data)

            # --- SINGLE VIDEO LOGIC ---

            ydl_opts_single = {
                "quiet": True,
                "no_warnings": True,
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "noplaylist": True,  # Ensure we only get one video
            }

            with yt_dlp.YoutubeDL(ydl_opts_single) as ydl_single:
                info = ydl_single.extract_info(video_url, download=False)

                formats_to_send = []
                if "formats" in info:
                    for f in info["formats"]:
                        # Use a reliable filter for actual downloadable files
                        if f.get("url") and f.get("filesize"):
                            formats_to_send.append(
                                {
                                    "format_id": f.get("format_id"),
                                    "ext": f.get("ext"),
                                    "resolution": f.get("resolution"),
                                    "url": f.get("url"),
                                    "filesize": f.get("filesize"),
                                    "format_note": f.get("format_note"),
                                }
                            )

                if not formats_to_send:
                    return (
                        jsonify(
                            {
                                "error": "No downloadable formats could be found for this video."
                            }
                        ),
                        500,
                    )

                response_data = {
                    "is_playlist": False,
                    "title": info.get("title", "No title"),
                    "thumbnail": info.get("thumbnail"),
                    "source": info.get("extractor_key", "N/A"),
                    "formats": formats_to_send,
                }
                return jsonify(response_data)

    except DownloadError as e:
        # Generic error for any download failure
        print(f"yt-dlp download error: {e}")
        return (
            jsonify(
                {
                    "error": "This video/playlist is unavailable. It may be private, region-locked, or from an unsupported site."
                }
            ),
            500,
        )

    except Exception as e:
        # Catch-all for any other server errors
        print(f"An unexpected error occurred: {e}")
        return (
            jsonify(
                {"error": "An unexpected server error occurred. Please try again."}
            ),
            500,
        )


# This part is for local development only
if __name__ == "__main__":
    app.run(debug=True, port=5000)
