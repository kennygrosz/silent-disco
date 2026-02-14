from flask import Flask
import os
from listener.listener import record_audio
from datetime import datetime
import time
import config
from models.snippet import Snippet
from services.spotify_service import SpotifyService
from services.recognition_service import RecognitionService
from utils.logging_config import LogCollector
from utils.validators import (
    validate_duration,
    validate_interval,
    validate_directory_path,
    ValidationError
)


app = Flask(__name__)


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
    
    ### Initialize services
    log_collector.info("Initializing Spotify and Recognition services")

    # Create Spotify service
    spotify_service = SpotifyService(
        client_id=config.cid,
        client_secret=config.secret,
        redirect_uri='https://github.com/kennygrosz/silent-disco',
        scope='user-modify-playback-state user-read-playback-state'
    )

    # Create Recognition service
    recognition_service = RecognitionService()

    # Save current queue
    pre_listen_queue = spotify_service.get_queue()

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
        snip = Snippet(output_folder=output_folder, snippet_duration=snippet_duration)

        log_collector.info(f"Initialized Snippet at: {snip.filepath_str}")

        # 1. Record and store snippet
        log_collector.info(f"Recording snippet: {snip.filename}")
        try:
            status = record_audio(snip.filepath_str, snip.snippet_duration)
            snip.mark_recorded()
            print(status)
            log_collector.info(f"Recording completed with status: {status}")
        except Exception as e:
            log_collector.error(f"Recording failed with exception: {str(e)}")
            snip.mark_failed()
            valid_snippet = False
            continue  # Skip to next iteration instead of exiting
        
        # 2. Process song with Recognition service
        if valid_snippet:
            log_collector.info("Processing snippet with Shazam")
            try:
                recognized_track = recognition_service.recognize(snip.filepath_str)

                if recognized_track is None:
                    log_collector.info("Snippet is unrecognizable")
                    snip.mark_unrecognized()
                    valid_snippet = False
                else:
                    snip.mark_recognized(recognized_track.track_string)
                    log_collector.info(f"Snippet is recognized. Track String = {snip.track_string}")

            except Exception as e:
                log_collector.error(f"Recognition failed with exception: {str(e)}")
                snip.mark_failed()
                valid_snippet = False
                continue  # Skip to next iteration instead of exiting


        # 3. Check if interruption is allowed and if song is queueable
        if valid_snippet:
            log_collector.info("Checking if interruption is permissible")

            interruption_allowed_flag, return_message = spotify_service.is_interruption_allowed()

            if interruption_allowed_flag is True:
                log_collector.info(return_message)
            else:
                log_collector.info("Interruption is not allowed. Reason below.")
                log_collector.info(return_message)

        ## LOGIC: If song appears as one of the last 5 songs in the queue list, then don't add it
        last_5_songs = queue[-5:]

        if valid_snippet is True and interruption_allowed_flag is True:
            # 3.1 Is song queueable?
            if snip.track_string not in last_5_songs:
                log_collector.info("Song is not in last 5 songs of silent disco queue history.")
                snip.mark_queueable()
            else:
                valid_snippet = False
                log_collector.info("Song is in last 5 songs of silent disco queue history. Skipping...")


        # 4. Play song on Spotify
        if valid_snippet is True and interruption_allowed_flag is True:
            # Search song using Spotify service
            log_collector.info("Searching for song on Spotify")
            spotify_track = spotify_service.search_track(snip.track_string)

            if spotify_track is None:
                log_collector.info(f"Song not found on Spotify: {snip.track_string}")
                valid_snippet = False
                continue

            # Store Spotify track information
            snip.set_spotify_info(
                song_id=spotify_track.id,
                song_uri=spotify_track.uri,
                song_name=spotify_track.name,
                song_artist=spotify_track.artist,
                duration_ms=spotify_track.duration_ms
            )

            log_collector.info(f"Found song: {snip.song_name} - {snip.song_artist}")

            # Get and activate preferred device
            active_device_id, device_name = spotify_service.get_and_activate_device(
                preferred_name=config.app_config.preferred_device_name
            )

            if not active_device_id:
                log_collector.info("No Spotify devices available - skipping playback")
                valid_snippet = False
                continue

            log_collector.info(f"Playing song on device: {device_name}")

            # Calculate safe position (play last 31 seconds of the song)
            position_ms = max(0, snip.duration_ms - config.app_config.playback_offset_ms)

            # Start playback with volume at 0 (silent playback)
            playback_success = spotify_service.start_playback(
                track_uri=snip.song_uri,
                device_id=active_device_id,
                position_ms=position_ms,
                volume=0
            )

            if playback_success:
                # Add to queue AFTER successful playback
                queue.append(snip.track_string)
                snip.mark_queued()
                log_collector.info("Successfully played and added to queue")
            else:
                log_collector.error("Playback failed")
                valid_snippet = False

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
def test_shazam():
    """Test Shazam recognition on a sample file."""
    filepath = 'song_snippets/test_snippet_20230524_131852.wav'  # the breeze - dr dog
    # filepath = 'song_snippets/test_snippet_20230524_132647.wav' #random shit

    recognition_service = RecognitionService()
    recognized_track = recognition_service.recognize(filepath)

    if recognized_track:
        return recognized_track.track_string
    else:
        return "Song not recognized"


@app.route('/test_spotify')
def test_spotify():
    """Test Spotify connection with auto-activation of preferred device."""
    try:
        # Create Spotify service
        spotify_service = SpotifyService(
            client_id=config.cid,
            client_secret=config.secret,
            redirect_uri='https://github.com/kennygrosz/silent-disco',
            scope='user-modify-playback-state user-read-playback-state'
        )

        # Get and activate preferred device
        device_id, device_name = spotify_service.get_and_activate_device(
            preferred_name=config.app_config.preferred_device_name
        )

        if not device_id:
            return {
                "status": "error",
                "message": "No Spotify devices found. Please open Spotify on any device.",
                "preferred_device": config.app_config.preferred_device_name
            }, 404

        # Start playback test with silent volume
        playback_success = spotify_service.start_playback(
            track_uri='spotify:track:0UV5zxRMz6AO4ZwUOZNIKI',
            device_id=device_id,
            position_ms=150000,
            volume=0
        )

        if not playback_success:
            return {
                "status": "error",
                "message": "Playback failed"
            }, 500

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
