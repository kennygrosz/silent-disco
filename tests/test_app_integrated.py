"""Tests for app_integrated.py - Main application controller."""

import os
import threading
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from app_integrated import SilentDiscoApp


@pytest.fixture
def app(tmp_path):
    """Create a SilentDiscoApp with test configuration."""
    return SilentDiscoApp(
        snippet_duration=10,
        interval_duration=60,
        output_folder=str(tmp_path),
        enable_ui=False,
    )


@pytest.fixture
def initialized_app(app):
    """App with mocked services."""
    app.spotify_service = MagicMock()
    app.recognition_service = MagicMock()
    return app


class TestInitialize:
    def test_initialize_creates_services(self, app):
        with patch.object(app, 'initialize_services') as mock_init:
            result = app.initialize()
            assert result is True
            mock_init.assert_called_once()

    def test_initialize_idempotent(self, initialized_app):
        with patch.object(initialized_app, 'initialize_services') as mock_init:
            initialized_app.initialize()
            mock_init.assert_not_called()  # Already has services

    def test_initialize_invalid_duration(self, tmp_path):
        app = SilentDiscoApp(snippet_duration=0, output_folder=str(tmp_path))
        result = app.initialize()
        assert result is False


class TestProcessSnippet:
    @patch('listener.listener.record_audio')
    def test_happy_path(self, mock_record, initialized_app):
        """Record -> Recognize -> Search -> Play"""
        mock_record.return_value = "Recording succeeded"

        # Mock recognition
        mock_recognized = MagicMock()
        mock_recognized.track_string = "Artist - Song"
        initialized_app.recognition_service.recognize.return_value = mock_recognized

        # Mock Spotify search
        mock_track = MagicMock()
        mock_track.id = 'abc'
        mock_track.uri = 'spotify:track:abc'
        mock_track.name = 'Song'
        mock_track.artist = 'Artist'
        mock_track.duration_ms = 240000
        mock_track.album_art_url = 'https://example.com/art.jpg'
        initialized_app.spotify_service.search_track.return_value = mock_track

        # Mock interruption check
        initialized_app.spotify_service.is_interruption_allowed.return_value = (True, "OK")

        # Mock device
        initialized_app.spotify_service.get_and_activate_device.return_value = ('dev1', 'Device')

        # Mock playback
        initialized_app.spotify_service.start_playback.return_value = True

        result = initialized_app.process_snippet()
        assert result is True
        assert len(initialized_app.queue) == 1

    @patch('listener.listener.record_audio')
    def test_unrecognized(self, mock_record, initialized_app):
        mock_record.return_value = "Recording succeeded"
        initialized_app.recognition_service.recognize.return_value = None

        result = initialized_app.process_snippet()
        assert result is False

    @patch('listener.listener.record_audio')
    def test_recording_interrupted(self, mock_record, initialized_app):
        mock_record.return_value = "Recording interrupted."
        initialized_app._stop_event.set()

        result = initialized_app.process_snippet()
        assert result is False

    @patch('listener.listener.record_audio')
    def test_spotify_search_fails(self, mock_record, initialized_app):
        mock_record.return_value = "Recording succeeded"

        mock_recognized = MagicMock()
        mock_recognized.track_string = "Artist - Song"
        initialized_app.recognition_service.recognize.return_value = mock_recognized

        initialized_app.spotify_service.search_track.return_value = None
        initialized_app.spotify_service.is_interruption_allowed.return_value = (True, "OK")

        result = initialized_app.process_snippet()
        assert result is False

    @patch('listener.listener.record_audio')
    def test_interruption_not_allowed(self, mock_record, initialized_app):
        mock_record.return_value = "Recording succeeded"

        mock_recognized = MagicMock()
        mock_recognized.track_string = "Artist - Song"
        initialized_app.recognition_service.recognize.return_value = mock_recognized

        mock_track = MagicMock()
        mock_track.id = 'abc'
        mock_track.uri = 'spotify:track:abc'
        mock_track.name = 'Song'
        mock_track.artist = 'Artist'
        mock_track.duration_ms = 240000
        mock_track.album_art_url = None
        initialized_app.spotify_service.search_track.return_value = mock_track
        initialized_app.spotify_service.is_interruption_allowed.return_value = (False, "Music playing")

        result = initialized_app.process_snippet()
        assert result is False


class TestCleanupSnippetFile:
    def test_deletes_existing_file(self, initialized_app, tmp_path):
        f = tmp_path / "test.wav"
        f.write_bytes(b'\x00' * 100)
        initialized_app._cleanup_snippet_file(str(f))
        assert not f.exists()

    def test_handles_missing_file(self, initialized_app):
        # Should not raise
        initialized_app._cleanup_snippet_file('/nonexistent/file.wav')

    def test_handles_none_filepath(self, initialized_app):
        initialized_app._cleanup_snippet_file(None)


class TestStopPauseResume:
    def test_stop(self, app):
        app.is_running = True
        app.stop()
        assert app.is_running is False
        assert app._stop_event.is_set()

    def test_pause(self, app):
        app.pause()
        assert app.is_paused is True

    def test_resume(self, app):
        app.is_paused = True
        app.resume()
        assert app.is_paused is False


class TestRetryRecognition:
    def test_retry_during_recording_queues(self, app):
        app._current_state = 'recording'
        result = app.retry_recognition()
        assert result == 'queued'
        assert app.retry_queued is True

    def test_retry_during_processing_queues(self, app):
        app._current_state = 'processing'
        result = app.retry_recognition()
        assert result == 'queued'

    def test_retry_during_waiting_immediate(self, app):
        app._current_state = 'waiting'
        result = app.retry_recognition()
        assert result is True
        assert app.retry_now is True


class TestMaybeClearTrack:
    def test_no_track_to_clear(self, app):
        app._last_track_time = 0
        app.maybe_clear_track()  # Should not raise

    @patch.object(SilentDiscoApp, 'clear_current_track')
    def test_clears_expired_track(self, mock_clear, app):
        import time
        app._last_track_time = time.time() - 400  # > 300s
        app.maybe_clear_track()
        mock_clear.assert_called_once()

    @patch.object(SilentDiscoApp, 'clear_current_track')
    def test_keeps_recent_track(self, mock_clear, app):
        import time
        app._last_track_time = time.time() - 10  # Only 10s ago
        app.maybe_clear_track()
        mock_clear.assert_not_called()
