import time
import azure.cognitiveservices.speech as speechsdk
import keyboard
import asyncio
import os
from pathlib import Path
from json_manager import load_settings
from dotenv import load_dotenv
from bot_utils import DEBUG

load_dotenv()

END_LISTEN_KEY = None
AUDIO_FOLDER = os.path.join(os.path.dirname(__file__), "audio")

VOICES = ["en-US-AvaNeural", "en-US-EmmaNeural", "en-US-JennyNeural", "en-US-AriaNeural", "en-US-JaneNeural", "en-US-LunaNeural", "en-US-SaraNeural", "en-US-NancyNeural", "en-US-AmberNeural", "en-US-AnaNeural", "en-US-AshleyNeural", "en-US-CoraNeural", "en-US-ElizabethNeural", "en-US-MichelleNeural", "en-US-AvaMultilingualNeural", "en-US-MonicaNeural", "en-US-BlueNeural", "en-US-AmandaMultilingualNeural", "en-US-LolaMultilingualNeural", "en-US-NancyMultilingualNeural", "en-US-ShimmerTurboMultilingualNeural", "en-US-SerenaMultilingualNeural", "en-US-PhoebeMultilingualNeural", "en-US-NovaTurboMultilingualNeural", "en-US-EvelynMultilingualNeural", "en-US-JennyMultilingualNeural", "en-US-EmmaMultilingualNeural", "en-US-CoraMultilingualNeural", "en-US-Aria:DragonHDLatestNeural", "en-US-Ava:DragonHDLatestNeural", "en-US-Emma:DragonHDLatestNeural", "en-US-Emma2:DragonHDLatestNeural", "en-US-Jenny:DragonHDLatestNeural", ]

class SpeechToTextManager:
    azure_speechconfig = None
    azure_audioconfig = None
    azure_speechrecognizer = None
    
    async def set_settings():
        settings = await load_settings()
        global END_LISTEN_KEY
        END_LISTEN_KEY = settings["Hotkeys"]["END_LISTEN_KEY"]

    if not END_LISTEN_KEY:
        asyncio.run(set_settings())

    def __init__(self):
        # Creates an instance of a speech config with specified subscription key and service region.
        # Replace with your own subscription key and service region (e.g., "westus").
        try:
            self.azure_speechconfig = speechsdk.SpeechConfig(subscription=os.getenv('AZURE_TTS_KEY'), region=os.getenv('AZURE_TTS_REGION'))
        except TypeError:
            exit("[ERROR]Ooops! You forgot to set AZURE_TTS_KEY or AZURE_TTS_REGION in your environment!")
        
        self.azure_speechconfig.speech_recognition_language="en-US"
        self.azure_speechconfig.speech_synthesis_voice_name='en-US-AvaMultilingualNeural'
        self.audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)

    def text_to_speech(self, text, voice):
        # Create the audio directory if it doesn't exist
        self.azure_speechconfig.speech_synthesis_voice_name = voice
        audio_dir = Path(__file__).parent / "audio"
        audio_dir.mkdir(exist_ok=True)

        # Generate the filename
        filename = f"___Msg{str(hash(text))}.wav"
        audio_path = audio_dir / filename

        # Synthesize speech
        audio_config = speechsdk.audio.AudioOutputConfig(filename=str(audio_path))
        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.azure_speechconfig,
            audio_config=audio_config
        )
        result = speech_synthesizer.speak_text_async(text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            if DEBUG:
                print(f"[DEBUG]Speech synthesized and saved to {audio_path}")
            return str(audio_path)
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            print(f"[WARNING]Speech synthesis canceled: {cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                if cancellation_details.error_details:
                    print(f"[WARNING]Error details: {cancellation_details.error_details}")
                    print("[WARNING]Did you set the speech resource key and region values?")
            return None

    def speechtotext_from_mic(self):
        
        self.azure_audioconfig = speechsdk.audio.AudioConfig(use_default_microphone=True)
        self.azure_speechrecognizer = speechsdk.SpeechRecognizer(speech_config=self.azure_speechconfig, audio_config=self.azure_audioconfig)

        print("[orange]Speak into your microphone.")
        speech_recognition_result = self.azure_speechrecognizer.recognize_once_async().get()
        text_result = speech_recognition_result.text

        if speech_recognition_result.reason == speechsdk.ResultReason.RecognizedSpeech:
            if DEBUG:
                print("[DEBUG]Recognized: {}".format(speech_recognition_result.text))
        elif speech_recognition_result.reason == speechsdk.ResultReason.NoMatch:
            print("[WARNING]No speech could be recognized: {}".format(speech_recognition_result.no_match_details))
        elif speech_recognition_result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = speech_recognition_result.cancellation_details
            print("[WARNING]Speech Recognition canceled: {}".format(cancellation_details.reason))
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print("[WARNING]Error details: {}".format(cancellation_details.error_details))
                print("[WARNING]Did you set the speech resource key and region values?")
        if DEBUG:
            print(f"[DEBUG]We got the following text: {text_result}")
        return text_result

    def speechtotext_from_file(self, filename):

        self.azure_audioconfig = speechsdk.AudioConfig(filename=filename)
        self.azure_speechrecognizer = speechsdk.SpeechRecognizer(speech_config=self.azure_speechconfig, audio_config=self.azure_audioconfig)

        print("[orange]Listening to the file \n")
        speech_recognition_result = self.azure_speechrecognizer.recognize_once_async().get()

        if speech_recognition_result.reason == speechsdk.ResultReason.RecognizedSpeech:
            if DEBUG:
                print("[DEBUG]Recognized: \n {}".format(speech_recognition_result.text))
        elif speech_recognition_result.reason == speechsdk.ResultReason.NoMatch:
            print("[WARNING]No speech could be recognized: {}".format(speech_recognition_result.no_match_details))
        elif speech_recognition_result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = speech_recognition_result.cancellation_details
            print("[WARNING]Speech Recognition canceled: {}".format(cancellation_details.reason))
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print("[WARNING]Error details: {}".format(cancellation_details.error_details))
                print("[WARNING]Did you set the speech resource key and region values?")

        return speech_recognition_result.text

    def speechtotext_from_file_continuous(self, filename):
        self.azure_audioconfig = speechsdk.audio.AudioConfig(filename=filename)
        self.azure_speechrecognizer = speechsdk.SpeechRecognizer(speech_config=self.azure_speechconfig, audio_config=self.azure_audioconfig)

        done = False
        def stop_cb(evt):
            if DEBUG:
                print('[DEBUG]CLOSING on {}'.format(evt))
            nonlocal done
            done = True

        # These are optional event callbacks that just print out when an event happens.
        # Recognized is useful as an update when a full chunk of speech has finished processing
        #self.azure_speechrecognizer.recognizing.connect(lambda evt: print('RECOGNIZING: {}'.format(evt)))
        self.azure_speechrecognizer.recognized.connect(lambda evt: print('[DEBUG]RECOGNIZED: {}'.format(evt)))
        self.azure_speechrecognizer.session_started.connect(lambda evt: print('[DEBUG]SESSION STARTED: {}'.format(evt)))
        self.azure_speechrecognizer.session_stopped.connect(lambda evt: print('[DEBUG]SESSION STOPPED {}'.format(evt)))
        self.azure_speechrecognizer.canceled.connect(lambda evt: print('[DEBUG]CANCELED {}'.format(evt)))

        # These functions will stop the program by flipping the "done" boolean when the session is either stopped or canceled
        self.azure_speechrecognizer.session_stopped.connect(stop_cb)
        self.azure_speechrecognizer.canceled.connect(stop_cb)

        # This is where we compile the results we receive from the ongoing "Recognized" events
        all_results = []
        def handle_final_result(evt):
            all_results.append(evt.result.text)
        self.azure_speechrecognizer.recognized.connect(handle_final_result)

        # Start processing the file
        if DEBUG:
            print("[DEBUG]Now processing the audio file...")
        self.azure_speechrecognizer.start_continuous_recognition()
        
        # We wait until stop_cb() has been called above, because session either stopped or canceled
        while not done:
            time.sleep(.5)

        # Now that we're done, tell the recognizer to end session
        # NOTE: THIS NEEDS TO BE OUTSIDE OF THE stop_cb FUNCTION. If it's inside that function the program just freezes. Not sure why.
        self.azure_speechrecognizer.stop_continuous_recognition()

        final_result = " ".join(all_results).strip()
        if DEBUG:
            print(f"\n\n[DEBUG]Heres the result we got from contiuous file read!\n\n{final_result}\n\n")
        return final_result

    def speechtotext_from_mic_continuous(self, stop_key=END_LISTEN_KEY):
        self.azure_speechrecognizer = speechsdk.SpeechRecognizer(speech_config=self.azure_speechconfig)

        done = False
        
        # Optional callback to print out whenever a chunk of speech is being recognized. This gets called basically every word.
        #def recognizing_cb(evt: speechsdk.SpeechRecognitionEventArgs):
        #    print('RECOGNIZING: {}'.format(evt))
        #self.azure_speechrecognizer.recognizing.connect(recognizing_cb)

        # Optional callback to print out whenever a chunk of speech is finished being recognized. Make sure to let this finish before ending the speech recognition.
        def recognized_cb(evt: speechsdk.SpeechRecognitionEventArgs):
            if DEBUG:
                print('[DEBUG]RECOGNIZED: {}'.format(evt))
        self.azure_speechrecognizer.recognized.connect(recognized_cb)

        # We register this to fire if we get a session_stopped or cancelled event.
        def stop_cb(evt: speechsdk.SessionEventArgs):
            if DEBUG:
                print('[DEBUG]CLOSING speech recognition on {}'.format(evt))
            nonlocal done
            done = True

        # Connect callbacks to the events fired by the speech recognizer
        self.azure_speechrecognizer.session_stopped.connect(stop_cb)
        self.azure_speechrecognizer.canceled.connect(stop_cb)

        # This is where we compile the results we receive from the ongoing "Recognized" events
        all_results = []
        def handle_final_result(evt):
            all_results.append(evt.result.text)
        self.azure_speechrecognizer.recognized.connect(handle_final_result)

        # Perform recognition. `start_continuous_recognition_async asynchronously initiates continuous recognition operation,
        # Other tasks can be performed on this thread while recognition starts...
        # wait on result_future.get() to know when initialization is done.
        # Call stop_continuous_recognition_async() to stop recognition.
        result_future = self.azure_speechrecognizer.start_continuous_recognition_async()
        result_future.get()  # wait for voidfuture, so we know engine initialization is done.
        print('[orange]Continuous Speech Recognition is now running, say something.')

        while not done:
            # METHOD 1 - Press the stop key. This is 'p' by default but user can provide different key
            if keyboard.is_pressed(stop_key):
                print("\n[orange]Ending azure speech recognition\n")
                self.azure_speechrecognizer.stop_continuous_recognition_async()
                time.sleep(2) # Wait for session to properly close
                break
            
            # METHOD 2 - User must type "stop" into cmd window
            #print('type "stop" then enter when done')
            #stop = input()
            #if (stop.lower() == "stop"):
            #    print('Stopping async recognition.')
            #    self.azure_speechrecognizer.stop_continuous_recognition_async()
            #    break

            # Other methods: https://stackoverflow.com/a/57644349

            # No real sample parallel work to do on this thread, so just wait for user to give the signal to stop.
            # Can't exit function or speech_recognizer will go out of scope and be destroyed while running.

        final_result = " ".join(all_results).strip()
        if DEBUG:
            print(f"\n\n[DEBUG]Heres the result we got!\n\n{final_result}\n\n")
        return final_result
    

        # The neural multilingual voice can speak different languages based on the input text.


# Tests
if __name__ == '__main__':

    TEST_FILE = r"C:\Users\Conner Altizer\Downloads\ElevenLabs_2025-04-04T20_52_14_Grandpa Spuds Oxley_pvc_sp100_s15_sb75_f2-5.mp3"
    speechtotext_manager = SpeechToTextManager()

    while True:
        #speechtotext_manager.speechtotext_from_mic()
        #speechtotext_manager.speechtotext_from_file(TEST_FILE)
        #speechtotext_manager.speechtotext_from_file_continuous(TEST_FILE)
        result = speechtotext_manager.speechtotext_from_mic_continuous()
        print(f"\n\nHERE IS THE RESULT:\n{result}")
        time.sleep(60)
