import os
import json
import keyboard
import asyncio
from dotenv import load_dotenv
from twitchio.ext import commands
from twitchio.ext.commands import cooldown, Bucket
from openai import OpenAI
from openai_chat import OpenAiManager
from audio_player import AudioManager
from azure_speech_to_text import SpeechToTextManager
from eleven_labs_manager import ElevenLabsManager
from eventsub_server import main as start_event_sub, set_bot_instance
from token_manager import refresh_token

load_dotenv()

CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_APP_SECRET")
BOT_TOKEN = refresh_token("bot", CLIENT_ID, CLIENT_SECRET)
BOT_NICK = os.getenv("BOT_NICK")
TWITCH_CHANNEL = os.getenv("TWITCH_CHANNEL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TEN_MESSAGES_KEY = os.getenv("10_MESSAGES_RESPOND_KEY")
LISTEN_AND_RESPOND_KEY = os.getenv("LISTEN_AND_RESPOND_KEY")
VOICED_SUMMARY_KEY = os.getenv("VOICE_SUMMARIZE_KEY")
ELEVENLABS_VOICE = os.getenv("ELEVENLABS_VOICE")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MESSAGES_FILE = os.path.join(BASE_DIR, "messages.json")
PROMPTS_FILE = os.path.join(BASE_DIR, "prompts.json")
MESSAGE_RESPOND_PROMPT = {}
SUMMARIZE_PROMPT = {}
HELPER_PROMPT = {}

openai_manager = OpenAiManager()
openai_client = OpenAI(api_key = OPENAI_API_KEY)
audio_manager = AudioManager()
tts_manager = SpeechToTextManager()
elevenlabs_manager = ElevenLabsManager()

global_bot_instance = None

def load_messages():
    try:
        with open(MESSAGES_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            else:
                return []
    except:
        return []

def save_message(author, content):
    messages = load_messages()
    formatted_message = f"{author}: {content}"
    messages.append(formatted_message)
    if len(messages) > 10:
        messages.pop(0)
    with open(MESSAGES_FILE, "w") as f:
        json.dump(messages, f, indent=4)

def load_prompts():
    try:
        with open(PROMPTS_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            else:
                return {}
    except:
        return {}
    
def set_prompts():
    prompts = load_prompts()
    global MESSAGE_RESPOND_PROMPT
    global SUMMARIZE_PROMPT
    global HELPER_PROMPT
    MESSAGE_RESPOND_PROMPT = {"role": "system", "content": (prompts["Respond to Messages"])}
    SUMMARIZE_PROMPT = {"role": "system", "content": (prompts["Summarize Messages"])}
    HELPER_PROMPT = {"role": "system", "content": (prompts["Respond to Streamer"])}

async def listen_for_keys():
    while True:
        await asyncio.sleep(0.1)  # Small delay to prevent busy-waiting
        # Check for key presses without blocking
        if keyboard.is_pressed(TEN_MESSAGES_KEY):
            print("page_down pressed")
            await respond_to_messages()
        elif keyboard.is_pressed(LISTEN_AND_RESPOND_KEY):
            await ask_maddieply()
        elif keyboard.is_pressed(VOICED_SUMMARY_KEY):
            await summarize_chat()


async def respond_to_messages():
    print("respond to messages called")

    messages = load_messages()
    messages_str = "\n".join(messages)
    prompt = [MESSAGE_RESPOND_PROMPT, 
              {"role": "user", "content": messages_str}]
    response = openai_manager.chat(prompt)
    channel = global_bot_instance.get_channel(TWITCH_CHANNEL)
    await channel.send(response)
    with open(MESSAGES_FILE, "w") as f:
        json.dump([], f, indent = 4)
    return

async def ask_maddieply():
    print("ask_maddie triggered")
    print ("[green]Now listening to your microphone:")

    mic_result = tts_manager.speechtotext_from_mic_continuous()

    if not mic_result or not mic_result.strip():
        print ("[red]Did not receive any input from your microphone!")
        return

    openai_result = openai_manager.chat_with_history(mic_result)

    elevenlabs_output = elevenlabs_manager.text_to_audio(openai_result, ELEVENLABS_VOICE, False)

    audio_manager.play_audio(elevenlabs_output, True, True, True)
    return

async def summarize_chat():
    print("summarize_chat triggered")

    messages = load_messages()
    messages_str = "\n".join(messages)
    full_prompt = [SUMMARIZE_PROMPT,
                   {"role": "user", "content": messages_str}]
    response = openai_manager.chat(full_prompt)
    elevenlabs_output = elevenlabs_manager.text_to_audio(response, ELEVENLABS_VOICE, False)
    audio_manager.play_audio(elevenlabs_output, True, True, True)
    return


#TO DO
#Respond to raids
#Channel point reward read out message
#Respond to subscribers
#See if can setup special keybinds instead of regular keys, maybe key combos



class Bot(commands.Bot):
    def __init__(self):
        super().__init__(token=BOT_TOKEN, prefix="!", nick=BOT_NICK, initial_channels=[TWITCH_CHANNEL])

        global global_bot_instance
        global_bot_instance = self

    async def event_ready(self):
        print(f"Bot {self.nick} is online!")
        channel = self.get_channel(TWITCH_CHANNEL)
        #await channel.send("Bot online!")

    async def handle_raid(self, username, viewer_count):
        print(f"RAID by {username} with {viewer_count} viewers!")
        channel = self.get_channel(TWITCH_CHANNEL)
        await channel.send(f"RAID ALERT: {username} has raided with {viewer_count} viewers!")
    
    async def handle_channel_points(self, reward_title, user_name):
        print(f"{user_name} redeemed {reward_title}")
        channel = self.get_channel(TWITCH_CHANNEL)
        await channel.send(f"{user_name} redeemed {reward_title}!")

    async def handle_subscription(self, user_name, tier):
        print(f"{user_name} subscribed! Tier {tier}")
        channel = self.get_channel(TWITCH_CHANNEL)
        await channel.send(f"Thanks for subscribing, {user_name}! Enjoy your Tier {tier} subscription!")

    async def handle_bits(self, user_name, bits):
        print(f"{user_name} donated {bits} bits!")
        channel = self.get_channel(TWITCH_CHANNEL)
        await channel.send(f"Thank you {user_name} for donating {bits} bits!")

    async def event_message(self, message):
        if message.echo:
            return
        print(f"{message.author.name}: {message.content}")
        save_message(message.author.name, message.content)
        await self.handle_commands(message)

    @commands.command(name="test")
    @cooldown(1, 30, Bucket.user)
    async def test(self, ctx):
        print("triggered repeat")
        try:
            await ctx.send("This is a test message.")
        except Exception as e:
            # Handle the cooldown error
            print(f"{ctx.author.name} tried to use the !test command too soon.")

async def main():
    bot = Bot()
    set_bot_instance(bot)
    asyncio.create_task(listen_for_keys())
    asyncio.create_task(start_event_sub())
    set_prompts()
    openai_manager.chat_history.append(HELPER_PROMPT)
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())
