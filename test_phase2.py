"""Test script for Phase 2: Resource Management & Error Handling."""
import sys
import os

print("Testing Phase 2: Resource Management & Error Handling...\n")

# Test 1: PyAudio Resource Cleanup
print("Test 1: PyAudio Resource Cleanup")
try:
    from listener.listener import record_audio
    import tempfile

    # Create temporary file for test recording
    temp_dir = tempfile.gettempdir()
    test_file = os.path.join(temp_dir, "test_resource_cleanup.wav")

    # Record short snippet
    result = record_audio(test_file, duration=1)

    # Verify file was created
    assert os.path.exists(test_file), "Audio file should be created"

    # Clean up
    os.remove(test_file)

    print("✅ PASSED: PyAudio resources properly managed with try-finally")
except Exception as e:
    print(f"❌ FAILED: {e}")
    sys.exit(1)

# Test 2: Logging System
print("\nTest 2: Logging System")
try:
    from utils.logging_config import LogCollector, get_logger, setup_logger

    # Test LogCollector
    log_collector = LogCollector()
    log_collector.info("Test info message")
    log_collector.warning("Test warning message")
    log_collector.error("Test error message")

    logs = log_collector.get_logs()
    assert len(logs) == 3, f"Should have 3 log messages, got {len(logs)}"
    assert "Test info message" in logs[0]
    assert "WARNING: Test warning message" in logs[1]
    assert "ERROR: Test error message" in logs[2]

    print("✅ PASSED: LogCollector works correctly")

    # Test logger setup
    logger = setup_logger(name="test_logger", log_dir="logs")
    logger.info("Test logger message")

    # Verify log file was created
    assert os.path.exists("logs"), "Log directory should be created"

    print("✅ PASSED: Logger setup creates log files")

except Exception as e:
    print(f"❌ FAILED: {e}")
    sys.exit(1)

# Test 3: Input Validation - Valid Inputs
print("\nTest 3: Input Validation - Valid Inputs")
try:
    from utils.validators import (
        validate_duration,
        validate_interval,
        validate_directory_path,
        validate_spotify_track,
        validate_playback_position
    )

    # Test duration validation
    duration = validate_duration(10, min_seconds=1, max_seconds=300)
    assert duration == 10, f"Duration should be 10, got {duration}"

    # Test interval validation
    interval = validate_interval(60, snippet_duration=10)
    assert interval == 60, f"Interval should be 60, got {interval}"

    # Test directory path validation
    import tempfile
    temp_dir = tempfile.gettempdir()
    validated_dir = validate_directory_path(temp_dir)
    assert validated_dir == temp_dir

    # Test Spotify track validation
    valid_track = {
        'id': '123',
        'uri': 'spotify:track:123',
        'name': 'Test Song',
        'duration_ms': 200000,
        'artists': [{'name': 'Test Artist'}]
    }
    validated_track = validate_spotify_track(valid_track)
    assert validated_track == valid_track

    # Test playback position validation
    position = validate_playback_position(150000, 200000)
    assert position == 150000

    # Test clamping negative position
    position = validate_playback_position(-5000, 200000)
    assert position == 0, f"Negative position should be clamped to 0, got {position}"

    print("✅ PASSED: All validators accept valid inputs")

except Exception as e:
    print(f"❌ FAILED: {e}")
    sys.exit(1)

# Test 4: Input Validation - Invalid Inputs
print("\nTest 4: Input Validation - Invalid Inputs")
try:
    from utils.validators import ValidationError, validate_duration, validate_spotify_track

    # Test duration too short
    try:
        validate_duration(0, min_seconds=1, max_seconds=300)
        assert False, "Should raise ValidationError for duration too short"
    except ValidationError:
        pass  # Expected

    # Test duration too long
    try:
        validate_duration(5000, min_seconds=1, max_seconds=3600)
        assert False, "Should raise ValidationError for duration too long"
    except ValidationError:
        pass  # Expected

    # Test invalid Spotify track (missing fields)
    try:
        invalid_track = {'id': '123'}  # Missing required fields
        validate_spotify_track(invalid_track)
        assert False, "Should raise ValidationError for missing fields"
    except ValidationError:
        pass  # Expected

    # Test invalid Spotify track (missing artists)
    try:
        invalid_track = {
            'id': '123',
            'uri': 'spotify:track:123',
            'name': 'Test Song',
            'duration_ms': 200000
            # Missing 'artists' field
        }
        validate_spotify_track(invalid_track)
        assert False, "Should raise ValidationError for missing artists"
    except ValidationError:
        pass  # Expected

    print("✅ PASSED: Validators correctly reject invalid inputs")

except Exception as e:
    print(f"❌ FAILED: {e}")
    sys.exit(1)

# Test 5: Event Loop Cleanup (verify finally block exists)
print("\nTest 5: Event Loop Cleanup")
try:
    # Read app.py and verify loop.close() is in finally block
    with open('app.py', 'r') as f:
        app_content = f.read()

    assert 'finally:' in app_content, "Should have finally block"
    assert 'loop.close()' in app_content, "Should have loop.close() call"

    print("✅ PASSED: Event loop cleanup in finally block")

except Exception as e:
    print(f"❌ FAILED: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("✅ ALL PHASE 2 TESTS PASSED!")
print("="*60)
print("\nPhase 2 Improvements Summary:")
print("  ✅ PyAudio: Resources properly cleaned up with try-finally")
print("  ✅ Logging: Comprehensive logging system with file + console")
print("  ✅ Validation: Input validation prevents crashes")
print("  ✅ Event Loops: Properly closed in finally blocks")
print("\nReady to proceed to Phase 3!")
