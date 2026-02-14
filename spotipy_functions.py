def search_song(sp, song_info):
    """Search for a song on Spotify.

    Args:
        sp: Spotify client instance
        song_info: Search query string

    Returns:
        First track result or None if no matches found
    """
    search_str = song_info
    result = sp.search(search_str, type='track', limit=1)

    # Safely get items with error handling
    items = result.get("tracks", {}).get('items', [])

    if not items:
        return None

    return items[0]


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
