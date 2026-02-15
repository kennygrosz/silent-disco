# Silent Disco

Listens to music playing in the room, identifies it with Shazam, and plays it on Spotify.

## What It Does

Silent Disco continuously records short audio snippets from your microphone, sends them to Shazam for recognition, then searches Spotify and starts playback on your connected device. It includes a real-time web UI with an audio visualizer, track history, and playback controls.

**Workflow:** Record audio &rarr; Recognize with Shazam &rarr; Search on Spotify &rarr; Play

Built for silent disco events, vinyl listening sessions, or any scenario where you want to automatically identify and stream what's playing around you.

## Quick Start

```bash
# Clone and set up
git clone https://github.com/kennygrosz/silent-disco.git
cd silent-disco
python -m venv silent-disco-env
source silent-disco-env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure Spotify credentials
cp .env.example .env
# Edit .env with your Spotify API credentials (see Configuration below)

# Enable git hooks (tests on commit, cleanup on pull)
git config core.hooksPath .githooks

# Run
python app_integrated.py
```

Then open http://localhost:5002 in your browser.

## Command-Line Options

| Option | Description | Default |
|---|---|---|
| `--no-ui` | Disable web interface (headless mode) | UI enabled |
| `--port` | Web UI port | 5002 |
| `--snippet-duration` | Audio snippet length in seconds | 10 |
| `--interval` | Time between recordings in seconds | 60 |
| `--time-limit` | Total runtime in seconds | None (infinite) |

**Examples:**

```bash
# Custom port
python app_integrated.py --port 8080

# Short snippets, frequent recording
python app_integrated.py --snippet-duration 5 --interval 30

# Run for 1 hour
python app_integrated.py --time-limit 3600

# Headless (no web UI)
python app_integrated.py --no-ui
```

## Web UI

The web interface at `http://localhost:5002` provides:

- **Real-time audio visualizer** -- FFT-based frequency bars reacting to room audio
- **Now playing** -- Currently recognized track with album art and mood-based colors
- **Track history** -- Recently recognized tracks with auto-updating timestamps
- **Controls:**
  - Stop/Start listening
  - Retry recognition on the last snippet
  - Test Spotify connection
  - Replay last recorded audio

The UI is also accessible on your local network at `http://<your-ip>:5002`.

## Architecture

```
silent-disco/
├── app_integrated.py              # Main controller -- orchestrates the full pipeline
├── web_server.py                  # Flask-SocketIO web UI with real-time updates
├── config.py                      # Configuration (SpotifyConfig, AppConfig)
├── models/
│   └── snippet.py                 # Snippet model with state machine
├── services/
│   ├── spotify_service.py         # Spotify API: search, playback, device management
│   └── recognition_service.py     # Shazam audio recognition
├── listener/
│   └── listener.py                # PyAudio microphone recording
├── utils/
│   ├── validators.py              # Input validation
│   └── logging_config.py          # Centralized logging
├── templates/                     # Web UI HTML
├── static/                        # Web UI assets
├── tests/                         # Test suite (154 tests)
├── .githooks/                     # Pre-commit and post-merge hooks
├── cleanup.sh                     # Remove generated/cached files
├── pytest.ini                     # Pytest configuration
├── requirements.txt               # Python dependencies
└── .env.example                   # Environment variable template
```

The app follows a **service layer pattern**: `SilentDiscoApp` orchestrates `SpotifyService`, `RecognitionService`, and the audio listener, while `web_server.py` handles the UI layer independently via shared `AppState`.

## Configuration

### Spotify API Credentials (required)

Create a Spotify app at https://developer.spotify.com/dashboard and add your credentials to `.env`:

```env
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
SPOTIFY_DEFAULT_DEVICE_ID=          # Optional: leave empty to auto-select
SPOTIFY_PREFERRED_DEVICE=           # Optional: e.g., "Kenny's MacBook Air"
```

### App Defaults

These are configured in `config.py` (`AppConfig`):

| Setting | Default | Description |
|---|---|---|
| `snippet_duration` | 10s | Recording length |
| `interval_duration` | 60s | Time between recordings |
| `duplicate_check_size` | 10 | Number of recent songs checked to prevent repeats |
| `playback_offset_ms` | 31000 | Plays the last 31 seconds of a track |
| `volume_preview` | 40 | Playback volume (0-100) |

## Testing

The project has 154 tests across 9 test files covering models, services, utilities, web routes, and end-to-end user journeys.

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=term-missing

# Run a specific test file
pytest tests/test_snippet.py
```

Tests run automatically before every commit via the pre-commit hook.

## Git Hooks

The `.githooks/` directory contains two hooks:

| Hook | Trigger | What It Does |
|---|---|---|
| `pre-commit` | `git commit` | Runs the full test suite; blocks commit if tests fail |
| `post-merge` | `git pull` | Runs `cleanup.sh` and `pip install -r requirements.txt` |

**Setup** (run once per clone):

```bash
git config core.hooksPath .githooks
```

To bypass the pre-commit hook in an emergency: `git commit --no-verify`

## Cleanup

```bash
./cleanup.sh
```

Removes all generated and cached files (audio snippets, `__pycache__`, logs, `.DS_Store`, etc.). Only deletes `.gitignore`d files -- safe to run anytime. This also runs automatically after every `git pull` via the post-merge hook.

## Troubleshooting

**Port already in use:**
```bash
python app_integrated.py --port 5003
```

**UI not loading:**
- Try `http://127.0.0.1:5002` instead of `localhost`
- Check the terminal for error messages
- Check firewall settings

**Visualizer not working:**
- Ensure microphone permissions are granted to your terminal/IDE
- Verify PyAudio is installed: `pip install pyaudio`
- Refresh the browser page

**Spotify not playing:**
- Ensure Spotify is open on at least one device
- Run the "Test Spotify" button in the web UI
- Check that your `.env` credentials are correct
