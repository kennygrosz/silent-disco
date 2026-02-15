"""End-to-end user journey tests for Silent Disco.

These tests simulate real user interactions through the web UI,
exercising the full stack: Flask routes → app controller → services → UI state.
All external dependencies (Spotify, Shazam, PyAudio) are mocked, but
the internal wiring between components is real.
"""

import time
import threading
from collections import deque
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from app_integrated import SilentDiscoApp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_spotify_track(name='Test Song', artist='Test Artist', track_id='abc123'):
    """Create a mock SpotifyTrack object."""
    track = MagicMock()
    track.id = track_id
    track.uri = f'spotify:track:{track_id}'
    track.name = name
    track.artist = artist
    track.duration_ms = 240000
    track.album_art_url = f'https://i.scdn.co/image/{track_id}'
    return track


def make_recognized_track(name='Test Song', artist='Test Artist'):
    """Create a mock RecognizedTrack from Shazam."""
    recognized = MagicMock()
    recognized.track_string = f'{artist} - {name}'
    recognized.artist = artist
    recognized.title = name
    return recognized


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def e2e_app(tmp_path):
    """A SilentDiscoApp wired up with the web server, all externals mocked."""
    app = SilentDiscoApp(
        snippet_duration=10,
        interval_duration=60,
        output_folder=str(tmp_path),
        enable_ui=True,
        ui_port=5099,
    )

    # Mock services so we don't hit real APIs
    app.spotify_service = MagicMock()
    app.recognition_service = MagicMock()

    # Wire up web server state (without actually starting a server thread)
    from web_server import app as flask_app, app_state, set_app_controller
    app_state.is_listening = False
    app_state.current_track = None
    app_state.track_history = deque(maxlen=20)
    app_state.next_recording_in = 0
    set_app_controller(app)

    # Mark web_server as "started" so update_ui_* methods work
    app.web_server = (flask_app, MagicMock(), app_state, MagicMock())

    yield app

    # Clean up
    app_state.app_controller = None
    app_state.current_track = None
    app_state.track_history = deque(maxlen=20)
    app_state.is_listening = False


@pytest.fixture
def client(e2e_app):
    """Flask test client wired to the e2e app."""
    from web_server import app as flask_app
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Journey 1: Full happy path — user starts listening, song recognized, plays
# ---------------------------------------------------------------------------

class TestHappyPath:
    @patch('web_server.socketio')
    @patch('web_server.audio_streamer')
    @patch('listener.listener.record_audio')
    def test_start_record_recognize_play(self, mock_record, mock_streamer,
                                         mock_socketio, e2e_app, client):
        """User presses Start → app records → Shazam recognizes → Spotify plays."""
        from web_server import app_state

        # --- User presses "Start Listening" ---
        # Set is_running=True so the route skips spawning a background run_loop thread
        # (we call process_snippet() manually in the test)
        e2e_app.is_running = True
        resp = client.post('/api/control/start')
        assert resp.get_json()['success'] is True
        # Web server marks state as listening
        assert app_state.is_listening is True

        # --- App processes a snippet (simulated) ---
        mock_record.return_value = "Recording succeeded"
        e2e_app.recognition_service.recognize.return_value = make_recognized_track(
            name='Blue in Green', artist='Miles Davis'
        )
        e2e_app.spotify_service.search_track.return_value = make_spotify_track(
            name='Blue in Green', artist='Miles Davis', track_id='miles001'
        )
        e2e_app.spotify_service.is_interruption_allowed.return_value = (True, "OK")
        e2e_app.spotify_service.get_and_activate_device.return_value = ('dev1', "Kenny's MacBook Air")
        e2e_app.spotify_service.start_playback.return_value = True

        result = e2e_app.process_snippet()
        assert result is True

        # --- Verify UI state ---
        assert app_state.current_track is not None
        assert app_state.current_track['name'] == 'Blue in Green'
        assert app_state.current_track['artist'] == 'Miles Davis'
        assert app_state.current_track['played_on_spotify'] is True
        assert app_state.current_track['blocked'] is False

        # Track appears in history
        assert len(app_state.track_history) == 1
        assert app_state.track_history[0]['name'] == 'Blue in Green'
        assert 'timestamp' in app_state.track_history[0]

        # History API returns it
        resp = client.get('/api/history')
        tracks = resp.get_json()['tracks']
        assert len(tracks) == 1
        assert tracks[0]['name'] == 'Blue in Green'

        # Spotify was called correctly
        e2e_app.spotify_service.start_playback.assert_called_once()
        call_args = e2e_app.spotify_service.start_playback.call_args
        assert call_args.kwargs['track_uri'] == 'spotify:track:miles001'

    @patch('web_server.socketio')
    @patch('web_server.audio_streamer')
    @patch('listener.listener.record_audio')
    def test_snippet_file_cleaned_up_after_processing(self, mock_record, mock_streamer,
                                                       mock_socketio, e2e_app, tmp_path):
        """Snippet WAV file is deleted after processing."""
        # Create a fake WAV file that record_audio would produce
        def fake_record(filepath, duration, stop_event=None):
            with open(filepath, 'wb') as f:
                f.write(b'\x00' * 1000)
            return "Recording succeeded"

        mock_record.side_effect = fake_record
        e2e_app.recognition_service.recognize.return_value = None  # Unrecognized

        e2e_app.process_snippet()

        # The snippet file should have been cleaned up
        wav_files = list(tmp_path.glob('*.wav'))
        assert len(wav_files) == 0


# ---------------------------------------------------------------------------
# Journey 2: Stop mid-recording → restart
# ---------------------------------------------------------------------------

class TestStopAndRestart:
    @patch('web_server.socketio')
    @patch('web_server.audio_streamer')
    @patch('listener.listener.record_audio')
    def test_stop_during_recording_then_restart(self, mock_record, mock_streamer,
                                                 mock_socketio, e2e_app, client):
        """User starts listening, stops mid-recording, then restarts."""
        from web_server import app_state

        # --- Start ---
        e2e_app.is_running = True
        client.post('/api/control/start')
        assert app_state.is_listening is True

        # --- Simulate recording being interrupted by stop ---
        def recording_gets_interrupted(filepath, duration, stop_event=None):
            return "Recording interrupted."

        mock_record.side_effect = recording_gets_interrupted
        e2e_app._stop_event.set()  # User pressed stop

        result = e2e_app.process_snippet()
        assert result is False

        # --- User presses Stop via UI ---
        resp = client.post('/api/control/stop')
        assert resp.get_json()['success'] is True
        assert app_state.is_listening is False
        assert e2e_app.is_running is False

        # --- User presses Start again ---
        e2e_app._stop_event.clear()
        mock_record.side_effect = None
        mock_record.return_value = "Recording succeeded"
        e2e_app.recognition_service.recognize.return_value = make_recognized_track()
        e2e_app.spotify_service.search_track.return_value = make_spotify_track()
        e2e_app.spotify_service.is_interruption_allowed.return_value = (True, "OK")
        e2e_app.spotify_service.get_and_activate_device.return_value = ('dev1', 'Device')
        e2e_app.spotify_service.start_playback.return_value = True

        e2e_app.is_running = True  # Prevent route from spawning thread
        resp = client.post('/api/control/start')
        assert resp.get_json()['success'] is True

        # New snippet processes successfully after restart
        result = e2e_app.process_snippet()
        assert result is True

    @patch('web_server.socketio')
    @patch('web_server.audio_streamer')
    def test_status_api_reflects_stop(self, mock_streamer, mock_socketio, e2e_app, client):
        """Status API correctly reflects stopped state."""
        from web_server import app_state

        # Start then stop
        e2e_app.is_running = True
        client.post('/api/control/start')
        client.post('/api/control/stop')

        resp = client.get('/api/status')
        data = resp.get_json()
        assert data['is_listening'] is False


# ---------------------------------------------------------------------------
# Journey 3: Spotify is busy — track recognized but can't play
# ---------------------------------------------------------------------------

class TestSpotifyBusy:
    @patch('web_server.socketio')
    @patch('web_server.audio_streamer')
    @patch('listener.listener.record_audio')
    def test_recognized_but_spotify_playing(self, mock_record, mock_streamer,
                                             mock_socketio, e2e_app, client):
        """Song recognized but Spotify is busy — shown as 'Recognized' not played."""
        from web_server import app_state

        mock_record.return_value = "Recording succeeded"
        e2e_app.recognition_service.recognize.return_value = make_recognized_track(
            name='So What', artist='Miles Davis'
        )
        e2e_app.spotify_service.search_track.return_value = make_spotify_track(
            name='So What', artist='Miles Davis', track_id='miles002'
        )
        # Spotify is busy
        e2e_app.spotify_service.is_interruption_allowed.return_value = (
            False, "There is an active spotify session right now and music is playing."
        )

        result = e2e_app.process_snippet()
        assert result is False

        # Track should still appear in UI but marked as blocked
        assert app_state.current_track is not None
        assert app_state.current_track['name'] == 'So What'
        assert app_state.current_track['blocked'] is True
        assert app_state.current_track['played_on_spotify'] is False

        # Track still added to history
        assert len(app_state.track_history) == 1

        # Spotify playback was NOT attempted
        e2e_app.spotify_service.start_playback.assert_not_called()

    @patch('web_server.socketio')
    @patch('web_server.audio_streamer')
    @patch('listener.listener.record_audio')
    def test_spotify_busy_then_free(self, mock_record, mock_streamer,
                                     mock_socketio, e2e_app, client):
        """First snippet blocked, second snippet plays because Spotify is now free."""
        from web_server import app_state

        mock_record.return_value = "Recording succeeded"

        # --- First snippet: Spotify busy ---
        e2e_app.recognition_service.recognize.return_value = make_recognized_track(
            name='So What', artist='Miles Davis'
        )
        e2e_app.spotify_service.search_track.return_value = make_spotify_track(
            name='So What', artist='Miles Davis', track_id='miles002'
        )
        e2e_app.spotify_service.is_interruption_allowed.return_value = (False, "Busy")

        result1 = e2e_app.process_snippet()
        assert result1 is False
        assert app_state.current_track['blocked'] is True

        # --- Second snippet: Spotify free, different song ---
        e2e_app.recognition_service.recognize.return_value = make_recognized_track(
            name='Take Five', artist='Dave Brubeck'
        )
        e2e_app.spotify_service.search_track.return_value = make_spotify_track(
            name='Take Five', artist='Dave Brubeck', track_id='dave001'
        )
        e2e_app.spotify_service.is_interruption_allowed.return_value = (True, "OK")
        e2e_app.spotify_service.get_and_activate_device.return_value = ('dev1', 'Device')
        e2e_app.spotify_service.start_playback.return_value = True

        result2 = e2e_app.process_snippet()
        assert result2 is True

        # Now playing shows the new track
        assert app_state.current_track['name'] == 'Take Five'
        assert app_state.current_track['blocked'] is False
        assert app_state.current_track['played_on_spotify'] is True

        # Both tracks in history
        assert len(app_state.track_history) == 2


# ---------------------------------------------------------------------------
# Journey 4: Same song recognized twice — deduplication
# ---------------------------------------------------------------------------

class TestDuplicateSongs:
    @patch('web_server.socketio')
    @patch('web_server.audio_streamer')
    @patch('listener.listener.record_audio')
    def test_same_song_twice_deduped_in_history(self, mock_record, mock_streamer,
                                                  mock_socketio, e2e_app, client):
        """Same song recognized twice in a row — only appears once in history."""
        from web_server import app_state

        mock_record.return_value = "Recording succeeded"

        recognized = make_recognized_track(name='Blue in Green', artist='Miles Davis')
        spotify_track = make_spotify_track(name='Blue in Green', artist='Miles Davis', track_id='miles001')

        e2e_app.recognition_service.recognize.return_value = recognized
        e2e_app.spotify_service.search_track.return_value = spotify_track
        e2e_app.spotify_service.is_interruption_allowed.return_value = (True, "OK")
        e2e_app.spotify_service.get_and_activate_device.return_value = ('dev1', 'Device')
        e2e_app.spotify_service.start_playback.return_value = True

        # First play
        e2e_app.process_snippet()

        # Second play — same song
        e2e_app.process_snippet()

        # History should have only 1 entry (deduplication in web_server.update_current_track)
        assert len(app_state.track_history) == 1
        assert app_state.track_history[0]['name'] == 'Blue in Green'

    @patch('web_server.socketio')
    @patch('web_server.audio_streamer')
    @patch('listener.listener.record_audio')
    def test_same_song_skipped_in_queue(self, mock_record, mock_streamer,
                                         mock_socketio, e2e_app, client):
        """Same song in recent queue is skipped (not played again on Spotify)."""
        mock_record.return_value = "Recording succeeded"

        recognized = make_recognized_track(name='Blue in Green', artist='Miles Davis')
        spotify_track = make_spotify_track(name='Blue in Green', artist='Miles Davis')

        e2e_app.recognition_service.recognize.return_value = recognized
        e2e_app.spotify_service.search_track.return_value = spotify_track
        e2e_app.spotify_service.is_interruption_allowed.return_value = (True, "OK")
        e2e_app.spotify_service.get_and_activate_device.return_value = ('dev1', 'Device')
        e2e_app.spotify_service.start_playback.return_value = True

        # First play succeeds
        result1 = e2e_app.process_snippet()
        assert result1 is True
        assert e2e_app.spotify_service.start_playback.call_count == 1

        # Second play — same track_string in queue, should be skipped
        result2 = e2e_app.process_snippet()
        assert result2 is False
        # Playback NOT called a second time
        assert e2e_app.spotify_service.start_playback.call_count == 1

    @patch('web_server.socketio')
    @patch('web_server.audio_streamer')
    @patch('listener.listener.record_audio')
    def test_different_songs_not_deduped(self, mock_record, mock_streamer,
                                          mock_socketio, e2e_app, client):
        """Different songs both appear in history and both play."""
        from web_server import app_state

        mock_record.return_value = "Recording succeeded"
        e2e_app.spotify_service.is_interruption_allowed.return_value = (True, "OK")
        e2e_app.spotify_service.get_and_activate_device.return_value = ('dev1', 'Device')
        e2e_app.spotify_service.start_playback.return_value = True

        # Song 1
        e2e_app.recognition_service.recognize.return_value = make_recognized_track(
            name='Blue in Green', artist='Miles Davis'
        )
        e2e_app.spotify_service.search_track.return_value = make_spotify_track(
            name='Blue in Green', artist='Miles Davis', track_id='miles001'
        )
        e2e_app.process_snippet()

        # Song 2
        e2e_app.recognition_service.recognize.return_value = make_recognized_track(
            name='Take Five', artist='Dave Brubeck'
        )
        e2e_app.spotify_service.search_track.return_value = make_spotify_track(
            name='Take Five', artist='Dave Brubeck', track_id='dave001'
        )
        e2e_app.process_snippet()

        assert len(app_state.track_history) == 2
        assert e2e_app.spotify_service.start_playback.call_count == 2


# ---------------------------------------------------------------------------
# Journey 5: Unrecognized → Retry → Success
# ---------------------------------------------------------------------------

class TestRetryAfterFailure:
    @patch('web_server.socketio')
    @patch('web_server.audio_streamer')
    @patch('listener.listener.record_audio')
    def test_unrecognized_then_retry_succeeds(self, mock_record, mock_streamer,
                                               mock_socketio, e2e_app, client):
        """First snippet unrecognized, user retries, second attempt recognizes."""
        from web_server import app_state

        mock_record.return_value = "Recording succeeded"

        # --- First attempt: unrecognized ---
        e2e_app.recognition_service.recognize.return_value = None

        result1 = e2e_app.process_snippet()
        assert result1 is False
        assert app_state.current_track is None  # Nothing to show

        # --- User presses Retry (during waiting state) ---
        e2e_app._current_state = 'waiting'
        resp = client.post('/api/control/retry')
        data = resp.get_json()
        assert data['success'] is True
        assert data['queued'] is False  # Immediate, not queued
        assert e2e_app.retry_now is True

        # --- Second attempt: recognized ---
        e2e_app.retry_now = False  # Reset (run_loop would do this)
        e2e_app.recognition_service.recognize.return_value = make_recognized_track(
            name='My Favorite Things', artist='John Coltrane'
        )
        e2e_app.spotify_service.search_track.return_value = make_spotify_track(
            name='My Favorite Things', artist='John Coltrane', track_id='coltrane001'
        )
        e2e_app.spotify_service.is_interruption_allowed.return_value = (True, "OK")
        e2e_app.spotify_service.get_and_activate_device.return_value = ('dev1', 'Device')
        e2e_app.spotify_service.start_playback.return_value = True

        result2 = e2e_app.process_snippet()
        assert result2 is True
        assert app_state.current_track['name'] == 'My Favorite Things'

    @patch('web_server.socketio')
    @patch('web_server.audio_streamer')
    @patch('listener.listener.record_audio')
    def test_retry_during_recording_gets_queued(self, mock_record, mock_streamer,
                                                  mock_socketio, e2e_app, client):
        """User presses retry while recording — gets queued, not immediate."""
        e2e_app._current_state = 'recording'
        resp = client.post('/api/control/retry')
        data = resp.get_json()
        assert data['success'] is True
        assert data['queued'] is True
        assert e2e_app.retry_queued is True


# ---------------------------------------------------------------------------
# Journey 6: No Spotify devices available
# ---------------------------------------------------------------------------

class TestNoSpotifyDevices:
    @patch('web_server.socketio')
    @patch('web_server.audio_streamer')
    @patch('listener.listener.record_audio')
    def test_recognized_but_no_devices(self, mock_record, mock_streamer,
                                        mock_socketio, e2e_app, client):
        """Song recognized and found on Spotify, but no playback devices."""
        from web_server import app_state

        mock_record.return_value = "Recording succeeded"
        e2e_app.recognition_service.recognize.return_value = make_recognized_track()
        e2e_app.spotify_service.search_track.return_value = make_spotify_track()
        e2e_app.spotify_service.is_interruption_allowed.return_value = (True, "OK")
        e2e_app.spotify_service.get_and_activate_device.return_value = (None, None)

        result = e2e_app.process_snippet()
        assert result is False

        # Track shown as blocked (no device)
        assert app_state.current_track is not None
        assert app_state.current_track['blocked'] is True

    @patch('web_server.socketio')
    @patch('web_server.audio_streamer')
    def test_test_spotify_no_devices(self, mock_streamer, mock_socketio, e2e_app, client):
        """User presses Test Spotify but no devices found."""
        e2e_app.spotify_service.get_and_activate_device.return_value = (None, None)

        resp = client.post('/api/control/test')
        assert resp.status_code == 404
        data = resp.get_json()
        assert data['success'] is False
        assert 'No Spotify devices' in data['message']

    @patch('web_server.socketio')
    @patch('web_server.audio_streamer')
    def test_test_spotify_success(self, mock_streamer, mock_socketio, e2e_app, client):
        """User presses Test Spotify with device available."""
        e2e_app.spotify_service.get_and_activate_device.return_value = ('dev1', "Kenny's MacBook Air")
        e2e_app.spotify_service.client.current_playback.return_value = None

        resp = client.post('/api/control/test')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['device'] == "Kenny's MacBook Air"
        assert data['has_active_session'] is False


# ---------------------------------------------------------------------------
# Journey 7: Multiple songs building up a session history
# ---------------------------------------------------------------------------

class TestMultiSongSession:
    @patch('web_server.socketio')
    @patch('web_server.audio_streamer')
    @patch('listener.listener.record_audio')
    def test_three_song_session(self, mock_record, mock_streamer,
                                 mock_socketio, e2e_app, client):
        """Simulate a 3-song listening session and verify history order."""
        from web_server import app_state

        mock_record.return_value = "Recording succeeded"
        e2e_app.spotify_service.is_interruption_allowed.return_value = (True, "OK")
        e2e_app.spotify_service.get_and_activate_device.return_value = ('dev1', 'Device')
        e2e_app.spotify_service.start_playback.return_value = True

        songs = [
            ('Blue in Green', 'Miles Davis', 'miles001'),
            ('Take Five', 'Dave Brubeck', 'dave001'),
            ('My Favorite Things', 'John Coltrane', 'coltrane001'),
        ]

        for name, artist, track_id in songs:
            e2e_app.recognition_service.recognize.return_value = make_recognized_track(name, artist)
            e2e_app.spotify_service.search_track.return_value = make_spotify_track(name, artist, track_id)
            result = e2e_app.process_snippet()
            assert result is True

        # History has all 3 tracks, most recent first
        assert len(app_state.track_history) == 3
        assert app_state.track_history[0]['name'] == 'My Favorite Things'
        assert app_state.track_history[1]['name'] == 'Take Five'
        assert app_state.track_history[2]['name'] == 'Blue in Green'

        # Queue has all 3 track strings
        assert len(e2e_app.queue) == 3

        # Current track is the latest
        assert app_state.current_track['name'] == 'My Favorite Things'

        # History API returns correct order
        resp = client.get('/api/history')
        tracks = resp.get_json()['tracks']
        assert [t['name'] for t in tracks] == ['My Favorite Things', 'Take Five', 'Blue in Green']

        # Timestamps are in descending order
        assert tracks[0]['timestamp'] >= tracks[1]['timestamp']
        assert tracks[1]['timestamp'] >= tracks[2]['timestamp']


# ---------------------------------------------------------------------------
# Journey 8: Song not found on Spotify (Shazam knows it, Spotify doesn't)
# ---------------------------------------------------------------------------

class TestSpotifySearchFails:
    @patch('web_server.socketio')
    @patch('web_server.audio_streamer')
    @patch('listener.listener.record_audio')
    def test_recognized_but_not_on_spotify(self, mock_record, mock_streamer,
                                            mock_socketio, e2e_app, client):
        """Shazam recognizes the song but Spotify search returns nothing."""
        mock_record.return_value = "Recording succeeded"
        e2e_app.recognition_service.recognize.return_value = make_recognized_track(
            name='Obscure Song', artist='Unknown Band'
        )
        e2e_app.spotify_service.search_track.return_value = None  # Not on Spotify
        e2e_app.spotify_service.is_interruption_allowed.return_value = (True, "OK")

        result = e2e_app.process_snippet()
        assert result is False
        # Playback should NOT be attempted
        e2e_app.spotify_service.start_playback.assert_not_called()
        e2e_app.spotify_service.get_and_activate_device.assert_not_called()


# ---------------------------------------------------------------------------
# Journey 9: Track display clears after timeout
# ---------------------------------------------------------------------------

class TestTrackDisplayTimeout:
    @patch('web_server.socketio')
    @patch('web_server.audio_streamer')
    @patch('listener.listener.record_audio')
    def test_track_clears_after_5_minutes(self, mock_record, mock_streamer,
                                           mock_socketio, e2e_app, client):
        """Track display clears after 5 minutes of being shown."""
        from web_server import app_state

        mock_record.return_value = "Recording succeeded"
        e2e_app.recognition_service.recognize.return_value = make_recognized_track()
        e2e_app.spotify_service.search_track.return_value = make_spotify_track()
        e2e_app.spotify_service.is_interruption_allowed.return_value = (True, "OK")
        e2e_app.spotify_service.get_and_activate_device.return_value = ('dev1', 'Device')
        e2e_app.spotify_service.start_playback.return_value = True

        e2e_app.process_snippet()
        assert app_state.current_track is not None

        # Simulate 5+ minutes passing
        e2e_app._last_track_time = time.time() - 400

        e2e_app.maybe_clear_track()
        assert app_state.current_track is None

    @patch('web_server.socketio')
    @patch('web_server.audio_streamer')
    @patch('listener.listener.record_audio')
    def test_track_persists_within_5_minutes(self, mock_record, mock_streamer,
                                              mock_socketio, e2e_app, client):
        """Track display persists if less than 5 minutes have passed."""
        from web_server import app_state

        mock_record.return_value = "Recording succeeded"
        e2e_app.recognition_service.recognize.return_value = make_recognized_track()
        e2e_app.spotify_service.search_track.return_value = make_spotify_track()
        e2e_app.spotify_service.is_interruption_allowed.return_value = (True, "OK")
        e2e_app.spotify_service.get_and_activate_device.return_value = ('dev1', 'Device')
        e2e_app.spotify_service.start_playback.return_value = True

        e2e_app.process_snippet()
        assert app_state.current_track is not None

        # Only 30 seconds have passed
        e2e_app._last_track_time = time.time() - 30

        e2e_app.maybe_clear_track()
        assert app_state.current_track is not None  # Still showing
