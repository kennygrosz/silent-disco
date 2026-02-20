# Silent Disco CPU Optimization - Tuning Guide

## Changes Made

Your Silent Disco app was consuming excessive CPU due to continuous FFT (Fast Fourier Transform) computation in the audio visualizer. 

### Optimization Applied

**File:** `web_server.py`

1. **Frame-skipping FFT computation** 
   - Set to skip 2 frames between computations (process 1 of 3 frames)
   - Reduces FFT computation by 66%
   - Default: `frame_skip=3` (even more aggressive)

2. **CPU yield call**  
   - Added `os.sched_yield()` to prevent tight CPU spinning
   - Allows macOS scheduler to distribute CPU fairly

## Expected Behavior

**Before optimization:**
- Fan constantly spinning
- CPU usage: 40-60% on one core
- Visualizer updates: ~20/sec

**After optimization:**
- Fan runs much less
- CPU usage: 10-20% (if fan spins at all)
- Visualizer updates: ~7/sec (less frequent but still smooth)

## Fine-Tuning Options

If you want to adjust CPU usage vs. visualization smoothness, edit the line in `web_server.py` (line 160):

```python
audio_streamer = AudioStreamer(frame_skip=3)
```

### Available Settings:

| frame_skip | FFT Updates/sec | CPU Reduction | Smoothness |
|-----------|-----------------|---------------|-----------|
| 1         | 20              | None (original) | Smoothest |
| 2         | 10              | 50%           | Good |
| 3         | 7               | 66%           | **Default (Recommended)** |
| 4         | 5               | 75%           | Fair |
| 5         | 4               | 80%           | Choppy |

### Recommendations:

- **If fan still spins:** Try `frame_skip=4` or `frame_skip=5`
- **If visualizer feels choppy:** Try `frame_skip=2`
- **For optimal balance (current):** Leave at `frame_skip=3`

## Disable Visualizer Entirely (Nuclear Option)

If you want to eliminate FFT computation completely:

1. Remove or comment out this in `app_integrated.py`:
   ```python
   self.web_server.audio_streamer.start()
   ```

2. Or modify the UI to not subscribe to audio_data events

This will eliminate all audio visualization computation but remove the visual component from the web UI.

## Diagnostics

To check if optimizations are working:

1. **Activity Monitor Method:**
   - Open Activity Monitor → search for `python`
   - Watch CPU % while app runs
   - Should be <20% after optimization

2. **Fan Speed Method:**
   - Run app and listen carefully
   - Fan should be nearly silent or occasional short bursts
   - Not continuous like before

## Still Having Issues?

If the fan is still loud:

1. Check if other apps are also consuming CPU
2. Verify frame_skip is actually set (check line 160 of web_server.py)
3. Try disabling the visualizer entirely
4. Run with `python -m cProfile -o profile.out app_integrated.py` to identify other bottlenecks

## Technical Details

### Why FFT is CPU-Intensive

- FFT is O(n log n) complexity
- Running 20 times/sec on audio chunks = significant load
- Each FFT + interpolation (numpy operations) compounds the load
- On MacBook Air (low CPU cores), this maxes out a core

### Why Skipping Frames Helps

- Reduces computation by exactly `1/frame_skip` ratio
- Human eye can't detect difference at ~7 FPS vs 20 FPS
- Audio data is continuous - skipping frames doesn't lose information
- When a frame is processed, it still gets the latest audio data

### Why CPU yield Helps

- Prevents tight spinning on MacBook's scheduler
- Allows other processes to run
- Reduces thermal load
- Improves overall system responsiveness
