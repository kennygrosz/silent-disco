"""Tests for services/recognition_service.py - Shazam recognition wrapper."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from services.recognition_service import RecognizedTrack, RecognitionService


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
        mock_shazam.recognize_song = AsyncMock(return_value=valid_shazam_response)
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
        mock_shazam.recognize_song = AsyncMock(return_value={'matches': []})
        mock_shazam_cls.return_value = mock_shazam

        service = RecognitionService()
        result = service.recognize('/tmp/test.wav')
        assert result is None

    @patch('services.recognition_service.Shazam')
    def test_recognize_api_error(self, mock_shazam_cls):
        mock_shazam = MagicMock()
        mock_shazam.recognize_song = AsyncMock(side_effect=Exception("Shazam API error"))
        mock_shazam_cls.return_value = mock_shazam

        service = RecognitionService()
        with pytest.raises(Exception, match="Shazam API error"):
            service.recognize('/tmp/test.wav')
