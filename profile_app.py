"""Wrapper to profile app_integrated.py for 30 seconds."""
import cProfile
import signal
import sys
from contextlib import contextmanager

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Profiling timeout")

@contextmanager
def time_limit(seconds):
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)

if __name__ == "__main__":
    profiler = cProfile.Profile()
    
    try:
        with time_limit(30):
            profiler.enable()
            # Import and run the app
            import app_integrated
            # The app's main will run
            profiler.disable()
    except TimeoutException:
        print("\nProfiling completed after 30 seconds")
        profiler.disable()
    except KeyboardInterrupt:
        print("\nProfiling interrupted by user")
        profiler.disable()
    except Exception as e:
        print(f"Error: {e}")
        profiler.disable()
    finally:
        # Save the profile
        profiler.dump_stats("profile.out")
        print("Profile saved to profile.out")
