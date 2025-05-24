import asyncio
import platform
import subprocess
import requests
import io
from pydub import AudioSegment
from simpleaudio import WaveObject
from google.cloud import texttospeech
import pyttsx3
import os
from pathlib import Path

try:
    from AppKit import NSSpeechSynthesizer
    MACOS_TTS_AVAILABLE = True
except ImportError:
    MACOS_TTS_AVAILABLE = False

# Piper TTS binary (bundled in .app)
PIPER_BINARY = os.path.join(os.path.dirname(__file__), "piper", "piper")
PIPER_MODELS_DIR = os.path.join(os.path.dirname(__file__), "piper", "models")

# Sesame CSM path (absolute path to csm directory)
SESAME_CSM_DIR = "/Users/heathen-admin/Desktop/Claude/LLMChat/r2/csm"
import sys
sys.path.append(SESAME_CSM_DIR)
from generator import load_csm_1b, Segment
import torchaudio

class MacOSTTS:
    def __init__(self, voice, log_callback):
        self.voice = voice
        self.log_callback = log_callback
        self.synthesizer = None
        if MACOS_TTS_AVAILABLE and platform.system() == "Darwin":
            self.setup_synthesizer()

    def setup_synthesizer(self):
        try:
            self.synthesizer = NSSpeechSynthesizer.alloc().initWithVoice_(self.voice)
            self.log_callback(f"Initialized macOS TTS with voice: {self.voice}", "system")
        except Exception as e:
            self.log_callback(f"Error initializing macOS TTS: {str(e)}", "error")
            self.synthesizer = None

    async def generate_and_play_audio(self, text):
        if not MACOS_TTS_AVAILABLE or platform.system() != "Darwin" or not self.synthesizer:
            self.log_callback("macOS TTS not available.", "error")
            return False
        try:
            self.synthesizer.startSpeakingString_(text)
            while self.synthesizer.isSpeaking():
                await asyncio.sleep(0.1)
            self.log_callback("macOS TTS playback finished.", "system")
            return True
        except Exception as e:
            self.log_callback(f"macOS TTS error: {str(e)}", "error")
            return False

    def get_available_voices(self):
        if not MACOS_TTS_AVAILABLE or platform.system() != "Darwin":
            return []
        try:
            voices = NSSpeechSynthesizer.availableVoices()
            voice_names = []
            for voice in voices:
                voice_id = str(voice)
                if "SiriVoice" in voice_id:
                    siri_number = voice_id.split("SiriVoice")[-1]
                    friendly_name = f"Siri Voice {siri_number}"
                else:
                    name = voice_id.split('.')[-1].replace("-compact", "").replace("-premium", "")
                    friendly_name = name
                voice_names.append(friendly_name)
            return sorted(voice_names)
        except Exception as e:
            self.log_callback(f"Error fetching macOS voices: {str(e)}", "error")
            return ["Alex"]

async def generate_and_play_audio_elevenlabs(text, voice_id, stability, similarity_boost, log_callback, api_key):
    if not api_key:
        log_callback("Error: ElevenLabs API key not set.", "error")
        return False
    if not voice_id:
        log_callback("Error: No Voice ID set for ElevenLabs.", "error")
        return False
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {"xi-api-key": api_key, "Content-Type": "application/json", "accept": "audio/mpeg"}
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {"stability": stability, "similarity_boost": similarity_boost}
        }
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        audio = AudioSegment.from_mp3(io.BytesIO(response.content))
        wave_obj = WaveObject.from_wave_file(io.BytesIO(audio.raw_data))
        play_obj = wave_obj.play()
        log_callback("Playing audio with simpleaudio...", "system")
        play_obj.wait_done()
        log_callback("Audio playback finished.", "system")
        return True
    except requests.RequestException as e:
        log_callback(f"ElevenLabs API error: {str(e)}", "error")
        return False

class GoogleCloudTTS:
    def __init__(self, voice_name, log_callback):
        self.client = texttospeech.TextToSpeechClient()
        self.voice_name = voice_name
        self.log_callback = log_callback

    async def generate_and_play_audio(self, text):
        try:
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name=self.voice_name
            )
            audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
            response = self.client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
            audio = AudioSegment.from_mp3(io.BytesIO(response.audio_content))
            wave_obj = WaveObject.from_wave_file(io.BytesIO(audio.raw_data))
            play_obj = wave_obj.play()
            self.log_callback("Playing audio with simpleaudio...", "system")
            play_obj.wait_done()
            self.log_callback("Google Cloud TTS playback finished.", "system")
            return True
        except Exception as e:
            self.log_callback(f"Google Cloud TTS error: {str(e)}", "error")
            return False

    def get_available_voices(self):
        try:
            voices = self.client.list_voices().voices
            return sorted([voice.name for voice in voices if voice.language_codes[0].startswith("en-")])
        except Exception as e:
            self.log_callback(f"Error fetching Google Cloud voices: {str(e)}", "error")
            return ["en-US-Standard-A"]

class PiperTTS:
    def __init__(self, model, log_callback):
        self.model = model
        self.log_callback = log_callback
        self.model_path = os.path.join(PIPER_MODELS_DIR, f"{model}.onnx")

    async def generate_and_play_audio(self, text):
        if not os.path.exists(PIPER_BINARY) or not os.path.exists(self.model_path):
            self.log_callback("Error: Piper binary or model not found.", "error")
            return False
        try:
            process = await asyncio.create_subprocess_exec(
                PIPER_BINARY, "--model", self.model_path, "--output_file", "temp_audio.wav",
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
            )
            await process.communicate(input=text.encode())
            audio = AudioSegment.from_wav("temp_audio.wav")
            wave_obj = WaveObject.from_wave_file(io.BytesIO(audio.raw_data))
            play_obj = wave_obj.play()
            self.log_callback("Playing audio with simpleaudio...", "system")
            play_obj.wait_done()
            self.log_callback("Piper TTS playback finished.", "system")
            os.remove("temp_audio.wav")
            return True
        except Exception as e:
            self.log_callback(f"Piper TTS error: {str(e)}", "error")
            return False

    def get_available_voices(self):
        try:
            return sorted([f.stem for f in Path(PIPER_MODELS_DIR).glob("*.onnx")])
        except Exception as e:
            self.log_callback(f"Error fetching Piper voices: {str(e)}", "error")
            return ["en_US-lessac-medium"]

class Pyttsx3TTS:
    def __init__(self, voice_id, log_callback):
        self.engine = pyttsx3.init()
        self.log_callback = log_callback
        if voice_id in self.get_available_voices():
            self.engine.setProperty('voice', voice_id)

    async def generate_and_play_audio(self, text):
        try:
            self.log_callback("Generating audio with pyttsx3...", "system")
            self.engine.say(text)
            self.engine.runAndWait()
            self.log_callback("pyttsx3 playback finished.", "system")
            return True
        except Exception as e:
            self.log_callback(f"pyttsx3 error: {str(e)}", "error")
            return False

    def get_available_voices(self):
        try:
            return [voice.id for voice in self.engine.getProperty('voices')]
        except Exception as e:
            self.log_callback(f"Error fetching pyttsx3 voices: {str(e)}", "error")
            return ["com.apple.speech.synthesis.voice.Alex"]

class OpenAITTS:
    def __init__(self, api_key, voice, log_callback):
        self.api_key = api_key
        self.voice = voice
        self.log_callback = log_callback

    async def generate_and_play_audio(self, text):
        try:
            response = requests.post(
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "tts-1",
                    "input": text,
                    "voice": self.voice
                }
            )
            response.raise_for_status()
            audio = AudioSegment.from_file(io.BytesIO(response.content), format="mp3")
            wave_obj = WaveObject.from_wave_file(io.BytesIO(audio.raw_data))
            play_obj = wave_obj.play()
            self.log_callback("Playing audio with simpleaudio...", "system")
            play_obj.wait_done()
            self.log_callback("OpenAI TTS playback finished.", "system")
            return True
        except Exception as e:
            self.log_callback(f"OpenAI TTS error: {str(e)}", "error")
            return False

    def get_available_voices(self):
        # OpenAI TTS voices as of May 2025
        return ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

class SesameCSMTTS:
    def __init__(self, speaker_id, log_callback):
        self.speaker_id = speaker_id
        self.log_callback = log_callback
        self.generator = None
        self.device = "cpu"  # Default to CPU for macOS
        self.sample_rate = None
        self._setup_generator()

    def _setup_generator(self):
        try:
            self.generator = load_csm_1b(device=self.device)
            self.sample_rate = self.generator.sample_rate
            self.log_callback("Initialized Sesame CSM TTS.", "system")
        except Exception as e:
            self.log_callback(f"Error initializing Sesame CSM TTS: {str(e)}", "error")
            self.generator = None

    async def generate_and_play_audio(self, text, context=None):
        if not self.generator:
            self.log_callback("Sesame CSM TTS not available.", "error")
            return False
        try:
            # Generate audio with Sesame CSM
            audio = self.generator.generate(
                text=text,
                speaker=self.speaker_id,
                context=context if context else [],
                max_audio_length_ms=10_000,
            )
            # Save and play the audio
            temp_audio_file = "temp_sesame_audio.wav"
            torchaudio.save(temp_audio_file, audio.unsqueeze(0).cpu(), self.sample_rate)
            audio_segment = AudioSegment.from_wav(temp_audio_file)
            wave_obj = WaveObject.from_wave_file(io.BytesIO(audio_segment.raw_data))
            play_obj = wave_obj.play()
            self.log_callback("Playing audio with simpleaudio...", "system")
            play_obj.wait_done()
            self.log_callback("Sesame CSM TTS playback finished.", "system")
            os.remove(temp_audio_file)
            return True
        except Exception as e:
            self.log_callback(f"Sesame CSM TTS error: {str(e)}", "error")
            return False

    def get_available_voices(self):
        # Sesame CSM doesn't have predefined voices; it uses speaker IDs
        # Return a list of speaker IDs as a placeholder
        return [str(i) for i in range(2)]  # Example: speaker IDs 0 and 1