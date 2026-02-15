"""Silent Disco - Integrated application with web UI.

Run with UI (default):    python app_integrated.py
Run without UI:           python app_integrated.py --no-ui
"""

import os
import sys
import time
import threading
import argparse
from datetime import datetime
from flask import Flask, jsonify

import config
from models.snippet import Snippet
from services.spotify_service import SpotifyService
from services.recognition_service import RecognitionService
from utils.logging_config import LogCollector
from utils.validators import (
    validate_duration,
    validate_interval,
    validate_directory_path,
    ValidationError
)


class SilentDiscoApp:
    """Main Silent Disco application controller."""

    def __init__(self,
                 snippet_duration=10,
                 interval_duration=60,
                 output_folder='song_snippets',
                 enable_ui=False,
                 ui_port=5002):
        """Initialize the Silent Disco app.

        Args:
            snippet_duration: Length of audio snippets in seconds
            interval_duration: Time between snippets in seconds
            output_folder: Directory to store audio snippets
            enable_ui: Whether to start the web UI
            ui_port: Port for web UI
        """
        self.snippet_duration = snippet_duration
        self.interval_duration = interval_duration
        self.output_folder = output_folder
        self.enable_ui = enable_ui
        self.ui_port = ui_port

        # State
        self.is_running = False
        self.is_paused = False
        self.retry_now = False  # Flag to interrupt sleep and retry immediately
        self.retry_queued = False  # Flag to queue a retry for after current recording
        self._stop_event = threading.Event()  # Event to interrupt recording
        self.current_snippet = None
        self.queue = []
        self.snippet_history = []
        self._last_track_time = 0  # Timestamp of last recognized track
        self._track_persist_seconds = 300  # 5 minutes

        # Logging
        self.log_collector = LogCollector()

        # Services (initialized in start())
        self.spotify_service = None
        self.recognition_service = None

        # Web server components
        self.web_server = None
        self.web_thread = None

    def initialize_services(self):
        """Initialize Spotify and Recognition services."""
        self.log_collector.info("Initializing Spotify and Recognition services")

        # Create Spotify service
        self.spotify_service = SpotifyService(
            client_id=config.spotify_config.client_id,
            client_secret=config.spotify_config.client_secret,
            redirect_uri='https://github.com/kennygrosz/silent-disco',
            scope='user-modify-playback-state user-read-playback-state'
        )

        # Create Recognition service
        self.recognition_service = RecognitionService()

        self.log_collector.info("Services initialized successfully")

    def start_web_server(self):
        """Start the web UI in a background thread."""
        if not self.enable_ui:
            return

        try:
            # Import web server components
            from web_server import app as web_app, socketio, app_state, audio_streamer, set_app_controller

            self.web_server = (web_app, socketio, app_state, audio_streamer)
            self.log_collector.info(f"Starting web UI on port {self.ui_port}")

            # Set app controller reference for control endpoints
            set_app_controller(self)

            # Start audio streaming
            audio_streamer.start()

            # Run web server in background thread
            def run_server():
                socketio.run(
                    web_app,
                    host='0.0.0.0',
                    port=self.ui_port,
                    debug=False,
                    allow_unsafe_werkzeug=True
                )

            self.web_thread = threading.Thread(target=run_server, daemon=True)
            self.web_thread.start()

            self.log_collector.info(f"Web UI started at http://localhost:{self.ui_port}")
            print(f"\n🎵 Web UI available at http://localhost:{self.ui_port}\n")

        except Exception as e:
            self.log_collector.error(f"Failed to start web UI: {e}")
            print(f"Warning: Could not start web UI: {e}")

    def update_ui_track(self, snippet, blocked=False):
        """Update the web UI with current track info.

        Args:
            snippet: Snippet object or None to clear
            blocked: If True, song was recognized but Spotify playback was blocked
        """
        if not self.enable_ui or not self.web_server:
            return

        try:
            from web_server import update_current_track

            if snippet is None:
                # Clear current track
                update_current_track(None)
            else:
                # Get album art URL from Spotify if available
                album_art_url = None
                if hasattr(snippet, 'album_art_url') and snippet.album_art_url:
                    album_art_url = snippet.album_art_url

                track_data = {
                    'name': snippet.song_name or snippet.track_string or 'Unknown',
                    'artist': snippet.song_artist or 'Unknown Artist',
                    'album_art_url': album_art_url,
                    'mood': self._get_mood_from_track(snippet),
                    'blocked': blocked,
                    'played_on_spotify': not blocked
                }
                update_current_track(track_data)
                self._last_track_time = time.time()
        except Exception as e:
            self.log_collector.error(f"Failed to update UI track: {e}")

    def update_ui_status(self, is_listening=None, next_recording_in=None):
        """Update the web UI status."""
        # Track current state for retry gating
        if isinstance(is_listening, str):
            self._current_state = is_listening

        if not self.enable_ui or not self.web_server:
            return

        try:
            from web_server import update_status
            update_status(is_listening=is_listening, next_recording_in=next_recording_in)
        except Exception as e:
            self.log_collector.error(f"Failed to update UI status: {e}")

    def _get_mood_from_track(self, snippet):
        """Determine mood from track (placeholder for now)."""
        # TODO: Implement mood detection based on Spotify audio features
        return 'energetic'  # Default mood

    def _cleanup_snippet_file(self, filepath):
        """Delete a snippet WAV file after processing."""
        try:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
                self.log_collector.info(f"Deleted snippet file: {filepath}")
        except Exception as e:
            self.log_collector.error(f"Failed to delete snippet: {e}")

    def process_snippet(self):
        """Process a single audio snippet."""
        valid_snippet = True

        # 0. Initialize snippet
        snip = Snippet(output_folder=self.output_folder, snippet_duration=self.snippet_duration)
        self.current_snippet = snip
        self.log_collector.info(f"Initialized Snippet at: {snip.filepath_str}")

        # 1. Record audio
        self.log_collector.info(f"Recording snippet: {snip.filename}")
        self.update_ui_status(is_listening='recording')  # Update to recording state

        # Pause audio streamer to avoid PyAudio conflict on macOS
        if self.enable_ui and self.web_server:
            try:
                from web_server import audio_streamer
                audio_streamer.stop()
                self.log_collector.info("Audio streamer paused for recording")
            except Exception as e:
                self.log_collector.error(f"Failed to pause audio streamer: {e}")

        try:
            from listener.listener import record_audio
            status = record_audio(snip.filepath_str, snip.snippet_duration, stop_event=self._stop_event)
            if self._stop_event.is_set():
                self.log_collector.info("Recording was interrupted by stop")
                snip.mark_failed()
                return False
            snip.mark_recorded()
            self.log_collector.info(f"Recording completed: {status}")
        except Exception as e:
            self.log_collector.error(f"Recording failed: {e}")
            snip.mark_failed()
            self.update_ui_status(is_listening='waiting')  # Back to waiting
            return False
        finally:
            # Resume audio streamer after recording
            if self.enable_ui and self.web_server:
                try:
                    from web_server import audio_streamer
                    audio_streamer.start()
                    self.log_collector.info("Audio streamer resumed after recording")
                except Exception as e:
                    self.log_collector.error(f"Failed to resume audio streamer: {e}")

        # From here on, ensure snippet file is cleaned up when done
        try:
            return self._process_recorded_snippet(snip)
        finally:
            self._cleanup_snippet_file(snip.filepath_str)

    def _process_recorded_snippet(self, snip):
        """Process a recorded snippet (recognition, search, playback)."""
        # 2. Recognize with Shazam
        self.log_collector.info("Processing snippet with Shazam")
        self.update_ui_status(is_listening='processing')  # Update to processing state

        try:
            recognized_track = self.recognition_service.recognize(snip.filepath_str)

            if recognized_track is None:
                self.log_collector.info("Snippet unrecognizable")
                snip.mark_unrecognized()
                return False
            else:
                snip.mark_recognized(recognized_track.track_string)
                self.log_collector.info(f"Recognized: {snip.track_string}")
        except Exception as e:
            self.log_collector.error(f"Recognition failed: {e}")
            snip.mark_failed()
            return False

        # 3. Search on Spotify first (so we can show track info to the UI regardless)
        self.log_collector.info("Searching for song on Spotify")
        spotify_track = self.spotify_service.search_track(snip.track_string)

        if spotify_track:
            snip.set_spotify_info(
                song_id=spotify_track.id,
                song_uri=spotify_track.uri,
                song_name=spotify_track.name,
                song_artist=spotify_track.artist,
                duration_ms=spotify_track.duration_ms,
                album_art_url=spotify_track.album_art_url
            )
            self.log_collector.info(f"Found: {snip.song_name} - {snip.song_artist}")
        else:
            self.log_collector.info(f"Song not found on Spotify: {snip.track_string}")

        # 4. Check if interruption is allowed
        self.log_collector.info("Checking if interruption is permissible")
        interruption_allowed, message = self.spotify_service.is_interruption_allowed()
        self.log_collector.info(message)

        if not interruption_allowed:
            # Still show the recognized track on the UI, but indicate it can't play
            self.update_ui_track(snip, blocked=True)
            self.snippet_history.append(snip)
            return False

        # 5. Check if song is in recent queue
        last_5_songs = self.queue[-5:] if len(self.queue) >= 5 else self.queue
        if snip.track_string in last_5_songs:
            self.log_collector.info("Song in recent queue history, skipping")
            return False

        snip.mark_queueable()

        if not spotify_track:
            return False

        # 6. Get active device and play
        active_device_id, device_name = self.spotify_service.get_and_activate_device(
            preferred_name=config.app_config.preferred_device_name
        )

        if not active_device_id:
            self.log_collector.info("No Spotify devices available")
            self.update_ui_track(snip, blocked=True)
            return False

        self.log_collector.info(f"Playing on device: {device_name}")

        # Calculate position (last 31 seconds)
        position_ms = max(0, snip.duration_ms - config.app_config.playback_offset_ms)

        # Start playback (volume 0)
        playback_success = self.spotify_service.start_playback(
            track_uri=snip.song_uri,
            device_id=active_device_id,
            position_ms=position_ms,
            volume=0
        )

        if playback_success:
            self.queue.append(snip.track_string)
            self.snippet_history.append(snip)
            snip.mark_queued()
            self.log_collector.info("Successfully played and queued")

            # Update UI
            self.update_ui_track(snip)

            return True
        else:
            self.log_collector.error("Playback failed")
            self.update_ui_track(snip, blocked=True)
            return False

    def clear_current_track(self):
        """Clear the current track display."""
        self.update_ui_track(None)
        self._last_track_time = 0

    def maybe_clear_track(self):
        """Clear track display only if it's been shown for more than 5 minutes."""
        if self._last_track_time == 0:
            return  # No track to clear
        elapsed = time.time() - self._last_track_time
        if elapsed >= self._track_persist_seconds:
            self.log_collector.info("Track display expired after 5 minutes")
            self.clear_current_track()

    def initialize(self):
        """Initialize services and web server (called once at startup)."""
        # Validate parameters
        try:
            self.snippet_duration = validate_duration(self.snippet_duration, min_seconds=1, max_seconds=300)
            self.interval_duration = validate_interval(self.interval_duration, self.snippet_duration)
            self.output_folder = validate_directory_path(self.output_folder, create_if_missing=True)
        except ValidationError as e:
            self.log_collector.error(f"Validation failed: {e}")
            return False

        # Initialize services (only if not already initialized)
        if not self.spotify_service:
            self.initialize_services()

        # Start web server if enabled (only if not already started)
        if not self.web_server:
            self.start_web_server()

        return True

    def run_loop(self, total_recording_time=None):
        """Run the main listening loop.

        Args:
            total_recording_time: Total time to run (None = infinite)
        """
        if not self.initialize():
            return

        # Calculate total loops
        total_loops = int(total_recording_time / self.interval_duration) if total_recording_time else None

        self.is_running = True
        self._stop_event.clear()  # Reset stop event for fresh run
        self.update_ui_status(is_listening=True)

        cnt = 0
        self.log_collector.info("Starting main loop")
        print("\n🎧 Silent Disco is listening...\n")

        try:
            while self.is_running:
                if not self.is_paused:
                    self.log_collector.info(f"Loop iteration {cnt}")

                    # Only clear track if it's been displayed for 5+ minutes
                    self.maybe_clear_track()

                    # Process snippet
                    self.process_snippet()

                    # Increment counter
                    cnt += 1

                    # Check if a retry was queued during recording/processing
                    if self.retry_queued:
                        self.retry_queued = False
                        self.log_collector.info("Executing queued retry - skipping sleep")
                        continue  # Skip sleep, immediately start next iteration

                    # Check if we should stop (time-based mode)
                    if total_loops is not None and cnt >= total_loops:
                        break

                    # Back to waiting state
                    self.update_ui_status(is_listening='waiting')

                    # Sleep until next iteration
                    sleep_time = self.interval_duration - self.snippet_duration

                    # Update UI with countdown
                    for remaining in range(sleep_time, 0, -1):
                        if not self.is_running or self.retry_now:
                            if self.retry_now:
                                self.log_collector.info("Sleep interrupted - retrying now")
                                self.retry_now = False  # Reset flag
                            break
                        self.update_ui_status(is_listening='waiting', next_recording_in=remaining)
                        time.sleep(1)
                else:
                    time.sleep(1)

        except KeyboardInterrupt:
            self.log_collector.info("Interrupted by user")
            print("\n\n⏸ Stopped by user\n")
        finally:
            self.is_running = False
            self.update_ui_status(is_listening=False)
            self.log_collector.info("Loop ended")
            print(f"\n✓ Processed {cnt} snippets\n")

    def stop(self):
        """Stop the listening loop and interrupt any in-progress recording."""
        self.is_running = False
        self._stop_event.set()  # Interrupt recording if in progress
        self.log_collector.info("Stop requested")

    def pause(self):
        """Pause the listening loop."""
        self.is_paused = True
        self.log_collector.info("Paused")

    def resume(self):
        """Resume the listening loop."""
        self.is_paused = False
        self.log_collector.info("Resumed")

    def retry_recognition(self):
        """Trigger immediate retry by interrupting the sleep loop.

        If currently recording or processing, queues the retry for after completion.
        If waiting in countdown, interrupts immediately.
        """
        if hasattr(self, '_current_state') and self._current_state in ('recording', 'processing'):
            self.retry_queued = True
            self.log_collector.info("Retry queued - will execute after current cycle")
            return 'queued'
        self.retry_now = True
        self.log_collector.info("Retry requested - interrupting sleep")
        return True


# Flask app for legacy routes and API control
app = Flask(__name__)

# Global app instance
silent_disco = None


@app.route('/')
def index():
    return 'Silent Disco is running'


@app.route('/api/control/start', methods=['POST'])
def api_start():
    """Start listening via API."""
    global silent_disco
    if silent_disco and not silent_disco.is_running:
        # Start in background thread
        thread = threading.Thread(target=silent_disco.run_loop, daemon=True)
        thread.start()
        return jsonify({'success': True, 'message': 'Started listening'})
    return jsonify({'success': False, 'message': 'Already running'}), 400


@app.route('/api/control/stop', methods=['POST'])
def api_stop():
    """Stop listening via API."""
    global silent_disco
    if silent_disco:
        silent_disco.stop()
        return jsonify({'success': True, 'message': 'Stopped listening'})
    return jsonify({'success': False, 'message': 'Not running'}), 400


@app.route('/test_spotify')
def test_spotify():
    """Test Spotify connection."""
    try:
        spotify_service = SpotifyService(
            client_id=config.spotify_config.client_id,
            client_secret=config.spotify_config.client_secret,
            redirect_uri='https://github.com/kennygrosz/silent-disco',
            scope='user-modify-playback-state user-read-playback-state'
        )

        device_id, device_name = spotify_service.get_and_activate_device(
            preferred_name=config.app_config.preferred_device_name
        )

        if not device_id:
            return {
                "status": "error",
                "message": "No Spotify devices found"
            }, 404

        return {
            "status": "success",
            "message": "Spotify connection OK",
            "device": device_name
        }, 200

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }, 500


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Silent Disco - Vinyl Companion for Spotify')
    parser.add_argument('--no-ui', action='store_true', help='Disable web UI (UI enabled by default)')
    parser.add_argument('--port', type=int, default=5002, help='Web UI port (default: 5002)')
    parser.add_argument('--snippet-duration', type=int, default=10, help='Snippet duration in seconds')
    parser.add_argument('--interval', type=int, default=60, help='Interval between snippets in seconds')
    parser.add_argument('--time-limit', type=int, default=None, help='Total recording time in seconds (None = infinite)')

    args = parser.parse_args()

    # Create app instance
    global silent_disco
    silent_disco = SilentDiscoApp(
        snippet_duration=args.snippet_duration,
        interval_duration=args.interval,
        enable_ui=not args.no_ui,  # UI enabled by default
        ui_port=args.port
    )

    # Initialize services and web server first
    if not silent_disco.initialize():
        return

    # Run the listening loop
    silent_disco.run_loop(total_recording_time=args.time_limit)

    # Keep process alive for web UI restart capability
    if silent_disco.enable_ui and silent_disco.web_server:
        print("\n🌐 Web UI still running. Press Ctrl+C to quit, or restart from the UI.\n")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Shutting down...\n")


if __name__ == '__main__':
    main()
