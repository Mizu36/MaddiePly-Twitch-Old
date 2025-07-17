import requests
import json
import time
import os
from bot_utils import DEBUG

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
TOKENS_FILE = os.path.join(DATA_DIR, "tokens.json")

def load_tokens():
    with open(TOKENS_FILE, "r") as f:
        return json.load(f)

def save_tokens(tokens):
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=4)

def get_refresh_token(account: str):
    tokens = load_tokens()
    return tokens[account]["refresh_token"]

def refresh_token(account: str, client_id, client_secret, force_refresh = False):
    tokens = load_tokens()
    if account not in tokens:
        raise ValueError(f"[ERROR]No token found for account '{account}'")
    
    last_refreshed = tokens[account].get("last_refreshed", 0)
    if not force_refresh and (time.time() - last_refreshed) < 3600:
        token = "oauth:" + tokens[account]["access_token"]
        return token
    
    refresh_token = tokens[account]["refresh_token"]

    response = requests.post("https://id.twitch.tv/oauth2/token", data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret
    })

    if response.status_code == 200:
        new_tokens = response.json()
        tokens[account]["access_token"] = new_tokens["access_token"]
        if "refresh_token" in new_tokens:
            tokens[account]["refresh_token"] = new_tokens["refresh_token"]
        tokens[account]["last_refreshed"] = int(time.time())
        save_tokens(tokens)
        token = "oauth:" + tokens[account]["access_token"]
        print("Refreshed access token")
        return token
    else:
        raise Exception(f"[ERROR]Failed to refresh token: {response.status_code} - {response.text}")
