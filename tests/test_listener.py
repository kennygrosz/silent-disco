"""Tests for listener/listener.py - Audio recording."""

import threading
import pytest
from unittest.mock import patch, MagicMock, call
from listener.listener import record_audio


class TestRecordAudio:
    @patch('listener.listener.wave.open')
    @patch('listener.listener.pyaudio.PyAudio')
    def test_normal_recording(self, mock_pyaudio_cls, mock_wave_open):
        # Setup mocks
        mock_p = MagicMock()
        mock_pyaudio_cls.return_value = mock_p
        mock_stream = MagicMock()
        mock_p.open.return_value = mock_stream
        mock_stream.read.return_value = b'\x00' * 1024
        mock_p.get_sample_size.return_value = 2

        mock_wf = MagicMock()
        mock_wave_open.return_value = mock_wf

        result = record_audio('/tmp/test.wav', duration=2)

        assert 'succeeded' in result.lower() or 'Recording' in result
        mock_stream.read.assert_called()
        mock_wf.writeframes.assert_called_once()
        # Cleanup happened
        mock_stream.close.assert_called_once()
        mock_p.terminate.assert_called_once()
        mock_wf.close.assert_called_once()

    @patch('listener.listener.wave.open')
    @patch('listener.listener.pyaudio.PyAudio')
    def test_stop_event_interrupts(self, mock_pyaudio_cls, mock_wave_open):
        mock_p = MagicMock()
        mock_pyaudio_cls.return_value = mock_p
        mock_stream = MagicMock()
        mock_p.open.return_value = mock_stream
        mock_stream.read.return_value = b'\x00' * 1024

        # Create a stop event that's already set
        stop_event = threading.Event()
        stop_event.set()

        result = record_audio('/tmp/test.wav', duration=10, stop_event=stop_event)

        assert 'interrupted' in result.lower()
        # Should NOT write a WAV file when interrupted
        mock_wave_open.assert_not_called()

    @patch('listener.listener.wave.open')
    @patch('listener.listener.pyaudio.PyAudio')
    def test_cleanup_on_error(self, mock_pyaudio_cls, mock_wave_open):
        mock_p = MagicMock()
        mock_pyaudio_cls.return_value = mock_p
        mock_stream = MagicMock()
        mock_p.open.return_value = mock_stream
        mock_stream.read.side_effect = Exception("Audio error")

        with pytest.raises(Exception, match="Audio error"):
            record_audio('/tmp/test.wav', duration=2)

        # Cleanup should still happen
        mock_stream.close.assert_called_once()
        mock_p.terminate.assert_called_once()

    @patch('listener.listener.wave.open')
    @patch('listener.listener.pyaudio.PyAudio')
    def test_chunk_count(self, mock_pyaudio_cls, mock_wave_open):
        """Verify correct number of chunks are read."""
        mock_p = MagicMock()
        mock_pyaudio_cls.return_value = mock_p
        mock_stream = MagicMock()
        mock_p.open.return_value = mock_stream
        mock_stream.read.return_value = b'\x00' * 1024
        mock_p.get_sample_size.return_value = 2
        mock_wf = MagicMock()
        mock_wave_open.return_value = mock_wf

        record_audio('/tmp/test.wav', duration=1)

        # RATE=44100, CHUNK=1024, duration=1 -> 44100/1024 * 1 ≈ 43 chunks
        expected_chunks = int(44100 / 1024 * 1)
        assert mock_stream.read.call_count == expected_chunks
