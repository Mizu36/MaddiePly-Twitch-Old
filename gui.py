import asyncio
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from functools import partial
import pygame
import sys
import io
import queue
import os
from json_manager import load_settings, save_settings, load_scheduled_messages, save_scheduled_messages, save_prompts, load_prompts
from audio_player import AUDIO_DEVICES, AudioManager
import bot_utils
from eleven_labs_manager import MODELS
from azure_speech_to_text import VOICES

pygame.init()
AudioManager.list_output_devices()
AD_LENGTHS = [30, 60, 90, 120, 150, 180]

class Redirector(io.StringIO):
    COLOR_TAGS = {
        "ERROR": {"foreground": "red"},
        "WARNING": {"foreground": "yellow"},
        "DEBUG": {"foreground": "light green"},
        "INFO": {"foreground": "white"},
        "GREEN": {"foreground": "green"},
        "ORANGE": {"foreground": "orange"},
        "YELLOW": {"foreground": "yellow"},
        "RED": {"foreground": "red"}
        # Add more custom tags/colors here
    }

    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self._setup_tags()

    def _setup_tags(self):
        for tag, opts in self.COLOR_TAGS.items():
            self.text_widget.tag_configure(tag, **opts)
        self.text_widget.tag_configure("DEFAULT", foreground="white")

    def write(self, s):
        for line in s.splitlines(True):
            tag, text = self._parse_tag(line)
            self.text_widget.after(0, lambda t=text, tg=tag: self._insert(t, tg))

    def _insert(self, text, tag):
        self.text_widget.insert(tk.END, text, tag)
        self.text_widget.see(tk.END)

    def _parse_tag(self, line):
        import re
        # Check for [TAG] at the start
        match = re.match(r"\[(\w+)\]\s*", line)
        if match:
            tag = match.group(1).upper()
            text = line[match.end():]
            if tag in self.COLOR_TAGS:
                return tag, text
        # Check for traceback or error/exception anywhere in the line
        if "Traceback" in line or "Error" in line or "Exception" in line:
            return "ERROR", line
        # Check for warning (case-insensitive)
        if re.search(r"warning", line, re.IGNORECASE):
            return "WARNING", line
        return "DEFAULT", line

    def flush(self):
        pass

class TwitchBotGUI(tk.Tk):
    async def async_init(self):
        await self.load_all_data()

    def __init__(self, gui_queue, loop):
        super().__init__()
        self.gui_queue = gui_queue
        self.loop = loop
        self.title("MaddiePly Twitch Bot")
        icon_path = os.path.join(os.path.dirname(__file__), "bot_icon.ico")
        self.iconbitmap(icon_path)
        self.geometry("700x950")
        self.settings = {}
        self.scheduled_tasks = {}
        self.listening_hotkey = None
        self.bot = None

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True)

        self.settings_tab = ttk.Frame(self.notebook)
        self.tasks_tab = ttk.Frame(self.notebook)
        self.prompts_tab = ttk.Frame(self.notebook)
        self.console_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.settings_tab, text='Settings')
        self.notebook.add(self.tasks_tab, text='Scheduled Tasks')
        self.notebook.add(self.prompts_tab, text='GPT Prompts')
        self.notebook.add(self.console_tab, text='Console')

        self.create_settings_tab()
        self.create_tasks_tab()
        self.create_prompts_tab()
        self.create_console_tab()
        
        self.after(100, self.poll_gui_queue)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def poll_gui_queue(self):
        try:
            while True:
                msg = self.gui_queue.get_nowait()
                self.console_text.insert(tk.END, msg + "\n")
                self.console_text.see(tk.END)
        except queue.Empty:
            pass
        self.after(100, self.poll_gui_queue)

    def set_bot(self):
        self.bot = bot_utils.get_bot_instance()

    def create_settings_tab(self):
        # Create a canvas and a vertical scrollbar for scrolling
        container = ttk.Frame(self.settings_tab)
        container.pack(fill='both', expand=True)

        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.settings_frame = ttk.Frame(canvas)

        self.settings_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=self.settings_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.settings_widgets = {}

        def add_entry(parent_frame, label, key, parent=None, readonly=False):
            ttk.Label(parent_frame, text=label).pack(anchor="w", padx=5, pady=2)
            entry = ttk.Entry(parent_frame)
            entry.pack(fill="x", padx=5, pady=2)
            value = self.settings.get(key, "")
            entry.insert(0, value)
            if readonly:
                entry.config(state="readonly")
            if parent:
                if parent not in self.settings_widgets:
                    self.settings_widgets[parent] = {}
                self.settings_widgets[parent][key] = entry
            else:
                self.settings_widgets[key] = entry

        # --- Basic Settings ---
        basic_frame = ttk.LabelFrame(self.settings_frame, text="Basic Settings")
        # --- Resub Settings ---
        resub_frame = ttk.LabelFrame(self.settings_frame, text="Resub Settings")
        # --- Bits Settings ---
        bits_frame = ttk.LabelFrame(self.settings_frame, text="Bits Settings")
        # --- Hotkeys ---
        hotkey_frame = ttk.LabelFrame(self.settings_frame, text="Hotkeys")

        # Add DEBUG checkbox
        self.debug_var = tk.BooleanVar(value=bot_utils.DEBUG)
        debug_checkbox = ttk.Checkbutton(
            self.settings_frame,
            text="Enable DEBUG",
            variable=self.debug_var,
            command=self.on_debug_checkbox
        )
        # Place it at the top right, next to Resub Settings
        debug_checkbox.grid(row=0, column=2, sticky="ne", padx=10, pady=8)

        # Place frames in a 2x2 grid
        basic_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=8)
        resub_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=8)
        bits_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=8)
        hotkey_frame.grid(row=1, column=1, sticky="nsew", padx=10, pady=8)

        # Make the grid expand
        self.settings_frame.grid_rowconfigure(0, weight=1)
        self.settings_frame.grid_rowconfigure(1, weight=1)
        self.settings_frame.grid_columnconfigure(0, weight=1)
        self.settings_frame.grid_columnconfigure(1, weight=1)

        # Add entries to each frame
        for label, key in [
            ("Bot Nickname", "Bot Nickname"),
            ("Broadcaster Channel", "Broadcaster Channel"),
            ("Broadcaster ID", "Broadcaster ID"),
            ("Elevenlabs Voice ID", "Elevenlabs Voice ID"),
            ("Audio Output Device", "Audio Output Device"),
            ("Raid Threshold", "Raid Threshold"),
            ("OBS Assistant Object Name", "OBS Assistant Object Name"),
            ("OBS Assistant Stationary Object Name", "OBS Assistant Stationary Object Name"),
            ("Ad Length (seconds)", "Ad Length (seconds)"),
            ("Ad Interval (minutes)", "Ad Interval (minutes)"),
            ("Seconds Between Events", "Seconds Between Events")
        ]:
            if label == "Audio Output Device":
                ttk.Label(basic_frame, text=label).pack(anchor="w", padx=5, pady=2)
                audio_device_var = tk.StringVar()
                audio_device_combobox = ttk.Combobox(
                    basic_frame,
                    textvariable=audio_device_var,
                    values=AUDIO_DEVICES,
                    state="readonly"
                )
                audio_device_combobox.pack(fill="x", padx=5, pady=2)
                # Set initial value from settings or default to first device
                audio_device_combobox.set(self.settings.get("Audio Output Device", AUDIO_DEVICES[0] if AUDIO_DEVICES else ""))
                self.settings_widgets["Audio Output Device"] = audio_device_combobox
            elif label == "Ad Length (seconds)":
                ttk.Label(basic_frame, text=label).pack(anchor="w", padx=5, pady=2)
                ad_length_var = tk.IntVar()
                ad_length_combobox = ttk.Combobox(
                    basic_frame,
                    textvariable=ad_length_var,
                    values=AD_LENGTHS,
                    state="readonly"
                )
                ad_length_combobox.pack(fill="x", padx=5, pady=2)
                ad_length_combobox.set(self.settings.get("Ad Length (seconds)", AD_LENGTHS[0] if AD_LENGTHS else 60))
                self.settings_widgets["Ad Length (seconds)"] = ad_length_combobox
            elif label not in ["Bot Nickname", "Broadcaster Channel", "Broadcaster ID"]:
                add_entry(basic_frame, label, key)
            else:
                add_entry(basic_frame, label, key, readonly=True)



        # --- Elevenlabs Synthesizer Model Combobox ---
        ttk.Label(basic_frame, text="Elevenlabs Synthesizer Model").pack(anchor="w", padx=5, pady=2)
        model_var = tk.StringVar()
        model_combobox = ttk.Combobox(
            basic_frame,
            textvariable=model_var,
            values=MODELS,
            state="normal"  # allow typing custom value
        )
        model_combobox.pack(fill="x", padx=5, pady=2)
        # Set initial value from settings or default to first model
        model_combobox.set(self.settings.get("Elevenlabs Synthesizer Model", MODELS[0] if MODELS else ""))
        self.settings_widgets["Elevenlabs Synthesizer Model"] = model_combobox

        ttk.Label(basic_frame, text="Azure TTS Backup Voice").pack(anchor="w", padx=5, pady=2)
        voice_var = tk.StringVar()
        voice_combobox = ttk.Combobox(
            basic_frame,
            textvariable=voice_var,
            values=VOICES,
            state="normal"  # allow typing custom value
        )
        voice_combobox.pack(fill="x", padx=5, pady=2)
        # Set initial value from settings or default to first model
        voice_combobox.set(self.settings.get("Azure TTS Backup Voice", VOICES[0] if VOICES else ""))
        self.settings_widgets["Azure TTS Backup Voice"] = voice_combobox

        for label, key in [
            ("Intern Max Month Count", "Intern Max Month Count"),
            ("Employee Max Month Count", "Employee Max Month Count"),
            ("Supervisor Max Month Count", "Supervisor Max Month Count"),
        ]:
            add_entry(resub_frame, label, key, parent="Resub")

        for label, key in [
            ("Normal Reaction Threshold", "Normal Reaction Threshold"),
            ("Impressed Reaction Threshold", "Impressed Reaction Threshold"),
            ("Exaggerated Reaction Threshold", "Exaggerated Reaction Threshold"),
            ("Screaming Reaction Threshold", "Screaming Reaction Threshold"),
        ]:
            add_entry(bits_frame, label, key, parent="Bits")

        self.audio_queue_var = tk.BooleanVar()
        ttk.Checkbutton(
            basic_frame, text="Event Queue Enabled",
            variable=self.audio_queue_var
        ).pack(anchor="w", padx=5, pady=2)

        self.auto_ad_var = tk.BooleanVar()
        ttk.Checkbutton(
            basic_frame, text="Auto Ad Enabled",
            variable=self.auto_ad_var
        ).pack(anchor="w", padx=5, pady=2)

        self.hotkey_widgets = {}
        self.hotkey_labels = {}

        self.settings_tab.bind_all('<KeyPress>', self.capture_hotkey_press)
        self.settings_tab.bind_all('<KeyRelease>', self.capture_hotkey_release)

        for hotkey_name in [
            "10_MESSAGES_RESPOND_KEY",
            "LISTEN_AND_RESPOND_KEY",
            "END_LISTEN_KEY",
            "VOICE_SUMMARIZE_KEY",
            "PLAY_NEXT_KEY",
            "SKIP_CURRENT_KEY",
            "REPLAY_LAST_KEY"
        ]:
            frame = ttk.Frame(hotkey_frame)
            frame.pack(fill="x", pady=2)
            label = ttk.Label(frame, text=hotkey_name)
            label.pack(side=tk.LEFT)
            btn = ttk.Button(frame, text="Change", command=partial(self.start_listening, hotkey_name))
            btn.pack(side=tk.RIGHT)
            self.hotkey_labels[hotkey_name] = ttk.Label(frame, text="")
            self.hotkey_labels[hotkey_name].pack(side=tk.RIGHT)

        ttk.Button(self.settings_frame, text="Save Settings", command=self.save_settings).grid(row=2, column=0, columnspan=2, pady=10)

    def on_debug_checkbox(self):
        if not self.bot:
            self.bot = bot_utils.get_bot_instance()
        asyncio.run_coroutine_threadsafe(self.bot.toggle_debug(), self.loop)

    def start_listening(self, hotkey_name):
        self.listening_hotkey = hotkey_name
        self.hotkey_labels[hotkey_name].config(text="Press keys...")
        self.pressed_keys = []

    def _normalize_key(self, keysym):
    # Map left/right modifiers to generic names
        mapping = {
            "control_l": "ctrl",
            "control_r": "ctrl",
            "shift_l": "shift",
            "shift_r": "shift",
            "alt_l": "alt",
            "alt_r": "alt",
            # Add more if needed
        }
        return mapping.get(keysym, keysym)

    def capture_hotkey_press(self, event):
        if not self.listening_hotkey:
            return
        key = self._normalize_key(event.keysym.lower())
        if key not in self.pressed_keys:
            self.pressed_keys.append(key)
        combo = "+".join(self.pressed_keys)
        self.hotkey_labels[self.listening_hotkey].config(text=combo)

    def capture_hotkey_release(self, event):
        if not self.listening_hotkey:
            return
        key = self._normalize_key(event.keysym.lower())
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)
        if not self.pressed_keys:
            combo = self.hotkey_labels[self.listening_hotkey].cget("text")
            if "Hotkeys" not in self.settings:
                self.settings["Hotkeys"] = {}
            self.settings["Hotkeys"][self.listening_hotkey] = combo
            self.listening_hotkey = None

    def save_settings(self):
        if not self.bot:
            self.bot = bot_utils.get_bot_instance()
        # Top-level settings
        for key, widget in self.settings_widgets.items():
            if isinstance(widget, dict):
                continue  # skip nested, handled below
            value = widget.get()
            # Convert to int if it's the Audio Output Device and is a digit
            if (key == "Audio Output Device" or key == "Raid Threshold" or key == "Ad Length (seconds)" or key == "Ad Interval (minutes)" or key == "Seconds Between Events") and value.isdigit():
                self.settings[key] = int(value)
        self.settings["Event Queue Enabled"] = self.audio_queue_var.get()
        self.settings["Auto Ad Enabled"] = self.auto_ad_var.get()
        self.settings["Elevenlabs Synthesizer Model"] = self.settings_widgets["Elevenlabs Synthesizer Model"].get()
        self.settings["Audio Output Device"] = self.settings_widgets["Audio Output Device"].get()

        # Nested: Resub
        if "Resub" not in self.settings:
            self.settings["Resub"] = {}
        for key, widget in self.settings_widgets.get("Resub", {}).items():
            self.settings["Resub"][key] = int(widget.get()) if widget.get().isdigit() else widget.get()

        # Nested: Bits
        if "Bits" not in self.settings:
            self.settings["Bits"] = {}
        for key, widget in self.settings_widgets.get("Bits", {}).items():
            self.settings["Bits"][key] = int(widget.get()) if widget.get().isdigit() else widget.get()

        try:
            asyncio.run_coroutine_threadsafe(save_settings(self.settings), self.loop)
        except RuntimeError:
            asyncio.run(save_settings(self.settings))

        try:
            asyncio.run_coroutine_threadsafe(self.bot.reload_global_variable(), self.loop)
        except Exception as e:
            print(f"[ERROR]Couldn't refresh variables in bot:\n{e}")


        messagebox.showinfo("Saved", "Settings saved successfully.")
        self.after(0, self.populate_settings_widgets)

    def create_tasks_tab(self):
        # Create a canvas and a vertical scrollbar for scrolling
        container = ttk.Frame(self.tasks_tab)
        container.pack(fill='both', expand=True)

        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.tasks_frame = ttk.Frame(canvas)

        self.tasks_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=self.tasks_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.refresh_tasks()
        ttk.Button(self.tasks_tab, text="Add Task", command=self.add_task_popup).pack(pady=10)

    def refresh_tasks(self):
        for widget in self.tasks_frame.winfo_children():
            widget.destroy()

        for task_id, task in self.scheduled_tasks.get("Messages", {}).items():
            frame = ttk.Frame(self.tasks_frame)
            frame.pack(fill='x', padx=10, pady=5)
            ttk.Label(frame, text=task["content"]).pack(side=tk.LEFT, expand=True, fill='x')

            enabled_var = tk.BooleanVar(value=task.get("enabled", False))
            cb = ttk.Checkbutton(frame, variable=enabled_var, command=partial(self.toggle_task, task_id, enabled_var))
            cb.pack(side=tk.LEFT)
            ttk.Button(frame, text="✏", width=3, command=partial(self.edit_task_popup, task_id)).pack(side=tk.LEFT)
            ttk.Button(frame, text="❌", width=3, command=partial(self.delete_task, task_id)).pack(side=tk.LEFT)

    def toggle_task(self, task_id, var):
        if bot_utils.DEBUG:
            print("[DEBUG]gui toggle task entered")
        if not self.bot:
            self.bot = bot_utils.get_bot_instance()
        fut = asyncio.run_coroutine_threadsafe(
            self.bot.toggle_automated_message(task_id),
            self.loop
        )
        # After the bot has finished toggling and saving, reload in GUI
        def after_toggle(_):
            # Reload the scheduled messages from disk and refresh the GUI
            asyncio.run_coroutine_threadsafe(self.load_scheduled_tasks_and_refresh(), self.loop)
        fut.add_done_callback(after_toggle)

    async def load_scheduled_tasks_and_refresh(self):
        self.scheduled_tasks = await load_scheduled_messages()
        self.after(0, self.refresh_tasks)
        

    def delete_task(self, task_id):
        if not self.bot:
            self.bot = bot_utils.get_bot_instance()
        task_id = str(task_id)
        enabled = self.scheduled_tasks["Messages"][task_id]["enabled"]
        del self.scheduled_tasks["Messages"][task_id]
        if enabled:
            asyncio.run_coroutine_threadsafe(self.bot.cancel_timed_message(task_id), self.loop)
        asyncio.run_coroutine_threadsafe(save_scheduled_messages(self.scheduled_tasks), self.loop)
        self.refresh_tasks()

    def add_task_popup(self):
        self.task_editor_popup()

    def edit_task_popup(self, task_id):
        task = self.scheduled_tasks["Messages"][task_id]
        self.task_editor_popup(task_id, task)

    def task_editor_popup(self, task_id=None, task_data=None):
        win = tk.Toplevel(self)
        win.title("Edit Task" if task_id else "New Task")

        ttk.Label(win, text="Message").pack()
        msg_entry = ttk.Entry(win, width=60)
        msg_entry.pack()
        if task_data:
            msg_entry.insert(0, task_data["content"])

        ttk.Label(win, text="Minutes (optional)").pack()
        min_entry = ttk.Entry(win)
        min_entry.pack()
        if task_data and task_data.get("minutes"):
            min_entry.insert(0, str(task_data["minutes"]))

        ttk.Label(win, text="Messages (optional)").pack()
        msg_count_entry = ttk.Entry(win)
        msg_count_entry.pack()
        if task_data and task_data.get("messages"):
            msg_count_entry.insert(0, str(task_data["messages"]))

        def confirm():
            content = msg_entry.get().strip()
            minutes = min_entry.get().strip()
            messages = msg_count_entry.get().strip()
            if not content or (not minutes and not messages):
                messagebox.showerror("Error", "Content and at least one of minutes/messages are required.")
                return

            if task_id is None:
                # New task: enabled is always False
                enabled = False
            else:
                # Editing: preserve previous enabled state
                enabled = self.scheduled_tasks["Messages"][task_id].get("enabled", False)

            task = {
                "content": content,
                "minutes": int(minutes) if minutes else None,
                "messages": int(messages) if messages else None,
                "enabled": enabled
            }
            if not task_id:
                new_id = str(max(map(int, self.scheduled_tasks["Messages"].keys()), default=0) + 1)
                task["id"] = int(new_id)
                self.scheduled_tasks["Messages"][new_id] = task
            else:
                task["id"] = int(task_id)
                self.scheduled_tasks["Messages"][task_id] = task

            try:
                asyncio.run_coroutine_threadsafe(save_scheduled_messages(self.scheduled_tasks), self.loop)
                if enabled:
                    asyncio.run_coroutine_threadsafe(self.bot.reset_scheduled_message(task["id"]), self.loop)
            except RuntimeError:
                asyncio.run(save_scheduled_messages(self.scheduled_tasks))
            win.destroy()
            self.refresh_tasks()


        ttk.Button(win, text="Confirm", command=confirm).pack(pady=10)

    def create_prompts_tab(self):
        self.prompts_widgets = {}

        # --- Frame with canvas and scrollbar for the whole tab ---
        container = ttk.Frame(self.prompts_tab)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- Async loader for prompts ---
        async def load_and_populate():
            prompts = await load_prompts()
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
            self.prompts_widgets.clear()
            row = 0
            for key, value in prompts.items():
                ttk.Label(scrollable_frame, text=key).grid(row=row, column=0, sticky="nw", pady=2)
                # Add a frame for each text box + its scrollbar
                text_frame = ttk.Frame(scrollable_frame)
                text_frame.grid(row=row, column=1, pady=2, sticky="nsew")
                text_widget = tk.Text(text_frame, height=5, width=60, wrap="word")
                text_widget.insert("1.0", value)
                text_widget.pack(side="left", fill="both", expand=True)
                # Add vertical scrollbar for this text widget
                text_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
                text_scroll.pack(side="right", fill="y")
                text_widget.config(yscrollcommand=text_scroll.set)
                self.prompts_widgets[key] = text_widget
                row += 1
            ttk.Button(scrollable_frame, text="Save Prompts", command=save_prompts_sync).grid(row=row, column=0, columnspan=2, pady=10)

        def save_prompts_sync():
            if not self.bot:
                self.bot = bot_utils.get_bot_instance()
            new_prompts = {key: widget.get("1.0", "end-1c") for key, widget in self.prompts_widgets.items()}
            try:
                asyncio.run_coroutine_threadsafe(save_prompts(new_prompts), self.loop)
            except RuntimeError:
                asyncio.run(save_prompts(new_prompts))
            try:
                asyncio.run_coroutine_threadsafe(self.bot.reload_global_prompts(), self.loop)
            except Exception as e:
                print(f"[ERROR]Couldn't refresh variables in bot:\n{e}")
            messagebox.showinfo("Saved", "Prompts saved successfully.")

        # Schedule the async loader
        self.after(0, lambda: asyncio.run_coroutine_threadsafe(load_and_populate(), self.loop))

    def create_console_tab(self):
        self.console_text = ScrolledText(self.console_tab, state='normal', background = "black", foreground = "white", font=("Consolas", 11))
        self.console_text.pack(fill='both', expand=True)
        sys.stdout = Redirector(self.console_text)
        sys.stderr = Redirector(self.console_text)

    async def load_all_data(self):
        self.settings = await load_settings()
        # Update the GUI widgets on the main thread
        self.after(0, self.populate_settings_widgets)

        self.scheduled_tasks = await load_scheduled_messages()
        if bot_utils.DEBUG:
            print(f"[DEBUG]Loaded scheduled tasks: {self.scheduled_tasks}")
        self.after(0, self.refresh_tasks)

    def populate_settings_widgets(self):
        for key, entry in self.settings_widgets.items():
            if isinstance(entry, dict):
                continue  # skip nested, handled below
            # Always set to normal before updating
            entry.config(state="normal")
            entry.delete(0, 'end')
            entry.insert(0, self.settings.get(key, ""))
            # Set back to readonly if this field should be readonly
            if key in ["Bot Nickname", "Broadcaster Channel", "Broadcaster ID"]:
                entry.config(state="readonly")
        self.audio_queue_var.set(self.settings.get("Event Queue Enabled", False))
        self.debug_var.set(self.settings.get("Debug", False))
        # Nested: Resub
        for key, widget in self.settings_widgets.get("Resub", {}).items():
            widget.delete(0, 'end')
            widget.insert(0, self.settings.get("Resub", {}).get(key, ""))
        # Nested: Bits
        for key, widget in self.settings_widgets.get("Bits", {}).items():
            widget.delete(0, 'end')
            widget.insert(0, self.settings.get("Bits", {}).get(key, ""))
        for key in self.hotkey_labels:
            self.hotkey_labels[key].config(text=self.settings.get("Hotkeys", {}).get(key, ""))
        model_widget = self.settings_widgets.get("Elevenlabs Synthesizer Model")
        if model_widget:
            model_widget.set(self.settings.get("Elevenlabs Synthesizer Model", MODELS[0] if MODELS else ""))
        audio_device_widget = self.settings_widgets.get("Audio Output Device")
        if audio_device_widget:
            audio_device_widget.set(self.settings.get("Audio Output Device", AUDIO_DEVICES[0] if AUDIO_DEVICES else ""))

    def on_close(self):
        if bot_utils.DEBUG:
            print("[DEBUG]GUI closed. Shutting down bot.")
        if self.bot is not None:
            # Schedule bot.close() on the bot's event loop
            asyncio.run_coroutine_threadsafe(self.bot.close(), self.loop)
        self.destroy()
        # Forcefully exit the process (kills all threads)
        os._exit(0)

def run_mainloop_async(gui_queue, loop):
    app = TwitchBotGUI(gui_queue, loop)
    app.mainloop()


if __name__ == "__main__":
    import asyncio

    app = TwitchBotGUI()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def run_asyncio_loop():
        loop.call_soon(loop.stop)
        loop.run_forever()
        app.after(10, run_asyncio_loop)

    loop.create_task(app.async_init())
    app.after(10, run_asyncio_loop)
    app.mainloop()



