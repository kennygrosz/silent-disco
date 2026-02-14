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