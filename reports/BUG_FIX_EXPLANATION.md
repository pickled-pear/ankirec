# Windows Audio Recording Input Lag - Root Cause & Fix

## The Problem

When recording stops and the input dialog appears, you experienced:
- **2 second delays** between key presses and text appearing
- **System-wide sluggishness**: Alt+Tab, Task Manager, and general typing all lagged
- **Self-resolving issue**: Lag improved or disappeared when the dialog window closed

This is a classic **Windows COM threading deadlock** scenario.

## Root Causes

### 1. COM Object References Held After Recording
The `soundcard` library wraps WASAPI (Windows Audio Session API) as COM objects. When recording stopped:
- The recorder object was not being explicitly closed
- COM objects were held in thread-local storage without cleanup
- Windows was unable to release resources tied to those COM objects

### 2. Recording Thread Blocking Message Processing
Windows has a critical requirement: **COM objects on a thread must periodically process Windows messages**. Your recording thread was:
- Holding references to the COM recorder after `is_recording = False`
- Not being garbage collected promptly
- Preventing the Windows message queue from being drained
- This starved the main UI thread of message processing

### 3. The Cascade Effect
- Main UI thread (running the dialog) couldn't process input messages
- Keyboard input piled up in the Windows message queue
- Each key press took ~2 seconds (COM timeout waiting for the thread to process messages)
- System-wide lag occurred because Windows couldn't dispatch messages to any application

## The Solution

### Fix 1: Explicit COM Object Cleanup (audio_windows.py)
```python
# In stop():
with self._lock:
    self.mic = None  # Release the COM device object immediately

import gc
gc.collect()  # Force garbage collection to clean up COM wrappers
```

**Why this works**: Releasing the `self.mic` reference and forcing garbage collection tells Windows that COM objects are no longer needed, freeing up Windows message queue resources.

### Fix 2: Explicit Recorder Context Exit (audio_windows.py)
```python
# In _record_loop():
recorder.__exit__(None, None, None)  # Explicitly close the context
recorder = None  # Release the reference
import gc
gc.collect()  # Force cleanup
```

**Why this works**: The `soundcard` recorder is a context manager. Explicitly calling `__exit__` ensures WASAPI resources are freed before the thread ends. Releasing the reference and forcing garbage collection removes any lingering COM wrappers.

### Fix 3: Message Queue Pump & Delay (flashcard.py)
```python
time.sleep(0.2)  # Give COM thread time to finish cleanup

# Pump the Windows message queue briefly
for _ in range(5):
    ctypes.windll.user32.PeekMessageA(...)
    ctypes.windll.kernel32.Sleep(10)
```

**Why this works**: 
- The sleep gives the recording thread time to finish `CoUninitialize()`
- Manually pumping the message queue with `PeekMessageA` drains queued input events
- This prevents a backlog of input that the UI thread would struggle to process

### Fix 4: Reduced Thread Join Timeout
Changed from 5 seconds to 2 seconds:
```python
self.record_thread.join(timeout=2)
```

**Why this works**: If the thread doesn't exit within 2 seconds, it's better to proceed anyway (and possibly show the dialog sluggish) than to block the main thread for 5 seconds, making the lag worse.

## Technical Details

### Windows Threading Model
- Each COM thread must initialize with `CoInitialize()`
- COM objects created on that thread are apartment-model bound
- Those objects must receive Windows messages to function properly
- If the thread is blocked or references are held, the message queue fills up

### The Cascade
```
Recording thread holds COM recorder → Recorder holds message pump lock
     ↓
Recorder not released after stop
     ↓
GC doesn't clean up COM wrappers
     ↓
Windows can't reclaim COM thread resources
     ↓
Message queue fills up
     ↓
Main UI thread can't process input
     ↓
2s delays on every keystroke
```

## Testing the Fix

1. **Record audio**: Press Alt+GR to start/stop
2. **Check responsiveness**: Open the dialog
3. **Type immediately**: You should see text appear within ~100 ms, not 2 seconds
4. **Monitor**: The lag should be gone or minimal

If lag persists, check:
- Is `ffmpeg` running in the background? (Check Task Manager)
- Are there other audio applications interfering?
- Is your system low on memory? (Could trigger aggressive GC)

## Prevention for Future Development

When working with COM objects on Windows:
1. **Always explicitly close/release** context managers and COM objects
2. **Force garbage collection** after releasing COM references
3. **Test on a clean reboot** — COM state can accumulate over time
4. **Use non-daemon threads** for COM work (you already do this)
5. **Keep COM thread operations short** — don't hold references longer than needed
6. **Pump the message queue** if the main thread might block during COM cleanup
