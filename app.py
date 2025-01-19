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


nest_asyncio.apply()

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
        return e

# This route is accessible at [IP_ADDRESS]:5000/start_loop
# Functionality:
##### Begin recording
##### Output and save a 5 second snippet every 15 seconds
@app.route('/start_loop')
def start_loop():

    ######
    # INITIALIZATION 
    #####

    # Initialize log
    log = []
    def print_log(log, msg):
        logtime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(logtime+" |\t"+msg)
        log.append(logtime+"\t"+msg)
        return

    print_log(log, "Initializing variables")

    # Define parameters
    ### Snippet params
    snippet_duration = 10 #seconds
    interval_duration = 60 #seconds
    total_recording_time = None #if this is a number, then the recording will stop after a specificed number of seconds
    total_loops = int(total_recording_time / interval_duration) if total_recording_time is not None else 1
    
    # total_loops = 0 #remember to remove

    ### File / Name information
    output_folder = 'song_snippets'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

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
    print_log(log, "Connecting to Spotify API")

    base_url = 'https://api.spotify.com'
    cid = config.cid
    secret = config.secret
    scope = 'user-modify-playback-state user-read-playback-state'
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=cid, client_secret=secret,redirect_uri='https://github.com/kennygrosz/silent-disco', scope=scope))
    default_device_id = '6078d94b3db63e070cf9b37a782f7ef06dbcc818'

    # save current queue
    pre_listen_queue = sp.queue()

    ######
    # LOOP  
    #####
    cnt = 0

    print_log(log, "Beginning loop, Iteration = "+str(cnt))


    while cnt <= total_loops:
        valid_snippet = True


        print_log(log, "Loop, Iteration = "+str(cnt))

        # 0. Initialize snippet
        snip = Snippet(output_folder, snippet_duration=snippet_duration)

        print_log(log, "Initialized Snippet at:"+snip.snippet_filepath)

        # 1. Record and store snippet
        print_log(log, "Recording snippet: "+snip.filename_str)
        try:
            status = record_audio(snip.snippet_filepath, snip.snippet_duration)
            snip.is_recorded = True
            print(status)
            print_log(log, "Recording completed with status: "+ status)
        except Exception as e: 
            print_log(log, "Recording failed with exception: "+ e)
            valid_snippet = False
            return log
        
        # 2. Process song with Shazamio to try to recognize it
        if valid_snippet:
            print_log(log, "Processing snippet with shazamio")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                trackdata, track_string = loop.run_until_complete(shazam_get_trackdata(snip.snippet_filepath))
                
                if track_string == "no_match":
                    print_log(log, "Snippet is unrecognizeable")
                    valid_snippet = False 
                    snip.track_string = "unrecognized"
                else:
                    snip.is_recognized = True
                    snip.track_string = track_string
                    print_log(log, "Snippet is recognized. Track String ="+snip.track_string)

            except Exception as e:
                print_log(log, "Recognition failed with exception: "+ e)
                valid_snippet = False 
                return log     


        # 3. Is song queueable?

            # Check if interruption is allowed

            if valid_snippet:
                print_log(log, "Checking if there is a current active spotify session to decide if interruption is permissible")

                interruption_allowed_flag, return_message = is_interruption_allowed(sp)

                if interruption_allowed_flag is True:
                    print_log(log, return_message)

                else: 
                    print_log(log, "Interruption is not allowed. Reason below.")
                    print_log(log, return_message)



            ## LOGIC: If song appears as one of the last 5 songs in the queue list, then don't add it
            last_5_songs = queue[-5:]

            if valid_snippet is True and interruption_allowed_flag is True:
                # 3.1 Is song queueable?
                if track_string not in last_5_songs:
                    print_log(log, "Song is not in last 5 songs of silent disco queue history. Adding to queue")
                    snip.is_queuable = True

                else:
                    valid_snippet = False
                    print_log(log, "Song is  in last 5 songs of silent disco queue history. Skipping...")





        # 4. Play song on Spotify
            if valid_snippet is True and interruption_allowed_flag is True:
                # Search song
                print_log(log, "searching for song on spotify")
                result = search_song(sp, snip.track_string)
                snip.song_id = result['id']
                snip.song_uri = result['uri']
                snip.song_name = result['name']
                snip.song_artist = result['artists'][0]['name']
                snip.duration_ms = result['duration_ms']

                # Result
                print_log(log, "Found song: "+ snip.song_name + "- "+snip.song_artist)

                # Play song
                try:
                    active_device_id =  [i['id'] for i in sp.devices()["devices"] if i['supports_volume'] is True][0]
                    sp.transfer_playback(device_id = active_device_id, force_play = True)
                    print_log(log,"playing song on device id" + active_device_id)
                    sp.start_playback(device_id=active_device_id, uris =[snip.song_uri], position_ms=snip.duration_ms - 31000)
                    # sp.volume(40)
                    # time.sleep(2)
                    sp.volume(0)

                    #add to queue
                    queue.append(snip.track_string)

                except Exception as e:
                    print_log(log, "Cannot play song, with exception: "+ str(e))
                    valid_snippet = False 
                    # return log     

        # Update counter and sleep if there will be more loops
        cnt += 1
        if total_recording_time == None:
            total_loops += 1
        if cnt <= total_loops:
            # sleep until next loop
            time.sleep(interval_duration-snippet_duration) ## FIX THIS TO REMOVE PROCESSING TIME FOR OTHER STEPS IN THE PROCESS

    return log

    return "Snippets complete"


# This route is accessible at [IP_ADDRESS]:5000/test_shazam
# Functionality:
##### pick a filename and see if shazam recognizes it
@app.route('/test_shazam')
async def test_shazam():
    filepath = 'song_snippets/test_snippet_20230524_131852.wav' # the breeze - dr dog
    # filepath = 'song_snippets/test_snippet_20230524_132647.wav' #random shit
    filepath = 'song_snippets_test/test_snippet_20250105_172611.wav' # Purge - Bas


    loop = asyncio.get_event_loop()
    trackdata, track_string = loop.run_until_complete(shazam_get_trackdata(filepath))

    return track_string


@app.route('/test_spotify')
def test_spotify():
    base_url = 'https://api.spotify.com'
    cid = config.cid
    secret = config.secret
    scope = 'user-modify-playback-state user-read-playback-state'
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=cid, client_secret=secret,redirect_uri='https://github.com/kennygrosz/silent-disco', scope=scope))

    print("------Printing List of Devices")
    print(sp.devices())
    
    #active_id = [i['id'] for i in sp.devices()["devices"] if i['supports_volume'] is True][0]
    default_device_id = '6078d94b3db63e070cf9b37a782f7ef06dbcc818'
    active_id = default_device_id

    #sp.transfer_playback(device_id = default_device_id, force_play = False)

    # check if there is an active session
    interruption_allowed_flag = is_interruption_allowed(sp)

    if interruption_allowed_flag:
        sp.start_playback(device_id=active_id, uris =['spotify:track:0UV5zxRMz6AO4ZwUOZNIKI'], position_ms=150000) 
        sp.volume(40)
        time.sleep(5)
        sp.volume(0)
        time.sleep(3)
        sp.volume(40)

    return "test completed"




if __name__ == '__main__':
    app.run()