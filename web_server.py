"""Flask web server for Silent Disco UI.

Provides real-time web interface with audio visualization and controls.
"""

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import threading
import time
import pyaudio
import numpy as np
from collections import deque
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'silent-disco-secret-key'
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
socketio = SocketIO(app, cors_allowed_origins="*")

# Shared state
class AppState:
    def __init__(self):
        self.is_listening = False
        self.current_track = None
        self.track_history = deque(maxlen=20)
        self.last_snippet = None
        self.device_name = "Kenny's MacBook Air"
        self.next_recording_in = 0
        self.app_controller = None  # Reference to main app controller

app_state = AppState()


def set_app_controller(controller):
    """Set reference to main app controller for control endpoints."""
    app_state.app_controller = controller

# Audio streaming for visualizer
class AudioStreamer:
    def __init__(self, rate=44100, chunk=2048, frame_skip=2):
        self.rate = rate
        self.chunk = chunk
        self.frame_skip = frame_skip  # Only process FFT every Nth frame to reduce CPU
        self.is_streaming = False
        self._stream = None
        self._p = None
        self._lock = threading.Lock()
        self._thread = None

    def start(self):
        """Start streaming audio data to clients."""
        with self._lock:
            if self.is_streaming:
                return

            self.is_streaming = True
            self._thread = threading.Thread(target=self._stream_audio, daemon=True)
            self._thread.start()
            logger.info("Audio streaming started")

    def stop(self):
        """Stop streaming audio data and wait for thread to finish."""
        self.is_streaming = False

        # Wait for streaming thread to finish and clean up its own resources
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

        logger.info("Audio streaming stopped")

    def _cleanup_audio(self):
        """Clean up PyAudio resources safely."""
        try:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
        except Exception:
            pass  # Ignore PortAudio errors during cleanup
        finally:
            self._stream = None

        try:
            if self._p:
                self._p.terminate()
        except Exception:
            pass
        finally:
            self._p = None

    def _stream_audio(self):
        """Stream audio data via WebSocket."""
        try:
            self._p = pyaudio.PyAudio()
            self._stream = self._p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk
            )

            import os
            frame_count = 0
            frame_skip = self.frame_skip  # Use configurable frame skip rate

            while self.is_streaming:
                try:
                    # Read audio data
                    data = self._stream.read(self.chunk, exception_on_overflow=False)
                    
                    # Only process FFT every Nth frame to reduce CPU usage
                    if frame_count % frame_skip == 0:
                        audio_data = np.frombuffer(data, dtype=np.int16)

                        # Convert to frequency domain (FFT)
                        fft = np.fft.fft(audio_data)
                        freqs = np.abs(fft[:len(fft)//2])

                        # Normalize and downsample to 128 bars
                        normalized = freqs / np.max(freqs) if np.max(freqs) > 0 else freqs
                        downsampled = np.interp(
                            np.linspace(0, len(normalized)-1, 128),
                            np.arange(len(normalized)),
                            normalized
                        )

                        # Send to all connected clients
                        socketio.emit('audio_data', {
                            'data': downsampled.tolist()
                        })

                    frame_count += 1

                except Exception as e:
                    if self.is_streaming:
                        logger.error(f"Error reading audio: {e}")

                time.sleep(0.05)  # ~20 FPS
                os.sched_yield()  # Yield CPU to prevent excessive spinning

        except Exception as e:
            logger.error(f"Audio streaming error: {e}")
        finally:
            self._cleanup_audio()

audio_streamer = AudioStreamer(frame_skip=3)  # Aggressive CPU optimization: process FFT every 3rd frame


# Routes
@app.route('/')
def index():
    """Serve the main UI."""
    from flask import make_response
    response = make_response(render_template('index.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/analytics')
def analytics():
    """Serve the analytics dashboard."""
    from flask import make_response
    response = make_response(render_template('analytics.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/api/status')
def get_status():
    """Get current application status."""
    return jsonify({
        'is_listening': app_state.is_listening,
        'current_track': app_state.current_track,
        'device_name': app_state.device_name,
        'next_recording_in': app_state.next_recording_in
    })


@app.route('/api/history')
def get_history():
    """Get track history."""
    return jsonify({
        'tracks': list(app_state.track_history)
    })


@app.route('/api/analytics')
def get_analytics():
    """Get analytics data for the dashboard."""
    if (app_state.app_controller
            and hasattr(app_state.app_controller, 'analytics_db')
            and app_state.app_controller.analytics_db):
        data = app_state.app_controller.analytics_db.get_analytics()
        return jsonify(data)
    return jsonify({
        'total_snippets': 0, 'recognized_count': 0,
        'unrecognized_count': 0, 'failed_count': 0,
        'played_count': 0, 'session_count': 0, 'recognition_rate': 0,
        'top_artists': [], 'top_songs': [],
        'by_hour': [0] * 24, 'by_day': [0] * 7,
        'album_art_urls': [], 'sessions': [],
    })


@app.route('/api/control/start', methods=['POST'])
def start_listening():
    """Start the listening loop."""
    if app_state.app_controller and not app_state.app_controller.is_running:
        # Start via app controller
        import threading
        thread = threading.Thread(target=app_state.app_controller.run_loop, daemon=True)
        thread.start()

    app_state.is_listening = True
    audio_streamer.start()

    # Emit status update to all clients
    socketio.emit('status_update', {
        'is_listening': True
    })

    return jsonify({'success': True, 'message': 'Listening started'})


@app.route('/api/control/stop', methods=['POST'])
def stop_listening():
    """Stop the listening loop."""
    if app_state.app_controller:
        # Stop via app controller
        app_state.app_controller.stop()

    app_state.is_listening = False
    audio_streamer.stop()

    # Emit status update to all clients
    socketio.emit('status_update', {
        'is_listening': False
    })

    return jsonify({'success': True, 'message': 'Listening stopped'})


@app.route('/api/control/retry', methods=['POST'])
def retry_recognition():
    """Retry recognition immediately by interrupting sleep."""
    if app_state.app_controller:
        result = app_state.app_controller.retry_recognition()
        if result == 'queued':
            return jsonify({'success': True, 'queued': True, 'message': 'Retry queued - will run after current cycle'})
        return jsonify({'success': True, 'queued': False, 'message': 'Retrying now...'})
    return jsonify({'success': False, 'message': 'App not running'}), 400


@app.route('/api/control/replay', methods=['POST'])
def replay_snippet():
    """Replay the last recorded snippet."""
    if not app_state.last_snippet:
        return jsonify({'success': False, 'message': 'No snippet to replay'}), 400

    # TODO: Implement replay logic
    return jsonify({'success': True, 'message': 'Replaying snippet...'})


@app.route('/api/control/test', methods=['POST'])
def test_spotify():
    """Test Spotify connection and get device info."""
    if app_state.app_controller and app_state.app_controller.spotify_service:
        try:
            spotify_service = app_state.app_controller.spotify_service

            # Get active device
            device_id, device_name = spotify_service.get_and_activate_device()

            if device_id:
                # Check if there's an active playback session
                playback = spotify_service.client.current_playback()
                is_playing = playback is not None and playback.get('is_playing', False)

                return jsonify({
                    'success': True,
                    'message': f'Connected to: {device_name}',
                    'device': device_name,
                    'device_id': device_id,
                    'has_active_session': is_playing
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'No Spotify devices available',
                    'device': None
                }), 404
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Spotify error: {str(e)}'
            }), 500
    else:
        return jsonify({'success': False, 'message': 'App not initialized'}), 400


# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info(f"Client connected: {request.sid}")

    # Send current state to newly connected client
    emit('status_update', {
        'is_listening': app_state.is_listening,
        'current_track': app_state.current_track,
        'device_name': app_state.device_name
    })

    emit('history_update', {
        'tracks': list(app_state.track_history)
    })


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info(f"Client disconnected: {request.sid}")


# Helper functions for integration with main app
def update_current_track(track_data):
    """Update the currently playing track.

    Args:
        track_data: Dict with keys: name, artist, album_art_url, mood, or None to clear
    """
    if track_data is None:
        # Clear current track
        app_state.current_track = None
        socketio.emit('track_update', {'track': None})
        return

    app_state.current_track = track_data

    # Add to history (skip if same song as most recent entry)
    is_duplicate = (
        app_state.track_history and
        app_state.track_history[0].get('name') == track_data.get('name') and
        app_state.track_history[0].get('artist') == track_data.get('artist')
    )
    if not is_duplicate:
        app_state.track_history.appendleft({
            **track_data,
            'timestamp': time.time()
        })
        # Only send history update if there's a new item (not a duplicate)
        socketio.emit('history_update', {
            'tracks': list(app_state.track_history)
        })

    # Broadcast track update
    socketio.emit('track_update', {
        'track': track_data
    })


def update_status(is_listening=None, next_recording_in=None):
    """Update application status.

    Args:
        is_listening: Status string ('waiting', 'recording', 'processing') or boolean
        next_recording_in: Seconds until next recording
    """
    if is_listening is not None:
        if isinstance(is_listening, bool):
            app_state.is_listening = is_listening
            status_text = 'listening' if is_listening else 'stopped'
        else:
            # String status: 'waiting', 'recording', 'processing'
            app_state.is_listening = is_listening
            status_text = is_listening

    if next_recording_in is not None:
        app_state.next_recording_in = next_recording_in

    # Broadcast to all clients
    socketio.emit('status_update', {
        'is_listening': app_state.is_listening,
        'status': status_text if is_listening is not None else None,
        'next_recording_in': app_state.next_recording_in
    })


def run_server(host='0.0.0.0', port=5001):
    """Run the Flask-SocketIO server.

    Args:
        host: Host to bind to (default: 0.0.0.0 for network access)
        port: Port to listen on (default: 5001)
    """
    logger.info(f"Starting Silent Disco web server on {host}:{port}")
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    # Start audio streaming
    audio_streamer.start()

    # Run server
    run_server()
