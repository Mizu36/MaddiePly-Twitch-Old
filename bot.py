import os
import glob
import keyboard
import asyncio
import re
import time
import random
import pygame
import threading
import queue
from gui import TwitchBotGUI
from dotenv import load_dotenv
from twitchio.ext import commands
from twitchio.ext.commands import cooldown, Bucket
from openai import OpenAI
from openai_chat import OpenAiManager
from audio_player import AudioManager
from azure_speech_to_text import SpeechToTextManager
from eleven_labs_manager import ElevenLabsManager
from obs_websockets import OBSWebsocketsManager
from bot_utils import set_bot_instance, get_bot_instance, set_debug
from eventsub_server import main as start_event_sub, ad_reset_event, trigger_ad
from token_manager import refresh_token
from json_manager import load_prompts, load_messages, save_messages, load_settings, save_settings, load_scheduled_messages, save_scheduled_messages

load_dotenv()

CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_APP_SECRET")
BOT_TOKEN = None
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BOT_NICK = None
TWITCH_CHANNEL = None
TEN_MESSAGES_KEY = None
LISTEN_AND_RESPOND_KEY = None
VOICED_SUMMARY_KEY = None
OBS_HOTKEY = None
ELEVENLABS_VOICE = None
PLAY_NEXT = None
SKIP_AUDIO = None
REPLAY_LAST = None
PLAY_AD = None
EVENT_QUEUE_ENABLED = None
TIME_BETWEEN_EVENTS = None
MESSAGE_RESPOND_PROMPT = {}
SUMMARIZE_PROMPT = {}
HELPER_PROMPT = {}
BIT_DONO = {}
BIT_DONO_W_MSG = {}
GIFTED_SUB = {}
RAID = {}
RESUB_INTERN = {}
RESUB_EMPLOYEE = {}
RESUB_SUPERVISOR = {}
RESUB_TENURED = {}
GIFT_CACHE = {}
TIMED_MESSAGES = []
RAID_THRESHOLD = None
INTERN_MONTHS = None
EMPLOYEE_MONTHS = None
SUPERVISOR_MONTHS = None
NORMAL_REACTION = None
IMPRESSED_REACTION = None
EXAGGERATED_REACTION = None
SCREAMING_REACTION = None
ASSISTANT_NAME = None
STATIONARY_ASSISTANT_NAME = None
DEBUG = None
AUDIO_FOLDER = os.path.join(os.path.dirname(__file__), "audio")
PLAY_NEXT_PRESSED = False
PREVIOUS_AUDIO = None
PAUSE_EVENT_QUEUE = False
CURRENT_EVENT = None
AUTO_AD_ENABLED = None
NUMBER_OF_EVENTS_IN_QUEUE = 0

openai_manager = OpenAiManager()
openai_client = OpenAI(api_key = OPENAI_API_KEY)
audio_manager = AudioManager()
tts_manager = SpeechToTextManager()
elevenlabs_manager = ElevenLabsManager()
obswebsockets_manager = OBSWebsocketsManager()

pygame.init()

global_bot_instance = None
gui_queue = queue.Queue()
hotkey_queue = queue.Queue()


async def pass_bot_instance():
    bot = get_bot_instance()
    return bot

async def set_global_variables():
    global TEN_MESSAGES_KEY
    global LISTEN_AND_RESPOND_KEY
    global VOICED_SUMMARY_KEY
    global ELEVENLABS_VOICE
    global BOT_NICK
    global TWITCH_CHANNEL #For twitch chat, not eventsub
    global BOT_TOKEN
    global OBS_HOTKEY
    global PLAY_NEXT
    global SKIP_AUDIO
    global REPLAY_LAST
    global PLAY_AD
    global EVENT_QUEUE_ENABLED
    global TIME_BETWEEN_EVENTS
    global RAID_THRESHOLD
    global INTERN_MONTHS
    global EMPLOYEE_MONTHS
    global SUPERVISOR_MONTHS
    global NORMAL_REACTION
    global IMPRESSED_REACTION
    global EXAGGERATED_REACTION
    global SCREAMING_REACTION
    global DEBUG
    global ASSISTANT_NAME
    global STATIONARY_ASSISTANT_NAME
    global AUTO_AD_ENABLED
    settings = await load_settings()
    DEBUG = settings["Debug"]
    set_debug(DEBUG)
    TEN_MESSAGES_KEY = settings["Hotkeys"]["10_MESSAGES_RESPOND_KEY"]
    LISTEN_AND_RESPOND_KEY = settings["Hotkeys"]["LISTEN_AND_RESPOND_KEY"]
    VOICED_SUMMARY_KEY = settings["Hotkeys"]["VOICE_SUMMARIZE_KEY"]
    PLAY_NEXT = settings["Hotkeys"]["PLAY_NEXT_KEY"]
    SKIP_AUDIO = settings["Hotkeys"]["SKIP_CURRENT_KEY"]
    REPLAY_LAST = settings["Hotkeys"]["REPLAY_LAST_KEY"]
    PLAY_AD = settings["Hotkeys"]["PLAY_AD"]
    EVENT_QUEUE_ENABLED = settings["Event Queue Enabled"]
    TIME_BETWEEN_EVENTS = settings["Seconds Between Events"]
    ELEVENLABS_VOICE = settings["Elevenlabs Voice ID"]
    BOT_NICK = settings["Bot Nickname"]
    TWITCH_CHANNEL = settings["Broadcaster Channel"]
    RAID_THRESHOLD = settings["Raid Threshold"]
    INTERN_MONTHS = settings["Resub"]["Intern Max Month Count"]
    EMPLOYEE_MONTHS = settings["Resub"]["Employee Max Month Count"]
    SUPERVISOR_MONTHS = settings["Resub"]["Supervisor Max Month Count"]
    NORMAL_REACTION = settings["Bits"]["Normal Reaction Threshold"]
    IMPRESSED_REACTION = settings["Bits"]["Impressed Reaction Threshold"]
    EXAGGERATED_REACTION = settings["Bits"]["Exaggerated Reaction Threshold"]
    SCREAMING_REACTION = settings["Bits"]["Screaming Reaction Threshold"]
    ASSISTANT_NAME = settings["OBS Assistant Object Name"]
    STATIONARY_ASSISTANT_NAME = settings["OBS Assistant Stationary Object Name"]
    AUTO_AD_ENABLED = settings["Auto Ad Enabled"]
    BOT_TOKEN = refresh_token("bot", CLIENT_ID, CLIENT_SECRET)

async def save_message(author, content):
    messages = await load_messages()
    formatted_message = f"{author}: {content}"
    messages.append(formatted_message)
    if len(messages) > 10:
        messages.pop(0)
    await save_messages(messages)

async def set_prompts():
    prompts = await load_prompts()
    global MESSAGE_RESPOND_PROMPT
    global SUMMARIZE_PROMPT
    global HELPER_PROMPT
    global BIT_DONO
    global BIT_DONO_W_MSG
    global GIFTED_SUB
    global RAID
    global RESUB_INTERN
    global RESUB_EMPLOYEE
    global RESUB_SUPERVISOR
    global RESUB_TENURED
    MESSAGE_RESPOND_PROMPT = {"role": "system", "content": (prompts["Respond to Messages"])}
    SUMMARIZE_PROMPT = {"role": "system", "content": (prompts["Summarize Messages"])}
    HELPER_PROMPT = {"role": "system", "content": (prompts["Respond to Streamer"])}
    BIT_DONO = {"role": "system", "content": (prompts["Bit Donation w/o Message"])}
    BIT_DONO_W_MSG = {"role": "system", "content": (prompts["Bit Donation w/ Message"])}
    GIFTED_SUB = {"role": "system", "content": (prompts["Gifted Sub"])}
    RAID = {"role": "system", "content": (prompts["Raid"])}
    RESUB_INTERN = {"role": "system", "content": (prompts["Resub Intern"])}
    RESUB_EMPLOYEE = {"role": "system", "content": (prompts["Resub Employee"])}
    RESUB_SUPERVISOR = {"role": "system", "content": (prompts["Resub Supervisor"])}
    RESUB_TENURED = {"role": "system", "content": (prompts["Resub Tenured Employee"])}

def global_hotkey_listener(hotkey_queue, settings):
    # Map hotkey names to their key combos
    hotkey_map = {
        "10_MESSAGES_RESPOND_KEY": settings["Hotkeys"]["10_MESSAGES_RESPOND_KEY"],
        "LISTEN_AND_RESPOND_KEY": settings["Hotkeys"]["LISTEN_AND_RESPOND_KEY"],
        "VOICE_SUMMARIZE_KEY": settings["Hotkeys"]["VOICE_SUMMARIZE_KEY"],
        "PLAY_NEXT_KEY": settings["Hotkeys"]["PLAY_NEXT_KEY"],
        "SKIP_CURRENT_KEY": settings["Hotkeys"]["SKIP_CURRENT_KEY"],
        "REPLAY_LAST_KEY": settings["Hotkeys"]["REPLAY_LAST_KEY"],
    }
    for name, combo in hotkey_map.items():
        if combo:  # Only register if combo is not empty
            print(f"[DEBUG]Registering hotkey: {combo} for {name}")
            keyboard.add_hotkey(combo, lambda n=name: hotkey_queue.put(n))
    # Block forever (or until main thread exits)
    keyboard.wait()

async def respond_to_messages():
    if DEBUG:
        print("[DEBUG]Respond to messages called")

    twitch_channel = TWITCH_CHANNEL
    messages = await load_messages()
    messages_str = "\n".join(messages)
    prompt = [MESSAGE_RESPOND_PROMPT, 
              {"role": "user", "content": messages_str}]
    response = openai_manager.chat(prompt)
    channel = global_bot_instance.get_channel(twitch_channel)
    await channel.send(response)
    await save_messages([])
    return

async def ask_maddieply():
    if DEBUG:
        print("[DEBUG]ask_maddie triggered")
    print ("[green]Now listening to your microphone:")

    global PAUSE_EVENT_QUEUE, CURRENT_EVENT
    PAUSE_EVENT_QUEUE = True

    mic_result = tts_manager.speechtotext_from_mic_continuous()

    if not mic_result or not mic_result.strip():
        print ("[red]Did not receive any input from your microphone!")
        PAUSE_EVENT_QUEUE = False
        return

    response = openai_manager.chat_with_history(mic_result)

    settings = await load_settings()
    model = settings["Elevenlabs Synthesizer Model"]

    try:
        output = elevenlabs_manager.text_to_audio(response, ELEVENLABS_VOICE, False, model=model)
    except Exception as e:
        print(f"[ERROR]Error generating audio: {e}")
        voice = settings["Azure TTS Backup Voice"]
        output = tts_manager.text_to_speech(response, voice)

    CURRENT_EVENT = asyncio.create_task(global_bot_instance.assistant_responds(output))
    try:
        await CURRENT_EVENT
    except asyncio.CancelledError:
        if DEBUG:
            print("[DEBUG]Assistant Responds was cancelled.")
    except Exception as e:
        if DEBUG:
            print(f"[ERROR]Error in assistant response: {e}")
    finally:
        PAUSE_EVENT_QUEUE = False
        CURRENT_EVENT = None

async def summarize_chat():
    if DEBUG:
        print("[DEBUG]summarize_chat triggered")

    global PAUSE_EVENT_QUEUE, CURRENT_EVENT
    PAUSE_EVENT_QUEUE = True

    messages = await load_messages()
    messages_str = "\n".join(messages)
    full_prompt = [SUMMARIZE_PROMPT,
                   {"role": "user", "content": messages_str}]
    response = openai_manager.chat(full_prompt)

    settings = await load_settings()
    model = settings["Elevenlabs Synthesizer Model"]

    try:
        output = elevenlabs_manager.text_to_audio(response, ELEVENLABS_VOICE, False, model=model)
    except Exception as e:
        print(f"[ERROR]Error generating audio: {e}")
        voice = settings["Azure TTS Backup Voice"]
        output = tts_manager.text_to_speech(response, voice)
    CURRENT_EVENT = asyncio.create_task(global_bot_instance.assistant_responds(output))
    try:
        await CURRENT_EVENT
    except asyncio.CancelledError:
        if DEBUG:
            print("[DEBUG] CURRENT_EVENT was cancelled.")
    except Exception as e:
        if DEBUG:
            print(f"[ERROR]Error in assistant response: {e}")
    finally:
        PAUSE_EVENT_QUEUE = False
        CURRENT_EVENT = None

async def cleanup_gift_cache():
    while True:
        now = time.time()
        to_delete = [k for k, v in GIFT_CACHE.items() if now - v["time"] > 30]
        for k in to_delete:
            del GIFT_CACHE[k]
        await asyncio.sleep(10)

async def process_hotkey_queue(bot, hotkey_queue):
    while True:
        global PLAY_NEXT_PRESSED
        global PAUSE_EVENT_QUEUE
        global CURRENT_EVENT
        try:
            hotkey = hotkey_queue.get_nowait()
        except queue.Empty:
            await asyncio.sleep(0.05)
            continue

        print(f"[DEBUG]Hotkey pressed {hotkey}")
        # Map hotkey names to bot actions
        if hotkey == "10_MESSAGES_RESPOND_KEY":
            await respond_to_messages()
        elif hotkey == "LISTEN_AND_RESPOND_KEY":
            await ask_maddieply()
        elif hotkey == "VOICE_SUMMARIZE_KEY":
            await summarize_chat()
        elif hotkey == "PLAY_NEXT_KEY":
            if not PLAY_NEXT_PRESSED and EVENT_QUEUE_ENABLED:
                PLAY_NEXT_PRESSED = True
        elif hotkey == "SKIP_CURRENT_KEY":
            if CURRENT_EVENT and not CURRENT_EVENT.done():
                audio_manager.stop_playback()
                CURRENT_EVENT.cancel()
        elif hotkey == "REPLAY_LAST_KEY":
            PAUSE_EVENT_QUEUE = True
            audio = bot.event_queue.get_last()
            bot.event_queue.is_playing = True
            CURRENT_EVENT = asyncio.create_task(bot.assistant_responds(audio))
            try:
                await CURRENT_EVENT
            except asyncio.CancelledError:
                if DEBUG:
                    print("[DEBUG] CURRENT_EVENT was cancelled.")
            except Exception as e:
                if DEBUG:
                    print(f"[ERROR]Error in assistant response: {e}")
            finally:
                bot.event_queue.is_playing = False
                PAUSE_EVENT_QUEUE = False
                CURRENT_EVENT = None
        elif hotkey == "PLAY_AD":
            await trigger_ad()
            ad_reset_event.set()

async def rng(minimum: int, maximum: int):
    return random.randint(minimum, maximum)

def delete_all_audio_files(folder_path: str):
    for ext in ("*.mp3", "*.wav"):
        for file_path in glob.glob(os.path.join(folder_path, ext)):
            os.remove(file_path)

async def purge_old_voice_responses(purge_all: bool):
    if purge_all:
        delete_all_audio_files(AUDIO_FOLDER)
    else:
        audio_files = []
        for ext in ("*.mp3", "*.wav"):
            audio_files.extend(glob.glob(os.path.join(AUDIO_FOLDER, ext)))

        if len(audio_files) <= 5:
            return
        
        audio_files.sort(key = os.path.getmtime)

        for file_path in audio_files[:-5]:
            os.remove(file_path)

class EventQueue:
    def __init__(self):
        self.queue = []
        self.played = []
        self.is_playing = False
    
    def add_audio(self, event: dict): #Adds event to the end of the queue
        global NUMBER_OF_EVENTS_IN_QUEUE
        self.queue.append(event)
        NUMBER_OF_EVENTS_IN_QUEUE += 1
        if DEBUG:
            print(f"[green]Audio added to queue, length: {NUMBER_OF_EVENTS_IN_QUEUE}")
        #"type": "event" or "audio", "audio": "audio_file_path", "from_user": "username", "event_type": "event_type"

    def add_event(self, event: dict): #Adds event to the front of the queue for priority
        global NUMBER_OF_EVENTS_IN_QUEUE
        self.queue.insert(0, event)
        NUMBER_OF_EVENTS_IN_QUEUE += 1
        if DEBUG:
            print(f"[green]Event added to queue, length: {NUMBER_OF_EVENTS_IN_QUEUE}")

    def is_next_event(self):
        if not self.queue:
            return False
        event = self.queue[0]
        if event["type"] == "event":
            return True
        else:
            return False

    def get_next(self):
        if self.queue:
            global NUMBER_OF_EVENTS_IN_QUEUE
            self.is_playing = True
            event = self.queue.pop(0)
            if DEBUG:
                print(f"Next event retrieved: {event}")
            NUMBER_OF_EVENTS_IN_QUEUE -= 1
            self.played.append(event)
            return event["audio"]
        return None
    
    def is_empty(self):
        return False if self.queue else True
    
    def get_last(self): #Used to replay the last played event
        if self.played:
            self.is_playing = True
            event = self.played[-1]
            return event["audio"]
        return None
    
    def replay_event(self, event_index: int): #Used to replay an event selected from GUI
        if self.played:
            self.is_playing = True
            event = self.played[event_index]
            return event["audio"]
        return False
    
    def remove_event(self, event_index: int): #Used to remove an event from the queue using the GUI
        self.queue.pop(event_index)

    def get_event(self, event_index: int):
        if 0 <= event_index < len(self.queue):
            return self.queue[event_index]
        return None
    
    def clear(self):
        self.queue.clear()

class Bot(commands.Bot):
    def __init__(self, gui_queue):
        super().__init__(token=BOT_TOKEN, prefix="!", nick=BOT_NICK, initial_channels=[TWITCH_CHANNEL])

        global global_bot_instance
        global_bot_instance = self
        self.gui_queue = gui_queue

        self.event_queue = EventQueue()

    async def event_ready(self):
        print(f"[green]Bot {self.nick} is online!")
        asyncio.create_task(purge_old_voice_responses(True))
        asyncio.create_task(self.start_automated_messages())
        asyncio.create_task(self.event_loop())
        settings = await load_settings()
        device = settings["Audio Output Device"]
        if device:
            audio_manager.set_output_device(device)
        
        channel = self.get_channel(TWITCH_CHANNEL)
        await channel.send("Bot online!")

    async def event_loop(self):
        global PREVIOUS_AUDIO, CURRENT_EVENT, PLAY_NEXT_PRESSED
        while True:
            if self.event_queue.is_playing:
                await asyncio.sleep(1)
                continue
            if EVENT_QUEUE_ENABLED:
                if self.event_queue.is_next_event():
                    if DEBUG:
                        print("[green]Next event is priority, playing next event.")
                    audio = self.event_queue.get_next()
                    PREVIOUS_AUDIO = audio
                    if audio:
                        CURRENT_EVENT = asyncio.create_task(self.assistant_responds(audio))
                        try:
                            await CURRENT_EVENT
                        except asyncio.CancelledError:
                            if DEBUG:
                                print("[DEBUG] CURRENT_EVENT was cancelled.")
                        except Exception as e:
                            print(f"[ERROR][EventQueue] Error processing event: {e}")
                        finally:
                            self.event_queue.is_playing = False
                            CURRENT_EVENT = None
                elif PLAY_NEXT_PRESSED:
                    if self.event_queue.is_empty():
                        if DEBUG:
                          print("[red]Play next pressed but queue empty.")
                          PLAY_NEXT_PRESSED = False
                        continue
                    if DEBUG:
                        print("[green]Play next pressed! Playing next audio.")
                    PLAY_NEXT_PRESSED = False
                    audio = self.event_queue.get_next()
                    PREVIOUS_AUDIO = audio
                    CURRENT_EVENT = asyncio.create_task(self.assistant_responds(audio))
                    try:
                        await CURRENT_EVENT
                    except asyncio.CancelledError:
                        if DEBUG:
                            print("[DEBUG] CURRENT_EVENT was cancelled.")
                    except Exception as e:
                        print(f"[ERROR][EventQueue] Error processing audio: {e}")
                    finally:
                        self.event_queue.is_playing = False
                        CURRENT_EVENT = None
                        await asyncio.sleep(TIME_BETWEEN_EVENTS if not self.event_queue.is_next_event() else 0.5)
                else:
                    await asyncio.sleep(0.1)
                continue

            if self.event_queue.is_empty():
                await asyncio.sleep(TIME_BETWEEN_EVENTS)
            elif not PAUSE_EVENT_QUEUE:
                if DEBUG:
                    print("[green]Queue disabled, automatically playing next event.")
                audio = self.event_queue.get_next()
                PREVIOUS_AUDIO = audio
                if audio:
                    CURRENT_EVENT = asyncio.create_task(self.assistant_responds(audio))
                    try:
                        await CURRENT_EVENT
                    except asyncio.CancelledError:
                        if DEBUG:
                            print("[DEBUG] CURRENT_EVENT was cancelled.")
                    except Exception as e:
                        print(f"[ERROR][EventQueue] Error processing audio: {e}")
                    finally:
                        self.event_queue.is_playing = False
                        CURRENT_EVENT = None
                    if not self.event_queue.is_next_event():
                        await asyncio.sleep(TIME_BETWEEN_EVENTS)
                    else:
                        await asyncio.sleep(0.5)
            else:
                if DEBUG:
                    print("[DEBUG]Event queue is paused, skipping processing.")
                await asyncio.sleep(0.5)
                continue

    async def reload_global_variable(self):
        settings = await load_settings()
        global ELEVENLABS_VOICE
        global RAID_THRESHOLD
        global INTERN_MONTHS
        global EMPLOYEE_MONTHS
        global SUPERVISOR_MONTHS
        global NORMAL_REACTION
        global IMPRESSED_REACTION
        global EXAGGERATED_REACTION
        global SCREAMING_REACTION
        global ASSISTANT_NAME
        global STATIONARY_ASSISTANT_NAME
        global EVENT_QUEUE_ENABLED
        global TIME_BETWEEN_EVENTS
        global AUTO_AD_ENABLED
        EVENT_QUEUE_ENABLED = settings["Event Queue Enabled"]
        TIME_BETWEEN_EVENTS = settings["Seconds Between Events"]
        ELEVENLABS_VOICE = settings["Elevenlabs Voice ID"]
        RAID_THRESHOLD = settings["Raid Threshold"]
        INTERN_MONTHS = settings["Resub"]["Intern Max Month Count"]
        EMPLOYEE_MONTHS = settings["Resub"]["Employee Max Month Count"]
        SUPERVISOR_MONTHS = settings["Resub"]["Supervisor Max Month Count"]
        NORMAL_REACTION = settings["Bits"]["Normal Reaction Threshold"]
        IMPRESSED_REACTION = settings["Bits"]["Impressed Reaction Threshold"]
        EXAGGERATED_REACTION = settings["Bits"]["Exaggerated Reaction Threshold"]
        SCREAMING_REACTION = settings["Bits"]["Screaming Reaction Threshold"]
        ASSISTANT_NAME = settings["OBS Assistant Object Name"]
        STATIONARY_ASSISTANT_NAME = settings["OBS Assistant Stationary Object Name"]
        AUTO_AD_ENABLED = settings["Auto Ad Enabled"]
        device = settings["Audio Output Device"]
        audio_manager.set_output_device(device)

    async def reload_global_prompts(self):
        prompts = await load_prompts()
        global MESSAGE_RESPOND_PROMPT
        global SUMMARIZE_PROMPT
        global HELPER_PROMPT
        global BIT_DONO
        global BIT_DONO_W_MSG
        global GIFTED_SUB
        global RAID
        global RESUB_INTERN
        global RESUB_EMPLOYEE
        global RESUB_SUPERVISOR
        global RESUB_TENURED
        MESSAGE_RESPOND_PROMPT = {"role": "system", "content": (prompts["Respond to Messages"])}
        SUMMARIZE_PROMPT = {"role": "system", "content": (prompts["Summarize Messages"])}
        HELPER_PROMPT = {"role": "system", "content": (prompts["Respond to Streamer"])}
        BIT_DONO = {"role": "system", "content": (prompts["Bit Donation w/o Message"])}
        BIT_DONO_W_MSG = {"role": "system", "content": (prompts["Bit Donation w/ Message"])}
        GIFTED_SUB = {"role": "system", "content": (prompts["Gifted Sub"])}
        RAID = {"role": "system", "content": (prompts["Raid"])}
        RESUB_INTERN = {"role": "system", "content": (prompts["Resub Intern"])}
        RESUB_EMPLOYEE = {"role": "system", "content": (prompts["Resub Employee"])}
        RESUB_SUPERVISOR = {"role": "system", "content": (prompts["Resub Supervisor"])}
        RESUB_TENURED = {"role": "system", "content": (prompts["Resub Tenured Employee"])}

    async def toggle_debug(self):
        print("entered toggle_debug in bot.py")
        settings = await load_settings()
        global DEBUG
        print(DEBUG)
        DEBUG = not DEBUG
        set_debug(DEBUG)
        print(DEBUG)
        settings["Debug"] = DEBUG
        asyncio.create_task(save_settings(settings))
        
    async def scheduled_message(self, minutes: int, messages: int, text: str, counter: dict):
        if DEBUG:
            print(f"[DEBUG]Scheduled message started with {minutes} minutes and {messages} messages. Text: {text}")
        try:
            if minutes and not messages:
                # Time-only trigger
                while True:
                    await asyncio.sleep(minutes * 60)
                    await global_bot_instance.send_message(text)

            elif messages and not minutes:
                # Message-count-only trigger
                while True:
                    await asyncio.sleep(1)
                    if counter["count"] >= messages:
                        await global_bot_instance.send_message(text)
                        counter["count"] = 0

            elif messages and minutes:
                # Combined trigger (message count + timer)
                while True:
                    await asyncio.sleep(minutes * 60)
                    if counter["count"] >= messages:
                        await global_bot_instance.send_message(text)
                        counter["count"] = 0
                    else:
                        if DEBUG:
                            print(f"[DEBUG]Timer elapsed but message count not met (count={counter['count']} < {messages})")

        except asyncio.CancelledError:
            if DEBUG:
                print("[DEBUG]Scheduled message task cancelled.")

    async def reset_scheduled_message(self, task_id):
        await self.cancel_timed_message(task_id)
        await self.start_timed_message(task_id)

    async def start_automated_messages(self):
        scheduled_messages = await load_scheduled_messages()
        for message in scheduled_messages["Messages"].values():
            if not message.get("enabled", False):
                continue

            minutes = message.get("minutes")
            messages = message.get("messages")
            text = message.get("content", "")
            message_id = str(message.get("id"))  # Add a unique ID per scheduled message

            message_counter = {"count": 0}
            task = asyncio.create_task(self.scheduled_message(minutes, messages, text, message_counter))

            TIMED_MESSAGES.append({
                "id": message_id,
                "task": task,
                "text": text,
                "counter": message_counter
            })

    async def cancel_timed_message(self, task_id):
        task_id = str(task_id)
        for scheduled in TIMED_MESSAGES:
            if scheduled["id"] == task_id:
                scheduled["task"].cancel()
                TIMED_MESSAGES.remove(scheduled)
                if DEBUG:
                    print(f"[DEBUG]Canceled scheduled message with ID: {task_id}")
                return True
        if DEBUG:
            print(f"[DEBUG]No scheduled message found with ID: {task_id}")
        return False

    async def start_timed_message(self, id):
        id = str(id)
        scheduled_messages = await load_scheduled_messages()
        task = scheduled_messages["Messages"][id]
        minutes = task["minutes"]
        messages = task["messages"]
        text = task.get("content", "")

        message_counter = {"count": 0}
        task = asyncio.create_task(self.scheduled_message(minutes, messages, text, message_counter))

        TIMED_MESSAGES.append({
            "id": id,
            "task": task,
            "text": text,
            "counter": message_counter
        })
        if DEBUG:
            print(f"[DEBUG]Added scheduled message with ID: {id}")

    async def toggle_automated_message(self, id):
        if DEBUG:
            print("[DEBUG]entered toggle_automated")
        scheduled_messages = await load_scheduled_messages()
        scheduled_messages["Messages"][id]["enabled"] = not scheduled_messages["Messages"][id]["enabled"]
        await save_scheduled_messages(scheduled_messages)
        if not scheduled_messages["Messages"][id]["enabled"]:
            await self.cancel_timed_message(id)
        else:
            await self.start_timed_message(id)

    async def send_message(self, message):
        try:
            channel = self.get_channel(TWITCH_CHANNEL)
            if channel:
                await channel.send(message)
            else:
                print(f"[ERROR]Channel '{TWITCH_CHANNEL}' not found.")
        except Exception as e:
            print(f"[ERROR]Exception while sending message: {e}")

    async def parse_elevenlabs_exception(self, exception):
        import ast
        error_text = str(exception)
        if "quota_exceeded" in error_text and "credits" in error_text:
            try:
                body_start = error_text.find("body: ")
                body_str = error_text[body_start + 6:].strip()
                if body_str.endswith("}"):
                    body_dict = ast.literal_eval(body_str)
                    message = body_dict["detail"]["message"]

                    remaining = re.search(r"have (\d+) credits", message)
                    required = re.search(r"(\d+) credits are required", message)
                    if remaining and required:
                        return f"[ERROR] ElevenLabs quota exceeded: {remaining.group(1)} credits remaining, {required.group(1)} required."
                    else:
                        return f"[ERROR] ElevenLabs quota exceeded: {message}"
            except Exception as parse_error:
                return f"[ERROR] Failed to parse ElevenLabs exception: {parse_error}"
        return str(exception)

    async def assistant_responds(self, output):
        try:
            obswebsockets_manager.activate_assistant(ASSISTANT_NAME)

            volumes, total_duration_ms = await audio_manager.process_audio(output)
            min_vol = min(volumes)
            max_vol = max(volumes)

            bounce_task = asyncio.create_task(obswebsockets_manager.bounce_while_talking(volumes, min_vol, max_vol, total_duration_ms, ASSISTANT_NAME, STATIONARY_ASSISTANT_NAME))
            loop = asyncio.get_running_loop()

            await loop.run_in_executor(None, audio_manager.play_audio, output, True, False, True)
            await bounce_task

            obswebsockets_manager.deactivate_assistant(ASSISTANT_NAME)
        except asyncio.CancelledError:
            if DEBUG:
                print("[DEBUG]Event was cancelled.")
                bounce_task.cancel()
                obswebsockets_manager.deactivate_assistant(ASSISTANT_NAME)
                raise

    async def handle_raid(self, event, game_name = None):#May need to adjust code to incoporate already existing policies.
        user_name = event.from_broadcaster_user_name
        viewer_count = event.viewers
        if DEBUG:
            print(f"[DEBUG]RAID by {user_name} with {viewer_count} viewers! Last playing {game_name}")
        channel = self.get_channel(TWITCH_CHANNEL)
        await channel.send(f"RAID ALERT: {user_name} has raided with {viewer_count} viewers! {f"Last seen playing {game_name}!" if game_name else ""}")
        if viewer_count >= RAID_THRESHOLD:
            prompt_2 = {"role": "user", "content": f"{user_name} has raided with {viewer_count} viewers! Last seen playing {game_name}!"}
            full_prompt = [RAID, prompt_2]
            response = openai_manager.chat(full_prompt)

            settings = await load_settings()
            model = settings["Elevenlabs Synthesizer Model"]

            try:
                output = elevenlabs_manager.text_to_audio(response, ELEVENLABS_VOICE, False, model=model)
            except Exception as e:
                print(await self.parse_elevenlabs_exception(e))
                voice = settings["Azure TTS Backup Voice"]
                output = tts_manager.text_to_speech(response, voice)
            queued_event = {"type": "event", "audio": output, "from_user": event.from_broadcaster_user_name, "event_type": "raid"}
            self.event_queue.add_event(queued_event)
    
    #Not currently used, but may be useful in the future
    async def handle_channel_points(self, event): #Placeholder for channel points
        user_name = event.user_name
        reward_title = event.reward.type
        reward_cost = event.reward.cost
        message = event.user_input
        redeemed_time = event.redeemed_at
        if DEBUG:
            print(f"[DEBUG]{user_name} used {reward_cost} channel points to redeem {reward_title} at {redeemed_time} with message: {message}")
        channel = self.get_channel(TWITCH_CHANNEL)
        await channel.send(f"{user_name} redeemed {reward_title}!")

    #Not currently used, but may be useful in the future
    async def handle_custom_channel_points(self, event): #Placeholder for custom channel points
        #May end up as a twitch version of !askmaddie and !policies
        user_name = event.user_name
        reward_title = event.reward.title
        reward_cost = event.reward.cost
        prompt = event.reward.prompt
        redeemed_time = event.redeemed_at
        if DEBUG:
            print(f"[DEBUG]{user_name} used {reward_cost} channel points to redeem {reward_title} at {redeemed_time} with message: {prompt}")
        channel = self.get_channel(TWITCH_CHANNEL)
        await channel.send(f"{user_name} redeemed {reward_title}!")

    async def handle_gift_subscription(self, gifter_name, recipient_list = None, gift_count = None, tier = None, gift_cumulative = None):
        #Gifter_name, recipient_list, and tier are grabbed from twitch chat
        #Gift_count and gift_cumulative are grabbed from eventsub
        global GIFT_CACHE
        if DEBUG:
            print("[DEBUG]Triggered gift subscription")
        if gifter_name:
            key = gifter_name.lower()

        if key not in GIFT_CACHE:
            GIFT_CACHE[key] = {"recipients": [], "count": 0, "time": time.time(), "tier": None, "cumulative": None}
        
        if recipient_list:
            GIFT_CACHE[key]["recipients"].extend(recipient_list)

        if gift_count:
            GIFT_CACHE[key]["count"] = gift_count

        if tier:
            GIFT_CACHE[key]["tier"] = tier

        if gift_cumulative:
            GIFT_CACHE[key]["gift_cumulative"] = gift_cumulative


        current = GIFT_CACHE[key]
        recipients = current["recipients"]
        count = current["count"]

        if count and len(recipients) >= count:
            if gifter_name == "Anonymous":
                gifter_name = "An anonymous gifter"
            recipients_str = ", ".join(recipients[:count])
            tier = current["tier"]
            gift_cumulative = current["cumulative"]

            if gift_cumulative:
                prompt_2 = {"role": "user", "content": f"{gifter_name} gifted {count} tier {tier} subs to the following users: {recipients_str}! They have gifted a total of {gift_cumulative} subs."}
            else:
                prompt_2 = {"role": "user", "content": f"{gifter_name} gifted {count} subs to: {recipients_str}."}
            
            full_prompt = [GIFTED_SUB, prompt_2]
            response = openai_manager.chat(full_prompt)

            settings = await load_settings()
            model = settings["Elevenlabs Synthesizer Model"]

            try:
                output = elevenlabs_manager.text_to_audio(response, ELEVENLABS_VOICE, False, model=model)
            except Exception as e:
                print(await self.parse_elevenlabs_exception(e))
                voice = settings["Azure TTS Backup Voice"]
                output = tts_manager.text_to_speech(response, voice)
            queued_event = {"type": "event", "audio": output, "from_user": gifter_name, "event_type": f"{count} gifted subs"}
            self.event_queue.add_event(queued_event)
            del GIFT_CACHE[key]

    async def handle_subscription(self, event):
        user_name = event.user_name
        tier = event.tier
        if tier == "1000":
            tier = 1
        elif tier == "2000":
            tier = 2
        elif tier == "3000":
            tier = 3
        if DEBUG:
            print(f"[DEBUG]{user_name} subscribed! Tier {tier}")
        channel = self.get_channel(TWITCH_CHANNEL)
        await channel.send(f"Thanks for subscribing, {user_name}! Enjoy your Tier {tier} subscription!")

    async def handle_subscription_message(self, event): #Placeholder for subscription message
        user_name = event.user_name
        tier = event.tier
        duration_months = getattr(event, "duration_months", 1)
        if tier == "1000":
            tier = 1
        elif tier == "2000":
            tier = 2
        elif tier == "3000":
            tier = 3
        if duration_months <= 2:
            random_number = await rng(1, 5)
            resub = {"role": "system", "content": RESUB_INTERN["content"].replace("<RNG>", str(random_number))}
        elif duration_months <= 6:
            random_number = await rng(6, 20)
            resub = {"role": "system", "content": RESUB_EMPLOYEE["content"].replace("<RNG>", str(random_number))}
        elif duration_months <= 12:
            random_number = await rng(21, 50)
            resub = {"role": "system", "content": RESUB_SUPERVISOR["content"].replace("<RNG>", str(random_number))}
        else:
            random_number = await rng(51, 100)
            resub = {"role": "system", "content": RESUB_TENURED["content"].replace("<RNG>", str(random_number))}
        message = getattr(event.message, "text", "") if hasattr(event, "message") else ""
        cumulative = getattr(event, "cumulative_months", 0)
        if message:
            if cumulative > 1:
                prompt_2 = {"role": "system", "content": f"{user_name} resubscribed for {duration_months} months in a row for a total of {cumulative} months! Tier {tier} with message: {message}"}
            else:
                prompt_2 = {"role": "system", "content": f"{user_name} resubscribed for {duration_months} months! Tier {tier} with message: {message}"}
        full_prompt = [resub, prompt_2]
        response = openai_manager.chat(full_prompt)
        full_response = f"{user_name} says: {message}. {response}"

        settings = await load_settings()
        model = settings["Elevenlabs Synthesizer Model"]

        try:
            output = elevenlabs_manager.text_to_audio(full_response, ELEVENLABS_VOICE, False, model=model)
        except Exception as e:
            print(await self.parse_elevenlabs_exception(e))
            voice = settings["Azure TTS Backup Voice"]
            output = tts_manager.text_to_speech(full_response, voice)

        queued_event = {"type": "event", "audio": output, "from_user": user_name, "event_type": f"Resub for {duration_months} months"}
        self.event_queue.add_event(queued_event)

    async def handle_bits(self, event):
        bits = event.bits
        if event.is_anonymous:
            username = "An anonymous user"
        else:
            username = event.user_name
        if bits < NORMAL_REACTION: #May change to add logic for showing on screen
            if DEBUG:
                print(f"[DEBUG]{username} donated {bits} bits, but it's not enough to trigger a response.")
            return
        prompts = await load_prompts()
        broadcaster_name = event.broadcaster_user_name
        message = None
        if DEBUG:
            print(f"[DEBUG]{username} donated {bits} bits!")
        channel = self.get_channel(TWITCH_CHANNEL)
        if not event.is_anonymous:
            await channel.send(f"{username} donated {bits} bits!")
        else:
            await channel.send(f"An anonymous user donated {bits} bits!")
        if bits >= NORMAL_REACTION:
            if bits >= NORMAL_REACTION and bits < IMPRESSED_REACTION:
                reaction = "Normal"
            elif bits >= IMPRESSED_REACTION and bits < EXAGGERATED_REACTION:
                reaction = "Impressed"
            elif bits >= EXAGGERATED_REACTION and bits < SCREAMING_REACTION:
                reaction = "Exaggerated"
            elif bits >= SCREAMING_REACTION:
                reaction = "Dear god, just yell!"
            if event.message == "" or event.message == None:
                if reaction != "Dear god, just yell!":
                    prompt_1 = {"role": "system", "content": f"{prompts["Bit Donation w/o Message"]}"}
                    prompt_2 = {"role": "system", "content": f"{username} donated {bits} to {broadcaster_name}. In response to the amount of bits, you should respond with a {reaction} reaction."}
                else:
                    prompt_1 = {"role": "system", "content": f"You are now Maddieply, the lovable anime catgirl secretary to the dystopian business ModdCorp. You are sarcastic, snarky, and sassy. You know all the rules and policies of ModdCorp, but are still lazy about your job. Your boss is ModdiPly, a twitch streamer and CEO of ModdCorp. Your job is to thank people who donate their twitch bits to ModdiPly. They've donated such an extreme amount of bits, you should be shocked and scream in excitement. You are not allowed to say anything else, just yell! Scream, freak out, and be as loud as possible!"}
                    prompt_2 = {"role": "system", "content": f"{username} donated {bits} to {broadcaster_name}. In response to the amount of bits, just yell! Scream, freak out, and be as loud as possible!"}
            else:
                message = event.message
                if reaction != "Dear god, just yell!":
                    prompt_1 = {"role": "system", "content": f"{prompts["Bit Donation w/ Message"]}"}
                    prompt_2 = {"role": "system", "content": f"{username} donated {bits} to {broadcaster_name}.\n{username}'s message: {message} In response to the amount of bits, you should respond with a {reaction} reaction."}
                else:
                    prompt_1 = {"role": "system", "content": f"You are now Maddieply, the lovable anime catgirl secretary to the dystopian business ModdCorp. You are sarcastic, snarky, and sassy. You know all the rules and policies of ModdCorp, but are still lazy about your job. Your boss is ModdiPly, a twitch streamer and CEO of ModdCorp. Your job is to thank people who donate their twitch bits to ModdiPly. They've donated such an extreme amount of bits, you should be shocked and scream in excitement. You are not allowed to say anything else, just yell! Scream, freak out, and be as loud as possible!"}
                    prompt_2 = {"role": "system", "content": f"{username} donated {bits} to {broadcaster_name}.\n{username}'s message: {message}."}
            
            full_prompt = [prompt_1, prompt_2]
            response = openai_manager.chat(full_prompt)

            settings = await load_settings()
            model = settings["Elevenlabs Synthesizer Model"]

            if message:
                full_response = f"'{message}.' {response}"
                try:
                    output = elevenlabs_manager.text_to_audio(full_response, ELEVENLABS_VOICE, False, model=model)
                except Exception as e:
                    print(await self.parse_elevenlabs_exception(e))
                    voice = settings["Azure TTS Backup Voice"]
                    output = tts_manager.text_to_speech(full_response, voice)
            else:
                try:
                    output = elevenlabs_manager.text_to_audio(response, ELEVENLABS_VOICE, False, model=model)
                except Exception as e:
                    print(await self.parse_elevenlabs_exception(e))
                    voice = settings["Azure TTS Backup Voice"]
                    output = tts_manager.text_to_speech(response, voice)

            queued_event = {"type": "audio", "audio": output, "from_user": username, "event_type": f"Bit Donation of {bits}"}
            self.event_queue.add_audio(queued_event)
        
    async def event_message(self, message):
        if message.echo:
            return
        
        for msg in TIMED_MESSAGES:
            if "counter" in msg:
                msg["counter"]["count"] += 1


        match_regular = re.match(r"^(.+?) gifted a Tier (\d) Sub to (.+?)!$", message.content)
        match_anon = re.match(r"^An anonymous gifter gave (.+?) a Tier (\d) Sub!$", message.content)
        if match_regular:
            gifter = match_regular.group(1)
            tier = match_regular.group(2)
            recipient = match_regular.group(3).strip()
            await global_bot_instance.handle_gift_subscription(gifter_name = gifter, recipient_list = [recipient], tier = tier)
        elif match_anon:
            gifter = "Anonymous"
            recipient = match_anon.group(1).strip()
            tier = match_anon.group(2)
            await global_bot_instance.handle_gift_subscription(gifter_name = gifter, recipient_list = [recipient], tier = tier)
        print(f"{message.author.name}: {message.content}")
        await save_message(message.author.name, message.content)
        await self.handle_commands(message)

    @commands.command(name="test")
    @cooldown(1, 30, Bucket.user)
    async def test(self, ctx):
        if DEBUG:
            print("[DEBUG]triggered repeat")
        try:
            await ctx.send("This is a test message.")
        except Exception as e:
            # Handle the cooldown error
            print(f"{ctx.author.name} tried to use the !test command too soon.")

def start_bot_in_thread(gui_queue):
    async def bot_main():
        await set_global_variables()
        bot = Bot(gui_queue)
        set_bot_instance(bot)
        asyncio.create_task(cleanup_gift_cache())
        asyncio.create_task(start_event_sub())
        asyncio.create_task(process_hotkey_queue(bot, hotkey_queue))  # <-- Start this BEFORE bot.start()
        await set_prompts()
        openai_manager.chat_history.append(HELPER_PROMPT)
        await bot.start()

    def run_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        bot_loop_holder['loop'] = loop  # Save the loop for the GUI
        loop.run_until_complete(bot_main())

    t = threading.Thread(target = run_loop, daemon = True)
    t.start()
    return t

bot_loop_holder = {}


if __name__ == "__main__":
    start_bot_in_thread(gui_queue)
    while 'loop' not in bot_loop_holder:
        time.sleep(0.05)
    bot_loop = bot_loop_holder['loop']
    settings = asyncio.run(load_settings())
    def run_gui():
        loop = asyncio.new_event_loop()
        app = TwitchBotGUI(gui_queue, bot_loop)
        asyncio.set_event_loop(loop)
        loop.run_until_complete(app.async_init())
        app.mainloop()

    gui_thread = threading.Thread(target=run_gui, daemon=True)
    gui_thread.start()

    global_hotkey_listener(hotkey_queue, settings)
    print("[red]Bot has stopped running.")
