"""Tests for models/snippet.py - Snippet state machine and data model."""

from pathlib import Path
from models.snippet import Snippet, SnippetState


class TestSnippetCreation:
    def test_initial_state_is_created(self, sample_snippet):
        assert sample_snippet.state == SnippetState.CREATED

    def test_generates_filename(self, sample_snippet):
        assert sample_snippet.filename.startswith('snippet_')
        assert sample_snippet.filename.endswith('.wav')

    def test_generates_timestamp_str(self, sample_snippet):
        assert len(sample_snippet.timestamp_str) == 15  # YYYYMMDD_HHMMSS

    def test_filepath_is_path_object(self, sample_snippet):
        assert isinstance(sample_snippet.filepath, Path)

    def test_filepath_str_is_string(self, sample_snippet):
        assert isinstance(sample_snippet.filepath_str, str)

    def test_filepath_contains_output_folder(self, sample_snippet):
        assert sample_snippet.output_folder in sample_snippet.filepath_str

    def test_snippet_duration_stored(self, sample_snippet):
        assert sample_snippet.snippet_duration == 10

    def test_optional_fields_are_none(self, sample_snippet):
        assert sample_snippet.track_string is None
        assert sample_snippet.song_id is None
        assert sample_snippet.song_uri is None
        assert sample_snippet.song_name is None
        assert sample_snippet.song_artist is None
        assert sample_snippet.duration_ms is None
        assert sample_snippet.album_art_url is None


class TestSnippetStateTransitions:
    def test_happy_path(self, sample_snippet):
        """CREATED -> RECORDED -> RECOGNIZED -> QUEUEABLE -> QUEUED"""
        snip = sample_snippet
        assert snip.state == SnippetState.CREATED

        snip.mark_recorded()
        assert snip.state == SnippetState.RECORDED

        snip.mark_recognized("Artist - Song")
        assert snip.state == SnippetState.RECOGNIZED
        assert snip.track_string == "Artist - Song"

        snip.mark_queueable()
        assert snip.state == SnippetState.QUEUEABLE

        snip.mark_queued()
        assert snip.state == SnippetState.QUEUED

    def test_unrecognized_path(self, recorded_snippet):
        recorded_snippet.mark_unrecognized()
        assert recorded_snippet.state == SnippetState.UNRECOGNIZED
        assert recorded_snippet.track_string == "unrecognized"

    def test_failed_from_any_state(self, sample_snippet):
        sample_snippet.mark_failed()
        assert sample_snippet.state == SnippetState.FAILED

    def test_recorded_guard_wrong_state(self, recorded_snippet):
        """mark_recorded() is no-op if not CREATED."""
        recorded_snippet.mark_recorded()
        assert recorded_snippet.state == SnippetState.RECORDED  # unchanged

    def test_recognized_guard_wrong_state(self, sample_snippet):
        """mark_recognized() is no-op if not RECORDED."""
        sample_snippet.mark_recognized("Artist - Song")
        assert sample_snippet.state == SnippetState.CREATED
        assert sample_snippet.track_string is None

    def test_queueable_guard_wrong_state(self, recorded_snippet):
        """mark_queueable() is no-op if not RECOGNIZED."""
        recorded_snippet.mark_queueable()
        assert recorded_snippet.state == SnippetState.RECORDED

    def test_queued_guard_wrong_state(self, recognized_snippet):
        """mark_queued() is no-op if not QUEUEABLE."""
        recognized_snippet.mark_queued()
        assert recognized_snippet.state == SnippetState.RECOGNIZED


class TestSnippetProperties:
    def test_is_recorded(self, recorded_snippet):
        assert recorded_snippet.is_recorded is True

    def test_is_not_recorded_when_created(self, sample_snippet):
        assert sample_snippet.is_recorded is False

    def test_is_recognized(self, recognized_snippet):
        assert recognized_snippet.is_recognized is True

    def test_is_not_recognized_when_recorded(self, recorded_snippet):
        assert recorded_snippet.is_recognized is False

    def test_is_queueable(self, recognized_snippet):
        recognized_snippet.mark_queueable()
        assert recognized_snippet.is_queueable is True

    def test_is_queued(self, recognized_snippet):
        recognized_snippet.mark_queueable()
        recognized_snippet.mark_queued()
        assert recognized_snippet.is_queued is True


class TestSnippetSpotifyInfo:
    def test_set_spotify_info(self, sample_snippet):
        sample_snippet.set_spotify_info(
            song_id='abc123',
            song_uri='spotify:track:abc123',
            song_name='Test Song',
            song_artist='Test Artist',
            duration_ms=240000,
            album_art_url='https://example.com/art.jpg'
        )
        assert sample_snippet.song_id == 'abc123'
        assert sample_snippet.song_uri == 'spotify:track:abc123'
        assert sample_snippet.song_name == 'Test Song'
        assert sample_snippet.song_artist == 'Test Artist'
        assert sample_snippet.duration_ms == 240000
        assert sample_snippet.album_art_url == 'https://example.com/art.jpg'

    def test_set_spotify_info_no_art(self, sample_snippet):
        sample_snippet.set_spotify_info(
            song_id='abc123',
            song_uri='spotify:track:abc123',
            song_name='Test Song',
            song_artist='Test Artist',
            duration_ms=240000,
        )
        assert sample_snippet.album_art_url is None


class TestSnippetRepr:
    def test_repr_format(self, sample_snippet):
        r = repr(sample_snippet)
        assert 'Snippet(' in r
        assert 'state=created' in r
        assert 'track=None' in r
