import asyncio
from twitchAPI.twitch import Twitch
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.object.eventsub import ChannelRaidEvent, ChannelCheerEvent, ChannelSubscribeEvent, ChannelPointsCustomRewardRedemptionAddEvent
from twitchAPI.type import AuthScope
from dotenv import load_dotenv
import os
from token_manager import refresh_token, get_refresh_token

load_dotenv()

# Twitch app credentials and setup
CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_APP_SECRET")
TWITCH_BROADCASTER_TOKEN = refresh_token("broadcaster", CLIENT_ID, CLIENT_SECRET)
TWITCH_BROADCASTER_REFRESH_TOKEN = get_refresh_token("broadcaster")
CHANNEL_NAME = os.getenv("TWITCH_CHANNEL")
CHANNEL_ID = os.getenv("BROADCASTER_USER_ID")

twitch = Twitch(CLIENT_ID, CLIENT_SECRET)
bot_instance = None
event_queue = asyncio.Queue()

def set_bot_instance(bot):
    global bot_instance
    bot_instance = bot

"""async def get_user_id():
    async for user in twitch.get_users(logins=[CHANNEL_NAME]):
        return user.id
    return None"""

async def on_subscribe(event: ChannelSubscribeEvent) -> None:
    subscription = event.event
    username = subscription.user_name
    tier = subscription.tier
    print(f"Subscription detected: {username} subscribed at Tier {tier}")
    #if bot_instance:
    #    await bot_instance.handle_subscription(username, tier)

async def on_raid(event: ChannelRaidEvent) -> None:
    raid = event.event
    username = raid.from_broadcaster_user_name
    viewer_count = raid.viewers
    print(f"RAID by {username} with {viewer_count} viewers!")
    #if bot_instance:
    #    await bot_instance.handle_raid(username, viewer_count)

async def on_points(event: ChannelPointsCustomRewardRedemptionAddEvent) -> None:
    redemption = event.event
    username = redemption.user_name
    reward_title = redemption.reward.type
    print(f"Channel Points: {username} redeemed {reward_title}")
    #if bot_instance:
    #    await bot_instance.handle_channel_points(reward_title, username)

async def on_points_custom(event: ChannelPointsCustomRewardRedemptionAddEvent) -> None:
    redemption = event.event
    username = redemption.user_name
    reward_title = redemption.reward.title
    print(f"Channel Points: {username} redeemed {reward_title}")
    #if bot_instance:
    #    await bot_instance.handle_channel_points(reward_title, username)

async def on_bits(event: ChannelCheerEvent) -> None:
    cheer = event.event
    username = cheer.user_name
    bits = cheer.bits
    print(f"Bits Donation detected: {username} donated {bits} bits.")
    #if bot_instance:
    #    await bot_instance.handle_bits(username, bits)

async def main():

    await twitch.authenticate_app([])
    #twitch_user_id = await get_user_id()
    #print(twitch_user_id)
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

    await eventsub.listen_channel_subscribe(CHANNEL_ID, on_subscribe)
    await eventsub.listen_channel_raid(on_raid, CHANNEL_ID)
    await eventsub.listen_channel_points_automatic_reward_redemption_add(CHANNEL_ID, on_points)
    await eventsub.listen_channel_points_custom_reward_redemption_add(CHANNEL_ID, on_points_custom)
    await eventsub.listen_channel_cheer(CHANNEL_ID, on_bits)

    print("Listening for Twitch EventSub WebSocket events...")
    await asyncio.Future()  # keep alive

if __name__ == "__main__":
    asyncio.run(main())