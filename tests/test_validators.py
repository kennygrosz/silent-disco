"""Tests for utils/validators.py - Input validation functions."""

import os
import pytest
from utils.validators import (
    ValidationError,
    validate_duration,
    validate_interval,
    validate_file_path,
    validate_directory_path,
    validate_spotify_track,
    validate_playback_position,
    validate_volume,
)


class TestValidateDuration:
    def test_valid_duration(self):
        assert validate_duration(10) == 10

    def test_min_boundary(self):
        assert validate_duration(1) == 1

    def test_max_boundary(self):
        assert validate_duration(3600) == 3600

    def test_too_short(self):
        with pytest.raises(ValidationError, match="at least"):
            validate_duration(0)

    def test_too_long(self):
        with pytest.raises(ValidationError, match="at most"):
            validate_duration(3601)

    def test_wrong_type(self):
        with pytest.raises(ValidationError, match="integer"):
            validate_duration("10")

    def test_custom_bounds(self):
        assert validate_duration(5, min_seconds=5, max_seconds=10) == 5


class TestValidateInterval:
    def test_valid_interval(self):
        assert validate_interval(60, snippet_duration=10) == 60

    def test_equal_to_snippet(self):
        assert validate_interval(10, snippet_duration=10) == 10

    def test_less_than_snippet(self):
        with pytest.raises(ValidationError, match=">="):
            validate_interval(5, snippet_duration=10)

    def test_wrong_type(self):
        with pytest.raises(ValidationError, match="integer"):
            validate_interval(60.0, snippet_duration=10)


class TestValidateFilePath:
    def test_valid_path(self):
        assert validate_file_path("/tmp/test.wav") == "/tmp/test.wav"

    def test_empty_path(self):
        with pytest.raises(ValidationError, match="empty"):
            validate_file_path("")

    def test_wrong_type(self):
        with pytest.raises(ValidationError, match="string"):
            validate_file_path(123)

    def test_must_exist_missing(self):
        with pytest.raises(ValidationError, match="does not exist"):
            validate_file_path("/nonexistent/file.wav", must_exist=True)

    def test_wrong_extension(self):
        with pytest.raises(ValidationError, match=".wav"):
            validate_file_path("/tmp/test.mp3", extension=".wav")

    def test_correct_extension(self):
        assert validate_file_path("/tmp/test.wav", extension=".wav") == "/tmp/test.wav"


class TestValidateDirectoryPath:
    def test_valid_existing_dir(self, tmp_path):
        assert validate_directory_path(str(tmp_path)) == str(tmp_path)

    def test_empty_path(self):
        with pytest.raises(ValidationError, match="empty"):
            validate_directory_path("")

    def test_wrong_type(self):
        with pytest.raises(ValidationError, match="string"):
            validate_directory_path(123)

    def test_nonexistent_no_create(self):
        with pytest.raises(ValidationError, match="does not exist"):
            validate_directory_path("/nonexistent/dir")

    def test_create_if_missing(self, tmp_path):
        new_dir = str(tmp_path / "new_subdir")
        result = validate_directory_path(new_dir, create_if_missing=True)
        assert result == new_dir
        assert os.path.isdir(new_dir)

    def test_path_is_file_not_dir(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x")
        with pytest.raises(ValidationError, match="not a directory"):
            validate_directory_path(str(f))


class TestValidateSpotifyTrack:
    def test_valid_track(self, valid_spotify_track_data):
        result = validate_spotify_track(valid_spotify_track_data)
        assert result == valid_spotify_track_data

    def test_missing_id(self, valid_spotify_track_data):
        del valid_spotify_track_data['id']
        with pytest.raises(ValidationError, match="id"):
            validate_spotify_track(valid_spotify_track_data)

    def test_missing_uri(self, valid_spotify_track_data):
        del valid_spotify_track_data['uri']
        with pytest.raises(ValidationError, match="uri"):
            validate_spotify_track(valid_spotify_track_data)

    def test_missing_artists(self, valid_spotify_track_data):
        del valid_spotify_track_data['artists']
        with pytest.raises(ValidationError, match="artist"):
            validate_spotify_track(valid_spotify_track_data)

    def test_empty_artists(self, valid_spotify_track_data):
        valid_spotify_track_data['artists'] = []
        with pytest.raises(ValidationError, match="artist"):
            validate_spotify_track(valid_spotify_track_data)

    def test_artists_not_list(self, valid_spotify_track_data):
        valid_spotify_track_data['artists'] = "not a list"
        with pytest.raises(ValidationError, match="list"):
            validate_spotify_track(valid_spotify_track_data)

    def test_artist_no_name(self, valid_spotify_track_data):
        valid_spotify_track_data['artists'] = [{'id': 'x'}]
        with pytest.raises(ValidationError, match="name"):
            validate_spotify_track(valid_spotify_track_data)

    def test_not_dict(self):
        with pytest.raises(ValidationError, match="dictionary"):
            validate_spotify_track("not a dict")


class TestValidatePlaybackPosition:
    def test_valid_position(self):
        assert validate_playback_position(30000, 240000) == 30000

    def test_clamps_negative(self):
        assert validate_playback_position(-100, 240000) == 0

    def test_clamps_over_duration(self):
        assert validate_playback_position(300000, 240000) == 240000

    def test_zero_position(self):
        assert validate_playback_position(0, 240000) == 0

    def test_negative_duration(self):
        with pytest.raises(ValidationError, match="negative"):
            validate_playback_position(0, -1)

    def test_wrong_type_position(self):
        with pytest.raises(ValidationError, match="integer"):
            validate_playback_position(30.0, 240000)

    def test_wrong_type_duration(self):
        with pytest.raises(ValidationError, match="integer"):
            validate_playback_position(30000, 240000.0)


class TestValidateVolume:
    def test_valid_volume(self):
        assert validate_volume(50) == 50

    def test_min_volume(self):
        assert validate_volume(0) == 0

    def test_max_volume(self):
        assert validate_volume(100) == 100

    def test_negative(self):
        with pytest.raises(ValidationError, match="between 0 and 100"):
            validate_volume(-1)

    def test_over_100(self):
        with pytest.raises(ValidationError, match="between 0 and 100"):
            validate_volume(101)

    def test_wrong_type(self):
        with pytest.raises(ValidationError, match="integer"):
            validate_volume(50.0)
