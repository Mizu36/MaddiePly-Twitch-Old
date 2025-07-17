shared_bot = None
DEBUG = None

def set_bot_instance(bot_instance):
    global shared_bot
    shared_bot = bot_instance

def get_bot_instance():
    return shared_bot

def get_debug():
    return DEBUG
    
def set_debug(param):
    DEBUG = param