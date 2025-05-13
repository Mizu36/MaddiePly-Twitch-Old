import json
import os
import threading
import aiofiles
import aiofiles.os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
PROMPTS_FILE = os.path.join(DATA_DIR, "prompts.json")
RULES_FILE = os.path.join(DATA_DIR, "prompt_rules.json")
TOP_RESPONSES_FILE = os.path.join(DATA_DIR, "top_responses.json")
QUOTES_FILE = os.path.join(DATA_DIR, "quotes.json")
MESSAGES_FILE = os.path.join(DATA_DIR, "messages.json")
BANNED_WORDS_FILE = os.path.join(DATA_DIR, "banned_words.json")
FILEPATHS = [SETTINGS_FILE, RULES_FILE, TOP_RESPONSES_FILE, MESSAGES_FILE, BANNED_WORDS_FILE, QUOTES_FILE, PROMPTS_FILE]
LISTS = [PROMPTS_FILE]
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
            await f.write("{}")

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

async def load_prompt_rules():
    return await async_load_json(RULES_FILE)
        
async def save_prompt_rules(data): #Not used currently, external editing only
    await async_save_json(RULES_FILE, data)

async def load_top_responses():
    return await async_load_json(TOP_RESPONSES_FILE)
        
async def save_top_responses(data):
    await async_save_json(TOP_RESPONSES_FILE, data)

async def load_banned_words():
    return await async_load_json(BANNED_WORDS_FILE)
        
async def save_banned_words(data):
    await async_save_json(BANNED_WORDS_FILE, data)

async def load_prompts():
    return await async_load_json(PROMPTS_FILE)
        
async def load_quotes():
    return await async_load_json(QUOTES_FILE)
        
async def save_quotes(data):
    await async_save_json(QUOTES_FILE, data)

                