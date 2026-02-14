from flask import Flask
import pyaudio
import wave
import os
from listener.listener import record_audio
from audio_recognition.audio_recognition import shazam_get_trackdata
from datetime import datetime
import time
import asyncio
import nest_asyncio
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import config
from class_snippet import Snippet
from spotipy_functions import search_song, is_interruption_allowed
from utils.logging_config import LogCollector, get_logger
from utils.validators import (
    validate_duration,
    validate_interval,
    validate_spotify_track,
    validate_directory_path,
    ValidationError
)


nest_asyncio.apply()

app = Flask(__name__)


def get_and_activate_spotify_device(sp, preferred_name=None):
    """Find and activate a Spotify device, preferring the specified device name.

    Args:
        sp: Spotify client instance
        preferred_name: Preferred device name (e.g., "Kenny's MacBook Air")

    Returns:
        tuple: (device_id, device_name) or (None, None) if no devices found
    """
    try:
        devices_response = sp.devices()
        devices = devices_response.get("devices", [])

        if not devices:
            print(f"No Spotify devices found. Please open Spotify on a device.")
            return None, None

        # Filter devices with volume control
        volume_devices = [d for d in devices if d.get('supports_volume', False)]

        if not volume_devices:
            print(f"No devices with volume control found.")
            return None, None

        # Try to find preferred device by name
        if preferred_name:
            preferred = next((d for d in volume_devices if preferred_name in d.get('name', '')), None)
            if preferred:
                device_id = preferred['id']
                device_name = preferred['name']
                # Activate the device (even if not currently playing)
                sp.transfer_playback(device_id=device_id, force_play=False)
                print(f"Activated preferred device: {device_name}")
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
            sp.transfer_playback(device_id=device_id, force_play=False)
            print(f"Activated device: {device_name}")

        return device_id, device_name

    except Exception as e:
        print(f"Error getting Spotify device: {e}")
        return None, None


@app.route('/')
def index():
    return 'Flask app is running'

# This route is accessible at [IP_ADDRESS]:5000/listener_test
# Functionality
##### Record for 5 seconds
##### Output file test_snippet_[timestamp] in the song_snippets_test folder
@app.route('/listener_test')
def listener_test():
    print("running listener test")

    snippet_duration = 5 #seconds
    output_folder = 'song_snippets_test'

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Generate a unique filename for the snippet

    ### Get timestring
    timestr = datetime.now().strftime("%Y%m%d_%H%M%S")

    ## Create filename
    filename_str = 'test_snippet_'+timestr+'.wav'

     ## Join to path
    snippet_filepath = os.path.join(output_folder, filename_str)

    print(snippet_filepath)
    
    try:
        status = record_audio(snippet_filepath, snippet_duration)
        print(status)
        return snippet_filepath
    except Exception as e: 
        print(e)
        return str(e)

# This route is accessible at [IP_ADDRESS]:5000/start_loop
# Functionality:
##### Begin recording
##### Output and save a 5 second snippet every 15 seconds
@app.route('/start_loop')
def start_loop():

    ######
    # INITIALIZATION
    #####

    # Initialize logging with new LogCollector
    log_collector = LogCollector()
    log_collector.info("Initializing variables")

    # Define parameters
    ### Snippet params
    snippet_duration = 10  # seconds
    interval_duration = 60  # seconds
    total_recording_time = None  # if this is a number, then the recording will stop after a specified number of seconds

    # Validate parameters
    try:
        snippet_duration = validate_duration(snippet_duration, min_seconds=1, max_seconds=300)
        interval_duration = validate_interval(interval_duration, snippet_duration)
        log_collector.info(f"Validated parameters - snippet: {snippet_duration}s, interval: {interval_duration}s")
    except ValidationError as e:
        log_collector.error(f"Parameter validation failed: {e}")
        return log_collector.get_logs()

    total_loops = int(total_recording_time / interval_duration) if total_recording_time is not None else 1

    ### File / Name information
    output_folder = 'song_snippets'
    try:
        output_folder = validate_directory_path(output_folder, create_if_missing=True)
        log_collector.info(f"Output directory validated: {output_folder}")
    except ValidationError as e:
        log_collector.error(f"Output directory validation failed: {e}")
        return log_collector.get_logs()

    ### Create data structure for storing songs
    all_snippets_list = []
    snippet_states = {
        "created": [],
        "recorded": [],
        "recognized": [],
        "unrecognized": [],
        "processing_failed": [],
        "unqueueable": [],
        "queueable": [],
        "queued": []
    }
    queue = []
    
    ### Connect to Spotify API
    log_collector.info("Connecting to Spotify API")

    base_url = 'https://api.spotify.com'
    cid = config.cid
    secret = config.secret
    scope = 'user-modify-playback-state user-read-playback-state'
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=cid, client_secret=secret,redirect_uri='https://github.com/kennygrosz/silent-disco', scope=scope))
    default_device_id = '7421ca5ee7d4c4d2931813a7eac18183dd61aaa3'

    # save current queue
    pre_listen_queue = sp.queue()

    ######
    # LOOP  
    #####
    cnt=0
    should_continue = True

    log_collector.info("Beginning loop, Iteration = "+str(cnt))


    while should_continue:
        valid_snippet = True
        interruption_allowed_flag = False  # Initialize

        log_collector.info("Loop, Iteration = "+str(cnt))

        # 0. Initialize snippet
        snip = Snippet(output_folder, snippet_duration=snippet_duration)

        log_collector.info("Initialized Snippet at:"+snip.snippet_filepath)

        # 1. Record and store snippet
        log_collector.info("Recording snippet: "+snip.filename_str)
        try:
            status = record_audio(snip.snippet_filepath, snip.snippet_duration)
            snip.is_recorded = True
            print(status)
            log_collector.info(f"Recording completed with status: {status}")
        except Exception as e:
            log_collector.error(f"Recording failed with exception: {str(e)}")
            valid_snippet = False
            continue  # Skip to next iteration instead of exiting
        
        # 2. Process song with Shazamio to try to recognize it
        if valid_snippet:
            log_collector.info("Processing snippet with shazamio")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                trackdata, track_string = loop.run_until_complete(shazam_get_trackdata(snip.snippet_filepath))
                
                if track_string == "no_match":
                    log_collector.info("Snippet is unrecognizeable")
                    valid_snippet = False 
                    snip.track_string = "unrecognized"
                else:
                    snip.is_recognized = True
                    snip.track_string = track_string
                    log_collector.info(f"Snippet is recognized. Track String = {snip.track_string}")

            except Exception as e:
                log_collector.error(f"Recognition failed with exception: {str(e)}")
                valid_snippet = False
                continue  # Skip to next iteration instead of exiting
            finally:
                loop.close()


        # 3. Check if interruption is allowed and if song is queueable
        if valid_snippet:
            log_collector.info("Checking if there is a current active spotify session to decide if interruption is permissible")

            interruption_allowed_flag, return_message = is_interruption_allowed(sp)

            if interruption_allowed_flag is True:
                log_collector.info(return_message)
            else: 
                log_collector.info("Interruption is not allowed. Reason below.")
                log_collector.info(return_message)

        ## LOGIC: If song appears as one of the last 5 songs in the queue list, then don't add it
        last_5_songs = queue[-5:]

        if valid_snippet is True and interruption_allowed_flag is True:
            # 3.1 Is song queueable?
            if track_string not in last_5_songs:
                log_collector.info("Song is not in last 5 songs of silent disco queue history.")
                snip.is_queuable = True
            else:
                valid_snippet = False
                log_collector.info("Song is in last 5 songs of silent disco queue history. Skipping...")


        # 4. Play song on Spotify
        if valid_snippet is True and interruption_allowed_flag is True:
            # Search song
            log_collector.info("Searching for song on Spotify")
            result = search_song(sp, snip.track_string)

            if result is None:
                log_collector.info(f"Song not found on Spotify: {snip.track_string}")
                valid_snippet = False
                continue

            # Validate Spotify track data
            try:
                result = validate_spotify_track(result)
            except ValidationError as e:
                log_collector.error(f"Invalid Spotify track data: {e}")
                valid_snippet = False
                continue

            snip.song_id = result['id']
            snip.song_uri = result['uri']
            snip.song_name = result['name']
            snip.song_artist = result['artists'][0]['name']
            snip.duration_ms = result['duration_ms']

            # Result
            log_collector.info(f"Found song: {snip.song_name} - {snip.song_artist}")

            # Play song
            try:
                # Get and activate preferred device
                active_device_id, device_name = get_and_activate_spotify_device(
                    sp,
                    preferred_name=config.app_config.preferred_device_name
                )

                if not active_device_id:
                    log_collector.info("No Spotify devices available - skipping playback")
                    valid_snippet = False
                    continue

                log_collector.info(f"Playing song on device: {device_name}")

                # Calculate safe position (prevent negative position_ms)
                # Play last 31 seconds of the song
                position_ms = max(0, snip.duration_ms - config.app_config.playback_offset_ms)

                sp.start_playback(
                    device_id=active_device_id,
                    uris=[snip.song_uri],
                    position_ms=position_ms
                )

                # Always keep volume at 0 (silent playback)
                sp.volume(0, device_id=active_device_id)

                # Add to queue AFTER successful playback
                queue.append(snip.track_string)
                log_collector.info("Successfully played and added to queue")

            except Exception as e:
                log_collector.error(f"Cannot play song, with exception: {str(e)}")
                valid_snippet = False
                # Continue to next iteration

        # Update counter and sleep if there will be more loops
        cnt += 1

        # Check if we should continue (time-based or infinite mode)
        if total_recording_time is not None:
            should_continue = cnt <= total_loops
        # If total_recording_time is None, loop runs indefinitely (should_continue stays True)

        if should_continue:
            # Calculate sleep time (accounting for processing time in future)
            time.sleep(interval_duration - snippet_duration)

    return log_collector.get_logs()


# This route is accessible at [IP_ADDRESS]:5000/test_shazam
# Functionality:
##### pick a filename and see if shazam recognizes it
@app.route('/test_shazam')
async def test_shazam():
    filepath = 'song_snippets/test_snippet_20230524_131852.wav' # the breeze - dr dog
    # filepath = 'song_snippets/test_snippet_20230524_132647.wav' #random shit


    loop = asyncio.get_event_loop()
    trackdata, track_string = loop.run_until_complete(shazam_get_trackdata(filepath))

    return track_string


@app.route('/test_spotify')
def test_spotify():
    """Test Spotify connection with auto-activation of preferred device."""
    try:
        cid = config.cid
        secret = config.secret
        scope = 'user-modify-playback-state user-read-playback-state'
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=cid,
            client_secret=secret,
            redirect_uri='https://github.com/kennygrosz/silent-disco',
            scope=scope
        ))

        # Get and activate preferred device
        device_id, device_name = get_and_activate_spotify_device(
            sp,
            preferred_name=config.app_config.preferred_device_name
        )

        if not device_id:
            return {
                "status": "error",
                "message": "No Spotify devices found. Please open Spotify on any device.",
                "preferred_device": config.app_config.preferred_device_name
            }, 404

        # Start playback test
        sp.start_playback(
            device_id=device_id,
            uris=['spotify:track:0UV5zxRMz6AO4ZwUOZNIKI'],
            position_ms=150000
        )

        # Always keep volume at 0 (silent playback)
        sp.volume(0, device_id=device_id)

        return {
            "status": "success",
            "message": "Spotify playback test successful!",
            "device_used": device_name,
            "preferred_device": config.app_config.preferred_device_name,
            "was_auto_activated": True
        }, 200

    except Exception as e:
        return {
            "status": "error",
            "message": f"Spotify test failed: {str(e)}",
            "error_type": type(e).__name__
        }, 500




if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)
