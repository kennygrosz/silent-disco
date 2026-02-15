"""Recognition service layer for Silent Disco application.

This module provides audio recognition using Shazam with proper
async handling and event loop management.
"""

import asyncio
from typing import Optional, Tuple
from dataclasses import dataclass
from shazamio import Shazam
from utils.logging_config import get_logger


logger = get_logger()


@dataclass
class RecognizedTrack:
    """Structured representation of a recognized track."""
    track_data: dict
    track_string: str  # Format: "Artist - Title"

    @property
    def artist(self) -> str:
        """Get artist name from track data."""
        return self.track_data.get('subtitle', 'Unknown Artist')

    @property
    def title(self) -> str:
        """Get track title from track data."""
        return self.track_data.get('title', 'Unknown Title')


class RecognitionService:
    """Service for audio recognition using Shazam."""

    def __init__(self):
        """Initialize recognition service."""
        self.shazam = Shazam()

    async def recognize_async(self, audio_filepath: str) -> Optional[RecognizedTrack]:
        """Recognize audio file asynchronously.

        Args:
            audio_filepath: Path to audio file to recognize

        Returns:
            RecognizedTrack if recognized, None otherwise
        """
        try:
            logger.debug(f"Recognizing audio: {audio_filepath}")
            alldata = await self.shazam.recognize(audio_filepath)

            if 'track' in alldata:
                # Get artist and track data
                trackdata = alldata['track']
                track_string = f"{trackdata['subtitle']} - {trackdata['title']}"

                logger.debug(f"Recognized: {track_string}")
                return RecognizedTrack(
                    track_data=trackdata,
                    track_string=track_string
                )
            else:
                logger.debug("Song unidentified by Shazam")
                return None

        except Exception as e:
            logger.error(f"Recognition failed: {e}")
            raise

    def recognize(self, audio_filepath: str) -> Optional[RecognizedTrack]:
        """Recognize audio file synchronously (manages event loop).

        Args:
            audio_filepath: Path to audio file to recognize

        Returns:
            RecognizedTrack if recognized, None otherwise

        Raises:
            Exception: If recognition fails
        """
        loop = None
        try:
            # Create new event loop for this operation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Run recognition
            result = loop.run_until_complete(self.recognize_async(audio_filepath))
            return result

        finally:
            # Always close event loop
            if loop is not None:
                loop.close()
