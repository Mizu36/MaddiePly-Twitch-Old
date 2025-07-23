import os
from openai import OpenAI
import tiktoken
import asyncio
from dotenv import load_dotenv
from bot_utils import DEBUG

load_dotenv()

DEFAULT_MODEL = 'gpt-4o'
CONVERATIONAL_MODEL = "ft:gpt-4o-2024-08-06:mizugaming:maddie:BllhDqyb"
API_KEY = os.getenv("OPENAI_API_KEY")
BOT_DETECTION_PROMPT = {"role": "system", "content": "You are a twitch moderator who's sole job is to review a chatter's message if it is their first time chatting. You are checking if they are a bot, scammer, or spammer. You will provide a single word response, Yes, No, or Maybe. Saying Yes means you think they are a bot, scammer, or spammer. No means they are not. And Maybe means you will need more context to determine, in which case I will append more of their messages as they come in until you change your answer. Always respond with a single word, Yes, No, Maybe, so that my program can automatically take action depending on your answer."}


def num_of_tokens(messages, model = DEFAULT_MODEL):
  """Returns the number of tokens used by a list of messages.
  Copied with minor changes from: https://platform.openai.com/docs/guides/chat/managing-tokens """
  try:
      encoding = tiktoken.get_encoding("o200k_base")
      num_tokens = 0
      for message in messages:
          num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
          for key, value in message.items():
              num_tokens += len(encoding.encode(value))
              if key == "name":  # if there's a name, the role is omitted
                  num_tokens += -1  # role is always required and always 1 token
      num_tokens += 2  # every reply is primed with <im_start>assistant
      return num_tokens
  except Exception:
      raise NotImplementedError(f"""[ERROR]num_tokens_from_messages() is not presently implemented for model {model}.
      #See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens.""")
  

class OpenAiManager:
    
    def __init__(self):
        self.chat_history = [] # Stores the entire conversation
        try:
            self.client = OpenAI(api_key = API_KEY)
        except TypeError:
            exit("[ERROR]Ooops! You forgot to set OPENAI_API_KEY in your environment!")

    # Asks a question with no chat history
    def chat(self, messages, conversational: bool):
        if not messages or not isinstance(messages, list):
            print("[ERROR]Didn't receive input!")
            return

        # Check that the prompt is under the token context limit
        if num_of_tokens(messages) > 4000:
            print("[WARNING]The length of this chat question is too large for the GPT model")
            return

        print("[orange]Asking ChatGPT a question...")



        # Process the answer
        completion = self.client.chat.completions.create(
                        model=CONVERATIONAL_MODEL if conversational else DEFAULT_MODEL,
                        messages=messages
                        )
        
        openai_answer = completion.choices[0].message.content
        print(f"[green]{openai_answer}")
        return openai_answer
    

    # Asks a question that includes the full conversation history
    def chat_with_history(self, prompt="", conversational: bool = False):
        if not prompt:
            print("[ERROR]Didn't receive input!")
            return

        # Add our prompt into the chat history
        self.chat_history.append({"role": "user", "content": prompt})

        # Check total token limit. Remove old messages as needed
        if DEBUG:
            print(f"[DEBUG]Chat History has a current token length of {num_of_tokens(self.chat_history)}")
        while num_of_tokens(self.chat_history) > 2000:
            self.chat_history.pop(1) # We skip the 1st message since it's the system message
            print(f"[orange]Popped a message! New token length is: {num_of_tokens(self.chat_history)}")

        print("[orange]Asking ChatGPT a question...")

        # Add this answer to our chat history
        completion = self.client.chat.completions.create(
                        model=CONVERATIONAL_MODEL if conversational else DEFAULT_MODEL,
                        messages=self.chat_history
                        )
        
        self.chat_history.append({"role": completion.choices[0].message.role, "content": completion.choices[0].message.content})

        # Process the answer
        openai_answer = completion.choices[0].message.content
        print(f"[green]{openai_answer}")
        return openai_answer
    
    def bot_detector(self, message):
        if not message:
            print("[ERROR]Called without input")
            return
        
        messages = [BOT_DETECTION_PROMPT, {"role": "user", "content": message}]

        completion = self.client.chat.completions.create(
            model = "ft:gpt-4o-mini-2024-07-18:mizugaming:bot-detector:Bv9zPaZq",
            messages=messages
        )
        openai_answer = completion.choices[0].message.content
        print(openai_answer)

        if openai_answer.lower().startswith("yes"):
            if DEBUG:
                print(f"[DEBUG]First time message is spam.")
            return True
        elif openai_answer.lower().startswith("no"):
            if DEBUG:
                print(f"[DEBUG]First time message is not spam.")
            return False
        elif openai_answer.lower().startswith("maybe"):
            if DEBUG:
                print(f"[DEBUG]Not sure if first message is spam.")
            return 3
        else:
            if DEBUG:
                print(f"[DEBUG]Invalid response from bot-detection AI: {openai_answer}")
            return 3