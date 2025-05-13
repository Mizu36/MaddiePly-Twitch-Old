import asyncio
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.object.eventsub import ChannelRaidEvent, ChannelCheerEvent, ChannelSubscribeEvent, ChannelPointsCustomRewardRedemptionAddEvent, ChannelPointsAutomaticRewardRedemptionAddEvent, ChannelSubscriptionGiftEvent, ChannelSubscriptionMessageEvent
from twitchAPI.type import AuthScope
from dotenv import load_dotenv
import os
from token_manager import refresh_token, get_refresh_token
from json_manager import load_prompts, save_quotes, load_settings
from bot_utils import get_bot_instance
from openai_chat import OpenAiManager
from eleven_labs_manager import ElevenLabsManager
from audio_player import AudioManager

load_dotenv()

# Twitch app credentials and setup
CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_APP_SECRET")
TWITCH_BROADCASTER_TOKEN = None
TWITCH_BROADCASTER_REFRESH_TOKEN = None

#Move non secrets out of .env and change the code

twitch = Twitch(CLIENT_ID, CLIENT_SECRET)
bot_instance = None
event_queue = asyncio.Queue()
openai_manager = OpenAiManager()
elevenlabs_manager = ElevenLabsManager()
audio_manager = AudioManager()

async def on_subscribe(event: ChannelSubscribeEvent) -> None:
    sub = event.event
    await get_bot_instance().handle_subscription(sub)

async def on_raid(event: ChannelRaidEvent) -> None:
    raid = event.event
    await get_bot_instance().handle_raid(raid)

async def on_points(event: ChannelPointsAutomaticRewardRedemptionAddEvent) -> None:
    redemption = event.event
    await get_bot_instance().handle_channel_points(redemption)

async def on_points_custom(event: ChannelPointsCustomRewardRedemptionAddEvent) -> None:
    redemption = event.event
    await get_bot_instance().handle_custom_channel_points(redemption)

async def on_bits(event: ChannelCheerEvent) -> None:
    cheer = event.event
    await get_bot_instance().handle_bits(cheer)

async def on_gift_sub(event: ChannelSubscriptionGiftEvent) -> None:
    print("GIFT SUB")
    gift = event.event
    count = gift.total
    cumulative = gift.cumulative_total
    if gift.is_anonymous:
        gifter_name = "Anonymous"
    else:
        gifter_name = gift.user_name
    await get_bot_instance().handle_gift_subscription(gifter_name = gifter_name, gift_count = count, gift_cumulative = cumulative)

async def on_sub_message(event: ChannelSubscriptionMessageEvent) -> None:
    sub_message = event.event
    await get_bot_instance().handle_subscription_message(sub_message)


class FakeEvent():
    def __init__(self, event_data):
        self.event = type("Event", (), event_data["event"])()

async def test():

    event_bits_data = {
    "subscription": {
        "id": "f1c2a387-161a-49f9-a165-0f21d7a4e1c4",
        "type": "channel.cheer",
        "version": "1",
        "status": "enabled",
        "cost": 0,
        "condition": {
            "broadcaster_user_id": "1337"
        },
         "transport": {
            "method": "webhook",
            "callback": "https://example.com/webhooks/callback"
        },
        "created_at": "2019-11-16T10:11:12.634234626Z"
    },
    "event": {
        "is_anonymous": False,
        "user_id": "1234",       # None if is_anonymous=true
        "user_login": "mizu36",  # None if is_anonymous=true
        "user_name": "Mizu36",   # None if is_anonymous=true
        "broadcaster_user_id": "1337",
        "broadcaster_user_login": "moddiply",
        "broadcaster_user_name": "ModdiPly",
        "message": "Here is a few dollars to buy some more cookies.",
        "bits": 1000
    }
}
    event_bits_anonymous_data = {
    "subscription": {
        "id": "f1c2a387-161a-49f9-a165-0f21d7a4e1c4",
        "type": "channel.cheer",
        "version": "1",
        "status": "enabled",
        "cost": 0,
        "condition": {
            "broadcaster_user_id": "1337"
        },
         "transport": {
            "method": "webhook",
            "callback": "https://example.com/webhooks/callback"
        },
        "created_at": "2019-11-16T10:11:12.634234626Z"
    },
    "event": {
        "is_anonymous": False,
        "user_id": None,       # None if is_anonymous=true
        "user_login": None,  # None if is_anonymous=true
        "user_name": None,   # None if is_anonymous=true
        "broadcaster_user_id": "1337",
        "broadcaster_user_login": "moddiply",
        "broadcaster_user_name": "ModdiPly",
        "message": "Here is a few dollars to buy some more cookies.",
        "bits": 1000
    }
}
    event_bits_no_message_data = {
    "subscription": {
        "id": "f1c2a387-161a-49f9-a165-0f21d7a4e1c4",
        "type": "channel.cheer",
        "version": "1",
        "status": "enabled",
        "cost": 0,
        "condition": {
            "broadcaster_user_id": "1337"
        },
         "transport": {
            "method": "webhook",
            "callback": "https://example.com/webhooks/callback"
        },
        "created_at": "2019-11-16T10:11:12.634234626Z"
    },
    "event": {
        "is_anonymous": True,
        "user_id": None,       # None if is_anonymous=true
        "user_login": None,  # None if is_anonymous=true
        "user_name": "Mizu36",   # None if is_anonymous=true
        "broadcaster_user_id": "1337",
        "broadcaster_user_login": "moddiply",
        "broadcaster_user_name": "ModdiPly",
        "message": "",
        "bits": 1000
    }
}
    event_raid_data = {
    "subscription": {
        "id": "f1c2a387-161a-49f9-a165-0f21d7a4e1c4",
        "type": "channel.raid",
        "version": "1",
        "status": "enabled",
        "cost": 0,
        "condition": {
            "to_broadcaster_user_id": "1337"
        },
         "transport": {
            "method": "webhook",
            "callback": "https://example.com/webhooks/callback"
        },
        "created_at": "2019-11-16T10:11:12.634234626Z"
    },
    "event": {
        "from_broadcaster_user_id": "1234",
        "from_broadcaster_user_login": "mizu36",
        "from_broadcaster_user_name": "Mizu36",
        "to_broadcaster_user_id": "1337",
        "to_broadcaster_user_login": "moddiply",
        "to_broadcaster_user_name": "ModdiPly",
        "viewers": 20
    }
}
    event_subscribe_message = {
    "subscription": {
        "id": "f1c2a387-161a-49f9-a165-0f21d7a4e1c4",
        "type": "channel.subscription.message",
        "version": "1",
        "status": "enabled",
        "cost": 0,
        "condition": {
           "broadcaster_user_id": "1337"
        },
         "transport": {
            "method": "webhook",
            "callback": "https://example.com/webhooks/callback"
        },
        "created_at": "2019-11-16T10:11:12.634234626Z"
    },
    "event": {
        "user_id": "1234",
        "user_login": "cool_user",
        "user_name": "Cool_User",
        "broadcaster_user_id": "1337",
        "broadcaster_user_login": "cooler_user",
        "broadcaster_user_name": "Cooler_User",
        "tier": "1000",
        "message": {
            "text": "Love the stream! FevziGG",
            "emotes": [
                {
                    "begin": 23,
                    "end": 30,
                    "id": "302976485"
                }
            ]
        },
        "cumulative_months": 15,
        "streak_months": 1, # None if not shared
        "duration_months": 6
    }
}
    event_gifted_sub = { #WORKING AS INTENDED
    "subscription": {
        "id": "f1c2a387-161a-49f9-a165-0f21d7a4e1c4",
        "type": "channel.subscription.gift",
        "version": "1",
        "status": "enabled",
        "cost": 0,
        "condition": {
           "broadcaster_user_id": "1337"
        },
         "transport": {
            "method": "webhook",
            "callback": "https://example.com/webhooks/callback"
        },
        "created_at": "2019-11-16T10:11:12.634234626Z"
    },
    "event": {
        "user_id": "1234",
        "user_login": "mizu36",
        "user_name": "Mizu36",
        "broadcaster_user_id": "1337",
        "broadcaster_user_login": "cooler_user",
        "broadcaster_user_name": "Cooler_User",
        "total": 2,
        "tier": "1000",
        "cumulative_total": None, #None if anonymous or not shared by the user
        "is_anonymous": True
    }
}
    event_subscribe = {
    "subscription": {
        "id": "f1c2a387-161a-49f9-a165-0f21d7a4e1c4",
        "type": "channel.subscribe",
        "version": "1",
        "status": "enabled",
        "cost": 0,
        "condition": {
           "broadcaster_user_id": "1337"
        },
         "transport": {
            "method": "webhook",
            "callback": "https://example.com/webhooks/callback"
        },
        "created_at": "2019-11-16T10:11:12.634234626Z"
    },
    "event": {
        "user_id": "1234",
        "user_login": "cool_user",
        "user_name": "Cool_User",
        "broadcaster_user_id": "1337",
        "broadcaster_user_login": "cooler_user",
        "broadcaster_user_name": "Cooler_User",
        "tier": "1000",
        "is_gift": False
    }
}
    
    #fake_event = FakeEvent(event_bits_data)
    #await on_bits(fake_event)
    
    #GIFTED_SUB WORKING AS INTENDED
    #fake_event = FakeEvent(event_gifted_sub)
    #await on_gift_sub(fake_event)


async def main():

    global TWITCH_BROADCASTER_TOKEN
    global TWITCH_BROADCASTER_REFRESH_TOKEN
    TWITCH_BROADCASTER_REFRESH_TOKEN = get_refresh_token("broadcaster")
    TWITCH_BROADCASTER_TOKEN = refresh_token("broadcaster", CLIENT_ID, CLIENT_SECRET)
    await twitch.authenticate_app([])
    await twitch.set_user_authentication(TWITCH_BROADCASTER_TOKEN, [
        AuthScope.CHANNEL_READ_SUBSCRIPTIONS,
        AuthScope.BITS_READ,
        AuthScope.CHAT_READ,
        AuthScope.CHAT_EDIT,
        AuthScope.CHANNEL_MODERATE,
        AuthScope.CHANNEL_READ_REDEMPTIONS,
        AuthScope.CHANNEL_EDIT_COMMERCIAL,
        AuthScope.CHANNEL_READ_HYPE_TRAIN,
        AuthScope.CHANNEL_MANAGE_BROADCAST,
        AuthScope.CHANNEL_MANAGE_REDEMPTIONS,
        AuthScope.CHANNEL_MANAGE_POLLS,
        AuthScope.CHANNEL_MANAGE_PREDICTIONS,
        AuthScope.CHANNEL_READ_POLLS,
        AuthScope.CHANNEL_READ_PREDICTIONS,
        AuthScope.CHANNEL_READ_GOALS,
        AuthScope.CHANNEL_MANAGE_RAIDS,
        AuthScope.CHANNEL_READ_VIPS,
        AuthScope.CHANNEL_MANAGE_VIPS,
        AuthScope.CHANNEL_READ_CHARITY,
        AuthScope.CHANNEL_MANAGE_ADS,
        AuthScope.CHANNEL_READ_ADS,
        AuthScope.MODERATOR_MANAGE_BANNED_USERS,
        AuthScope.MODERATOR_MANAGE_CHAT_SETTINGS,
        AuthScope.MODERATOR_MANAGE_CHAT_MESSAGES,
        AuthScope.MODERATOR_READ_CHATTERS,
        AuthScope.MODERATOR_READ_SHOUTOUTS,
        AuthScope.MODERATOR_MANAGE_SHOUTOUTS,
        AuthScope.MODERATOR_READ_UNBAN_REQUESTS,
        AuthScope.MODERATOR_MANAGE_UNBAN_REQUESTS,
        AuthScope.MODERATOR_READ_SUSPICIOUS_USERS
    ], TWITCH_BROADCASTER_REFRESH_TOKEN)

    eventsub = EventSubWebsocket(twitch)
    
    eventsub.start()
    # Subscribe to all the events

    settings = await load_settings()
    channel_id = settings["Broadcaster ID"] #For eventsub, not twitch chat

    await eventsub.listen_channel_subscribe(channel_id, on_subscribe)
    await eventsub.listen_channel_raid(on_raid, channel_id)
    await eventsub.listen_channel_points_automatic_reward_redemption_add(channel_id, on_points)
    await eventsub.listen_channel_points_custom_reward_redemption_add(channel_id, on_points_custom)
    await eventsub.listen_channel_cheer(channel_id, on_bits)
    await eventsub.listen_channel_subscription_gift(channel_id, on_gift_sub)
    await eventsub.listen_channel_subscription_message(channel_id, on_sub_message)

    print("Listening for Twitch EventSub WebSocket events...")
    await test()
    await asyncio.Future()  # keep alive

if __name__ == "__main__":
    asyncio.run(main())