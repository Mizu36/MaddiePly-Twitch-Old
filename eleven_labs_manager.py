from elevenlabs import stream, play, save, VoiceSettings
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv
from bot_utils import DEBUG
from json_manager import load_settings
import time
import os

load_dotenv()

try:
  client = ElevenLabs(api_key = (os.getenv('ELEVENLABS_API_KEY')))
except TypeError:
  exit("Ooops! You forgot to set ELEVENLABS_API_KEY in your environment!")

DEFAULT_VOICE = "9BWtsMINqrJLrRacOk9x" #Aria
DEFAULT_STABILITY = 0.5 #Ranges 0 to 1
DEFAULT_SPEED = 1 #Ranges 0.7 to 1.2
DEFAULT_SIMILARITY = 0.75 #Ranges 0 to 1

MODELS = ["eleven_v3", "eleven_multilingual_v2", "eleven_flash_v2_5", "eleven_flash_v2", "eleven_turbo_v2_5", "eleven_turbo_v2"]

class ElevenLabsManager:

    def __init__(self):
        # CALLING voices() IS NECESSARY TO INSTANTIATE 11LABS FOR SOME FUCKING REASON
        all_voices = client.voices.get_all()
        #print(f"\nAll ElevenLabs voices: \n{all_voices}\n")

    # Convert text to speech, then save it to file. Returns the file path
    def text_to_audio(self, input_text, voice=DEFAULT_VOICE, save_as_wave=True, subdirectory="audio", model="eleven_multilingual_v2"):
        audio_saved = client.text_to_speech.convert(
          text=input_text,
          voice_id=voice,
          model_id=model,
          voice_settings=VoiceSettings(
              stability=DEFAULT_STABILITY,
              similarity_boost=DEFAULT_SIMILARITY,
              speed=DEFAULT_SPEED
           )
        )
        if save_as_wave:
          file_name = f"___Msg{str(hash(input_text))}.wav"
        else:
          file_name = f"___Msg{str(hash(input_text))}.mp3"
        tts_file = os.path.join(os.path.abspath(os.curdir), subdirectory, file_name)
        save(audio_saved, tts_file)
        return tts_file

    # Convert text to speech, then play it out loud
    def text_to_audio_played(self, input_text, voice=DEFAULT_VOICE, model="eleven_multilingual_v2"):
        audio = client.generate(
          text=input_text,
          voice=voice,
          model=model
        )
        play(audio)

    # Convert text to speech, then stream it out loud (don't need to wait for full speech to finish)
    def text_to_audio_streamed(self, input_text, voice=DEFAULT_VOICE, model="eleven_multilingual_v2"):
        audio_stream = client.generate(
          text=input_text,
          voice=voice,
          model=model,
          stream=True
        )
        stream(audio_stream)


if __name__ == '__main__':
    elevenlabs_manager = ElevenLabsManager()

    elevenlabs_manager.text_to_audio_streamed("This is my streamed test audio, I'm so much cooler than played", "Doug Melina")
    time.sleep(2)
    elevenlabs_manager.text_to_audio_played("This is my played test audio, helo hello", "Doug Melina")
    time.sleep(2)
    file_path = elevenlabs_manager.text_to_audio("This is my saved test audio, please make me beautiful", "Doug Melina")
    print("Finished with all tests")

    time.sleep(30)
