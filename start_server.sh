#!/bin/bash
# Start the Silent Disco Flask server

cd "$(dirname "$0")"

echo "Starting Silent Disco Flask server..."
echo "Server will be available at:"
echo "  - http://localhost:5000"
echo "  - http://127.0.0.1:5000"
echo ""
echo "Available endpoints:"
echo "  - GET /                 - Health check"
echo "  - GET /listener_test    - Test audio recording (5 seconds)"
echo "  - GET /start_loop       - Start the main listening loop"
echo "  - GET /test_shazam      - Test Shazam recognition"
echo "  - GET /test_spotify     - Test Spotify connection"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=========================================="
echo ""

export FLASK_APP=app.py
export FLASK_ENV=development
python app.py
