import pygame
import pygame._sdl2.audio as sdl2_audio
import time
import os
import asyncio
import soundfile as sf
from mutagen.mp3 import MP3
from pydub import AudioSegment
from bot_utils import DEBUG
from json_manager import load_settings

AUDIO_DEVICES = []

class AudioManager:
    def __init__(self):
        self.output_device = None
        self.cached_output_device = None
        self._should_stop = False
        self._is_playing = False
        self.device_object = None
        self.init_mixer()

    def init_mixer(self):
        # Initialize mixer with or without a specific device
        if pygame.mixer.get_init():
            pygame.mixer.quit()
        if self.output_device is not None:
            pygame.mixer.init(devicename=self.output_device, frequency=48000, buffer=1024)
        else:
            pygame.mixer.init(frequency=48000, buffer=1024)

    @staticmethod
    def list_output_devices():
        devices = sdl2_audio.get_audio_device_names(iscapture=False)
        #print("[DEBUG][AudioManager] Available output devices:")
        for idx, name in enumerate(devices):
            AUDIO_DEVICES.append(name)
            #print(f"[DEBUG]  {idx}: {name}")
        return devices

    def set_output_device(self, device_name_or_index):
        self.cached_output_device = device_name_or_index
        devices = self.list_output_devices()
        if isinstance(device_name_or_index, int):
            if 0 <= device_name_or_index < len(devices):
                self.output_device = devices[device_name_or_index]
            else:
                print(f"[ERROR][AudioManager] Invalid device index: {device_name_or_index}")
                return
        elif isinstance(device_name_or_index, str):
            if device_name_or_index in devices:
                self.output_device = device_name_or_index
            else:
                print(f"[ERROR][AudioManager] Device '{device_name_or_index}' not found.")
                return
        else:
            print("[ERROR][AudioManager] Invalid device identifier.")
            return
        self.init_mixer()

    def stop_playback(self):
        self._should_stop = True
        self._is_playing = False
        try:
            pygame.mixer.music.stop()
            pygame.mixer.stop()
        except Exception as e:
            print(f"[ERROR]{e} - Could not stop playback.")

    def is_playing(self):
        return self._is_playing

    def play_audio(self, file_path, sleep_during_playback=True, delete_file=False, play_using_music=True, output_device = None):
        try:
            if output_device and output_device != self.cached_output_device:
                self.set_output_device(output_device)
            self._is_playing = True
            if not pygame.mixer.get_init():
                self.init_mixer()
            if play_using_music:
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.play()
            else:
                pygame_sound = pygame.mixer.Sound(file_path)
                pygame_sound.play()

            if sleep_during_playback:
                _, ext = os.path.splitext(file_path)
                if ext.lower() == '.wav':
                    wav_file = sf.SoundFile(file_path)
                    file_length = wav_file.frames / wav_file.samplerate
                    wav_file.close()
                elif ext.lower() == '.mp3':
                    mp3_file = MP3(file_path)
                    file_length = mp3_file.info.length
                else:
                    print("[WARNING]Cannot play audio, unknown file type")
                    return

                elapsed = 0
                interval = 0.1
                while elapsed < file_length:
                    if self._should_stop:
                        print("[WARNING][AudioManager] Playback interrupted!")
                        self._should_stop = False
                        break
                    time.sleep(interval)
                    elapsed += interval
            self._is_playing = False
            if delete_file:
                try:
                    pygame.mixer.music.stop()
                except:
                    pass
                try:
                    os.remove(file_path)
                    if DEBUG:
                        print(f"[DEBUG][AudioManager] Deleted file: {file_path}")
                except Exception as e:
                    print(f"[WARNING][AudioManager] Could not delete {file_path}: {e}")
        except Exception as e:
            print(f"[ERROR][AudioManager] Error playing audio: {e}")

    async def play_audio_async(self, file_path):
        if not pygame.mixer.get_init():
            self.init_mixer()
        pygame_sound = pygame.mixer.Sound(file_path)
        pygame_sound.play()
        _, ext = os.path.splitext(file_path)
        if ext.lower() == '.wav':
            wav_file = sf.SoundFile(file_path)
            file_length = wav_file.frames / wav_file.samplerate
            wav_file.close()
        elif ext.lower() == '.mp3':
            mp3_file = MP3(file_path)
            file_length = mp3_file.info.length
        else:
            print("[WARNING]Cannot play audio, unknown file type")
            return
        await asyncio.sleep(file_length)

    async def process_audio(self, audio_file):
        audio = AudioSegment.from_mp3(audio_file)
        frame_ms = 50
        frames = [audio[i:i+frame_ms] for i in range(0, len(audio), frame_ms)]
        volumes = [frame.rms for frame in frames]
        return volumes, len(audio)

    async def map_volume_to_y(self, vol, min_vol, max_vol, base_y = 800, max_bounce = 25):
        if max_vol - min_vol == 0:
            return base_y
        normalized = (vol - min_vol) / (max_vol - min_vol)
        bounce = normalized * max_bounce
        return base_y - bounce

# Example usage:
if __name__ == '__main__':
    audio_manager = AudioManager()
    devices = audio_manager.list_output_devices()
    if devices:
        # Set to the first available device for demo
        audio_manager.set_output_device(0)
    MP3_FILEPATH = "TestAudio_MP3.mp3"
    WAV_FILEPATH = "TestAudio_WAV.wav"
    if os.path.exists(MP3_FILEPATH):
        audio_manager.play_audio(MP3_FILEPATH)
    if os.path.exists(WAV_FILEPATH):
        audio_manager.play_audio(WAV_FILEPATH)