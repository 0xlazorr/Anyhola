from enum import Enum
import ipaddress
import os
import re
from urllib.parse import urlparse
from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
from yt_dlp.utils import DownloadError

app = Flask(__name__)
CORS(app)


# =====================================================================
# Extraction Finite State Machine
# =====================================================================

class ExtractionState(Enum):
    RECEIVED = "RECEIVED"
    VALIDATING_URL = "VALIDATING_URL"
    EXTRACTING_METADATA = "EXTRACTING_METADATA"
    PARSING_FORMATS = "PARSING_FORMATS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ExtractionFSM:
    """Explicit FSM governing the video metadata extraction lifecycle."""

    _VALID_TRANSITIONS = {
        ExtractionState.RECEIVED: {ExtractionState.VALIDATING_URL, ExtractionState.FAILED},
        ExtractionState.VALIDATING_URL: {ExtractionState.EXTRACTING_METADATA, ExtractionState.FAILED},
        ExtractionState.EXTRACTING_METADATA: {ExtractionState.PARSING_FORMATS, ExtractionState.FAILED},
        ExtractionState.PARSING_FORMATS: {ExtractionState.COMPLETED, ExtractionState.FAILED},
        ExtractionState.COMPLETED: set(),
        ExtractionState.FAILED: set(),
    }

    def __init__(self):
        self.state = ExtractionState.RECEIVED

    def transition_to(self, next_state: ExtractionState):
        allowed = self._VALID_TRANSITIONS.get(self.state, set())
        if next_state not in allowed:
            raise ValueError(f"Illegal transition from {self.state.value} to {next_state.value}")
        self.state = next_state


# =====================================================================
# SSRF & URL Validation
# =====================================================================

def is_safe_url(url: str) -> bool:
    """Validate URL scheme and ensure no access to private, loopback, or metadata addresses."""
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Reject loopback, link-local, and cloud metadata
        if hostname.lower() in ("localhost", "127.0.0.1", "::1", "169.254.169.254", "metadata.google.internal"):
            return False

        # If IP address provided directly, check against private IP ranges
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        except ValueError:
            # Domain name, allowed
            pass

        return True
    except Exception:
        return False


@app.route("/api/download", methods=["POST"])
def download_video():
    fsm = ExtractionFSM()
    data = request.get_json(silent=True)
    if not data:
        fsm.transition_to(ExtractionState.FAILED)
        return jsonify({"error": "Invalid JSON body"}), 400

    video_url = data.get("videoUrl")
    if not video_url:
        fsm.transition_to(ExtractionState.FAILED)
        return jsonify({"error": "Video URL is required"}), 400

    fsm.transition_to(ExtractionState.VALIDATING_URL)
    if not is_safe_url(video_url):
        fsm.transition_to(ExtractionState.FAILED)
        return jsonify({"error": "Invalid or disallowed URL scheme/host"}), 400

    try:
        fsm.transition_to(ExtractionState.EXTRACTING_METADATA)
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "extract_flat": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if not info:
                fsm.transition_to(ExtractionState.FAILED)
                return jsonify({"error": "Could not extract video metadata"}), 404

            fsm.transition_to(ExtractionState.PARSING_FORMATS)

            # Playlist handling
            if "entries" in info and info["entries"]:
                video_list = []
                for entry in info["entries"]:
                    if entry:
                        video_list.append({
                            "title": entry.get("title"),
                            "url": entry.get("url"),
                            "thumbnail": entry.get("thumbnail"),
                            "duration": entry.get("duration"),
                        })

                response_data = {
                    "is_playlist": True,
                    "playlist_title": info.get("title"),
                    "source": info.get("extractor_key", "N/A"),
                    "videos": video_list,
                }
                fsm.transition_to(ExtractionState.COMPLETED)
                return jsonify(response_data)

            # Single video handling
            ydl_opts_single = {
                "quiet": True,
                "no_warnings": True,
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "noplaylist": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts_single) as ydl_single:
                single_info = ydl_single.extract_info(video_url, download=False)
                formats_to_send = []
                if single_info and "formats" in single_info:
                    for f in single_info["formats"]:
                        if f.get("url") and f.get("filesize"):
                            formats_to_send.append({
                                "format_id": f.get("format_id"),
                                "ext": f.get("ext"),
                                "resolution": f.get("resolution"),
                                "url": f.get("url"),
                                "filesize": f.get("filesize"),
                                "format_note": f.get("format_note"),
                            })

                if not formats_to_send:
                    fsm.transition_to(ExtractionState.FAILED)
                    return jsonify({"error": "No downloadable formats found for this media"}), 404

                response_data = {
                    "is_playlist": False,
                    "title": single_info.get("title", "No title"),
                    "thumbnail": single_info.get("thumbnail"),
                    "source": single_info.get("extractor_key", "N/A"),
                    "formats": formats_to_send,
                }
                fsm.transition_to(ExtractionState.COMPLETED)
                return jsonify(response_data)

    except DownloadError as e:
        fsm.transition_to(ExtractionState.FAILED)
        return jsonify({"error": "Media unavailable (private, region-locked, or unsupported site)"}), 502

    except Exception:
        fsm.transition_to(ExtractionState.FAILED)
        return jsonify({"error": "An internal error occurred during extraction"}), 500


if __name__ == "__main__":
    is_debug = os.getenv("FLASK_DEBUG", "0").lower() in ("1", "true")
    app.run(debug=is_debug, port=5000)
