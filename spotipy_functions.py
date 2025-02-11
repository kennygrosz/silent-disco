
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth


def search_song(sp, song_info):
    
    search_str = song_info
    result = sp.search(search_str, type = 'track')
    # song_id = result["tracks"]['items'][0]['id'] #pick first result

    
    return result["tracks"]['items'][0]

def is_interruption_allowed(sp):
    """ 
    Checks current spotify session, returns True if interrupting the session is allowed. 
    
    Interruption is NOT allowed if there is another song actively playing on spotify
    """

    is_interruption_allowed = True

    current_playback_output = sp.current_playback()

#    print(test_output)

    if current_playback_output is None:
        return_message = "No active session. Interrupt away!"

    elif 'is_playing' in current_playback_output and current_playback_output['is_playing'] is True:
        is_interruption_allowed = False
        return_message = "There is an active spotify session right now and music is playing. Interruption not allowed. Skipping...."

    elif 'is_playing' in current_playback_output and current_playback_output['is_playing'] is False:
        return_message = "There is an active spotify session right now but music is NOT playing. Interruption is allowed."
        is_interruption_allowed = True
    else:
        return_message = "No active session. Interrupt away!"


    return is_interruption_allowed, return_message