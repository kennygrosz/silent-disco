
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth


def search_song(sp, song_info):
    
    search_str = song_info
    result = sp.search(search_str, type = 'track')
    # song_id = result["tracks"]['items'][0]['id'] #pick first result

    
    return result["tracks"]['items'][0]