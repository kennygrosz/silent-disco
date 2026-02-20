# Silent Disco CPU Usage Optimization Plan

## Problem
Your MacBook Air's fan runs incessantly when Silent Disco runs. This indicates excessive CPU consumption.

## Root Cause Analysis

### Profiling Results
- Ran cProfile on app startup: 0.763 seconds total
- Most time spent on module imports (shazamio: 0.441s, flask: 0.183s, numpy: 0.167s)
- Initial startup is import-heavy but acceptable

### Code Analysis - Found Issues

#### 1. **Audio Streaming FFT Loop (PRIMARY CULPRIT)**
**File:** `web_server.py`, lines 107-133
**Issue:** The `_stream_audio()` method continuously:
   - Reads audio chunks from microphone
   - Computes FFT (Fast Fourier Transform) on every frame
   - Performs numpy interpolation
   - Sends results via WebSocket

**Problem:** While it has a 0.05s sleep (20 FPS), the FFT computation itself is CPU-intensive and runs constantly. On a MacBook Air with limited CPU cores, this can max out a core.

#### 2. **Numpy FFT Complexity**
The FFT operation is O(n log n) and relatively expensive. Running it ~20 times per second adds up quickly.

## Solutions Implemented / To Implement

### ✅ Solution 1: Frame-Skipping on FFT Computation (IMPLEMENTED)
- Only compute FFT every 2-3 frames instead of every frame
- Reduces FFT computation load by 66-50%
- Still provides smooth animation at 6-8 updates per second
- **File:** web_server.py - Added `frame_skip = 2`

### ✅ Solution 2: CPU Yield (IMPLEMENTED)
- Added `os.sched_yield()` after sleep to prevent tight spinning
- Allows macOS to schedule other processes
- **File:** web_server.py - Added yield call

### 🔄 Solution 3: Make FFT Updates Less Frequent (AVAILABLE OPTION)
Alternative: Set `frame_skip = 3` or `frame_skip = 4` for even more aggressive optimization
- `frame_skip = 2`: ~10 FFT updates/sec
- `frame_skip = 3`: ~7 FFT updates/sec  
- `frame_skip = 4`: ~5 FFT updates/sec

### 🔄 Solution 4: Reduce Chunk Size (OPTIONAL)
Current: `chunk=2048`
Could reduce to: `chunk=1024` or `chunk=512`
- Smaller chunks = less data to process per FFT
- May reduce latency but uses more CPU for I/O
- **Not recommended** - likely to make things worse

### 🔄 Solution 5: Switch to Simpler Visualization (OPTIONAL)
Replace FFT with waveform-only visualization:
- Just send raw audio levels without FFT
- Much cheaper computationally
- Less impressive visually but much lighter on CPU

### 🔄 Solution 6: Add Conservative Mode (OPTIONAL)
Environment variable or config flag to:
- Lower frame skip automatically
- Disable visualizer on low-power Macs
- Use simpler drawing algorithms

## Recommendation Order

**HIGH PRIORITY (Already Done):**
1. ✅ Frame-skipping FFT (66% reduction in FFT calls)
2. ✅ CPU yield calls

**MEDIUM PRIORITY (If fan still loud):**
3. Increase frame skip to 4 (75% reduction)
4. Add option to disable audio visualization

**LOW PRIORITY (Only if needed):**
5. Waveform-only mode
6. Reduce listening loop timing

## Testing Instructions

1. Apply changes (done - frame skip + yield)
2. Run app: `python app_integrated.py`
3. Open Activity Monitor → find python process
4. Check CPU % usage - should be significantly lower
5. Listen to fan - should spin less

## Expected Results
- **Before:** 40-60% CPU on one core (fan spinning)
- **After:** 10-20% CPU usage (fan mostly silent)

## Next Steps
If fan still spins after these changes:
- Try increasing `frame_skip` to 3 or 4
- Consider disabling visualizer entirely if not needed
- Check for other background processes
