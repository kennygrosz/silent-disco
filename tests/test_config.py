"""Tests for config.py - Configuration loading."""

import pytest
from unittest.mock import patch
from config import SpotifyConfig, AppConfig


class TestSpotifyConfig:
    @patch.dict('os.environ', {
        'SPOTIFY_CLIENT_ID': 'test_id',
        'SPOTIFY_CLIENT_SECRET': 'test_secret',
        'SPOTIFY_REDIRECT_URI': 'http://localhost:9999/callback',
        'SPOTIFY_DEFAULT_DEVICE_ID': 'device123',
    })
    def test_from_env_all_values(self):
        cfg = SpotifyConfig.from_env()
        assert cfg.client_id == 'test_id'
        assert cfg.client_secret == 'test_secret'
        assert cfg.redirect_uri == 'http://localhost:9999/callback'
        assert cfg.default_device_id == 'device123'

    @patch.dict('os.environ', {
        'SPOTIFY_CLIENT_ID': 'test_id',
        'SPOTIFY_CLIENT_SECRET': 'test_secret',
    }, clear=True)
    def test_from_env_defaults(self):
        cfg = SpotifyConfig.from_env()
        assert cfg.redirect_uri == 'http://localhost:8888/callback'
        assert cfg.default_device_id is None

    @patch.dict('os.environ', {
        'SPOTIFY_CLIENT_ID': '',
        'SPOTIFY_CLIENT_SECRET': 'test_secret',
    }, clear=True)
    def test_missing_client_id_raises(self):
        with pytest.raises(ValueError, match="Missing required Spotify credentials"):
            SpotifyConfig.from_env()

    @patch.dict('os.environ', {
        'SPOTIFY_CLIENT_ID': 'test_id',
        'SPOTIFY_CLIENT_SECRET': '',
    }, clear=True)
    def test_missing_client_secret_raises(self):
        with pytest.raises(ValueError, match="Missing required Spotify credentials"):
            SpotifyConfig.from_env()


class TestAppConfig:
    def test_defaults(self):
        cfg = AppConfig()
        assert cfg.snippet_duration == 10
        assert cfg.interval_duration == 60
        assert cfg.output_folder == 'song_snippets'
        assert cfg.duplicate_check_size == 10
        assert cfg.playback_offset_ms == 31000
        assert cfg.volume_preview == 40
