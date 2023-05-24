from flask import Flask
import pyaudio
import wave
import os
from listener.listener import record_audio
from audio_recognition.audio_recognition import shazam_test
import time
import asyncio
import nest_asyncio
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
    timestr = time.strftime("%Y%m%d_%H%M%S")

    ## Create filename
    filename_str = 'test_snippet_'+timestr+'.wav'

     ## Join to path
    snippet_filepath = os.path.join(output_folder, filename_str)

    print(snippet_filepath)
    
    try:
        status = record_audio(snippet_filepath, snippet_duration)
        print(status)
    except Exception as e: 
        print(e)

# This route is accessible at [IP_ADDRESS]:5000/begin_listener
# Functionality:
##### Begin recording
##### Output and save a 5 second snippet every 15 seconds
@app.route('/begin_listener')
def begin_listener():

    print("beginning listening")

    snippet_duration = 5 #seconds
    interval_duration = 15 #seconds
    total_recording_time = 60 #seconds

    # Define output folder
    output_folder = 'song_snippets'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    
    # start recording loop
    total_loops = int(total_recording_time / interval_duration)
    
    for i in range(total_loops):

        # Define filename
        timestr = time.strftime("%Y%m%d_%H%M%S")  # Get timestring
        filename_str = 'snippet_'+timestr+'.wav' # Create filename

        # Join to path
        snippet_filepath = os.path.join(output_folder, filename_str)

        try:
            status = record_audio(snippet_filepath, snippet_duration)
            print(status)
        except Exception as e: 
            print(e)

        time.sleep(interval_duration-snippet_duration)

    return "Snippets complete"


# This route is accessible at [IP_ADDRESS]:5000/test_shazam
# Functionality:
##### pick a filename and see if shazam recognizes it
@app.route('/test_shazam')
async def test_shazam():
    filepath = 'song_snippets/test_snippet_20230524_131852.wav' # the breeze - dr dog
    filepath = 'song_snippets/test_snippet_20230524_132647.wav' #random shit


    loop = asyncio.get_event_loop()
    loop.run_until_complete(shazam_test(filepath))

    return "complete"



if __name__ == '__main__':
    app.run()