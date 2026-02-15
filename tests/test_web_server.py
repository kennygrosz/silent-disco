"""Tests for web_server.py - Flask routes and state management."""

import time
import pytest
from unittest.mock import patch, MagicMock
from collections import deque


class TestAppState:
    def test_initial_state(self):
        from web_server import AppState
        state = AppState()
        assert state.is_listening is False
        assert state.current_track is None
        assert isinstance(state.track_history, deque)
        assert len(state.track_history) == 0
        assert state.app_controller is None


class TestUpdateCurrentTrack:
    def setup_method(self):
        """Reset app_state before each test."""
        from web_server import app_state
        app_state.current_track = None
        app_state.track_history = deque(maxlen=20)

    @patch('web_server.socketio')
    def test_set_track(self, mock_socketio):
        from web_server import update_current_track, app_state

        track = {'name': 'Song', 'artist': 'Artist'}
        update_current_track(track)

        assert app_state.current_track == track
        assert len(app_state.track_history) == 1
        assert app_state.track_history[0]['name'] == 'Song'
        assert 'timestamp' in app_state.track_history[0]

    @patch('web_server.socketio')
    def test_clear_track(self, mock_socketio):
        from web_server import update_current_track, app_state

        app_state.current_track = {'name': 'Old Song'}
        update_current_track(None)
        assert app_state.current_track is None

    @patch('web_server.socketio')
    def test_deduplication(self, mock_socketio):
        from web_server import update_current_track, app_state

        track = {'name': 'Song', 'artist': 'Artist'}
        update_current_track(track)
        update_current_track(track)  # Same track again

        assert len(app_state.track_history) == 1

    @patch('web_server.socketio')
    def test_different_tracks_not_deduped(self, mock_socketio):
        from web_server import update_current_track, app_state

        update_current_track({'name': 'Song 1', 'artist': 'Artist'})
        update_current_track({'name': 'Song 2', 'artist': 'Artist'})

        assert len(app_state.track_history) == 2


class TestUpdateStatus:
    def setup_method(self):
        from web_server import app_state
        app_state.is_listening = False
        app_state.next_recording_in = 0

    @patch('web_server.socketio')
    def test_update_boolean_status(self, mock_socketio):
        from web_server import update_status, app_state

        update_status(is_listening=True)
        assert app_state.is_listening is True

    @patch('web_server.socketio')
    def test_update_string_status(self, mock_socketio):
        from web_server import update_status, app_state

        update_status(is_listening='recording')
        assert app_state.is_listening == 'recording'

    @patch('web_server.socketio')
    def test_update_countdown(self, mock_socketio):
        from web_server import update_status, app_state

        update_status(next_recording_in=45)
        assert app_state.next_recording_in == 45


class TestFlaskRoutes:
    @pytest.fixture
    def client(self):
        from web_server import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def setup_method(self):
        from web_server import app_state
        app_state.is_listening = False
        app_state.current_track = None
        app_state.track_history = deque(maxlen=20)
        app_state.next_recording_in = 0
        app_state.app_controller = None

    def test_get_status(self, client):
        resp = client.get('/api/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'is_listening' in data
        assert data['is_listening'] is False

    def test_get_history_empty(self, client):
        resp = client.get('/api/history')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['tracks'] == []

    def test_stop_with_controller(self, client):
        from web_server import app_state
        mock_controller = MagicMock()
        app_state.app_controller = mock_controller

        with patch('web_server.audio_streamer'):
            with patch('web_server.socketio'):
                resp = client.post('/api/control/stop')

        assert resp.status_code == 200
        mock_controller.stop.assert_called_once()

    def test_retry_no_controller(self, client):
        resp = client.post('/api/control/retry')
        assert resp.status_code == 400

    def test_test_spotify_not_initialized(self, client):
        resp = client.post('/api/control/test')
        assert resp.status_code == 400
