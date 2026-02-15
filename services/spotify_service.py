"""Spotify service layer for Silent Disco application.

This module provides a clean interface to Spotify API operations,
including device management, search, and playback control.
"""

import time
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from utils.logging_config import get_logger
from utils.validators import validate_spotify_track, ValidationError


logger = get_logger()


@dataclass
class SpotifyTrack:
    """Structured representation of a Spotify track."""
    id: str
    uri: str
    name: str
    artist: str
    duration_ms: int
    album_art_url: Optional[str] = None

    @classmethod
    def from_api_response(cls, track_data: Dict[str, Any]) -> 'SpotifyTrack':
        """Create SpotifyTrack from Spotify API response.

        Args:
            track_data: Track dictionary from Spotify API

        Returns:
            SpotifyTrack instance

        Raises:
            ValidationError: If track data is invalid
        """
        # Validate track data has required fields
        validated = validate_spotify_track(track_data)

        # Extract album art URL (get medium size image)
        album_art_url = None
        if 'album' in validated and 'images' in validated['album']:
            images = validated['album']['images']
            if images:
                # Get medium size image (usually index 1) or first available
                album_art_url = images[1]['url'] if len(images) > 1 else images[0]['url']

        return cls(
            id=validated['id'],
            uri=validated['uri'],
            name=validated['name'],
            artist=validated['artists'][0]['name'],
            duration_ms=validated['duration_ms'],
            album_art_url=album_art_url
        )


class SpotifyService:
    """Service for Spotify API operations with caching and error handling."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, scope: str):
        """Initialize Spotify service.

        Args:
            client_id: Spotify client ID
            client_secret: Spotify client secret
            redirect_uri: OAuth redirect URI
            scope: Spotify API scopes
        """
        self.client = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=scope
            )
        )

        # Device caching to reduce API calls
        self._cached_device_id: Optional[str] = None
        self._cached_device_name: Optional[str] = None
        self._device_cache_time: float = 0
        self._device_cache_ttl: int = 300  # 5 minutes

    def _is_device_cache_valid(self) -> bool:
        """Check if cached device is still valid.

        Returns:
            True if cache is valid, False otherwise
        """
        if not self._cached_device_id:
            return False

        age = time.time() - self._device_cache_time
        return age < self._device_cache_ttl

    def get_and_activate_device(self, preferred_name: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """Find and activate a Spotify device, with caching.

        Args:
            preferred_name: Preferred device name (e.g., "Kenny's MacBook Air")

        Returns:
            Tuple of (device_id, device_name) or (None, None) if no devices found
        """
        # Return cached device if still valid
        if self._is_device_cache_valid():
            logger.debug(f"Using cached device: {self._cached_device_name}")
            return self._cached_device_id, self._cached_device_name

        try:
            devices_response = self.client.devices()
            devices = devices_response.get("devices", [])

            if not devices:
                logger.warning("No Spotify devices found")
                return None, None

            # Filter devices with volume control
            volume_devices = [d for d in devices if d.get('supports_volume', False)]

            if not volume_devices:
                logger.warning("No devices with volume control found")
                return None, None

            # Try to find preferred device by name
            if preferred_name:
                preferred = next(
                    (d for d in volume_devices if preferred_name in d.get('name', '')),
                    None
                )
                if preferred:
                    device_id = preferred['id']
                    device_name = preferred['name']
                    # Activate the device
                    self.client.transfer_playback(device_id=device_id, force_play=False)
                    logger.info(f"Activated preferred device: {device_name}")

                    # Cache the device
                    self._cached_device_id = device_id
                    self._cached_device_name = device_name
                    self._device_cache_time = time.time()

                    return device_id, device_name

            # Fallback: use active device or first available
            active = next((d for d in volume_devices if d.get('is_active')), None)
            if active:
                device_id = active['id']
                device_name = active['name']
            else:
                # No active device, activate the first one
                device_id = volume_devices[0]['id']
                device_name = volume_devices[0]['name']
                self.client.transfer_playback(device_id=device_id, force_play=False)
                logger.info(f"Activated device: {device_name}")

            # Cache the device
            self._cached_device_id = device_id
            self._cached_device_name = device_name
            self._device_cache_time = time.time()

            return device_id, device_name

        except Exception as e:
            logger.error(f"Error getting Spotify device: {e}")
            return None, None

    def search_track(self, query: str) -> Optional[SpotifyTrack]:
        """Search for a track on Spotify.

        Args:
            query: Search query string

        Returns:
            SpotifyTrack if found, None otherwise
        """
        try:
            result = self.client.search(query, type='track', limit=1)
            items = result.get("tracks", {}).get('items', [])

            if not items:
                logger.info(f"No search results for: {query}")
                return None

            track_data = items[0]

            # Validate and convert to SpotifyTrack
            try:
                track = SpotifyTrack.from_api_response(track_data)
                logger.debug(f"Found track: {track.name} by {track.artist}")
                return track
            except ValidationError as e:
                logger.error(f"Invalid track data from Spotify: {e}")
                return None

        except Exception as e:
            logger.error(f"Track search failed: {e}")
            return None

    def start_playback(
        self,
        track_uri: str,
        device_id: str,
        position_ms: int = 0,
        volume: int = 0
    ) -> bool:
        """Start playback of a track.

        Args:
            track_uri: Spotify track URI
            device_id: Device ID to play on
            position_ms: Starting position in milliseconds
            volume: Volume level (0-100)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Start playback
            self.client.start_playback(
                device_id=device_id,
                uris=[track_uri],
                position_ms=position_ms
            )

            # Set volume
            self.client.volume(volume, device_id=device_id)

            logger.debug(f"Started playback: {track_uri} at {position_ms}ms, volume {volume}")
            return True

        except Exception as e:
            logger.error(f"Playback failed: {e}")
            return False

    def is_interruption_allowed(self) -> Tuple[bool, str]:
        """Check if interrupting current Spotify session is allowed.

        Interruption is NOT allowed if music is actively playing.

        Returns:
            Tuple of (is_allowed, message)
        """
        try:
            current_playback = self.client.current_playback()

            if current_playback is None:
                return True, "No active session. Interrupt away!"

            if current_playback.get('is_playing') is True:
                return False, "There is an active spotify session right now and music is playing. Interruption not allowed."

            if current_playback.get('is_playing') is False:
                return True, "There is an active spotify session right now but music is NOT playing. Interruption is allowed."

            return True, "No active session. Interrupt away!"

        except Exception as e:
            logger.error(f"Failed to check playback status: {e}")
            # Default to allowing interruption if we can't check
            return True, f"Could not check playback status: {e}"

    def get_queue(self) -> Optional[Dict[str, Any]]:
        """Get current Spotify queue.

        Returns:
            Queue data or None if failed
        """
        try:
            return self.client.queue()
        except Exception as e:
            logger.error(f"Failed to get queue: {e}")
            return None
