"""Shared test fixtures for Silent Disco test suite."""

import pytest
from unittest.mock import MagicMock, patch
from models.snippet import Snippet, SnippetState


@pytest.fixture
def sample_snippet(tmp_path):
    """A fresh Snippet in CREATED state."""
    return Snippet(output_folder=str(tmp_path), snippet_duration=10)


@pytest.fixture
def recorded_snippet(sample_snippet):
    """A Snippet that has been recorded."""
    sample_snippet.mark_recorded()
    return sample_snippet


@pytest.fixture
def recognized_snippet(recorded_snippet):
    """A Snippet that has been recognized."""
    recorded_snippet.mark_recognized("Test Artist - Test Song")
    return recorded_snippet


@pytest.fixture
def valid_spotify_track_data():
    """Mock Spotify API track response."""
    return {
        'id': 'abc123',
        'uri': 'spotify:track:abc123',
        'name': 'Test Song',
        'duration_ms': 240000,
        'artists': [{'name': 'Test Artist'}],
        'album': {
            'images': [
                {'url': 'https://i.scdn.co/image/large', 'height': 640},
                {'url': 'https://i.scdn.co/image/medium', 'height': 300},
                {'url': 'https://i.scdn.co/image/small', 'height': 64},
            ]
        }
    }


@pytest.fixture
def valid_shazam_response():
    """Mock Shazam API recognition response."""
    return {
        'track': {
            'title': 'Test Song',
            'subtitle': 'Test Artist',
            'key': '12345',
        }
    }


@pytest.fixture
def mock_spotify_client():
    """Mocked spotipy.Spotify client."""
    client = MagicMock()
    client.devices.return_value = {
        'devices': [
            {
                'id': 'device1',
                'name': "Kenny's MacBook Air",
                'is_active': True,
                'supports_volume': True,
            }
        ]
    }
    client.search.return_value = {
        'tracks': {
            'items': [{
                'id': 'abc123',
                'uri': 'spotify:track:abc123',
                'name': 'Test Song',
                'duration_ms': 240000,
                'artists': [{'name': 'Test Artist'}],
                'album': {'images': [{'url': 'https://example.com/art.jpg'}]}
            }]
        }
    }
    client.current_playback.return_value = None
    return client
