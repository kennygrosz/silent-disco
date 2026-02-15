"""Configuration management for Silent Disco application."""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class SpotifyConfig:
    """Spotify API configuration."""
    client_id: str
    client_secret: str
    redirect_uri: str
    default_device_id: Optional[str] = None

    @classmethod
    def from_env(cls) -> 'SpotifyConfig':
        """Load Spotify configuration from environment variables.

        Returns:
            SpotifyConfig instance

        Raises:
            ValueError: If required environment variables are missing
        """
        client_id = os.getenv('SPOTIFY_CLIENT_ID', '')
        client_secret = os.getenv('SPOTIFY_CLIENT_SECRET', '')

        if not client_id or not client_secret:
            raise ValueError(
                "Missing required Spotify credentials. "
                "Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables."
            )

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=os.getenv('SPOTIFY_REDIRECT_URI', 'http://localhost:8888/callback'),
            default_device_id=os.getenv('SPOTIFY_DEFAULT_DEVICE_ID') or None
        )


@dataclass
class AppConfig:
    """Application configuration."""
    snippet_duration: int = 10
    interval_duration: int = 60
    output_folder: str = 'song_snippets'
    duplicate_check_size: int = 10
    playback_offset_ms: int = 31000
    volume_preview: int = 40
    preferred_device_name: str = os.getenv('SPOTIFY_PREFERRED_DEVICE', '')


# Global configuration instances
# These will be initialized when the module is imported
spotify_config = SpotifyConfig.from_env()
app_config = AppConfig()
