import os
import keyboard
import asyncio
import re
import time
from dotenv import load_dotenv
from twitchio.ext import commands
from twitchio.ext.commands import cooldown, Bucket
from openai import OpenAI
from openai_chat import OpenAiManager
from audio_player import AudioManager
from azure_speech_to_text import SpeechToTextManager
from eleven_labs_manager import ElevenLabsManager
from bot_utils import set_bot_instance, get_bot_instance
from eventsub_server import main as start_event_sub
from token_manager import refresh_token
from json_manager import load_prompts, load_messages, save_messages, load_settings

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
ELEVENLABS_VOICE = None
MESSAGE_RESPOND_PROMPT = {}
SUMMARIZE_PROMPT = {}
HELPER_PROMPT = {}
GIFT_CACHE = {}

openai_manager = OpenAiManager()
openai_client = OpenAI(api_key = OPENAI_API_KEY)
audio_manager = AudioManager()
tts_manager = SpeechToTextManager()
elevenlabs_manager = ElevenLabsManager()

global_bot_instance = None


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
    settings = await load_settings()
    TEN_MESSAGES_KEY = settings["Hotkeys"]["10_MESSAGES_RESPOND_KEY"]
    LISTEN_AND_RESPOND_KEY = settings["Hotkeys"]["LISTEN_AND_RESPOND_KEY"]
    VOICED_SUMMARY_KEY = settings["Hotkeys"]["VOICE_SUMMARIZE_KEY"]
    ELEVENLABS_VOICE = settings["Elevenlabs Voice ID"]
    BOT_NICK = settings["Bot Nickname"]
    TWITCH_CHANNEL = settings["Broadcaster Channel"]
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
    MESSAGE_RESPOND_PROMPT = {"role": "system", "content": (prompts["Respond to Messages"])}
    SUMMARIZE_PROMPT = {"role": "system", "content": (prompts["Summarize Messages"])}
    HELPER_PROMPT = {"role": "system", "content": (prompts["Respond to Streamer"])}

async def listen_for_keys():
    while True:
        await asyncio.sleep(0.1)  # Small delay to prevent busy-waiting
        # Check for key presses without blocking
        if keyboard.is_pressed(TEN_MESSAGES_KEY):
            print(f"{TEN_MESSAGES_KEY} pressed")
            await respond_to_messages()
        elif keyboard.is_pressed(LISTEN_AND_RESPOND_KEY):
            await ask_maddieply()
        elif keyboard.is_pressed(VOICED_SUMMARY_KEY):
            await summarize_chat()

async def respond_to_messages():
    print("respond to messages called")

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

    messages = await load_messages()
    messages_str = "\n".join(messages)
    full_prompt = [SUMMARIZE_PROMPT,
                   {"role": "user", "content": messages_str}]
    response = openai_manager.chat(full_prompt)
    elevenlabs_output = elevenlabs_manager.text_to_audio(response, ELEVENLABS_VOICE, False)
    audio_manager.play_audio(elevenlabs_output, True, True, True)
    return

async def cleanup_gift_cache():
    while True:
        now = time.time()
        to_delete = [k for k, v in GIFT_CACHE.items() if now - v["time"] > 30]
        for k in to_delete:
            del GIFT_CACHE[k]
        await asyncio.sleep(10)



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

    async def handle_raid(self, event):
        user_name = event.from_broadcaster_user_name
        viewer_count = event.viewers
        print(f"RAID by {user_name} with {viewer_count} viewers!")
        channel = self.get_channel(TWITCH_CHANNEL)
        await channel.send(f"RAID ALERT: {user_name} has raided with {viewer_count} viewers!")
    
    async def handle_channel_points(self, event): #Placeholder for channel points
        user_name = event.user_name
        reward_title = event.reward.type
        reward_cost = event.reward.cost
        message = event.user_input
        redeemed_time = event.redeemed_at
        print(f"{user_name} used {reward_cost} channel points to redeem {reward_title} at {redeemed_time} with message: {message}")
        channel = self.get_channel(TWITCH_CHANNEL)
        await channel.send(f"{user_name} redeemed {reward_title}!")

    async def handle_custom_channel_points(self, event): #Placeholder for custom channel points
        user_name = event.user_name
        reward_title = event.reward.title
        reward_cost = event.reward.cost
        prompt = event.reward.prompt
        redeemed_time = event.redeemed_at
        print(f"{user_name} used {reward_cost} channel points to redeem {reward_title} at {redeemed_time} with message: {prompt}")
        channel = self.get_channel(TWITCH_CHANNEL)
        await channel.send(f"{user_name} redeemed {reward_title}!")

    async def handle_gift_subscription(self, gifter_name, recipient_list = None, gift_count = None, tier = None, gift_cumulative = None):
        #Gifter_name, recipient_list, and tier are grabbed from twitch chat
        #Gift_count and gift_cumulative are grabbed from eventsub
        global GIFT_CACHE
        print("Triggered gift subscription")
        if gifter_name:
            key = gifter_name.lower()

        if key not in GIFT_CACHE:
            GIFT_CACHE[key] = {"recipients": [], "count": 0, "time": time.time(), "tier": tier, "cumulative": gift_cumulative}
        
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

            settings, prompts = await asyncio.gather(load_settings(), load_prompts())
            elevenlabs_voice = settings["Elevenlabs Voice ID"]
            prompt_1 = {"role": "system", "content": f"{prompts["Gifted Sub"]}"} 

            if gift_cumulative:
                prompt_2 = {"role": "user", "content": f"{gifter_name} gifted {count} tier {tier} subs to the following users: {recipients_str}! They have gifted a total of {gift_cumulative} subs."}
            else:
                prompt_2 = {"role": "user", "content": f"{gifter_name} gifted {count} subs to: {recipients_str}."}
            
            full_prompt = [prompt_1, prompt_2]
            response = openai_manager.chat(full_prompt)
            elevenlabs_output = elevenlabs_manager.text_to_audio(response, elevenlabs_voice, False)
            audio_manager.play_audio(elevenlabs_output, True, True, True)
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
        print(f"{user_name} subscribed! Tier {tier}")
        channel = self.get_channel(TWITCH_CHANNEL)
        await channel.send(f"Thanks for subscribing, {user_name}! Enjoy your Tier {tier} subscription!")

    async def handle_subscription_message(self, event): #Placeholder for subscription message
        user_name = event.user_name
        tier = event.tier
        duration_months = event.duration_months
        if tier == "1000":
            tier = 1
        elif tier == "2000":
            tier = 2
        elif tier == "3000":
            tier = 3
        message = event.message.text
        streak = event.streak_months
        cumulative_months = event.cumulative_months
        if streak == 1 or streak == None:
            print(f"{user_name} subscribed! Tier {tier} with message: {message}")
        elif streak > 1:
            print(f"{user_name} resubscribed for {streak} months in a row for a total of {cumulative_months} months! Tier {tier} with message: {message}")

    async def handle_bits(self, event):
        settings, prompts = await asyncio.gather(load_settings(), load_prompts())
        bits = event.bits
        broadcaster_name = event.broadcaster_user_name
        if event.is_anonymous:
            username = "An anonymous user"
        else:
            username = event.user_name
        message = None
        elevenlabs_voice = settings["Elevenlabs Voice ID"]
        print(f"{username} donated {bits} bits!")
        channel = self.get_channel(TWITCH_CHANNEL)
        if not event.is_anonymous:
            await channel.send(f"Thank you {username} for donating {bits} bits!")
        else:
            await channel.send(f"An anonymous user donated {bits} bits!")
        if bits >= 100:
            if bits >= 100 and bits < 1000:
                reaction = "Normal"
            elif bits >= 1000 and bits < 5000:
                reaction = "Impressed"
            elif bits >= 5000 and bits < 10000:
                reaction = "Exaggerated"
            elif bits > 10000:
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
            if message:
                full_response = f"'{message}.' {response}"
                try:
                    elevenlabs_output = elevenlabs_manager.text_to_audio(full_response, elevenlabs_voice, False)
                    audio_manager.play_audio(elevenlabs_output, True, True, True)
                except Exception as e:
                    print(f"Error playing audio: {e}")
                    print(full_response)
                return
            try:
                elevenlabs_output = elevenlabs_manager.text_to_audio(response, elevenlabs_voice, False)
                audio_manager.play_audio(elevenlabs_output, True, True, True)
            except Exception as e:
                print(f"Error playing audio: {e}")
                print(response)
            return
        else:
            return

    async def event_message(self, message):
        if message.echo:
            return
        
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
    await set_prompts()
    openai_manager.chat_history.append(HELPER_PROMPT)
    await bot.start()

if __name__ == "__main__":
    async def startup():
        await set_global_variables()
        asyncio.create_task(cleanup_gift_cache())
    asyncio.run(startup())
    asyncio.run(main())
