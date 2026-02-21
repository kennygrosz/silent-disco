"""Browser-based UI tests using Playwright.

These tests start the Flask-SocketIO server and load the page in a real
headless browser, catching issues that unit tests miss:
- JavaScript syntax errors
- Missing DOM elements
- Socket.IO connection failures
"""

import pytest
import threading
import time
from unittest.mock import patch
from playwright.sync_api import Page, expect


TEST_PORT = 5099


@pytest.fixture(scope="module")
def server():
    """Start Flask-SocketIO server in a background thread for UI testing."""
    from web_server import app, socketio, app_state, AudioStreamer
    from collections import deque

    # Reset app state to clean defaults
    app_state.is_listening = False
    app_state.current_track = None
    app_state.track_history = deque(maxlen=20)
    app_state.last_snippet = None
    app_state.next_recording_in = 0
    app_state.app_controller = None

    # Patch AudioStreamer so it doesn't try to open the microphone
    with patch.object(AudioStreamer, 'start'), \
         patch.object(AudioStreamer, 'stop'):

        def run():
            socketio.run(app, host='127.0.0.1', port=TEST_PORT,
                         debug=False, allow_unsafe_werkzeug=True)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

        # Wait for server to be ready
        import socket
        for _ in range(50):
            try:
                s = socket.create_connection(('127.0.0.1', TEST_PORT), timeout=0.1)
                s.close()
                break
            except (ConnectionRefusedError, OSError):
                time.sleep(0.1)
        else:
            pytest.fail("Server did not start within 5 seconds")

        yield TEST_PORT


class TestUILoads:
    """Tests that the UI loads and renders correctly in a real browser."""

    def test_no_javascript_errors(self, server, page: Page):
        """Page should load without any JavaScript errors.

        This catches syntax errors like the extra '}' that broke the UI.
        """
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        page.goto(f"http://127.0.0.1:{server}")
        page.wait_for_load_state("networkidle")

        assert errors == [], f"JavaScript errors on page load: {errors}"

    def test_key_ui_elements_present(self, server, page: Page):
        """Critical UI elements should be present in the DOM."""
        page.goto(f"http://127.0.0.1:{server}")
        page.wait_for_load_state("networkidle")

        expect(page.locator("#visualizer")).to_be_visible()
        expect(page.locator(".now-playing")).to_be_visible()
        expect(page.locator(".controls")).to_be_visible()
        expect(page.locator(".history-panel")).to_be_visible()

    def test_header_renders(self, server, page: Page):
        """The app header should display the title."""
        page.goto(f"http://127.0.0.1:{server}")

        header = page.locator(".header h1")
        expect(header).to_contain_text("SILENT DISCO")

    def test_disconnected_banner_hides_on_connect(self, server, page: Page):
        """Banner should hide once Socket.IO connects to the server."""
        page.goto(f"http://127.0.0.1:{server}")

        banner = page.locator("#disconnected-banner")
        # Socket.IO should connect and hide the banner
        expect(banner).to_be_hidden(timeout=5000)
