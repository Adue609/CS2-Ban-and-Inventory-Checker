import tkinter as tk
from tkinter import ttk, scrolledtext
import logging
import threading
import time
import queue
from typing import Optional, Callable

from utils.logger import get_logger

logger = get_logger("GUI")

NOT_PROCESSED_SYMBOL = "No"
PROCESSED_SYMBOL = "Yes"

# Apple Glass Morphism Color Palette
BG_PRIMARY = "#0A0E27"  # Deep dark blue (almost black)
BG_SURFACE = "#1A1F3A"  # Transparent white surface
BG_SURFACE_ALT = "#252D4D"  # Slightly more transparent white
FG_PRIMARY = "#F5F5F7"  # Apple's primary text (slightly off-white)
FG_MUTED = "#A1A1A6"  # Muted text color
ACCENT = "#0A84FF"  # Apple's system blue
SUCCESS = "#34C759"  # Apple's green
WARNING = "#FF9500"  # Apple's orange
DANGER = "#FF3B30"  # Apple's red
CARD_RADIUS = 20  # Larger rounded corners for Apple look

# Thread-safe queue for log messages
_log_queue = queue.Queue()
_inventory_queue = queue.Queue()


def reset_inventory_progress(items: list[str]) -> None:
    _inventory_queue.put({"action": "reset", "items": list(items or [])})


def mark_inventory_processed(item: str, inventory_details: str = "") -> None:
    if not item:
        return
    _inventory_queue.put({
        "action": "processed",
        "item": str(item),
        "inventory_details": str(inventory_details or ""),
    })


class QueueHandler(logging.Handler):
    """Custom logging handler that puts log records into a thread-safe queue."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            _log_queue.put({
                "message": msg,
                "level": record.levelname,
                "thread": record.threadName,
            })
        except Exception:
            self.handleError(record)


class GlassCard(tk.Frame):
    """Apple-style glass morphism card with frosted glass effect."""
    
    def __init__(self, parent, title: str = "", padding: int = 16, **kwargs):
        super().__init__(parent, bg=BG_PRIMARY, **kwargs)
        self._padding = padding
        self._title = title
        
        # Create a canvas for the glass background
        self._canvas = tk.Canvas(
            self,
            bg=BG_PRIMARY,
            highlightthickness=0,
            bd=0,
            relief=tk.FLAT
        )
        self._canvas.pack(fill=tk.BOTH, expand=True)
        
        # Create frame for content
        self.body = tk.Frame(self._canvas, bg=BG_PRIMARY)
        self._window_id = self._canvas.create_window(
            padding, padding,
            anchor="nw",
            window=self.body,
            tags="content"
        )
        
        # Title label
        if title:
            self.title_label = tk.Label(
                self.body,
                text=title,
                bg=BG_PRIMARY,
                fg=FG_PRIMARY,
                font=("SF Pro Display", 13, "bold"),
                anchor="w",
            )
            self.title_label.pack(fill=tk.X, padx=4, pady=(0, 12))
        
        self._canvas.bind("<Configure>", self._on_configure)
        self.bind("<Configure>", self._on_frame_configure)
    
    def _on_frame_configure(self, event=None):
        """Redraw when frame is resized."""
        self._canvas.delete("glass_bg")
        self._draw_glass_background()
    
    def _on_configure(self, event=None):
        """Update window coordinates on canvas resize."""
        width = event.width if event else self.winfo_width()
        height = event.height if event else self.winfo_height()
        
        # Update window position and size
        self._canvas.coords(self._window_id, self._padding, self._padding)
        self._canvas.itemconfig(
            self._window_id,
            width=max(1, width - (self._padding * 2)),
            height=max(1, height - (self._padding * 2))
        )
    
    def _draw_glass_background(self):
        """Draw the frosted glass background."""
        width = self.winfo_width() or 300
        height = self.winfo_height() or 200
        
        # Main rounded rectangle (glass effect)
        r = CARD_RADIUS
        points = [
            r, 0,
            width - r, 0,
            width, 0,
            width, r,
            width, height - r,
            width, height,
            width - r, height,
            r, height,
            0, height,
            0, height - r,
            0, r,
            0, 0,
        ]
        
        self._canvas.create_polygon(
            points,
            smooth=True,
            splinesteps=24,
            fill=BG_SURFACE,
            outline=BG_SURFACE_ALT,
            width=1,
            tags="glass_bg"
        )
        
        # Add subtle inner glow
        self._canvas.create_rectangle(
            2, 2, width - 2, height - 2,
            outline=BG_SURFACE_ALT,
            fill="",
            width=1,
            tags="glass_bg"
        )


# Backward compatibility alias
RoundedCard = GlassCard


class BotControlGUI:
    """GUI for controlling the bot and updating prices with Apple glass morphism design."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("CS2 Ban Checker - Control Panel")
        self.root.geometry("1000x750")
        self.root.minsize(900, 640)
        self.root.resizable(True, True)
        self.root.configure(bg=BG_PRIMARY)
        
        # Apply custom window appearance on macOS
        try:
            if self.root.tk.call('tk', 'windowingsystem') == 'aqua':
                self.root.tk.call('::tk::unsupported::MacWindowStyle', 'style', self.root._w, 'transparent', 'unified')
        except:
            pass

        # Callbacks (will be set by the caller)
        self.on_start_bot: Optional[Callable[[], None]] = None
        self.on_stop_bot: Optional[Callable[[], None]] = None
        self.on_pause_bot: Optional[Callable[[], None]] = None
        self.on_resume_bot: Optional[Callable[[], None]] = None
        self.on_restart_bot: Optional[Callable[[], None]] = None
        self.on_force_update_prices: Optional[Callable[[], None]] = None

        # State
        self.bot_running = False
        self.bot_paused = False

        self._setup_theme()

        # Create UI
        self._create_widgets()
        self._start_log_reader()

    def _setup_theme(self) -> None:
        """Configure Apple-inspired theme."""
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Configure colors for glass morphism
        style.configure("App.TFrame", background=BG_PRIMARY)
        style.configure("Card.TFrame", background=BG_PRIMARY)
        style.configure("App.TLabel", background=BG_PRIMARY, foreground=FG_PRIMARY, font=("SF Pro Display", 10))
        style.configure("Muted.TLabel", background=BG_PRIMARY, foreground=FG_MUTED, font=("SF Pro Display", 10))
        style.configure("Title.TLabel", background=BG_PRIMARY, foreground=FG_PRIMARY, font=("SF Pro Display", 13, "bold"))
        style.configure("Status.TLabel", background=BG_PRIMARY, foreground=FG_PRIMARY, font=("SF Pro Display", 11, "bold"))

        style.configure("App.TLabelframe", background=BG_PRIMARY, borderwidth=0, relief="flat")
        style.configure("App.TLabelframe.Label", background=BG_PRIMARY, foreground=FG_PRIMARY, font=("SF Pro Display", 11, "bold"))

        style.configure(
            "App.TNotebook",
            background=BG_PRIMARY,
            borderwidth=0,
            tabmargins=(2, 2, 2, 0),
        )
        style.configure(
            "App.TNotebook.Tab",
            background=BG_PRIMARY,
            foreground=FG_MUTED,
            padding=(16, 10),
            font=("SF Pro Display", 11),
        )
        style.map(
            "App.TNotebook.Tab",
            background=[("selected", BG_PRIMARY)],
            foreground=[("selected", ACCENT)],
        )

        # Button styling with glass effect
        style.configure(
            "App.TButton",
            background=BG_SURFACE,
            foreground=FG_PRIMARY,
            padding=(14, 10),
            borderwidth=1,
            relief="flat",
            focusthickness=0,
            font=("SF Pro Display", 11, "bold"),
        )
        style.map(
            "App.TButton",
            background=[("active", BG_SURFACE_ALT), ("disabled", BG_PRIMARY)],
            foreground=[("disabled", FG_MUTED)],
            relief=[("pressed", "solid")],
        )

        style.configure("Primary.TButton", background=ACCENT, foreground="#FFFFFF")
        style.map("Primary.TButton", background=[("active", "#0973EA"), ("disabled", BG_SURFACE)])

        style.configure("Danger.TButton", background=DANGER, foreground="#FFFFFF")
        style.map("Danger.TButton", background=[("active", "#E63228"), ("disabled", BG_SURFACE)])

        style.configure("Warning.TButton", background=WARNING, foreground="#000000")
        style.map("Warning.TButton", background=[("active", "#E68600"), ("disabled", BG_SURFACE)])

        style.configure(
            "App.Treeview",
            background=BG_PRIMARY,
            foreground=FG_PRIMARY,
            fieldbackground=BG_PRIMARY,
            bordercolor=BG_SURFACE,
            rowheight=28,
            font=("SF Pro Display", 10),
        )
        style.map("App.Treeview", background=[("selected", BG_SURFACE_ALT)], foreground=[("selected", FG_PRIMARY)])
        style.configure(
            "App.Treeview.Heading",
            background=BG_PRIMARY,
            foreground=FG_PRIMARY,
            relief="flat",
            font=("SF Pro Display", 10, "bold"),
        )
        style.map("App.Treeview.Heading", background=[("active", BG_SURFACE)])

    def _create_widgets(self) -> None:
        """Create the GUI widgets."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="12", style="App.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Create notebook (tabbed interface)
        notebook = ttk.Notebook(main_frame, style="App.TNotebook")
        notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Control Panel
        control_tab = ttk.Frame(notebook, padding="12", style="Card.TFrame")
        notebook.add(control_tab, text="Control Panel")
        self._create_control_tab(control_tab)

        # Tab 2: Logs
        log_tab = ttk.Frame(notebook, padding="12", style="Card.TFrame")
        notebook.add(log_tab, text="Logs")
        self._create_log_tab(log_tab)

        # Tab 3: Inventory Progress
        inventory_tab = ttk.Frame(notebook, padding="12", style="Card.TFrame")
        notebook.add(inventory_tab, text="Inventory Progress")
        self._create_inventory_tab(inventory_tab)

    def _create_control_tab(self, parent: ttk.Frame) -> None:
        """Create the control panel tab with glass morphism design."""
        # Bot Control Section
        bot_card = GlassCard(parent, title="Bot Control", padding=16)
        bot_card.pack(fill=tk.X, pady=(0, 12), padx=0)
        bot_frame = bot_card.body

        button_frame = ttk.Frame(bot_frame, style="Card.TFrame")
        button_frame.pack(fill=tk.X, pady=8)

        self.btn_start = ttk.Button(
            button_frame,
            text="[>] Start Bot",
            command=self._on_start_clicked,
            width=16,
            style="Primary.TButton",
        )
        self.btn_start.pack(side=tk.LEFT, padx=6)

        self.btn_stop = ttk.Button(
            button_frame,
            text="[#] Stop Bot",
            command=self._on_stop_clicked,
            width=16,
            state=tk.DISABLED,
            style="Danger.TButton",
        )
        self.btn_stop.pack(side=tk.LEFT, padx=6)

        self.btn_pause = ttk.Button(
            button_frame,
            text="[||] Pause",
            command=self._on_pause_clicked,
            width=16,
            state=tk.DISABLED,
            style="Warning.TButton",
        )
        self.btn_pause.pack(side=tk.LEFT, padx=6)

        self.btn_resume = ttk.Button(
            button_frame,
            text="[>] Resume",
            command=self._on_resume_clicked,
            width=16,
            state=tk.DISABLED,
            style="App.TButton",
        )
        self.btn_resume.pack(side=tk.LEFT, padx=6)

        self.btn_restart = ttk.Button(
            button_frame,
            text="[*] Restart",
            command=self._on_restart_clicked,
            width=16,
            state=tk.DISABLED,
            style="App.TButton",
        )
        self.btn_restart.pack(side=tk.LEFT, padx=6)

        # Status label
        self.status_label = ttk.Label(
            bot_frame,
            text="Status: Stopped",
            style="Status.TLabel",
            foreground=DANGER,
        )
        self.status_label.pack(pady=8)

        # Price Control Section
        price_card = GlassCard(parent, title="Price Management", padding=16)
        price_card.pack(fill=tk.X, pady=(0, 12), padx=0)
        price_frame = price_card.body

        price_info = ttk.Label(
            price_frame,
            text="Prices are always fetched from cache.\nClick 'Force Update All Prices' to refresh prices from Steam.",
            style="Muted.TLabel",
            justify=tk.LEFT,
        )
        price_info.pack(pady=8)

        self.btn_force_update = ttk.Button(
            price_frame,
            text="[*] Force Update All Prices from Steam",
            command=self._on_force_update_clicked,
            style="App.TButton",
        )
        self.btn_force_update.pack(pady=6, fill=tk.X)

        # Info Section
        info_card = GlassCard(parent, title="Information", padding=16)
        info_card.pack(fill=tk.BOTH, expand=True, padx=0)
        info_frame = info_card.body

        info_text = (
            "Bot Operation:\n"
            "  [>] Start: Begin the continuous check loop (runs every 60 minutes)\n"
            "  [#] Stop: Halt the bot completely\n"
            "  [||] Pause: Temporarily suspend the bot (can be resumed)\n"
            "  [>] Resume: Continue from pause\n\n"
            "Price Management:\n"
            "  - Prices are cached locally and reused from cache\n"
            "  - Click 'Force Update All Prices' to refresh all prices from Steam\n"
            "  - Price cache expires after 7 days (configured)\n\n"
            "Logs:\n"
            "  - Check the 'Logs' tab for real-time operation logs\n"
            "  - Each thread has its own log file in logs/threads/\n"
        )

        info_display = tk.Label(
            info_frame,
            text=info_text,
            font=("SF Pro Display", 10),
            justify=tk.LEFT,
            anchor="nw",
            bg=BG_PRIMARY,
            fg=FG_PRIMARY,
            padx=8,
            pady=8,
        )
        info_display.pack(fill=tk.BOTH, expand=True)

    def _create_log_tab(self, parent: ttk.Frame) -> None:
        """Create the logs tab with glass design."""
        self.log_notebook = ttk.Notebook(parent, style="App.TNotebook")
        self.log_notebook.pack(fill=tk.BOTH, expand=True)

        all_tab = ttk.Frame(self.log_notebook, style="Card.TFrame")
        self.log_notebook.add(all_tab, text="All Logs")

        self.log_display = self._create_scrolled_log_widget(all_tab)
        self._configure_log_tags(self.log_display)
        self._thread_log_displays: dict[str, scrolledtext.ScrolledText] = {}

    def _create_inventory_tab(self, parent: ttk.Frame) -> None:
        """Create the inventory progress tab with glass design."""
        header = ttk.Frame(parent, style="Card.TFrame")
        header.pack(fill=tk.X, pady=(0, 12))

        self.inventory_summary_var = tk.StringVar(value="Total: 0 | Processed: 0")
        ttk.Label(header, textvariable=self.inventory_summary_var, style="Title.TLabel").pack(side=tk.LEFT)

        inventory_card = GlassCard(parent, title="Inventory Progress", padding=16)
        inventory_card.pack(fill=tk.BOTH, expand=True, padx=0)
        tree_container = tk.Frame(inventory_card.body, bg=BG_PRIMARY)
        tree_container.pack(fill=tk.BOTH, expand=True)

        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

        self.inventory_tree = ttk.Treeview(
            tree_container,
            columns=("processed", "target", "inventory_details"),
            show="headings",
            height=20,
            style="App.Treeview",
        )
        self.inventory_tree.heading("processed", text="Processed")
        self.inventory_tree.heading("target", text="Inventory Target")
        self.inventory_tree.heading("inventory_details", text="Inventory Details")
        self.inventory_tree.column("processed", width=90, minwidth=90, stretch=False, anchor="center")
        self.inventory_tree.column("target", width=360, minwidth=220, stretch=True, anchor="w")
        self.inventory_tree.column("inventory_details", width=1100, minwidth=500, stretch=True, anchor="w")
        self.inventory_tree.grid(row=0, column=0, sticky="nsew")

        y_scroll = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.inventory_tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")

        x_scroll = ttk.Scrollbar(tree_container, orient=tk.HORIZONTAL, command=self.inventory_tree.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")

        self.inventory_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self._inventory_row_by_target: dict[str, str] = {}
        self._inventory_processed_count = 0

    def _inventory_target_key(self, value: str) -> str:
        return " ".join(str(value or "").split()).strip().casefold()

    def _create_scrolled_log_widget(self, parent: ttk.Frame) -> scrolledtext.ScrolledText:
        """Create a scrolled text widget with glass morphism styling."""
        widget = scrolledtext.ScrolledText(
            parent,
            wrap=tk.WORD,
            width=100,
            height=30,
            font=("Monaco", 10),
            bg=BG_PRIMARY,
            fg=FG_PRIMARY,
            insertbackground=FG_PRIMARY,
            relief=tk.FLAT,
            borderwidth=0,
        )
        widget.pack(fill=tk.BOTH, expand=True)
        return widget

    def _configure_log_tags(self, widget: scrolledtext.ScrolledText) -> None:
        """Configure log message color tags with Apple color scheme."""
        widget.tag_config("DEBUG", foreground="#8E97A8")
        widget.tag_config("INFO", foreground=ACCENT)
        widget.tag_config("WARNING", foreground=WARNING)
        widget.tag_config("ERROR", foreground=DANGER)
        widget.tag_config("CRITICAL", foreground="#FF1744")

    def _ensure_thread_log_display(self, thread_name: str) -> scrolledtext.ScrolledText:
        display = self._thread_log_displays.get(thread_name)
        if display is not None:
            return display

        tab = ttk.Frame(self.log_notebook, style="Card.TFrame")
        self.log_notebook.add(tab, text=thread_name)
        display = self._create_scrolled_log_widget(tab)
        self._configure_log_tags(display)
        self._thread_log_displays[thread_name] = display
        return display

    def _on_start_clicked(self) -> None:
        """Handle start button click."""
        logger.info("Start bot button clicked")
        if self.on_start_bot:
            try:
                self.on_start_bot()
                self.bot_running = True
                self.bot_paused = False
                self._update_button_states()
                self._update_status("Running")
            except Exception as e:
                logger.error("Failed to start bot: %s", e)

    def _on_stop_clicked(self) -> None:
        """Handle stop button click."""
        logger.info("Stop bot button clicked")
        if self.on_stop_bot:
            try:
                self.on_stop_bot()
                self.bot_running = False
                self.bot_paused = False
                self._update_button_states()
                self._update_status("Stopped")
            except Exception as e:
                logger.error("Failed to stop bot: %s", e)

    def _on_pause_clicked(self) -> None:
        """Handle pause button click."""
        logger.info("Pause bot button clicked")
        if self.on_pause_bot:
            try:
                self.on_pause_bot()
                self.bot_running = True
                self.bot_paused = True
                self._update_button_states()
                self._update_status("Paused")
            except Exception as e:
                logger.error("Failed to pause bot: %s", e)

    def _on_resume_clicked(self) -> None:
        """Handle resume button click."""
        logger.info("Resume bot button clicked")
        if self.on_resume_bot:
            try:
                self.on_resume_bot()
                self.bot_running = True
                self.bot_paused = False
                self._update_button_states()
                self._update_status("Running")
            except Exception as e:
                logger.error("Failed to resume bot: %s", e)

    def _on_restart_clicked(self) -> None:
        """Handle restart button click."""
        logger.info("Restart bot button clicked")
        if self.on_restart_bot:
            try:
                self.on_restart_bot()
                self.bot_running = True
                self.bot_paused = False
                self._update_button_states()
                self._update_status("Running")
            except Exception as e:
                logger.error("Failed to restart bot: %s", e)

    def _on_force_update_clicked(self) -> None:
        """Handle force update prices button click."""
        logger.info("Force update prices button clicked")
        if self.on_force_update_prices:
            # Run in separate thread to not block GUI
            thread = threading.Thread(target=self._force_update_thread, daemon=True)
            thread.start()

    def _on_reset_updated_flags_clicked(self) -> None:
        pass

    def _force_update_thread(self) -> None:
        """Run force update in a background thread."""
        try:
            self.btn_force_update.config(state=tk.DISABLED)
            logger.info("Starting force update of all prices...")
            if self.on_force_update_prices:
                self.on_force_update_prices()
            logger.info("Force update of prices completed")
        except Exception as e:
            logger.error("Force update failed: %s", e)
        finally:
            self.btn_force_update.config(state=tk.NORMAL)

    def _update_button_states(self) -> None:
        """Update button enabled/disabled states based on bot state."""
        if not self.bot_running:
            self.btn_start.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.DISABLED)
            self.btn_pause.config(state=tk.DISABLED)
            self.btn_resume.config(state=tk.DISABLED)
            self.btn_restart.config(state=tk.DISABLED)
        elif self.bot_paused:
            self.btn_start.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            self.btn_pause.config(state=tk.DISABLED)
            self.btn_resume.config(state=tk.NORMAL)
            self.btn_restart.config(state=tk.NORMAL)
        else:
            self.btn_start.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            self.btn_pause.config(state=tk.NORMAL)
            self.btn_resume.config(state=tk.DISABLED)
            self.btn_restart.config(state=tk.NORMAL)

    def _update_status(self, status: str) -> None:
        """Update the status label and color using Apple colors."""
        color_map = {
            "Running": SUCCESS,
            "Paused": WARNING,
            "Stopped": DANGER,
        }
        color = color_map.get(status, FG_PRIMARY)
        self.status_label.config(
            text=f"Status: {status}",
            foreground=color,
        )

    def _start_log_reader(self) -> None:
        """Start a background thread to read logs and update the display."""
        thread = threading.Thread(target=self._log_reader_loop, daemon=True)
        thread.start()

    def _log_reader_loop(self) -> None:
        """Background thread that reads logs and updates GUI."""
        while True:
            try:
                for _ in range(100):
                    payload = _log_queue.get_nowait()
                    self.root.after(0, self._append_log, payload)
            except queue.Empty:
                pass
            except Exception as e:
                logger.exception("Error in log reader: %s", e)

            try:
                for _ in range(100):
                    payload = _inventory_queue.get_nowait()
                    self.root.after(0, self._apply_inventory_update, payload)
            except queue.Empty:
                time.sleep(0.1)
            except Exception as e:
                logger.exception("Error in inventory queue reader: %s", e)
                time.sleep(1)

    def _append_log(self, payload) -> None:
        """Append a message to the log display."""
        try:
            if isinstance(payload, dict):
                message = str(payload.get("message", ""))
                tag = str(payload.get("level", "INFO"))
                thread_name = str(payload.get("thread", "Unknown"))
            else:
                message = str(payload)
                tag = "INFO"
                thread_name = "Unknown"

            self._append_to_display(self.log_display, message, tag)

            thread_display = self._ensure_thread_log_display(thread_name)
            self._append_to_display(thread_display, message, tag)
        except Exception as e:
            logger.exception("Error appending log: %s", e)

    def _append_to_display(self, display: scrolledtext.ScrolledText, message: str, tag: str) -> None:
        display.insert(tk.END, message + "\n", tag)
        display.see(tk.END)

        line_count = int(display.index(tk.END).split(".")[0])
        if line_count > 1000:
            display.delete("1.0", "2.0")

    def _apply_inventory_update(self, payload: dict) -> None:
        action = str(payload.get("action", "")) if isinstance(payload, dict) else ""
        if action == "reset":
            items = payload.get("items", []) if isinstance(payload, dict) else []
            normalized = []
            seen = set()
            for item in items or []:
                value = str(item).strip()
                key = self._inventory_target_key(value)
                if not value or key in seen:
                    continue
                seen.add(key)
                normalized.append(value)

            for row in self.inventory_tree.get_children():
                self.inventory_tree.delete(row)

            self._inventory_row_by_target.clear()
            self._inventory_processed_count = 0

            for target in normalized:
                row_id = self.inventory_tree.insert("", tk.END, values=(NOT_PROCESSED_SYMBOL, target, ""))
                self._inventory_row_by_target[self._inventory_target_key(target)] = row_id

            self._update_inventory_summary()
            return

        if action == "processed":
            target = str(payload.get("item", "")).strip()
            inventory_details = str(payload.get("inventory_details", "")) if isinstance(payload, dict) else ""
            inventory_details = " | ".join(part.strip() for part in inventory_details.splitlines() if part.strip())
            if not target:
                return

            target_key = self._inventory_target_key(target)
            row_id = self._inventory_row_by_target.get(target_key)
            if row_id is None:
                row_id = self.inventory_tree.insert("", tk.END, values=(PROCESSED_SYMBOL, target, inventory_details))
                self._inventory_row_by_target[target_key] = row_id
                self._inventory_processed_count += 1
                self._update_inventory_summary()
                return

            self.inventory_tree.set(row_id, "target", target)
            self.inventory_tree.set(row_id, "inventory_details", inventory_details)
            current = str(self.inventory_tree.set(row_id, "processed"))
            if current != PROCESSED_SYMBOL:
                self.inventory_tree.set(row_id, "processed", PROCESSED_SYMBOL)
                self._inventory_processed_count += 1
                self._update_inventory_summary()

    def _update_inventory_summary(self) -> None:
        total = len(self._inventory_row_by_target)
        self.inventory_summary_var.set(f"Total: {total} | Processed: {self._inventory_processed_count}")


def setup_gui_logging() -> None:
    """Set up logging to the GUI queue."""
    queue_handler = QueueHandler()
    queue_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] [%(threadName)s] %(name)s: %(message)s")
    queue_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(queue_handler)

    logger.info("GUI logging initialized")


def create_gui_window(
    on_start_bot: Callable[[], None],
    on_stop_bot: Callable[[], None],
    on_pause_bot: Callable[[], None],
    on_resume_bot: Callable[[], None],
    on_restart_bot: Callable[[], None],
    on_force_update_prices: Callable[[], None],
) -> tk.Tk:
    """Create and return the main GUI window with callbacks."""
    root = tk.Tk()
    gui = BotControlGUI(root)

    gui.on_start_bot = on_start_bot
    gui.on_stop_bot = on_stop_bot
    gui.on_pause_bot = on_pause_bot
    gui.on_resume_bot = on_resume_bot
    gui.on_restart_bot = on_restart_bot
    gui.on_force_update_prices = on_force_update_prices

    return root
