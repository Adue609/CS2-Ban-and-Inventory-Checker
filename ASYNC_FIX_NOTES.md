# Fix: Bot Event Loop Synchronization

## Problem

When the GUI tried to start/stop the bot via buttons, the following errors occurred:
```
RuntimeWarning: coroutine 'Loop._loop' was never awaited
Failed to start check_steam: no running event loop
```

### Root Cause

The GUI thread was trying to schedule tasks on `bot.loop` before the bot's event loop was fully initialized and running. Discord.py event loops are only ready after the `on_ready()` event fires.

## Solution

### 1. Added Event Synchronization Signal

```python
_bot_ready = asyncio.Event()  # Signal when bot event loop is ready
```

This allows the bot to signal when its event loop is ready.

### 2. Set Signal in on_ready()

```python
@bot.event
async def on_ready():
    # Signal that bot event loop is ready
    if not _bot_ready.is_set():
        _bot_ready.set()
```

This ensures the GUI knows when it's safe to schedule tasks.

### 3. Created Helper Coroutines

```python
async def _start_check_steam():
    """Helper coroutine to start the check_steam task."""
    try:
        check_steam.start()
    except Exception as e:
        logger.error("Error starting check_steam: %s", e)

async def _stop_check_steam():
    """Helper coroutine to stop the check_steam task."""
    try:
        check_steam.stop()
    except Exception as e:
        logger.error("Error stopping check_steam: %s", e)
```

These properly execute within the bot's event loop context.

### 4. Updated GUI Callbacks

GUI buttons now:
1. Check if `_bot_ready.is_set()` before scheduling
2. Use `asyncio.run_coroutine_threadsafe()` to execute on bot's loop
3. Call the helper coroutines which execute `check_steam` methods

```python
def on_start_bot():
    if not check_steam.is_running():
        try:
            if _bot_ready.is_set():
                asyncio.run_coroutine_threadsafe(
                    _start_check_steam(),
                    bot.loop
                )
        except Exception as e:
            logger.error("Failed to start check_steam: %s", e)
```

## Flow

1. **Discord bot connects** ? `on_ready()` fires
2. **on_ready() sets `_bot_ready` event**
3. **GUI thread can now safely schedule tasks** on bot's loop
4. **User clicks Start Bot**
5. **GUI verifies event loop is ready** via `_bot_ready.is_set()`
6. **GUI schedules coroutine on bot's loop** via `asyncio.run_coroutine_threadsafe()`
7. **Coroutine executes** in proper async context

## Result

? No more "no running event loop" errors  
? No more unawaited coroutine warnings  
? GUI buttons work reliably  
? Proper cross-thread async scheduling  

## Testing

1. Run `python BanChecker.py`
2. Wait for GUI window to appear
3. Discord bot connects (visible in logs)
4. Click "Start Bot" in GUI
5. `check_steam` loop starts without errors
6. Click "Pause", "Resume", "Stop" as needed
