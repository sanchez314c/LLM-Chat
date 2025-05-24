import asyncio
from google.cloud import speech
import pyaudio
import wave
import whisperx
import numpy as np
import requests

class GoogleCloudSTT:
    def __init__(self, log_callback):
        self.client = speech.SpeechClient()
        self.log_callback = log_callback
        self.is_recording = False

    async def record_and_transcribe(self, duration=5):
        """Record audio and transcribe using Google Cloud STT."""
        try:
            self.is_recording = True
            audio_file = "temp_recording.wav"
            p = pyaudio.PyAudio()
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)
            frames = []
            self.log_callback("Recording audio...", "system")
            for _ in range(0, int(16000 / 1024 * duration)):
                if not self.is_recording:
                    break
                data = stream.read(1024)
                frames.append(data)
            stream.stop_stream()
            stream.close()
            p.terminate()
            wf = wave.open(audio_file, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(16000)
            wf.writeframes(b''.join(frames))
            wf.close()

            with open(audio_file, 'rb') as audio_file:
                content = audio_file.read()
            audio = speech.RecognitionAudio(content=content)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code="en-US"
            )
            response = self.client.recognize(config=config, audio=audio)
            transcript = "".join(result.alternatives[0].transcript for result in response.results)
            self.log_callback("Transcription completed with Google Cloud STT.", "system")
            return transcript
        except Exception as e:
            self.log_callback(f"Google Cloud STT error: {str(e)}", "error")
            return ""
        finally:
            try:
                import os
                os.remove(audio_file)
            except:
                pass

    def stop_recording(self):
        """Stop ongoing recording."""
        self.is_recording = False

class OpenAIWhisperSTT:
    def __init__(self, api_key, log_callback=None):
        self.api_key = api_key
        self.log_callback = log_callback
        self.is_recording = False

    async def record_and_transcribe(self, duration=5):
        """Record audio and transcribe using OpenAI Whisper API."""
        try:
            self.is_recording = True
            audio_file = "temp_recording.wav"
            p = pyaudio.PyAudio()
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)
            frames = []
            if self.log_callback:
                self.log_callback("Recording audio...", "system")
            for _ in range(0, int(16000 / 1024 * duration)):
                if not self.is_recording:
                    break
                data = stream.read(1024)
                frames.append(data)
            stream.stop_stream()
            stream.close()
            p.terminate()
            wf = wave.open(audio_file, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(16000)
            wf.writeframes(b''.join(frames))
            wf.close()

            with open(audio_file, 'rb') as f:
                response = requests.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "multipart/form-data"
                    },
                    files={"file": (audio_file, f, "audio/wav")},
                    data={"model": "whisper-1", "language": "en"}
                )
                response.raise_for_status()
                result = response.json()
                transcript = result["text"]
                if self.log_callback:
                    self.log_callback("Transcription completed with OpenAI Whisper API.", "system")
                return transcript
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"OpenAI Whisper API STT error: {str(e)}", "error")
            return ""
        finally:
            try:
                import os
                os.remove(audio_file)
            except:
                pass

    def stop_recording(self):
        """Stop ongoing recording."""
        self.is_recording = False

class WhisperXSTT:
    def __init__(self, model_size="large-v2", device="cpu", batch_size=16, compute_type="float16", hf_token=None, log_callback=None):
        self.model = whisperx.load_model(model_size, device, compute_type="float32")
        self.device = device
        self.batch_size = batch_size
        self.hf_token = hf_token
        self.log_callback = log_callback
        self.is_recording = False
        self.diarize_model = None
        if self.hf_token:
            try:
                self.diarize_model = whisperx.DiarizationPipeline(use_auth_token=self.hf_token, device=self.device)
            except Exception as e:
                if self.log_callback:
                    self.log_callback(f"Failed to initialize diarization model: {str(e)}", "error")

    async def record_and_transcribe(self, duration=5):
        """Record audio and transcribe using WhisperX without alignment or diarization."""
        try:
            self.is_recording = True
            audio_file = "temp_recording.wav"
            p = pyaudio.PyAudio()
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)
            frames = []
            if self.log_callback:
                self.log_callback("Recording audio...", "system")
            for _ in range(0, int(16000 / 1024 * duration)):
                if not self.is_recording:
                    break
                data = stream.read(1024)
                frames.append(data)
            stream.stop_stream()
            stream.close()
            p.terminate()
            wf = wave.open(audio_file, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(16000)
            wf.writeframes(b''.join(frames))
            wf.close()

            # Load audio
            audio = whisperx.load_audio(audio_file)

            # Transcribe with Whisper
            result = self.model.transcribe(audio, batch_size=self.batch_size)
            if self.log_callback:
                self.log_callback("Transcription completed with WhisperX (no alignment or diarization).", "system")

            # Combine segments into a single transcript without alignment or diarization
            transcript = " ".join(segment["text"] for segment in result["segments"])
            return transcript
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"WhisperX STT error: {str(e)}", "error")
            return ""
        finally:
            try:
                import os
                os.remove(audio_file)
            except:
                pass

    def stop_recording(self):
        """Stop ongoing recording."""
        self.is_recording = False