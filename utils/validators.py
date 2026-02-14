"""Input validation utilities for Silent Disco application.

This module provides validation functions for user inputs, configuration values,
and external data to prevent crashes and ensure data integrity.
"""

import os
from typing import Optional, Dict, Any


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


def validate_duration(duration: int, min_seconds: int = 1, max_seconds: int = 3600) -> int:
    """Validate audio recording duration.

    Args:
        duration: Duration in seconds
        min_seconds: Minimum allowed duration (default: 1)
        max_seconds: Maximum allowed duration (default: 3600 = 1 hour)

    Returns:
        Validated duration

    Raises:
        ValidationError: If duration is out of valid range
    """
    if not isinstance(duration, int):
        raise ValidationError(f"Duration must be an integer, got {type(duration).__name__}")

    if duration < min_seconds:
        raise ValidationError(f"Duration must be at least {min_seconds} seconds, got {duration}")

    if duration > max_seconds:
        raise ValidationError(f"Duration must be at most {max_seconds} seconds, got {duration}")

    return duration


def validate_interval(interval: int, snippet_duration: int) -> int:
    """Validate interval duration between recordings.

    Args:
        interval: Interval in seconds
        snippet_duration: Duration of each recording snippet

    Returns:
        Validated interval

    Raises:
        ValidationError: If interval is invalid
    """
    if not isinstance(interval, int):
        raise ValidationError(f"Interval must be an integer, got {type(interval).__name__}")

    if interval < snippet_duration:
        raise ValidationError(
            f"Interval ({interval}s) must be >= snippet duration ({snippet_duration}s)"
        )

    return interval


def validate_file_path(filepath: str, must_exist: bool = False, extension: Optional[str] = None) -> str:
    """Validate file path.

    Args:
        filepath: Path to validate
        must_exist: If True, file must already exist (default: False)
        extension: Required file extension (e.g., '.wav') (default: None)

    Returns:
        Validated file path

    Raises:
        ValidationError: If path is invalid
    """
    if not isinstance(filepath, str):
        raise ValidationError(f"File path must be a string, got {type(filepath).__name__}")

    if not filepath:
        raise ValidationError("File path cannot be empty")

    if must_exist and not os.path.exists(filepath):
        raise ValidationError(f"File does not exist: {filepath}")

    if extension and not filepath.endswith(extension):
        raise ValidationError(f"File must have {extension} extension, got: {filepath}")

    return filepath


def validate_directory_path(dirpath: str, create_if_missing: bool = False) -> str:
    """Validate directory path.

    Args:
        dirpath: Directory path to validate
        create_if_missing: If True, create directory if it doesn't exist (default: False)

    Returns:
        Validated directory path

    Raises:
        ValidationError: If path is invalid
    """
    if not isinstance(dirpath, str):
        raise ValidationError(f"Directory path must be a string, got {type(dirpath).__name__}")

    if not dirpath:
        raise ValidationError("Directory path cannot be empty")

    if not os.path.exists(dirpath):
        if create_if_missing:
            try:
                os.makedirs(dirpath, exist_ok=True)
            except Exception as e:
                raise ValidationError(f"Failed to create directory {dirpath}: {e}")
        else:
            raise ValidationError(f"Directory does not exist: {dirpath}")

    if not os.path.isdir(dirpath):
        raise ValidationError(f"Path exists but is not a directory: {dirpath}")

    return dirpath


def validate_spotify_track(track_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate Spotify track data contains required fields.

    Args:
        track_data: Track data dictionary from Spotify API

    Returns:
        Validated track data

    Raises:
        ValidationError: If required fields are missing
    """
    if not isinstance(track_data, dict):
        raise ValidationError(f"Track data must be a dictionary, got {type(track_data).__name__}")

    required_fields = ['id', 'uri', 'name', 'duration_ms']

    missing_fields = [field for field in required_fields if field not in track_data]

    if missing_fields:
        raise ValidationError(f"Track data missing required fields: {', '.join(missing_fields)}")

    # Validate artists array exists and has at least one artist
    if 'artists' not in track_data or not track_data['artists']:
        raise ValidationError("Track data must have at least one artist")

    if not isinstance(track_data['artists'], list):
        raise ValidationError("Track artists must be a list")

    if 'name' not in track_data['artists'][0]:
        raise ValidationError("Track artist must have a name")

    return track_data


def validate_playback_position(position_ms: int, duration_ms: int) -> int:
    """Validate playback position is within track duration.

    Args:
        position_ms: Playback position in milliseconds
        duration_ms: Track duration in milliseconds

    Returns:
        Validated position (clamped to [0, duration_ms])

    Raises:
        ValidationError: If inputs are invalid
    """
    if not isinstance(position_ms, int):
        raise ValidationError(f"Position must be an integer, got {type(position_ms).__name__}")

    if not isinstance(duration_ms, int):
        raise ValidationError(f"Duration must be an integer, got {type(duration_ms).__name__}")

    if duration_ms < 0:
        raise ValidationError(f"Duration cannot be negative: {duration_ms}")

    # Clamp position to valid range [0, duration_ms]
    return max(0, min(position_ms, duration_ms))


def validate_volume(volume: int) -> int:
    """Validate volume level.

    Args:
        volume: Volume level (0-100)

    Returns:
        Validated volume

    Raises:
        ValidationError: If volume is out of range
    """
    if not isinstance(volume, int):
        raise ValidationError(f"Volume must be an integer, got {type(volume).__name__}")

    if volume < 0 or volume > 100:
        raise ValidationError(f"Volume must be between 0 and 100, got {volume}")

    return volume
