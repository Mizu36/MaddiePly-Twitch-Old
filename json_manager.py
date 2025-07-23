import json
import os
import threading
import aiofiles
import aiofiles.os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
PROMPTS_FILE = os.path.join(DATA_DIR, "prompts.json")
MESSAGES_FILE = os.path.join(DATA_DIR, "messages.json")
SCHEDULED_MESSAGES_FILE = os.path.join(DATA_DIR, "scheduled_messages.json")
COMMANDS_FILE = os.path.join(DATA_DIR, "commands.json")
TOKENS_FILE = os.path.join(DATA_DIR, "tokens.json")
STREAMATHON_TRACKER = os.path.join(DATA_DIR, "streamathon_tracker.json")
FILEPATHS = [SETTINGS_FILE, MESSAGES_FILE, PROMPTS_FILE, SCHEDULED_MESSAGES_FILE, COMMANDS_FILE, TOKENS_FILE]
LISTS = [MESSAGES_FILE]
lock = threading.Lock()

def populate_data_folder():
    for file in FILEPATHS:
        ensure_file_exists(file)
        print(f"{file} created.")

async def ensure_file_exists(filepath):
    try: 
        await aiofiles.os.stat(filepath)
    except FileNotFoundError:
        async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
            if filepath not in LISTS:
                await f.write("{}")
            else:
                await f.write("[]")
            await new_json(filepath)

async def async_load_json(path):
    await ensure_file_exists(path)
    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        content = await f.read()
        return json.loads(content)

async def async_save_json(path, data):
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(data, indent=4))

async def load_settings():
    return await async_load_json(SETTINGS_FILE)

async def save_settings(data):
    await async_save_json(SETTINGS_FILE, data)

async def load_messages():
    return await async_load_json(MESSAGES_FILE)
        
async def save_messages(data):
    await async_save_json(MESSAGES_FILE, data)

async def load_prompts():
    return await async_load_json(PROMPTS_FILE)

async def save_prompts(data):
    return await async_save_json(PROMPTS_FILE, data)
        
async def load_scheduled_messages():
    return await async_load_json(SCHEDULED_MESSAGES_FILE)

async def save_scheduled_messages(data):
    await async_save_json(SCHEDULED_MESSAGES_FILE, data)

async def load_commands():
    return await async_load_json(COMMANDS_FILE)

async def save_commands(data):
    await async_save_json(COMMANDS_FILE, data)

async def load_tracker():
    return await async_load_json(STREAMATHON_TRACKER)

async def save_tracker(data):
    await async_save_json(STREAMATHON_TRACKER, data)

async def new_json(file):
    if file == SETTINGS_FILE:
        settings = {
                    "Bot Nickname": None,
                    "Broadcaster Channel": None,
                    "Broadcaster ID": None,
                    "Elevenlabs Voice ID": None,
                    "Elevenlabs Synthesizer Model": None,
                    "Azure TTS Backup Voice": None,
                    "Event Queue Enabled": False,
                    "Seconds Between Events": 5,
                    "Audio Output Device": None,
                    "Auto Ad Enabled": False,
                    "Ad Length (seconds)": 60,
                    "Ad Interval (minutes)": 60,
                    "Hotkeys": {
                        "LISTEN_AND_RESPOND_KEY": None,
                        "END_LISTEN_KEY": None,
                        "VOICE_SUMMARIZE_KEY": None,
                        "PLAY_NEXT_KEY": None,
                        "SKIP_CURRENT_KEY": None,
                        "REPLAY_LAST_KEY": None,
                        "PLAY_AD": None,
                        "PAUSE_QUEUE": None
                    },
                    "Raid Threshold": 1,
                    "Resub": {
                        "Intern Max Month Count": 2,
                        "Employee Max Month Count": 6,
                        "Supervisor Max Month Count": 12
                    },
                    "Bits": {
                        "Normal Reaction Threshold": 100,
                        "Impressed Reaction Threshold": 1000,
                        "Exaggerated Reaction Threshold": 5000,
                        "Screaming Reaction Threshold": 10000
                    },
                    "OBS Assistant Object Name": None,
                    "OBS Assistant Stationary Object Name": None,
                    "Onscreen Location": None,
                    "Offscreen Location": None,
                    "Streamathon Mode": False,
                    "Progress Bar Name": "Progress Bar",
                    "Progress Bar Transform Full-Sized": {},
                    "Debug": False,
                }
        await save_settings(settings)
    elif file == TOKENS_FILE:
        tokens = {
                    "bot": {
                        "access_token": None,
                        "refresh_token": None,
                        "last_refreshed": 0
                    },
                    "broadcaster": {
                        "access_token": None,
                        "refresh_token": None,
                        "last_refreshed": 0
                    }
                }
        await async_save_json(TOKENS_FILE, tokens)
    elif file == PROMPTS_FILE:
        prompts = {
                    "Respond to Messages": None,
                    "Summarize Messages": None,
                    "Respond to Streamer": None,
                    "Bit Donation w/o Message": None,
                    "Bit Donation w/ Message": None,
                    "Gifted Sub": None, 
                    "Raid": None,
                    "Resub Intern": None,
                    "Resub Employee": None,
                    "Resub Supervisor": None,
                    "Resub Tenured Employee": None
                }
        await save_prompts(prompts)
    elif file == SCHEDULED_MESSAGES_FILE:
        scheduled_messages = {
            "Messages": {}
        }
        await save_scheduled_messages(scheduled_messages)