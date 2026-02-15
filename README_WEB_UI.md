# Silent Disco Web UI

## 🚀 Quick Start

### Run with Web UI (Default)
```bash
python app_integrated.py
```

Then open http://localhost:5002 in your browser to see the interface.

### Run without UI (Headless)
```bash
python app_integrated.py --no-ui
```

Or use the original `app.py` for headless operation.

## 📋 Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--no-ui` | Disable web interface | UI enabled |
| `--port` | Web UI port | 5002 |
| `--snippet-duration` | Audio snippet length (seconds) | 10 |
| `--interval` | Time between snippets (seconds) | 60 |
| `--time-limit` | Total recording time (seconds) | None (infinite) |

## 💡 Examples

### Basic usage (UI enabled by default)
```bash
python app_integrated.py
```

### Custom port
```bash
python app_integrated.py --port 8080
```

### Short snippets, frequent recording
```bash
python app_integrated.py --snippet-duration 5 --interval 30
```

### Run for 1 hour only
```bash
python app_integrated.py --time-limit 3600
```

### Headless (no UI)
```bash
python app_integrated.py --no-ui
```

## 🎨 Web UI Features

When you enable the UI with `--ui`, you get:

- **Real-time Audio Visualizer** - Live visualization of room audio with psychedelic effects
- **Now Playing** - Shows currently recognized track with mood-based colors
- **Track History** - List of recently played tracks
- **Live Controls**:
  - ⏸ **Stop/Start Listening** - Toggle the recognition loop
  - 🔄 **Retry Recognition** - Retry recognition on last snippet
  - 🎧 **Test Spotify** - Test Spotify connection
  - ▶ **Replay Last Snippet** - Replay the last recorded audio

## 🌐 Network Access

The web UI is accessible on your local network:
- Local: `http://localhost:5002`
- Network: `http://[your-ip]:5002`

Find your IP with:
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

## 🔧 How It Works

1. **Default mode (UI enabled)**:
   - Starts Flask-SocketIO web server in background thread
   - Streams real-time audio data to visualizer via WebSocket
   - Updates track info and history as songs are recognized
   - Control buttons send commands to the main app
   - Access at http://localhost:5002

2. **Headless mode (`--no-ui`)**:
   - Runs the listening loop directly
   - Logs output to console only
   - Lower resource usage
   - Same functionality, just no web interface

## 📝 Backwards Compatibility

The original `app.py` still works as before with Flask routes:
- `/start_loop` - Start listening
- `/test_spotify` - Test Spotify connection
- `/test_shazam` - Test Shazam recognition

Use `app_integrated.py` for the new integrated experience with optional UI.

## 🎯 Recommended Setup

For best results when using the web UI:
1. Open the web interface on a screen across the room from your record player
2. Start listening with the UI controls
3. Watch the visualizer react to music in real-time
4. See recognized tracks appear in the history panel

## 🐛 Troubleshooting

**Port already in use:**
```bash
# Use a different port
python app_integrated.py --ui --port 5003
```

**UI not loading:**
- Check firewall settings
- Try accessing via http://127.0.0.1:5002 instead
- Check console for error messages

**Visualizer not working:**
- Ensure microphone permissions are granted
- Check that PyAudio is properly installed
- Try refreshing the browser page
