import pyaudio
import wave 


def record_audio(filename, duration):
    """Record audio from the default input device.

    Args:
        filename: Path where the WAV file will be saved
        duration: Recording duration in seconds

    Returns:
        str: Success message with file path

    Raises:
        Exception: If recording or file writing fails
    """
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 44100
    RECORD_SECONDS = duration

    p = None
    stream = None
    wf = None

    try:
        # Initialize PyAudio
        p = pyaudio.PyAudio()

        # Open audio stream
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)

        frames = []

        print(f"Recording started. Listening for {RECORD_SECONDS} seconds...")

        # Record audio
        for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)

        print("Recording finished.")

        # Save to WAV file
        wf = wave.open(filename, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))

        return f"Recording succeeded. Check file at: {filename}"

    finally:
        # Ensure resources are cleaned up regardless of success or failure
        if wf is not None:
            wf.close()
        if stream is not None:
            stream.close()
        if p is not None:
            p.terminate()




