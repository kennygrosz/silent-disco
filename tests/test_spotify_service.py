"""Tests for services/spotify_service.py - Spotify API wrapper."""

import time
import pytest
from unittest.mock import patch, MagicMock
from services.spotify_service import SpotifyTrack, SpotifyService
from utils.validators import ValidationError


class TestSpotifyTrack:
    def test_from_api_response(self, valid_spotify_track_data):
        track = SpotifyTrack.from_api_response(valid_spotify_track_data)
        assert track.id == 'abc123'
        assert track.uri == 'spotify:track:abc123'
        assert track.name == 'Test Song'
        assert track.artist == 'Test Artist'
        assert track.duration_ms == 240000
        assert track.album_art_url == 'https://i.scdn.co/image/medium'

    def test_from_api_response_single_image(self):
        data = {
            'id': 'abc', 'uri': 'spotify:track:abc', 'name': 'Song',
            'duration_ms': 100000,
            'artists': [{'name': 'Artist'}],
            'album': {'images': [{'url': 'https://example.com/only.jpg'}]}
        }
        track = SpotifyTrack.from_api_response(data)
        assert track.album_art_url == 'https://example.com/only.jpg'

    def test_from_api_response_no_album(self):
        data = {
            'id': 'abc', 'uri': 'spotify:track:abc', 'name': 'Song',
            'duration_ms': 100000,
            'artists': [{'name': 'Artist'}],
        }
        track = SpotifyTrack.from_api_response(data)
        assert track.album_art_url is None

    def test_from_api_response_missing_fields(self):
        with pytest.raises(ValidationError):
            SpotifyTrack.from_api_response({'id': 'abc'})


class TestSpotifyServiceDeviceCache:
    @patch('services.spotify_service.spotipy.Spotify')
    @patch('services.spotify_service.SpotifyOAuth')
    def test_cache_valid(self, mock_oauth, mock_spotify):
        service = SpotifyService('id', 'secret', 'uri', 'scope')
        service._cached_device_id = 'dev1'
        service._cached_device_name = 'My Device'
        service._device_cache_time = time.time()
        assert service._is_device_cache_valid() is True

    @patch('services.spotify_service.spotipy.Spotify')
    @patch('services.spotify_service.SpotifyOAuth')
    def test_cache_expired(self, mock_oauth, mock_spotify):
        service = SpotifyService('id', 'secret', 'uri', 'scope')
        service._cached_device_id = 'dev1'
        service._device_cache_time = time.time() - 600  # 10 min ago
        assert service._is_device_cache_valid() is False

    @patch('services.spotify_service.spotipy.Spotify')
    @patch('services.spotify_service.SpotifyOAuth')
    def test_cache_empty(self, mock_oauth, mock_spotify):
        service = SpotifyService('id', 'secret', 'uri', 'scope')
        assert service._is_device_cache_valid() is False


class TestSpotifyServiceDevices:
    @patch('services.spotify_service.spotipy.Spotify')
    @patch('services.spotify_service.SpotifyOAuth')
    def test_preferred_device_found(self, mock_oauth, mock_spotify_cls):
        client = MagicMock()
        mock_spotify_cls.return_value = client
        client.devices.return_value = {
            'devices': [
                {'id': 'dev1', 'name': "Kenny's MacBook Air", 'is_active': False, 'supports_volume': True},
                {'id': 'dev2', 'name': 'Speaker', 'is_active': True, 'supports_volume': True},
            ]
        }

        service = SpotifyService('id', 'secret', 'uri', 'scope')
        service.client = client
        dev_id, dev_name = service.get_and_activate_device(preferred_name="Kenny's MacBook")
        assert dev_id == 'dev1'
        assert "Kenny" in dev_name
        client.transfer_playback.assert_called_once()

    @patch('services.spotify_service.spotipy.Spotify')
    @patch('services.spotify_service.SpotifyOAuth')
    def test_fallback_to_active(self, mock_oauth, mock_spotify_cls):
        client = MagicMock()
        mock_spotify_cls.return_value = client
        client.devices.return_value = {
            'devices': [
                {'id': 'dev2', 'name': 'Speaker', 'is_active': True, 'supports_volume': True},
            ]
        }

        service = SpotifyService('id', 'secret', 'uri', 'scope')
        service.client = client
        dev_id, dev_name = service.get_and_activate_device(preferred_name="Nonexistent")
        assert dev_id == 'dev2'

    @patch('services.spotify_service.spotipy.Spotify')
    @patch('services.spotify_service.SpotifyOAuth')
    def test_no_devices(self, mock_oauth, mock_spotify_cls):
        client = MagicMock()
        mock_spotify_cls.return_value = client
        client.devices.return_value = {'devices': []}

        service = SpotifyService('id', 'secret', 'uri', 'scope')
        service.client = client
        dev_id, dev_name = service.get_and_activate_device()
        assert dev_id is None
        assert dev_name is None

    @patch('services.spotify_service.spotipy.Spotify')
    @patch('services.spotify_service.SpotifyOAuth')
    def test_no_volume_devices(self, mock_oauth, mock_spotify_cls):
        client = MagicMock()
        mock_spotify_cls.return_value = client
        client.devices.return_value = {
            'devices': [{'id': 'dev1', 'name': 'TV', 'is_active': True, 'supports_volume': False}]
        }

        service = SpotifyService('id', 'secret', 'uri', 'scope')
        service.client = client
        dev_id, dev_name = service.get_and_activate_device()
        assert dev_id is None


class TestSpotifyServiceSearch:
    @patch('services.spotify_service.spotipy.Spotify')
    @patch('services.spotify_service.SpotifyOAuth')
    def test_search_found(self, mock_oauth, mock_spotify_cls):
        client = MagicMock()
        mock_spotify_cls.return_value = client
        client.search.return_value = {
            'tracks': {'items': [{
                'id': 'abc', 'uri': 'spotify:track:abc', 'name': 'Song',
                'duration_ms': 200000, 'artists': [{'name': 'Artist'}],
                'album': {'images': []}
            }]}
        }

        service = SpotifyService('id', 'secret', 'uri', 'scope')
        service.client = client
        result = service.search_track("Artist - Song")
        assert result is not None
        assert result.name == 'Song'

    @patch('services.spotify_service.spotipy.Spotify')
    @patch('services.spotify_service.SpotifyOAuth')
    def test_search_not_found(self, mock_oauth, mock_spotify_cls):
        client = MagicMock()
        mock_spotify_cls.return_value = client
        client.search.return_value = {'tracks': {'items': []}}

        service = SpotifyService('id', 'secret', 'uri', 'scope')
        service.client = client
        result = service.search_track("Nonexistent")
        assert result is None

    @patch('services.spotify_service.spotipy.Spotify')
    @patch('services.spotify_service.SpotifyOAuth')
    def test_search_api_error(self, mock_oauth, mock_spotify_cls):
        client = MagicMock()
        mock_spotify_cls.return_value = client
        client.search.side_effect = Exception("API error")

        service = SpotifyService('id', 'secret', 'uri', 'scope')
        service.client = client
        result = service.search_track("query")
        assert result is None


class TestSpotifyServicePlayback:
    @patch('services.spotify_service.spotipy.Spotify')
    @patch('services.spotify_service.SpotifyOAuth')
    def test_start_playback_success(self, mock_oauth, mock_spotify_cls):
        client = MagicMock()
        mock_spotify_cls.return_value = client

        service = SpotifyService('id', 'secret', 'uri', 'scope')
        service.client = client
        result = service.start_playback('spotify:track:abc', 'dev1', 30000, 50)
        assert result is True
        client.start_playback.assert_called_once()
        client.volume.assert_called_once_with(50, device_id='dev1')

    @patch('services.spotify_service.spotipy.Spotify')
    @patch('services.spotify_service.SpotifyOAuth')
    def test_start_playback_failure(self, mock_oauth, mock_spotify_cls):
        client = MagicMock()
        mock_spotify_cls.return_value = client
        client.start_playback.side_effect = Exception("Playback error")

        service = SpotifyService('id', 'secret', 'uri', 'scope')
        service.client = client
        result = service.start_playback('spotify:track:abc', 'dev1')
        assert result is False


class TestSpotifyServiceInterruption:
    @patch('services.spotify_service.spotipy.Spotify')
    @patch('services.spotify_service.SpotifyOAuth')
    def test_no_session(self, mock_oauth, mock_spotify_cls):
        client = MagicMock()
        mock_spotify_cls.return_value = client
        client.current_playback.return_value = None

        service = SpotifyService('id', 'secret', 'uri', 'scope')
        service.client = client
        allowed, msg = service.is_interruption_allowed()
        assert allowed is True

    @patch('services.spotify_service.spotipy.Spotify')
    @patch('services.spotify_service.SpotifyOAuth')
    def test_music_playing(self, mock_oauth, mock_spotify_cls):
        client = MagicMock()
        mock_spotify_cls.return_value = client
        client.current_playback.return_value = {'is_playing': True}

        service = SpotifyService('id', 'secret', 'uri', 'scope')
        service.client = client
        allowed, msg = service.is_interruption_allowed()
        assert allowed is False

    @patch('services.spotify_service.spotipy.Spotify')
    @patch('services.spotify_service.SpotifyOAuth')
    def test_music_paused(self, mock_oauth, mock_spotify_cls):
        client = MagicMock()
        mock_spotify_cls.return_value = client
        client.current_playback.return_value = {'is_playing': False}

        service = SpotifyService('id', 'secret', 'uri', 'scope')
        service.client = client
        allowed, msg = service.is_interruption_allowed()
        assert allowed is True
