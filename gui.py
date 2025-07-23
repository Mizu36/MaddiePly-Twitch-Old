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
import json
from json_manager import load_settings, save_settings, load_scheduled_messages, save_scheduled_messages, save_prompts, load_prompts, load_commands, save_commands
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
        self.geometry("750x950")
        self.settings = {}
        self.scheduled_tasks = {}
        self.listening_hotkey = None
        self.bot = None
        self.queue_cache = None
        self.played_cache = None

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True)

        self.settings_tab = ttk.Frame(self.notebook)
        self.tasks_tab = ttk.Frame(self.notebook)
        self.prompts_tab = ttk.Frame(self.notebook)
        self.console_tab = ttk.Frame(self.notebook)
        self.commands_tab = ttk.Frame(self.notebook)
        self.event_queue = ttk.Frame(self.notebook)
        self.tools_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.settings_tab, text='Settings')
        self.notebook.add(self.tasks_tab, text='Scheduled Tasks')
        self.notebook.add(self.prompts_tab, text='GPT Prompts')
        self.notebook.add(self.console_tab, text='Console')
        self.notebook.add(self.commands_tab, text='Commands')
        self.notebook.add(self.event_queue, text='TTS Events')
        self.notebook.add(self.tools_tab, text="Tools")

        self.create_settings_tab()
        self.create_tasks_tab()
        self.create_prompts_tab()
        self.create_console_tab()
        self.create_commands_tab()
        self.create_event_queue_tab()
        self.create_tools_tab()
        
        self.after(100, self.poll_gui_queue)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def bind_mousewheel(self, widget, target_canvas):
        def _on_mousewheel(event):
            # Windows and macOS
            if hasattr(event, 'delta'):
                target_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            # Linux
            elif event.num == 4:
                target_canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                target_canvas.yview_scroll(1, "units")

        # Windows/macOS
        widget.bind("<Enter>", lambda e: widget.bind_all("<MouseWheel>", _on_mousewheel))
        widget.bind("<Leave>", lambda e: widget.unbind_all("<MouseWheel>"))

        # Linux
        widget.bind("<Enter>", lambda e: widget.bind_all("<Button-4>", _on_mousewheel))
        widget.bind("<Leave>", lambda e: widget.unbind_all("<Button-4>"))
        widget.bind("<Enter>", lambda e: widget.bind_all("<Button-5>", _on_mousewheel))
        widget.bind("<Leave>", lambda e: widget.unbind_all("<Button-5>"))



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
        self.bind_mousewheel(self.settings_frame, canvas)




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
            ("Seconds Between Events", "Seconds Between Events"),
            ("Progress Bar Name", "Progress Bar Name")
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

        self.streamathon_var = tk.BooleanVar()
        ttk.Checkbutton(
            basic_frame, text="Streamathon Mode",
            variable=self.streamathon_var
        ).pack(anchor="w", padx=5, pady=2)

        self.hotkey_widgets = {}
        self.hotkey_labels = {}

        self.settings_tab.bind_all('<KeyPress>', self.capture_hotkey_press)
        self.settings_tab.bind_all('<KeyRelease>', self.capture_hotkey_release)

        for hotkey_name in [
            "LISTEN_AND_RESPOND_KEY",
            "END_LISTEN_KEY",
            "VOICE_SUMMARIZE_KEY",
            "PLAY_NEXT_KEY",
            "SKIP_CURRENT_KEY",
            "REPLAY_LAST_KEY",
            "PLAY_AD",
            "PAUSE_QUEUE"
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
                continue
            value = widget.get()
            if key in ["Audio Output Device", "Raid Threshold", "Ad Length (seconds)", "Ad Interval (minutes)", "Seconds Between Events"] and value.isdigit():
                self.settings[key] = int(value)
            else:
                self.settings[key] = value

        self.settings["Event Queue Enabled"] = self.audio_queue_var.get()
        self.settings["Auto Ad Enabled"] = self.auto_ad_var.get()
        self.settings["Streamathon Mode"] = self.streamathon_var.get()
        self.settings["Elevenlabs Synthesizer Model"] = self.settings_widgets["Elevenlabs Synthesizer Model"].get()
        self.settings["Audio Output Device"] = self.settings_widgets["Audio Output Device"].get()

        # Nested: Resub
        self.settings.setdefault("Resub", {})
        for key, widget in self.settings_widgets.get("Resub", {}).items():
            self.settings["Resub"][key] = int(widget.get()) if widget.get().isdigit() else widget.get()

        # Nested: Bits
        self.settings.setdefault("Bits", {})
        for key, widget in self.settings_widgets.get("Bits", {}).items():
            self.settings["Bits"][key] = int(widget.get()) if widget.get().isdigit() else widget.get()

        # Instead of asyncio.run or run_coroutine_threadsafe
        async def do_save():
            try:
                await save_settings(self.settings)
                await self.bot.reload_global_variable()
                self.after(0, self.populate_settings_widgets)
                self.after(0, lambda: messagebox.showinfo("Saved", "Settings saved successfully."))
            except Exception as e:
                print(f"[ERROR] Saving settings: {e}")

        # Schedule coroutine safely
        self.loop.call_soon_threadsafe(lambda: asyncio.create_task(do_save()))


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
        self.bind_mousewheel(self.tasks_frame, canvas)

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
        self.bind_mousewheel(scrollable_frame, canvas)

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

    def create_commands_tab(self):
        container = ttk.Frame(self.commands_tab)
        container.pack(fill='both', expand=True, padx=10, pady=10)

        canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient='vertical', command=canvas.yview)
        self.commands_frame = ttk.Frame(canvas)

        self.commands_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=self.commands_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        self.bind_mousewheel(self.commands_frame, canvas)

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        btn_frame = ttk.Frame(self.commands_tab)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="Add Command", command=self.add_command_popup).pack(side=tk.LEFT, padx=5)

        self.load_commands_into_listbox()

    def load_commands_into_listbox(self):
        async def _load():
            try:
                commands = await load_commands()
                def update_gui():
                    for widget in self.commands_frame.winfo_children():
                        widget.destroy()

                    style = ttk.Style()
                    style.configure("Card.TFrame", background="#f5f5f5", padding=10)
                    style.configure("Cmd.TLabel", background="#ffffff", relief="solid", padding=5, anchor='w')
                    style.configure("Res.TLabel", background="#eef6ff", relief="solid", padding=5, anchor='w', wraplength=600)

                    for cmd, res in commands.items():
                        # Individual command container
                        card = ttk.Frame(self.commands_frame, style="Card.TFrame")
                        card.pack(fill='x', padx=5, pady=5, anchor='w')

                        # Top row: command label + buttons
                        top_row = ttk.Frame(card, style="Card.TFrame")
                        top_row.pack(fill='x', anchor='w')

                        # Command label that sizes to content
                        cmd_label = ttk.Label(top_row, text=cmd, style="Cmd.TLabel", justify='left')
                        cmd_label.pack(side=tk.LEFT, padx=(0, 10))

                        # Buttons aligned to top-right
                        btn_frame = ttk.Frame(top_row, style="Card.TFrame")
                        btn_frame.pack(side=tk.RIGHT, anchor='n')
                        ttk.Button(btn_frame, text="Edit", command=lambda c=cmd, r=res: self.command_editor_popup(c, r)).pack(side=tk.LEFT, padx=2)
                        ttk.Button(btn_frame, text="Delete", command=lambda c=cmd: self.delete_command(c)).pack(side=tk.LEFT, padx=2)

                        # Response label with dynamic vertical size and word wrap
                        res_label = ttk.Label(card, text=res, style="Res.TLabel", justify='left', wraplength=600)
                        res_label.pack(pady=(5, 0), anchor='w')

                self.after(0, update_gui)
            except Exception as e:
                print(f"[ERROR] Loading commands: {e}")

        asyncio.run_coroutine_threadsafe(_load(), self.loop)

    def delete_command(self, cmd):
        async def _delete():
            try:
                data = await load_commands()
                if cmd in data:
                    del data[cmd]
                    await save_commands(data)
                    if self.bot:
                        await self.bot.reload_commands()
                self.after(0, lambda: self.load_commands_into_listbox())
            except Exception as e:
                print(f"[ERROR] Deleting command '{cmd}': {e}")

        asyncio.run_coroutine_threadsafe(_delete(), self.loop)

    def add_command_popup(self):
        self.command_editor_popup()

    def command_editor_popup(self, cmd_text="", res_text=""):
        popup = tk.Toplevel(self)
        popup.title("Edit Command" if cmd_text else "Add Command")

        popup.geometry("500x200")  # Wider popup
        popup.transient(self)
        popup.grab_set()

        popup.update_idletasks()
        x = self.winfo_rootx() + self.winfo_width() // 2 - 250
        y = self.winfo_rooty() + self.winfo_height() // 2 - 100
        popup.geometry(f"+{x}+{y}")

        ttk.Label(popup, text="Command:").pack(pady=(10, 0))
        cmd_entry = ttk.Entry(popup, width=60)
        cmd_entry.pack()
        cmd_entry.insert(0, cmd_text)

        ttk.Label(popup, text="Response:").pack(pady=(10, 0))
        res_entry = ttk.Entry(popup, width=60)
        res_entry.pack()
        res_entry.insert(0, res_text)

        def save():
            if not self.bot:
                self.bot = bot_utils.get_bot_instance()
            cmd = cmd_entry.get().strip().lower()
            res = res_entry.get().strip()
            if not cmd.startswith("!"):
                messagebox.showerror("Error", "Command must start with '!'")
                return
            if cmd and res:
                try:
                    async def save_and_reload():
                        data = await load_commands()
                        data[cmd] = res
                        await save_commands(data)
                        await self.bot.reload_commands()
                        self.after(0, lambda: self.load_commands_into_listbox())
                        popup.destroy()
                    asyncio.run_coroutine_threadsafe(save_and_reload(), self.loop)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save: {e}")

        ttk.Button(popup, text="Save", command=save).pack(pady=10)

    
    def create_event_queue_tab(self):
        self.event_queue_widgets = {}

        container = ttk.Frame(self.event_queue)
        container.pack(fill='both', expand=True)

        self.event_queue_frame = ttk.Frame(container)
        self.event_queue_frame.pack(fill='both', expand=True)

        self.queue_label = ttk.Label(self.event_queue_frame, text="Upcoming Events")
        self.queue_label.pack()

        self.queue_events_container = ttk.Frame(self.event_queue_frame)
        self.queue_events_container.pack(fill='x', padx=10)

        self.played_label = ttk.Label(self.event_queue_frame, text="Played Events")
        self.played_label.pack(pady=(20, 0))

        self.played_events_container = ttk.Frame(self.event_queue_frame)
        self.played_events_container.pack(fill='x', padx=10)

        self.event_queue.after(500, self.refresh_event_lists_periodically)

    def refresh_event_lists_periodically(self):
        if self.notebook.index(self.notebook.select()) == self.notebook.tabs().index(str(self.event_queue)):
            self.refresh_event_lists()
        self.event_queue.after(500, self.refresh_event_lists_periodically)

    def refresh_event_lists(self):
        if not self.bot:
            self.bot = bot_utils.get_bot_instance()

        try:
            queue = self.bot.event_queue.get_queue()
            played = self.bot.event_queue.get_played()

            queue_serial = json.dumps(queue, sort_keys=True)
            played_serial = json.dumps(played, sort_keys=True)


            if hasattr(self, "queue_cache") and hasattr(self, "played_cache"):
                if self.queue_cache == queue_serial and self.played_cache == played_serial:
                    return

            self.queue_cache = queue_serial
            self.played_cache = played_serial

            for widget in self.queue_events_container.winfo_children():
                widget.destroy()
            for widget in self.played_events_container.winfo_children():
                widget.destroy()

            for i, event in enumerate(queue):
                frame = ttk.Frame(self.queue_events_container)
                frame.pack(fill='x', pady=2)
                label = ttk.Label(frame, text=f"[{i}] {event.get('event_type', '?')} from {event.get('from_user', '?')} - {event.get('audio', '')}", width=100)
                label.pack(side=tk.LEFT, padx=5)
                ttk.Button(frame, text="Play", command=lambda idx=i: self.play_event(idx)).pack(side=tk.LEFT, padx=2)
                ttk.Button(frame, text="Delete", command=lambda idx=i: self.delete_event(idx, played=False)).pack(side=tk.LEFT, padx=2)

            for i, event in enumerate(played):
                frame = ttk.Frame(self.played_events_container)
                frame.pack(fill='x', pady=2)
                label = ttk.Label(frame, text=f"[{i}] {event.get('event_type', '?')} from {event.get('from_user', '?')} - {event.get('audio', '')}", width=100)
                label.pack(side=tk.LEFT, padx=5)
                ttk.Button(frame, text="Replay", command=lambda idx=i: self.replay_event(idx)).pack(side=tk.LEFT, padx=2)
                ttk.Button(frame, text="Delete", command=lambda idx=i: self.delete_event(idx, played=True)).pack(side=tk.LEFT, padx=2)

        except Exception as e:
            print(f"[ERROR] While refreshing event lists: {e}")

    def play_event(self, index):
        if self.bot:
            asyncio.run_coroutine_threadsafe(self.bot.play_specific_event(index, is_replay=False), self.loop)

    def replay_event(self, index):
        if self.bot:
            asyncio.run_coroutine_threadsafe(self.bot.play_specific_event(index, is_replay=True), self.loop)

    def delete_event(self, index, played):
        if not self.bot:
            return
        if played:
            asyncio.run_coroutine_threadsafe(self.bot.remove_specific_event(index, True), self.loop)
        else:
            asyncio.run_coroutine_threadsafe(self.bot.remove_specific_event(index, False), self.loop)
        self.refresh_event_lists()

    def create_tools_tab(self):
        ttk.Label(self.tools_tab, text="Trigger Actions", font=("Segoe UI", 12, "bold")).pack(pady=10)

        ask_button = ttk.Button(self.tools_tab, text="Ask MaddiePly", command=self.ask_maddieply)
        ask_button.pack(pady=5)

        summarize_button = ttk.Button(self.tools_tab, text="Summarize Chat", command=self.summarize_chat)
        summarize_button.pack(pady=5)

        trigger_ad_button = ttk.Button(self.tools_tab, text="Trigger Ad Break", command=self.trigger_ad)
        trigger_ad_button.pack(pady=5)

        ttk.Separator(self.tools_tab).pack(fill="x", pady=10)

        # --- Stream Tools Section ---
        tools_frame = ttk.LabelFrame(self.tools_tab, text="Stream Tools")
        tools_frame.pack(padx=10, pady=10, fill="x")

        # Save transform buttons
        on_screen_button = ttk.Button(tools_frame, text="Save On Screen Location", command=self.capture_assistant_location_onscreen)
        on_screen_button.pack(pady=5, fill="x")

        off_screen_button = ttk.Button(tools_frame, text="Save Off Screen Location", command=self.capture_assistant_location_offscreen)
        off_screen_button.pack(pady=5, fill="x")

        prog_bar_button = ttk.Button(tools_frame, text="Save Progress Bar Transform", command=self.save_prog_bar_transform)
        prog_bar_button.pack(pady=5, fill="x")

        # Manual Donation Entry
        ttk.Label(tools_frame, text="Manual Donation Entry", font=("Segoe UI", 10, "bold")).pack(pady=(10, 0))

        donation_frame = ttk.Frame(tools_frame)
        donation_frame.pack(pady=5)

        self.donation_var = tk.StringVar()

        donation_entry = ttk.Entry(donation_frame, textvariable=self.donation_var, width=15)
        donation_entry.pack(side="left", padx=(0, 5))

        def submit_donation():
            value = self.donation_var.get().strip()
            try:
                amount = float(value)
                if amount <= 0:
                    raise ValueError
                if not self.bot:
                    self.bot = bot_utils.get_bot_instance()
                asyncio.run_coroutine_threadsafe(self.bot.manual_donation_entry(amount), self.loop)
                self.donation_var.set("")
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a positive number.")

        submit_button = ttk.Button(donation_frame, text="Submit", command=submit_donation)
        submit_button.pack(side="left")




    def ask_maddieply(self):
        try:
            if not self.bot:
                self.bot = bot_utils.get_bot_instance()
            asyncio.run_coroutine_threadsafe(self.bot.ask(), self.loop)
        except Exception as e:
            print(f"[ERROR]Failed to call ask_maddieply: {e}")

    def summarize_chat(self):
        try:
            if not self.bot:
                self.bot = bot_utils.get_bot_instance()
            asyncio.run_coroutine_threadsafe(self.bot.summarize(), self.loop)
        except Exception as e:
            print(f"[ERROR]Failed to call summarize_chat: {e}")

    def trigger_ad(self):
        try:
            if not self.bot:
                self.bot = bot_utils.get_bot_instance()
            asyncio.run_coroutine_threadsafe(self.bot.ad(), self.loop)
        except Exception as e:
            print(f"[ERROR]Failed to call trigger_ad: {e}")

    def capture_assistant_location_onscreen(self):
        try:
            if not self.bot:
                self.bot = bot_utils.get_bot_instance()
            asyncio.run_coroutine_threadsafe(self.bot.obs_capture_location(True), self.loop)
        except Exception as e:
            print(f"[ERROR]Failed to call obs_capture_location (onscreen): {e}")

    def capture_assistant_location_offscreen(self):
        try:
            if not self.bot:
                self.bot = bot_utils.get_bot_instance()
            asyncio.run_coroutine_threadsafe(self.bot.obs_capture_location(False), self.loop)
        except Exception as e:
            print(f"[ERROR]Failed to call obs_capture_location (offscreen): {e}")

    def save_prog_bar_transform(self):
        try:
            if not self.bot:
                self.bot = bot_utils.get_bot_instance()
            asyncio.run_coroutine_threadsafe(self.bot.obs_capture_transform(), self.loop)
        except Exception as e:
            print(f"[ERROR]Failed to call obs_capture_transform (progress bar): {e}")

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
        self.auto_ad_var.set(self.settings.get("Auto Ad Enabled", False))
        self.streamathon_var.set(self.settings.get("Streamathon Mode", False))
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



