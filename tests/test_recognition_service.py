"""Tests for services/recognition_service.py - Shazam recognition wrapper."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from services.recognition_service import RecognizedTrack, RecognitionService


class TestShazamioContract:
    """Contract tests that verify the real shazamio library (no mocking).

    These catch version/API mismatches between our code and the installed package.
    """

    def test_shazam_importable(self):
        from shazamio import Shazam
        assert Shazam is not None

    def test_shazam_has_recognize_method(self):
        from shazamio import Shazam
        shazam = Shazam()
        assert hasattr(shazam, 'recognize'), (
            "Shazam is missing 'recognize' method — "
            "installed shazamio version may be too old"
        )

    def test_shazamio_version(self):
        from importlib.metadata import version
        installed = version('shazamio')
        assert installed == '0.7.0', (
            f"Expected shazamio 0.7.0, got {installed}"
        )


class TestRecognizedTrack:
    def test_artist_property(self):
        track = RecognizedTrack(
            track_data={'subtitle': 'Test Artist', 'title': 'Test Song'},
            track_string='Test Artist - Test Song'
        )
        assert track.artist == 'Test Artist'

    def test_title_property(self):
        track = RecognizedTrack(
            track_data={'subtitle': 'Test Artist', 'title': 'Test Song'},
            track_string='Test Artist - Test Song'
        )
        assert track.title == 'Test Song'

    def test_missing_artist_default(self):
        track = RecognizedTrack(track_data={}, track_string='Unknown')
        assert track.artist == 'Unknown Artist'

    def test_missing_title_default(self):
        track = RecognizedTrack(track_data={}, track_string='Unknown')
        assert track.title == 'Unknown Title'


class TestRecognitionService:
    @patch('services.recognition_service.Shazam')
    def test_recognize_found(self, mock_shazam_cls, valid_shazam_response):
        mock_shazam = MagicMock()
        mock_shazam.recognize = AsyncMock(return_value=valid_shazam_response)
        mock_shazam_cls.return_value = mock_shazam

        service = RecognitionService()
        result = service.recognize('/tmp/test.wav')

        assert result is not None
        assert result.track_string == 'Test Artist - Test Song'
        assert result.artist == 'Test Artist'
        assert result.title == 'Test Song'

    @patch('services.recognition_service.Shazam')
    def test_recognize_not_found(self, mock_shazam_cls):
        mock_shazam = MagicMock()
        mock_shazam.recognize = AsyncMock(return_value={'matches': []})
        mock_shazam_cls.return_value = mock_shazam

        service = RecognitionService()
        result = service.recognize('/tmp/test.wav')
        assert result is None

    @patch('services.recognition_service.Shazam')
    def test_recognize_api_error(self, mock_shazam_cls):
        mock_shazam = MagicMock()
        mock_shazam.recognize = AsyncMock(side_effect=Exception("Shazam API error"))
        mock_shazam_cls.return_value = mock_shazam

        service = RecognitionService()
        with pytest.raises(Exception, match="Shazam API error"):
            service.recognize('/tmp/test.wav')
