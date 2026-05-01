# GUI Control Panel

The GUI control panel provides a user-friendly interface to manage the CS2 Ban Checker bot and price updates.

## Features

### Control Panel Tab

**Bot Control Buttons:**
- **Start Bot**: Launch the continuous check loop (runs every 60 minutes)
- **Stop Bot**: Halt the bot completely
- **Pause**: Temporarily suspend bot checks (can be resumed)
- **Resume**: Continue from pause state

**Status Indicator:**
- Displays current bot state with color coding:
  - Green: Running
  - Orange: Paused
  - Red: Stopped

**Price Management:**
- **Force Update All Prices**: Manually refresh all item prices from Steam
  - Prices are always fetched from cache during normal operation
  - This button forces a complete refresh from Steam API
  - Button is disabled during update to prevent concurrent updates

**Information Section:**
- Quick reference guide for all operations

### Logs Tab

Real-time log viewer with:
- Color-coded log levels:
  - Gray: DEBUG
  - Blue: INFO
  - Orange: WARNING
  - Red: ERROR
  - Dark Red: CRITICAL
- Scrollable display (keeps last 1000 lines)
- Thread names visible for multi-threaded debugging
- Automatic scroll to latest message

## Usage

### Starting the GUI

The GUI is automatically launched when `BanChecker.py` is run:

```bash
python BanChecker.py
```

The GUI window opens alongside the Discord bot. The bot **does NOT auto-start** when using the GUI - you must click "Start Bot" to begin the check loop.

### Basic Workflow

1. **Wait for GUI to initialize**
   - The Discord bot connects automatically
   - GUI window appears and is ready for commands

2. **Start the bot** by clicking "Start Bot"
   - GUI signals the bot to begin the continuous check loop (runs every 60 minutes)
   - Status indicator turns green (Running)
   - Check the Logs tab to monitor operations

3. **Monitor status** in the status indicator
   - Green: Bot running and checking profiles
   - Orange: Bot paused (can resume)
   - Red: Bot stopped
   - Check logs tab for detailed operations

4. **Update prices manually** by clicking "Force Update All Prices"
   - Use when you need fresh pricing data from Steam
   - Button disables while updating to prevent concurrent requests
   - Does not interrupt bot check operations

5. **Pause/Resume** as needed:
   - **Pause**: Suspends checks without stopping the bot (resume later)
   - **Resume**: Continue checks from paused state
   - Useful for maintenance or manual updates

6. **Stop Bot** when done
   - Halts all profile checking operations
   - Discord connection remains active
   - Can start again with "Start Bot" button

## Architecture

### GUI Components

- `utils/gui.py`: Contains `BotControlGUI` class and supporting functions
- `QueueHandler`: Thread-safe logging handler for GUI display
- `BotControlGUI`: Main GUI window with tabs and controls

### Integration with BanChecker

The GUI runs in a separate thread and communicates with the main bot via:
- Global state variables (`_bot_running`, `_bot_paused`, `_gui_ready`)
- Callback functions for bot control
- Thread-safe queue for log messages
- Signal flag that tells Discord `on_ready()` whether to auto-start the check loop

### Bot Startup Logic

When `BanChecker.py` runs:
1. GUI thread starts and initializes
2. `_gui_ready` flag is set to `True`
3. Discord bot connects
4. In `on_ready()` event, bot checks if GUI is ready:
   - If GUI is ready: **Does NOT auto-start** the check loop (waits for GUI commands)
   - If GUI is not ready (error/timeout): **Auto-starts** the check loop (fallback mode)
5. User clicks "Start Bot" in GUI to begin the check loop

### Thread Safety

- Log messages passed through thread-safe `queue.Queue`
- All Tkinter updates via `root.after()` for thread safety
- Button state updates synchronized with bot state

## Customization

### Changing GUI Window Size

In `utils/gui.py`, modify the `geometry` call:

```python
self.root.geometry("900x700")  # width x height
```

### Adding More Controls

Add buttons/controls in `_create_control_tab()` method:

```python
new_button = ttk.Button(
    parent_frame,
    text="Button Label",
    command=self._callback_method,
)
new_button.pack(side=tk.LEFT, padx=5)
```

### Adjusting Log Display

Change number of retained lines in `_append_log()`:

```python
if line_count > 1000:  # Modify this value
    self.log_display.delete("1.0", "2.0")
```

## Requirements

- Python 3.8+
- tkinter (included with most Python distributions)
- discord.py
- requests

## Notes

- GUI gives 1 second for Discord to connect before starting the check loop loop
- Bot **does not auto-start** when GUI is active (you must click "Start Bot")
- If GUI fails to initialize, bot auto-starts the check loop (fallback for errors)
- All bot logic remains in `BanChecker.py`
- Prices are always cached unless explicitly updated via "Force Update All Prices"
- Each thread logs to `logs/threads/<thread_name>.log`
- GUI logs visible in console and GUI log tab simultaneously
- Button states always reflect actual bot state
