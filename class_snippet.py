from datetime import datetime
import os

# #defining class for snippets

class Snippet:
    def __init__(self, output_folder="song_snippets", snippet_duration=5):
        self.output_folder = output_folder
        self.snippet_duration = snippet_duration
        self.timestamp = datetime.now()
        self.timestamp_str = self.timestamp.strftime("%Y%m%d_%H%M%S")
        self.filename_str = 'snippet_'+self.timestamp_str+'.wav' 
        self.snippet_filepath = os.path.join(self.output_folder, self.filename_str)
        self.is_recorded = False
        self.is_recognized = False
        self.is_queuable = False 
        self.is_queued = False 
        self.track_string = None
        self.song_id = None
        self.song_uri = None
        self.song_name = None
        self.song_artist = None
        self.duration_ms = None



