shared_bot = None

def set_bot_instance(bot_instance):
    global shared_bot
    shared_bot = bot_instance

def get_bot_instance():
    return shared_bot
