"""Snippet model for Silent Disco application.

This module provides the Snippet model representing an audio recording
with state tracking and proper type hints.
"""

from datetime import datetime
from pathlib import Path
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field


class SnippetState(Enum):
    """State of a snippet in the processing pipeline."""
    CREATED = "created"
    RECORDED = "recorded"
    RECOGNIZED = "recognized"
    UNRECOGNIZED = "unrecognized"
    QUEUEABLE = "queueable"
    QUEUED = "queued"
    FAILED = "failed"


@dataclass
class Snippet:
    """Represents an audio snippet with state tracking.

    Attributes:
        output_folder: Directory where snippet will be saved
        snippet_duration: Duration of snippet in seconds
        timestamp: When snippet was created
        filename: Name of the WAV file
        filepath: Full path to the WAV file
        state: Current processing state
        track_string: Recognized track string (Artist - Title)
        song_id: Spotify track ID
        song_uri: Spotify track URI
        song_name: Song name from Spotify
        song_artist: Artist name from Spotify
        duration_ms: Song duration in milliseconds
    """

    output_folder: str
    snippet_duration: int = 5

    # Auto-generated fields
    timestamp: datetime = field(default_factory=datetime.now)
    state: SnippetState = field(default=SnippetState.CREATED)

    # Populated during processing
    track_string: Optional[str] = None
    song_id: Optional[str] = None
    song_uri: Optional[str] = None
    song_name: Optional[str] = None
    song_artist: Optional[str] = None
    duration_ms: Optional[int] = None

    def __post_init__(self):
        """Initialize computed fields."""
        self.timestamp_str = self.timestamp.strftime("%Y%m%d_%H%M%S")
        self.filename = f'snippet_{self.timestamp_str}.wav'

        # Use Path for proper path handling
        self._filepath = Path(self.output_folder) / self.filename

    @property
    def filepath(self) -> Path:
        """Get snippet file path as Path object."""
        return self._filepath

    @property
    def filepath_str(self) -> str:
        """Get snippet file path as string (for compatibility)."""
        return str(self._filepath)

    @property
    def is_recorded(self) -> bool:
        """Check if snippet has been recorded."""
        return self.state in [
            SnippetState.RECORDED,
            SnippetState.RECOGNIZED,
            SnippetState.QUEUEABLE,
            SnippetState.QUEUED
        ]

    @property
    def is_recognized(self) -> bool:
        """Check if snippet has been recognized."""
        return self.state in [
            SnippetState.RECOGNIZED,
            SnippetState.QUEUEABLE,
            SnippetState.QUEUED
        ]

    @property
    def is_queueable(self) -> bool:
        """Check if snippet can be queued."""
        return self.state == SnippetState.QUEUEABLE

    @property
    def is_queued(self) -> bool:
        """Check if snippet has been queued."""
        return self.state == SnippetState.QUEUED

    def mark_recorded(self):
        """Mark snippet as recorded."""
        if self.state == SnippetState.CREATED:
            self.state = SnippetState.RECORDED

    def mark_recognized(self, track_string: str):
        """Mark snippet as recognized.

        Args:
            track_string: Recognized track string (Artist - Title)
        """
        if self.state == SnippetState.RECORDED:
            self.state = SnippetState.RECOGNIZED
            self.track_string = track_string

    def mark_unrecognized(self):
        """Mark snippet as unrecognized."""
        if self.state == SnippetState.RECORDED:
            self.state = SnippetState.UNRECOGNIZED
            self.track_string = "unrecognized"

    def mark_queueable(self):
        """Mark snippet as queueable."""
        if self.state == SnippetState.RECOGNIZED:
            self.state = SnippetState.QUEUEABLE

    def mark_queued(self):
        """Mark snippet as queued."""
        if self.state == SnippetState.QUEUEABLE:
            self.state = SnippetState.QUEUED

    def mark_failed(self):
        """Mark snippet processing as failed."""
        self.state = SnippetState.FAILED

    def set_spotify_info(
        self,
        song_id: str,
        song_uri: str,
        song_name: str,
        song_artist: str,
        duration_ms: int
    ):
        """Set Spotify track information.

        Args:
            song_id: Spotify track ID
            song_uri: Spotify track URI
            song_name: Song name
            song_artist: Artist name
            duration_ms: Song duration in milliseconds
        """
        self.song_id = song_id
        self.song_uri = song_uri
        self.song_name = song_name
        self.song_artist = song_artist
        self.duration_ms = duration_ms

    def __repr__(self) -> str:
        """String representation of Snippet."""
        return f"Snippet(file={self.filename}, state={self.state.value}, track={self.track_string})"
