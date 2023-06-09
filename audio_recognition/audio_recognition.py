
from shazamio import Shazam
import asyncio
import ffmpeg


async def shazam_test(audio_filepath):
    
    shazam = Shazam()
    alldata = await shazam.recognize_song(audio_filepath)

    if 'track' in alldata:
        # Get artist and track data
        trackdata = alldata['track']
        trackid = trackdata['subtitle'] + " - " + trackdata['title']

        print(trackdata)

        return trackdata
    else:
        print("Song unidentified")

    

        # # Move file from 'new_recordings' to 'old_recordings' directory and rename to Track ID
        # os.replace(newrec_path + "/" + files, oldrec_path + "/" + trackid + " [Analyzed " + current_timestamp + "]" + extension)
        # # Count your successes
        # current_success_counter += 1
        # # Write to log file and print current analysis status
        # file.write("Track " + str(current_id_counter) + "/" + str(newrec_file_counter) + ": " + trackid + "\n")
        # print("Track " + str(current_id_counter) + "/" + str(newrec_file_counter) + " found: " + trackid)