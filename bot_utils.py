shared_bot = None
DEBUG = None
CURRENTLY_RESPONDING = False

def set_bot_instance(bot_instance):
    global shared_bot
    shared_bot = bot_instance

def get_bot_instance():
    return shared_bot

def get_debug():
    return DEBUG
    
def set_debug(param):
    global DEBUG
    DEBUG = param

def set_currently_responding(is_responding):
    global CURRENTLY_RESPONDING
    CURRENTLY_RESPONDING = is_responding

def get_currently_responding(is_responding):
    global CURRENTLY_RESPONDING
    return CURRENTLY_RESPONDING