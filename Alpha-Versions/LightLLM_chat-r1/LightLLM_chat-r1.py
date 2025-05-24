import tkinter as tk
from tkinter import ttk, scrolledtext, simpledialog, Menu as tkMenu, messagebox, Text
import openai
import requests
import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime
import asyncio
import platform
import pygame
import io
import subprocess
import threading
import pyperclip  # For clipboard operations
import torch
import torchaudio
from huggingface_hub import hf_hub_download

# macOS Native TTS Dependencies
try:
    from AppKit import NSSpeechSynthesizer
    from Foundation import NSAutoreleasePool
    MACOS_TTS_AVAILABLE = True
except ImportError:
    MACOS_TTS_AVAILABLE = False

# Sesame CSM Dependencies
try:
    from generator import load_csm_1b, Segment
    SESAME_CSM_AVAILABLE = False  # Temporarily disable Sesame CSM
except ImportError:
    SESAME_CSM_AVAILABLE = False

# --- Cross-Platform Font Selection ---
FONT_FAMILY = "SF Pro Display" if platform.system() == "Darwin" else "Segoe UI" if platform.system() == "Windows" else "Ubuntu"

# --- Dark Theme Colors (Updated to Match Grok UI Exactly) ---
DARK_BG = "#181B1C"          # Main background
LEFT_PANEL_BG = "#202426"    # Side panels
MEDIUM_DARK_BG = "#2E3436"   # Interactive elements
LIGHT_TEXT = "#D9E0E3"       # Primary text
MEDIUM_TEXT = "#8A9396"      # Secondary text
ACCENT_COLOR_USER = "#C8CED1" # User messages
ACCENT_COLOR_ASSISTANT = "#F5F8FA" # Assistant messages
BORDER_COLOR = "#2A2F31"      # Borders
SELECT_BG_COLOR = "#37474F"   # Selection/highlight
ERROR_TEXT = "#F44336"        # Errors
SYSTEM_TEXT = "#FFFFFF"       # System messages

# --- Light Theme Colors (For Toggle) ---
LIGHT_BG = "#F5F5F5"
LIGHT_LEFT_PANEL_BG = "#E0E0E0"
LIGHT_MEDIUM_BG = "#D0D0D0"
LIGHT_TEXT_DARK = "#333333"
LIGHT_ACCENT_USER = "#666666"
LIGHT_ACCENT_ASSISTANT = "#000000"

# --- Configuration and API Key Management ---
CONFIG_FILE = os.path.expanduser("~/.voyeur_chat_config.json")
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"
XAI_API_KEY_ENV = "XAI_API_KEY"
ELEVENLABS_API_KEY_ENV = "ELEVENLABS_API_KEY"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        "tts_provider": "None",  # Default to no TTS
        "voice_id": "",  # Global Voice ID for ElevenLabs
        "default_system_prompt": "You are a helpful AI assistant.",
        "macos_voice": "Alex",  # Default macOS voice
        "sesame_speaker": 0,  # Default speaker for Sesame CSM
        "openai_api_key": os.getenv(OPENAI_API_KEY_ENV, ""),
        "openrouter_api_key": os.getenv(OPENROUTER_API_KEY_ENV, ""),
        "xai_api_key": os.getenv(XAI_API_KEY_ENV, ""),
        "anthropic_api_key": "",
        "huggingface_api_key": "",
        "google_api_key": "",
        "perplexity_api_key": "",
        "together_api_key": "",
        "groq_api_key": "",
        "pi_api_key": "",
        "mistral_api_key": "",
        "deepseek_api_key": ""
    }

def save_config(config_data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f)

config = load_config()
openai_api_key = config.get("openai_api_key")
openrouter_api_key = config.get("openrouter_api_key")
xai_api_key = config.get("xai_api_key")
elevenlabs_api_key = os.getenv(ELEVENLABS_API_KEY_ENV)  # API key from environment variable only
anthropic_api_key = config.get("anthropic_api_key")
huggingface_api_key = config.get("huggingface_api_key")
google_api_key = config.get("google_api_key")
perplexity_api_key = config.get("perplexity_api_key")
together_api_key = config.get("together_api_key")
groq_api_key = config.get("groq_api_key")
pi_api_key = config.get("pi_api_key")
mistral_api_key = config.get("mistral_api_key")
deepseek_api_key = config.get("deepseek_api_key")
voice_id = config.get("voice_id", "")  # Global Voice ID for ElevenLabs

if openai_api_key:
    openai.api_key = openai_api_key

# --- SQLite Database Setup ---
DB_DIR = os.path.expanduser("~/.lightllm_chat")
DB_PATH = os.path.join(DB_DIR, "lightllm_chat.db")

def ensure_db_directory():
    Path(DB_DIR).mkdir(parents=True, exist_ok=True)

def init_database():
    ensure_db_directory()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_active_at TEXT NOT NULL,
            llm_model TEXT,
            system_prompt TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            api_response_json TEXT,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

def create_conversation_in_db(title="New Chat", model="", system_prompt=""):
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO conversations (title, created_at, last_active_at, llm_model, system_prompt) VALUES (?, ?, ?, ?, ?)",
                   (title, now, now, model, system_prompt))
    conn.commit()
    conv_id = cursor.lastrowid
    conn.close()
    return conv_id

def add_message_to_db(conversation_id, role, content, api_response_json=None):
    timestamp = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (conversation_id, role, content, timestamp, api_response_json) VALUES (?, ?, ?, ?, ?)",
                   (conversation_id, role, content, timestamp, api_response_json))
    cursor.execute("UPDATE conversations SET last_active_at = ? WHERE id = ?", (timestamp, conversation_id))
    conn.commit()
    conn.close()

def fetch_conversations_from_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, last_active_at FROM conversations ORDER BY last_active_at DESC")
    conversations = cursor.fetchall()
    conn.close()
    return conversations

def fetch_messages_from_db(conversation_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content, timestamp FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC", (conversation_id,))
    messages = cursor.fetchall()
    conn.close()
    return messages

def update_conversation_title_in_db(conversation_id, new_title):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE conversations SET title = ? WHERE id = ?", (new_title, conversation_id))
    conn.commit()
    conn.close()

def delete_conversation_in_db(conversation_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    conn.close()

# --- Model Fetching ---
def fetch_openai_models(api_key_to_use):
    if not api_key_to_use:
        return []
    try:
        client = openai.OpenAI(api_key=api_key_to_use)
        models = client.models.list()
        return sorted([model.id for model in models.data if "gpt" in model.id.lower() or "text-" in model.id.lower()], reverse=True)
    except Exception as e:
        print(f"Error fetching OpenAI models: {e}")
        return []

def fetch_openrouter_models(api_key_to_use):
    if not api_key_to_use:
        return []
    try:
        response = requests.get("https://openrouter.ai/api/v1/models", headers={"Authorization": f"Bearer {api_key_to_use}"})
        response.raise_for_status()
        models_data = response.json()["data"]
        return sorted([model["id"] for model in models_data], key=lambda x: x.lower())
    except Exception as e:
        print(f"Error fetching OpenRouter models: {e}")
        return []

def fetch_xai_models(api_key_to_use):
    if not api_key_to_use:
        return []
    try:
        response = requests.get("https://api.x.ai/v1/models", headers={"Authorization": f"Bearer {api_key_to_use}"})
        response.raise_for_status()
        models_data = response.json().get("data", [])
        return sorted([model["id"] for model in models_data])
    except Exception as e:
        print(f"Error fetching XAI models: {e}")
        return []

def fetch_anthropic_models(api_key_to_use):
    if not api_key_to_use:
        return []
    try:
        # Anthropic doesn't have a public model list endpoint; we'll use known models
        # Models as of May 2025: Claude 3 series
        known_models = ["claude-3-opus-20240229", "claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
        return sorted(known_models)
    except Exception as e:
        print(f"Error fetching Anthropic models: {e}")
        return []

def fetch_huggingface_models(api_key_to_use):
    if not api_key_to_use:
        return []
    try:
        response = requests.get("https://api-inference.huggingface.co/models", headers={"Authorization": f"Bearer {api_key_to_use}"})
        response.raise_for_status()
        models_data = response.json()
        return sorted([model["modelId"] for model in models_data if model.get("pipeline_tag") == "text-generation"])
    except Exception as e:
        print(f"Error fetching HuggingFace models: {e}")
        return []

def fetch_google_models(api_key_to_use):
    if not api_key_to_use:
        return []
    try:
        response = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key_to_use}")
        response.raise_for_status()
        models_data = response.json().get("models", [])
        return sorted([model["name"] for model in models_data if "gemini" in model["name"].lower()])
    except Exception as e:
        print(f"Error fetching Google Gemini models: {e}")
        return []

def fetch_perplexity_models(api_key_to_use):
    if not api_key_to_use:
        return []
    try:
        # Perplexity API doesn't provide a model list endpoint; using known models
        known_models = ["llama-3-sonar-large-32k-online", "llama-3-sonar-small-32k-online"]
        return sorted(known_models)
    except Exception as e:
        print(f"Error fetching Perplexity models: {e}")
        return []

def fetch_together_models(api_key_to_use):
    if not api_key_to_use:
        return []
    try:
        response = requests.get("https://api.together.ai/models", headers={"Authorization": f"Bearer {api_key_to_use}"})
        response.raise_for_status()
        models_data = response.json()
        return sorted([model["name"] for model in models_data])
    except Exception as e:
        print(f"Error fetching Together.ai models: {e}")
        return []

def fetch_groq_models(api_key_to_use):
    if not api_key_to_use:
        return []
    try:
        response = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {api_key_to_use}"})
        response.raise_for_status()
        models_data = response.json().get("data", [])
        return sorted([model["id"] for model in models_data])
    except Exception as e:
        print(f"Error fetching Groq models: {e}")
        return []

def fetch_pi_models(api_key_to_use):
    if not api_key_to_use:
        return []
    try:
        # Pi.ai API doesn't have a public model list; using known models
        known_models = ["xAI-Pi"]
        return sorted(known_models)
    except Exception as e:
        print(f"Error fetching Pi.ai models: {e}")
        return []

def fetch_mistral_models(api_key_to_use):
    if not api_key_to_use:
        return []
    try:
        response = requests.get("https://api.mixtral.ai/v1/models", headers={"Authorization": f"Bearer {api_key_to_use}"})
        response.raise_for_status()
        models_data = response.json().get("models", [])
        return sorted([model["id"] for model in models_data])
    except Exception as e:
        print(f"Error fetching Mistral models: {e}")
        return []

def fetch_deepseek_models(api_key_to_use):
    if not api_key_to_use:
        return []
    try:
        response = requests.get("https://api.deepseek.com/v1/models", headers={"Authorization": f"Bearer {api_key_to_use}"})
        response.raise_for_status()
        models_data = response.json().get("data", [])
        return sorted([model["id"] for model in models_data])
    except Exception as e:
        print(f"Error fetching DeepSeek models: {e}")
        return []

# --- ElevenLabs TTS Function ---
async def generate_and_play_audio_elevenlabs(text, voice_id, stability, similarity_boost, log_callback):
    if not elevenlabs_api_key:
        log_callback("Error: ElevenLabs API key not set in environment variable ELEVENLABS_API_KEY.", "error")
        return False
    if not voice_id:
        log_callback("Error: No global Voice ID set for ElevenLabs. Please set a Voice ID in the settings menu.", "error")
        return False

    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": elevenlabs_api_key,
            "Content-Type": "application/json",
            "accept": "audio/mpeg"
        }
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost
            }
        }
        log_callback(f"Sending request to ElevenLabs with voice ID: {voice_id}", "system")
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            log_callback(f"ElevenLabs API error: {response.status_code} - {response.text}", "error")
            return False
        
        temp_file_path = "temp_audio.mp3"
        with open(temp_file_path, "wb") as f:
            f.write(response.content)
        log_callback(f"Audio received from ElevenLabs and saved to {temp_file_path}.", "system")

        try:
            pygame.mixer.init()
            pygame.mixer.music.load(temp_file_path)
            pygame.mixer.music.play()
            log_callback("Playing audio with pygame...", "system")
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.1)
            log_callback("Audio playback finished.", "system")
            return True
        except Exception as e:
            log_callback(f"Pygame error: {str(e)}", "error")
            log_callback("Falling back to system audio player.", "system")
            if platform.system() == "Darwin":  # macOS
                subprocess.run(["afplay", temp_file_path], check=True)
            elif platform.system() == "Windows":  # Windows
                subprocess.run(["start", "", temp_file_path], shell=True, check=True)
            elif platform.system() == "Linux":  # Linux
                subprocess.run(["aplay", temp_file_path], check=True)
            else:
                log_callback("System audio player not supported on this platform.", "error")
                return False
            return True
    except requests.RequestException as e:
        log_callback(f"ElevenLabs API request failed: {str(e)}", "error")
        return False
    except Exception as e:
        log_callback(f"Unexpected error during ElevenLabs audio generation: {str(e)}", "error")
        return False

# --- Sesame CSM TTS Function ---
class SesameCSMTTS:
    def __init__(self, log_callback):
        self.log_callback = log_callback
        self.generator = None
        self.device = "cpu"
        if torch.backends.mps.is_available():
            self.device = "mps"
        elif torch.cuda.is_available():
            self.device = "cuda"
        self.load_model()

    def load_model(self):
        if not SESAME_CSM_AVAILABLE:
            self.log_callback("Error: Sesame CSM dependencies not installed. Please install 'generator' package.", "error")
            return
        try:
            # Download model checkpoint from Hugging Face (user must have access)
            self.log_callback("Attempting to download Sesame CSM-1B model from Hugging Face...", "system")
            model_path = hf_hub_download(repo_id="SesameAILabs/csm", filename="csm-1b.pt")
            self.log_callback(f"Downloaded Sesame CSM-1B model to {model_path}", "system")
            self.generator = load_csm_1b(device=self.device)
            self.log_callback(f"Loaded Sesame CSM-1B model on device: {self.device}", "system")
        except Exception as e:
            self.log_callback(f"Error loading Sesame CSM-1B model: {str(e)}", "error")
            self.log_callback("Please ensure you have access to the Sesame CSM-1B model on Hugging Face and have run 'huggingface-cli login'.", "error")
            self.generator = None

    async def generate_and_play_audio(self, text, speaker=0, context=None):
        if self.generator is None:
            self.log_callback("Error: Sesame CSM model not loaded.", "error")
            return False
        try:
            self.log_callback("Generating audio with Sesame CSM...", "system")
            context = context if context is not None else []
            audio = self.generator.generate(
                text=text,
                speaker=speaker,
                context=context,
                max_audio_length_ms=10_000
            )
            temp_file_path = "temp_audio.wav"
            torchaudio.save(temp_file_path, audio.unsqueeze(0).cpu(), self.generator.sample_rate)
            self.log_callback(f"Audio generated by Sesame CSM and saved to {temp_file_path}.", "system")

            try:
                pygame.mixer.init()
                pygame.mixer.music.load(temp_file_path)
                pygame.mixer.music.play()
                self.log_callback("Playing audio with pygame...", "system")
                while pygame.mixer.music.get_busy():
                    await asyncio.sleep(0.1)
                self.log_callback("Audio playback finished.", "system")
                return True
            except Exception as e:
                self.log_callback(f"Pygame error: {str(e)}", "error")
                self.log_callback("Falling back to system audio player.", "system")
                if platform.system() == "Darwin":  # macOS
                    subprocess.run(["afplay", temp_file_path], check=True)
                elif platform.system() == "Windows":  # Windows
                    subprocess.run(["start", "", temp_file_path], shell=True, check=True)
                elif platform.system() == "Linux":  # Linux
                    subprocess.run(["aplay", temp_file_path], check=True)
                else:
                    self.log_callback("System audio player not supported on this platform.", "error")
                    return False
                return True
        except Exception as e:
            self.log_callback(f"Error generating audio with Sesame CSM: {str(e)}", "error")
            return False

    def create_context(self, conversation_log):
        if not self.generator:
            return []
        context = []
        for msg in conversation_log[-5:]:  # Last 5 messages for context
            role = msg["role"]
            content = msg["content"]
            speaker = 0 if role == "user" else 1  # Simple speaker mapping
            # Note: CSM requires audio context, but since we don't have audio history,
            # we'll use text-only context. In a production app, you might cache audio.
            segment = Segment(text=content, speaker=speaker, audio=None)
            context.append(segment)
        return context

# --- macOS Native TTS Function ---
class MacOSTTS:
    def __init__(self, voice, log_callback):
        self.voice = voice
        self.log_callback = log_callback
        self.synthesizer = None
        if MACOS_TTS_AVAILABLE and platform.system() == "Darwin":
            self.setup_synthesizer()

    def setup_synthesizer(self):
        try:
            pool = NSAutoreleasePool.alloc().init()
            self.synthesizer = NSSpeechSynthesizer.alloc().initWithVoice_(self.voice)
            if self.synthesizer is None:
                self.log_callback(f"Error: Could not initialize macOS TTS with voice {self.voice}.", "error")
            else:
                self.log_callback(f"Initialized macOS TTS with voice: {self.voice}", "system")
            pool.release()
        except Exception as e:
            self.log_callback(f"Error initializing macOS TTS: {str(e)}", "error")
            self.synthesizer = None

    def set_voice(self, voice):
        self.voice = voice
        self.setup_synthesizer()

    async def generate_and_play_audio(self, text):
        if not MACOS_TTS_AVAILABLE or platform.system() != "Darwin":
            self.log_callback("Error: macOS TTS is not available on this platform.", "error")
            return False
        if self.synthesizer is None:
            self.log_callback("Error: macOS TTS synthesizer not initialized.", "error")
            return False
        try:
            pool = NSAutoreleasePool.alloc().init()
            self.log_callback("Generating audio with macOS TTS...", "system")
            self.synthesizer.startSpeakingString_(text)
            while self.synthesizer.isSpeaking():
                await asyncio.sleep(0.1)
            self.log_callback("macOS TTS playback finished.", "system")
            pool.release()
            return True
        except Exception as e:
            self.log_callback(f"Error with macOS TTS playback: {str(e)}", "error")
            return False

    def get_available_voices(self):
        if not MACOS_TTS_AVAILABLE or platform.system() != "Darwin":
            return []
        try:
            pool = NSAutoreleasePool.alloc().init()
            voices = NSSpeechSynthesizer.availableVoices()
            voice_names = []
            for voice in voices:
                voice_id = str(voice)
                # Log the raw voice identifier for debugging
                self.log_callback(f"Found voice identifier: {voice_id}", "system")
                # Parse the voice name
                # Example identifiers: 
                # - com.apple.speech.synthesis.voice.Alex → "Alex"
                # - com.apple.voices.SiriVoice3 → "Siri Voice 3"
                # - com.apple.ttsbundle.Samantha-compact → "Samantha"
                if "SiriVoice" in voice_id:
                    # Extract the Siri voice number and format it
                    siri_number = voice_id.split("SiriVoice")[-1]
                    friendly_name = f"Siri Voice {siri_number}"
                else:
                    # For standard voices, take the last component and clean it up
                    name = voice_id.split('.')[-1]
                    # Remove suffixes like "-compact" or "-premium"
                    name = name.replace("-compact", "").replace("-premium", "")
                    friendly_name = name
                voice_names.append(friendly_name)
            pool.release()
            # Log the parsed voice names
            self.log_callback(f"Available voices: {', '.join(voice_names)}", "system")
            return sorted(voice_names)
        except Exception as e:
            self.log_callback(f"Error fetching available macOS voices: {str(e)}", "error")
            return ["Alex"]  # Fallback to a default voice

class VoyeurChat(tk.Tk):
    def __init__(self):
        super().__init__()
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self.is_dark_mode = tk.BooleanVar(value=True)
        self.tts_provider = tk.StringVar(value=config.get("tts_provider", "None"))
        self.voice_id = config.get("voice_id", "")  # Global Voice ID for ElevenLabs
        self.macos_voice = tk.StringVar(value=config.get("macos_voice", "Alex"))
        self.sesame_speaker = tk.IntVar(value=config.get("sesame_speaker", 0))
        
        # Initialize TTS providers as None; we'll set them up after UI
        self.sesame_csm = None
        self.macos_tts = None
        
        self._configure_styles()
        
        self.title("Voyeur Chat")
        self.geometry("1600x1200")
        self.conversation_id_map = {}
        self.current_conversation_id = None
        self.available_models = []
        self.model_groups = {
            'OpenAI': [], 'OpenRouter': [], 'XAI': [], 'Anthropic': [], 'HuggingFace': [],
            'Google': [], 'Perplexity': [], 'Together': [], 'Groq': [], 'Pi': [],
            'Mistral': [], 'DeepSeek': []
        }
        self.chat_modes = ["Normal", "Assistant", "Code Assistant", "Sarcastic Assistant"]
        self.current_chat_mode = tk.StringVar(self)
        self.current_chat_mode.set(self.chat_modes[0])
        self.conversation_log = []
        self.placeholder_visible = True
        self.message_frames = []
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.run_loop, daemon=True)
        self.thread.start()
        init_database()
        self._init_ui()  # UI is fully initialized here
        
        # Initialize TTS providers after UI setup
        if MACOS_TTS_AVAILABLE and platform.system() == "Darwin":
            self.macos_tts = MacOSTTS(self.macos_voice.get(), self.add_log_message)
            self.macos_voices = self.macos_tts.get_available_voices()
            # Update the dropdown with available voices
            self.macos_voice_menu['menu'].delete(0, 'end')
            for voice in self.macos_voices:
                self.macos_voice_menu['menu'].add_command(label=voice, command=tk._setit(self.macos_voice, voice))
            # Ensure the selected voice is valid; fall back to first available voice if not
            if self.macos_voice.get() not in self.macos_voices:
                self.macos_voice.set(self.macos_voices[0] if self.macos_voices else "Alex")
            # Sesame CSM is disabled for now; re-enable later
            # if SESAME_CSM_AVAILABLE:
            #     self.sesame_csm = SesameCSMTTS(self.add_log_message)
        
        self.load_initial_models()
        self.load_or_create_conversation()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _configure_styles(self):
        # Dark Theme
        self.style.configure("MainDark.TFrame", background=DARK_BG, borderwidth=0)
        self.style.configure("Dark.TFrame", background=DARK_BG)
        self.style.configure("Secondary.TFrame", background=LEFT_PANEL_BG, borderwidth=0)
        self.style.configure("Secondary.Dark.TLabel", background=LEFT_PANEL_BG, foreground=LIGHT_TEXT, font=(FONT_FAMILY, 18))
        self.style.configure("Dark.TLabel", background=LEFT_PANEL_BG, foreground=LIGHT_TEXT, font=(FONT_FAMILY, 18))
        self.style.configure("MainDark.TLabel", background=DARK_BG, foreground=LIGHT_TEXT, font=(FONT_FAMILY, 18))
        self.style.configure("Section.TLabel", background=LEFT_PANEL_BG, foreground=LIGHT_TEXT, font=(FONT_FAMILY, 20, "bold"))
        self.style.configure("Dark.TButton", background=MEDIUM_DARK_BG, foreground=LIGHT_TEXT, bordercolor=BORDER_COLOR, borderwidth=0, relief=tk.FLAT, padding=4, font=(FONT_FAMILY, 14))
        self.style.map("Dark.TButton", background=[('active', '#3A4042')], relief=[('pressed', tk.FLAT), ('active', tk.FLAT)])
        self.style.configure("Dark.TCheckbutton", background=LEFT_PANEL_BG, foreground=LIGHT_TEXT, font=(FONT_FAMILY, 14))
        self.style.map("Dark.TCheckbutton", background=[('active', SELECT_BG_COLOR)], foreground=[('active', LIGHT_TEXT)])
        self.style.configure("Dark.TMenubutton", background=MEDIUM_DARK_BG, foreground=LIGHT_TEXT, bordercolor=BORDER_COLOR, borderwidth=0, relief=tk.FLAT, arrowcolor=LIGHT_TEXT, padding=4, font=(FONT_FAMILY, 18))
        self.style.map("Dark.TMenubutton", background=[('active', '#3A4042')])
        self.style.configure("Secondary.Dark.Horizontal.TScale", background=DARK_BG, troughcolor="#3A3A3C", sliderrelief=tk.FLAT, sliderthickness=8, bordercolor=BORDER_COLOR)
        self.style.map("Secondary.Dark.Horizontal.TScale", background=[('active', MEDIUM_DARK_BG)], troughcolor=[('active', SELECT_BG_COLOR)])
        self.style.configure("Dark.TEntry", fieldbackground=MEDIUM_DARK_BG, foreground=LIGHT_TEXT, bordercolor=BORDER_COLOR, borderwidth=0, relief=tk.FLAT, insertcolor=LIGHT_TEXT, padding=4, font=(FONT_FAMILY, 18))
        self.style.configure("TScrollbar", troughcolor=DARK_BG, background=MEDIUM_DARK_BG, bordercolor=BORDER_COLOR, arrowcolor=LIGHT_TEXT, relief=tk.FLAT, arrowsize=14)
        self.style.map("TScrollbar", background=[('active', SELECT_BG_COLOR)])

        # Light Theme
        self.style.configure("MainLight.TFrame", background=LIGHT_BG, borderwidth=0)
        self.style.configure("Light.TFrame", background=LIGHT_BG)
        self.style.configure("Secondary.Light.TFrame", background=LIGHT_LEFT_PANEL_BG, borderwidth=0)
        self.style.configure("Secondary.Light.TLabel", background=LIGHT_LEFT_PANEL_BG, foreground=LIGHT_TEXT_DARK, font=(FONT_FAMILY, 18))
        self.style.configure("Light.TLabel", background=LIGHT_LEFT_PANEL_BG, foreground=LIGHT_TEXT_DARK, font=(FONT_FAMILY, 18))
        self.style.configure("MainLight.TLabel", background=LIGHT_BG, foreground=LIGHT_TEXT_DARK, font=(FONT_FAMILY, 18))
        self.style.configure("Section.Light.TLabel", background=LIGHT_LEFT_PANEL_BG, foreground=LIGHT_TEXT_DARK, font=(FONT_FAMILY, 20, "bold"))
        self.style.configure("Light.TButton", background=LIGHT_MEDIUM_BG, foreground=LIGHT_TEXT_DARK, bordercolor=BORDER_COLOR, borderwidth=0, relief=tk.FLAT, padding=4, font=(FONT_FAMILY, 14))
        self.style.map("Light.TButton", background=[('active', '#B0B0B0')], relief=[('pressed', tk.FLAT), ('active', tk.FLAT)])
        self.style.configure("Light.TCheckbutton", background=LIGHT_LEFT_PANEL_BG, foreground=LIGHT_TEXT_DARK, font=(FONT_FAMILY, 14))
        self.style.map("Light.TCheckbutton", background=[('active', '#A0A0A0')], foreground=[('active', LIGHT_TEXT_DARK)])
        self.style.configure("Light.TMenubutton", background=LIGHT_MEDIUM_BG, foreground=LIGHT_TEXT_DARK, bordercolor=BORDER_COLOR, borderwidth=0, relief=tk.FLAT, arrowcolor=LIGHT_TEXT_DARK, padding=4, font=(FONT_FAMILY, 18))
        self.style.map("Light.TMenubutton", background=[('active', '#B0B0B0')])
        self.style.configure("Secondary.Light.Horizontal.TScale", background=LIGHT_BG, troughcolor="#C0C0C0", sliderrelief=tk.FLAT, sliderthickness=8, bordercolor=BORDER_COLOR)
        self.style.map("Secondary.Light.Horizontal.TScale", background=[('active', LIGHT_MEDIUM_BG)], troughcolor=[('active', '#A0A0A0')])
        self.style.configure("Light.TEntry", fieldbackground=LIGHT_MEDIUM_BG, foreground=LIGHT_TEXT_DARK, bordercolor=BORDER_COLOR, borderwidth=0, relief=tk.FLAT, insertcolor=LIGHT_TEXT_DARK, padding=4, font=(FONT_FAMILY, 18))
        self.style.configure("Light.TScrollbar", troughcolor=LIGHT_BG, background=LIGHT_MEDIUM_BG, bordercolor=BORDER_COLOR, arrowcolor=LIGHT_TEXT_DARK, relief=tk.FLAT, arrowsize=14)
        self.style.map("Light.TScrollbar", background=[('active', '#A0A0A0')])

    def update_theme(self):
        theme = "MainDark.TFrame" if self.is_dark_mode.get() else "MainLight.TFrame"
        self.main_frame.configure(style=theme)
        self.chat_frame.configure(style=theme)
        self.input_area_frame.configure(style=theme)
        self.status_frame.configure(style="Secondary.TFrame" if self.is_dark_mode.get() else "Secondary.Light.TFrame")
        self.chat_list_panel.configure(style="Secondary.TFrame" if self.is_dark_mode.get() else "Secondary.Light.TFrame")
        self.settings_panel.configure(style="Secondary.TFrame" if self.is_dark_mode.get() else "Secondary.Light.TFrame")
        self.chat_canvas.configure(bg=DARK_BG if self.is_dark_mode.get() else LIGHT_BG)
        self.chat_listbox.configure(bg=LEFT_PANEL_BG if self.is_dark_mode.get() else LIGHT_LEFT_PANEL_BG, fg=LIGHT_TEXT if self.is_dark_mode.get() else LIGHT_TEXT_DARK)
        self.user_input.configure(bg=MEDIUM_DARK_BG if self.is_dark_mode.get() else LIGHT_MEDIUM_BG, fg=LIGHT_TEXT if self.is_dark_mode.get() else LIGHT_TEXT_DARK, insertbackground=LIGHT_TEXT if self.is_dark_mode.get() else LIGHT_TEXT_DARK)
        self.status_window.configure(bg=DARK_BG if self.is_dark_mode.get() else LIGHT_BG, fg=LIGHT_TEXT if self.is_dark_mode.get() else LIGHT_TEXT_DARK)
        self.tts_provider_menu.configure(style="Dark.TMenubutton" if self.is_dark_mode.get() else "Light.TMenubutton")
        self.macos_voice_menu.configure(style="Dark.TMenubutton" if self.is_dark_mode.get() else "Light.TMenubutton")
        self.sesame_speaker_entry.configure(style="Dark.TEntry" if self.is_dark_mode.get() else "Light.TEntry")
        self.send_button.configure(style="Dark.TButton" if self.is_dark_mode.get() else "Light.TButton")
        for frame in self.message_frames:
            frame.configure(style=theme)
            for widget in frame.winfo_children():
                if isinstance(widget, ttk.Label):
                    widget.configure(style="MainDark.TLabel" if self.is_dark_mode.get() else "MainLight.TLabel")
                elif isinstance(widget, ttk.Button):
                    widget.configure(style="Dark.TButton" if self.is_dark_mode.get() else "Light.TButton")

    def save_tts_config(self):
        global config
        config["tts_provider"] = self.tts_provider.get()
        config["voice_id"] = self.voice_id
        config["macos_voice"] = self.macos_voice.get()
        config["sesame_speaker"] = self.sesame_speaker.get()
        save_config(config)
        self.refresh_conversation()  # Refresh to show/hide play buttons
        # Update macOS TTS voice if changed
        if self.macos_tts and self.tts_provider.get() == "macOS Native":
            self.macos_tts.set_voice(self.macos_voice.get())

    def run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _init_ui(self):
        self.configure(bg=DARK_BG if self.is_dark_mode.get() else LIGHT_BG)
        self.config_menu = tkMenu(self, tearoff=0, bg=MEDIUM_DARK_BG, fg=LIGHT_TEXT, activebackground=SELECT_BG_COLOR, activeforeground=LIGHT_TEXT, relief=tk.FLAT, bd=0, font=(FONT_FAMILY, 18))
        self.settings_menu = tkMenu(self.config_menu, tearoff=0, bg=MEDIUM_DARK_BG, fg=LIGHT_TEXT, activebackground=SELECT_BG_COLOR, activeforeground=LIGHT_TEXT, relief=tk.FLAT, bd=0, font=(FONT_FAMILY, 18))
        self.settings_menu.add_command(label="Configure API Keys", command=self.configure_api_keys)
        self.settings_menu.add_command(label="Rename Thread", command=self.rename_selected_thread)
        self.settings_menu.add_command(label="Set ElevenLabs Voice ID", command=self.set_elevenlabs_voice_id)
        self.settings_menu.add_command(label="Set Default System Prompt", command=self.set_default_system_prompt)
        self.config_menu.add_cascade(label="Settings", menu=self.settings_menu)
        self.config(menu=self.config_menu)

        self.main_frame = ttk.Frame(self, style="MainDark.TFrame")
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Left Panel: Chat List
        self.chat_list_panel = ttk.Frame(self.main_frame, width=300, style="Secondary.TFrame")
        self.chat_list_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 2))
        self.chat_list_panel.pack_propagate(False)
        ttk.Label(self.chat_list_panel, text="Chats", style="Section.TLabel").pack(pady=(10, 5), anchor="w", padx=10)
        self.search_entry = ttk.Entry(self.chat_list_panel, style="Dark.TEntry")
        self.search_entry.pack(fill=tk.X, pady=5, padx=10)
        self.search_entry.insert(0, "Search chats...")
        self.search_entry.bind("<FocusIn>", self.clear_search_placeholder)
        self.search_entry.bind("<FocusOut>", self.restore_search_placeholder)
        self.search_entry.bind("<KeyRelease>", self.search_chats)
        self.chat_listbox = tk.Listbox(self.chat_list_panel, height=30, bg=LEFT_PANEL_BG, fg=LIGHT_TEXT,
                                       selectbackground=SELECT_BG_COLOR, selectforeground=LIGHT_TEXT,
                                       relief=tk.FLAT, bd=0, highlightthickness=0, exportselection=False, font=(FONT_FAMILY, 18))
        self.chat_listbox.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)
        self.chat_listbox.bind("<<ListboxSelect>>", self.on_chat_select)
        self.chat_listbox.bind("<Button-3>", self.show_chat_list_context_menu)
        ttk.Button(self.chat_list_panel, text="Delete Chat", command=self.delete_selected_thread, style="Dark.TButton").pack(fill=tk.X, pady=(0, 5), padx=10, side=tk.BOTTOM)
        ttk.Button(self.chat_list_panel, text="New Chat", command=self.create_new_conversation, style="Dark.TButton").pack(fill=tk.X, pady=(0, 10), padx=10, side=tk.BOTTOM)

        # Center Panel: Chat Display, Input, and Status Window
        center_panel = ttk.Frame(self.main_frame, style="MainDark.TFrame")
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))

        # Chat Canvas (Main Chat Area, Background)
        self.chat_frame = ttk.Frame(center_panel, style="MainDark.TFrame")
        self.chat_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(5, 0))
        self.chat_canvas = tk.Canvas(self.chat_frame, bg=DARK_BG, highlightthickness=0)
        self.chat_scrollbar = ttk.Scrollbar(self.chat_frame, orient=tk.VERTICAL, command=self.chat_canvas.yview)
        self.chat_scrollable_frame = ttk.Frame(self.chat_canvas, style="MainDark.TFrame")

        self.chat_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        )

        self.chat_canvas.configure(yscrollcommand=self.chat_scrollbar.set)

        self.chat_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.chat_window = self.chat_canvas.create_window((0, 0), window=self.chat_scrollable_frame, anchor="nw")

        def _configure_canvas(event):
            canvas_width = event.width
            self.chat_canvas.itemconfig(self.chat_window, width=canvas_width)
        self.chat_canvas.bind("<Configure>", _configure_canvas)

        self.chat_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Input Area (Centered Vertically in the Center Panel)
        self.input_area_frame = ttk.Frame(center_panel, style="MainDark.TFrame")
        self.input_area_frame.place(relx=0.5, rely=0.5, relwidth=1.0, anchor="center")
        self.user_input = scrolledtext.ScrolledText(
            self.input_area_frame, height=3, bg=MEDIUM_DARK_BG, fg=LIGHT_TEXT,
            insertbackground=LIGHT_TEXT, wrap=tk.WORD, relief=tk.FLAT,
            bd=0, highlightthickness=0, font=(FONT_FAMILY, 18), padx=10, pady=5,
            selectbackground=SELECT_BG_COLOR, insertwidth=4
        )
        self.user_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.user_input.insert("1.0", "Type a message...")
        self.user_input.bind("<FocusIn>", self.clear_placeholder_text)
        self.user_input.bind("<FocusOut>", self.restore_placeholder_text)
        self.user_input.bind("<Return>", self.send_message_on_enter)
        self.user_input.bind("<Shift-Return>", self.add_newline)
        self.send_button = ttk.Button(self.input_area_frame, text="▶", width=2, command=self.send_message, style="Dark.TButton")
        self.send_button.pack(side=tk.RIGHT, padx=5)

        # Status Window (Bottom of Center Panel)
        self.status_frame = ttk.Frame(center_panel, style="MainDark.TFrame")
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))
        self.status_window = scrolledtext.ScrolledText(self.status_frame, height=5, wrap=tk.WORD, state=tk.NORMAL,
                                                       bg=DARK_BG, fg=LIGHT_TEXT, relief=tk.FLAT, bd=0,
                                                       highlightthickness=0, font=(FONT_FAMILY, 16), padx=14, pady=14,
                                                       selectbackground=SELECT_BG_COLOR)
        self.status_window.pack(fill=tk.X, expand=True)
        self.status_window.tag_configure("system", foreground=SYSTEM_TEXT, font=(FONT_FAMILY, 16))
        self.status_window.tag_configure("error", foreground=ERROR_TEXT, font=(FONT_FAMILY, 16, "bold"))

        # Right Panel: Settings
        self.settings_panel = ttk.Frame(self.main_frame, width=300, style="Secondary.TFrame")
        self.settings_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 0))
        self.settings_panel.pack_propagate(False)

        controls_frame = self.settings_panel
        ttk.Label(controls_frame, text="Model", style="Section.TLabel").pack(pady=(10, 5), anchor="w", padx=10)
        self.model_var = tk.StringVar(self)
        self.model_menu = ttk.OptionMenu(controls_frame, self.model_var, "Loading models...", style="Dark.TMenubutton")
        self.model_menu.pack(fill=tk.X, pady=3, padx=10)
        self.model_var.trace_add("write", self.on_model_change)
        ttk.Button(controls_frame, text="Refresh Models", command=self.refresh_models, style="Dark.TButton").pack(fill=tk.X, pady=(0, 10), padx=10)

        ttk.Label(controls_frame, text="Chat Mode", style="Section.TLabel").pack(pady=(10, 5), anchor="w", padx=10)
        ttk.Label(controls_frame, text="Personality", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        self.chat_mode_menu = ttk.OptionMenu(controls_frame, self.current_chat_mode, self.current_chat_mode.get(), *self.chat_modes, style="Dark.TMenubutton")
        self.chat_mode_menu.pack(fill=tk.X, pady=3, padx=10)
        self.current_chat_mode.trace_add("write", self.on_chat_mode_change)

        ttk.Label(controls_frame, text="Theme", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        ttk.Checkbutton(controls_frame, text="Dark Mode", variable=self.is_dark_mode, command=self.update_theme, style="Dark.TButton").pack(fill=tk.X, pady=3, padx=10)

        # TTS Settings
        ttk.Label(controls_frame, text="TTS Settings", style="Section.TLabel").pack(pady=(10, 5), anchor="w", padx=10)
        ttk.Label(controls_frame, text="TTS Provider", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        tts_options = ["None"]
        if elevenlabs_api_key:
            tts_options.append("ElevenLabs")
        if MACOS_TTS_AVAILABLE and platform.system() == "Darwin":
            tts_options.append("macOS Native")
        # Disabled Sesame CSM for now
        # if SESAME_CSM_AVAILABLE:
        #     tts_options.append("Sesame CSM")
        self.tts_provider_menu = ttk.OptionMenu(controls_frame, self.tts_provider, self.tts_provider.get(), *tts_options, command=lambda _: self.save_tts_config(), style="Dark.TMenubutton")
        self.tts_provider_menu.pack(fill=tk.X, pady=3, padx=10)

        # ElevenLabs Settings
        self.elevenlabs_settings_frame = ttk.Frame(controls_frame, style="Secondary.TFrame")
        ttk.Label(self.elevenlabs_settings_frame, text="Voice Stability", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        stability_frame = ttk.Frame(self.elevenlabs_settings_frame, style="Secondary.TFrame")
        stability_frame.pack(fill=tk.X, pady=3, padx=10)
        self.stability_var = tk.DoubleVar(value=0.5)
        self.stability_slider = ttk.Scale(stability_frame, from_=0.0, to_=1.0, orient=tk.HORIZONTAL, variable=self.stability_var, command=lambda v: self.stability_display.config(text=f"{self.stability_var.get():.2f}"), style="Secondary.Dark.Horizontal.TScale")
        self.stability_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.stability_display = ttk.Label(stability_frame, text=f"{self.stability_var.get():.2f}", style="Secondary.Dark.TLabel", font=(FONT_FAMILY, 16))
        self.stability_display.pack(side=tk.RIGHT, padx=5)

        ttk.Label(self.elevenlabs_settings_frame, text="Voice Similarity", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        similarity_frame = ttk.Frame(self.elevenlabs_settings_frame, style="Secondary.TFrame")
        similarity_frame.pack(fill=tk.X, pady=3, padx=10)
        self.similarity_var = tk.DoubleVar(value=0.5)
        self.similarity_slider = ttk.Scale(similarity_frame, from_=0.0, to_=1.0, orient=tk.HORIZONTAL, variable=self.similarity_var, command=lambda v: self.similarity_display.config(text=f"{self.similarity_var.get():.2f}"), style="Secondary.Dark.Horizontal.TScale")
        self.similarity_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.similarity_display = ttk.Label(similarity_frame, text=f"{self.similarity_var.get():.2f}", style="Secondary.Dark.TLabel", font=(FONT_FAMILY, 16))
        self.similarity_display.pack(side=tk.RIGHT, padx=5)

        # macOS Native Settings
        self.macos_settings_frame = ttk.Frame(controls_frame, style="Secondary.TFrame")
        ttk.Label(self.macos_settings_frame, text="macOS Voice", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        macos_voices = self.macos_voices if hasattr(self, 'macos_voices') else ["Alex"]
        self.macos_voice_menu = ttk.OptionMenu(self.macos_settings_frame, self.macos_voice, self.macos_voice.get(), *macos_voices, command=lambda _: self.save_tts_config(), style="Dark.TMenubutton")
        self.macos_voice_menu.pack(fill=tk.X, pady=3, padx=10)

        # Sesame CSM Settings
        self.sesame_settings_frame = ttk.Frame(controls_frame, style="Secondary.TFrame")
        ttk.Label(self.sesame_settings_frame, text="Sesame Speaker ID", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        self.sesame_speaker_entry = ttk.Entry(self.sesame_settings_frame, textvariable=self.sesame_speaker, style="Dark.TEntry")
        self.sesame_speaker_entry.pack(fill=tk.X, pady=3, padx=10)
        ttk.Button(self.sesame_settings_frame, text="Save Speaker ID", command=self.save_tts_config, style="Dark.TButton").pack(fill=tk.X, pady=(0, 10), padx=10)

        # Other Settings
        ttk.Label(controls_frame, text="Temp", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        temp_frame = ttk.Frame(controls_frame, style="Secondary.TFrame")
        temp_frame.pack(fill=tk.X, pady=3, padx=10)
        self.temperature_var = tk.DoubleVar(value=0.7)
        self.temp_slider = ttk.Scale(temp_frame, from_=0, to_=1, orient=tk.HORIZONTAL, variable=self.temperature_var, command=self.update_temp_display, style="Secondary.Dark.Horizontal.TScale")
        self.temp_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.temp_display = ttk.Label(temp_frame, text=f"{self.temperature_var.get():.2f}", style="Secondary.Dark.TLabel", font=(FONT_FAMILY, 16))
        self.temp_display.pack(side=tk.RIGHT, padx=5)

        ttk.Label(controls_frame, text="Max Tokens", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        self.max_tokens_var = tk.IntVar(value=1024)
        self.max_tokens_entry = ttk.Entry(controls_frame, textvariable=self.max_tokens_var, style="Dark.TEntry")
        self.max_tokens_entry.pack(fill=tk.X, pady=3, padx=10)
        max_tokens_presets_options = ["1024", "2048", "4096", "8192", "16000", "Custom"]
        self.max_tokens_preset_var = tk.StringVar(value="Custom")
        self.max_tokens_preset_menu = ttk.OptionMenu(controls_frame, self.max_tokens_preset_var, self.max_tokens_preset_var.get(), *max_tokens_presets_options, command=self.set_max_tokens_from_preset, style="Dark.TMenubutton")
        self.max_tokens_preset_menu.pack(fill=tk.X, pady=3, padx=10)

        ttk.Label(controls_frame, text="Context Limit", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        context_options = ["Last 10 Messages", "Last 20 Messages", "Last 50 Messages", "No Limit"]
        self.context_limit_var = tk.StringVar(value="Last 50 Messages")
        ttk.OptionMenu(controls_frame, self.context_limit_var, self.context_limit_var.get(), *context_options, style="Dark.TMenubutton").pack(fill=tk.X, pady=3, padx=10)

        ttk.Label(controls_frame, text="Presence", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        presence_frame = ttk.Frame(controls_frame, style="Secondary.TFrame")
        presence_frame.pack(fill=tk.X, pady=3, padx=10)
        self.presence_penalty_var = tk.DoubleVar(value=0.0)
        self.presence_penalty_slider = ttk.Scale(presence_frame, from_=-2.0, to_=2.0, orient=tk.HORIZONTAL, variable=self.presence_penalty_var, command=lambda v: self.presence_display.config(text=f"{self.presence_penalty_var.get():.1f}"), style="Secondary.Dark.Horizontal.TScale")
        self.presence_penalty_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.presence_display = ttk.Label(presence_frame, text=f"{self.presence_penalty_var.get():.1f}", style="Secondary.Dark.TLabel", font=(FONT_FAMILY, 16))
        self.presence_display.pack(side=tk.RIGHT, padx=5)
        ttk.Button(controls_frame, text="Reset", command=self.reset_presence_penalty, style="Dark.TButton").pack(fill=tk.X, pady=3, padx=10)

        ttk.Label(controls_frame, text="Frequency", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        frequency_frame = ttk.Frame(controls_frame, style="Secondary.TFrame")
        frequency_frame.pack(fill=tk.X, pady=3, padx=10)
        self.frequency_penalty_var = tk.DoubleVar(value=0.0)
        self.frequency_penalty_slider = ttk.Scale(frequency_frame, from_=-2.0, to_=2.0, orient=tk.HORIZONTAL, variable=self.frequency_penalty_var, command=lambda v: self.frequency_display.config(text=f"{self.frequency_penalty_var.get():.1f}"), style="Secondary.Dark.Horizontal.TScale")
        self.frequency_penalty_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.frequency_display = ttk.Label(frequency_frame, text=f"{self.frequency_penalty_var.get():.1f}", style="Secondary.Dark.TLabel", font=(FONT_FAMILY, 16))
        self.frequency_display.pack(side=tk.RIGHT, padx=5)
        ttk.Button(controls_frame, text="Reset", command=self.reset_frequency_penalty, style="Dark.TButton").pack(fill=tk.X, pady=3, padx=10)

        ttk.Label(controls_frame, text="Top P", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        top_p_frame = ttk.Frame(controls_frame, style="Secondary.TFrame")
        top_p_frame.pack(fill=tk.X, pady=3, padx=10)
        self.top_p_var = tk.DoubleVar(value=1.0)
        self.top_p_slider = ttk.Scale(top_p_frame, from_=0.0, to_=1.0, orient=tk.HORIZONTAL, variable=self.top_p_var, command=lambda v: self.top_p_display.config(text=f"{self.top_p_var.get():.2f}"), style="Secondary.Dark.Horizontal.TScale")
        self.top_p_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.top_p_display = ttk.Label(top_p_frame, text=f"{self.top_p_var.get():.2f}", style="Secondary.Dark.TLabel", font=(FONT_FAMILY, 16))
        self.top_p_display.pack(side=tk.RIGHT, padx=5)
        ttk.Button(controls_frame, text="Reset", command=self.reset_top_p, style="Dark.TButton").pack(fill=tk.X, pady=3, padx=10)

        ttk.Label(controls_frame, text="Top K", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        self.top_k_var = tk.IntVar(value=40)
        self.top_k_entry = ttk.Entry(controls_frame, textvariable=self.top_k_var, style="Dark.TEntry")
        self.top_k_entry.pack(fill=tk.X, pady=3, padx=10)
        ttk.Button(controls_frame, text="Reset", command=self.reset_top_k, style="Dark.TButton").pack(fill=tk.X, pady=3, padx=10)

        ttk.Label(controls_frame, text="Reasoning", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        reasoning_options = ["None", "Low", "Medium", "High"]
        self.reasoning_effort_var = tk.StringVar(value="Medium")
        self.reasoning_effort_menu = ttk.OptionMenu(controls_frame, self.reasoning_effort_var, self.reasoning_effort_var.get(), *reasoning_options, style="Dark.TMenubutton")
        self.reasoning_effort_menu.pack(fill=tk.X, pady=3, padx=10)

        ttk.Label(controls_frame, text="System Prompt", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        self.system_prompt_text_widget = scrolledtext.ScrolledText(controls_frame, height=6, wrap=tk.WORD,
                                                                 bg=MEDIUM_DARK_BG, fg=LIGHT_TEXT, insertbackground=LIGHT_TEXT,
                                                                 relief=tk.FLAT, bd=0, font=(FONT_FAMILY, 18), selectbackground=SELECT_BG_COLOR)
        self.system_prompt_text_widget.pack(fill=tk.X, pady=3, padx=10)
        self.refresh_button = ttk.Button(controls_frame, text="Refresh Models", command=self.load_initial_models, style="Dark.TButton")
        self.refresh_button.pack(pady=10, fill=tk.X, padx=10)

        # Initially hide provider-specific settings
        self.update_tts_settings_visibility()

    def update_tts_settings_visibility(self):
        provider = self.tts_provider.get()
        if provider == "ElevenLabs":
            self.elevenlabs_settings_frame.pack(fill=tk.X, pady=3, padx=10)
        else:
            self.elevenlabs_settings_frame.pack_forget()
        if provider == "macOS Native":
            self.macos_settings_frame.pack(fill=tk.X, pady=3, padx=10)
        else:
            self.macos_settings_frame.pack_forget()
        # Disabled Sesame CSM for now
        # if provider == "Sesame CSM":
        #     self.sesame_settings_frame.pack(fill=tk.X, pady=3, padx=10)
        # else:
        #     self.sesame_settings_frame.pack_forget()

    def _on_mousewheel(self, event):
        self.chat_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def set_elevenlabs_voice_id(self):
        global voice_id, config
        new_voice_id = simpledialog.askstring("ElevenLabs Voice ID", "Enter the global ElevenLabs Voice ID:", initialvalue=self.voice_id or "", parent=self)
        if new_voice_id is not None:
            self.voice_id = new_voice_id
            config["voice_id"] = new_voice_id
            save_config(config)
            self.add_log_message(f"Global Voice ID set to: {new_voice_id}", "system")
            self.refresh_conversation()  # Refresh to update play buttons

    def set_default_system_prompt(self):
        global config
        new_default_prompt = simpledialog.askstring("Default System Prompt", "Enter the default system prompt for new conversations:", initialvalue=config.get("default_system_prompt", "You are a helpful AI assistant."), parent=self)
        if new_default_prompt is not None:
            config["default_system_prompt"] = new_default_prompt
            save_config(config)
            self.add_log_message("Default system prompt updated.", "system")

    def rename_selected_thread(self):
        if self.current_conversation_id is None:
            messagebox.showwarning("No Selection", "Please select a conversation to rename.")
            return
        new_title = simpledialog.askstring("Rename Thread", "Enter new thread name:", parent=self)
        if new_title:
            update_conversation_title_in_db(self.current_conversation_id, new_title)
            self.refresh_chat_list()

    def load_or_create_conversation(self):
        conversations = fetch_conversations_from_db()
        if conversations:
            self.current_conversation_id = conversations[0][0]
            self.on_chat_select(None)
        else:
            self.create_new_conversation()
        self.refresh_chat_list()

    def create_new_conversation(self):
        system_prompt = self.system_prompt_text_widget.get(1.0, tk.END).strip()
        if not system_prompt:
            system_prompt = config.get("default_system_prompt", "You are a helpful AI assistant.")
        model_selection = self.model_var.get()
        current_model = "" if not model_selection or model_selection == "Loading models..." else model_selection
        new_title = f"New Chat {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        self.current_conversation_id = create_conversation_in_db(title=new_title, model=current_model, system_prompt=system_prompt)
        for frame in self.message_frames:
            frame.destroy()
        self.message_frames = []
        self.conversation_log = []
        self.refresh_chat_list()

    def refresh_chat_list(self):
        self.chat_listbox.delete(0, tk.END)
        conversations = fetch_conversations_from_db()
        self.conversation_id_map.clear()
        for index, (conv_id, title, _) in enumerate(conversations):
            display_title = title if title else f"Conversation {conv_id}"
            self.chat_listbox.insert(tk.END, display_title)
            self.conversation_id_map[index] = conv_id
            if conv_id == self.current_conversation_id:
                self.chat_listbox.selection_clear(0, tk.END)
                self.chat_listbox.selection_set(index)
                self.chat_listbox.activate(index)
                self.chat_listbox.see(index)

    def search_chats(self, event=None):
        query = self.search_entry.get().strip().lower()
        if query == "search chats...":
            query = ""
        self.chat_listbox.delete(0, tk.END)
        self.conversation_id_map.clear()
        conversations = fetch_conversations_from_db()
        for index, (conv_id, title, _) in enumerate(conversations):
            if query in title.lower() or not query:
                display_title = title if title else f"Conversation {conv_id}"
                self.chat_listbox.insert(tk.END, display_title)
                self.conversation_id_map[index] = conv_id
                if conv_id == self.current_conversation_id:
                    self.chat_listbox.selection_set(index)

    def on_chat_select(self, event):
        if not self.chat_listbox.curselection():
            return
        selected_index = self.chat_listbox.curselection()[0]
        if selected_index not in self.conversation_id_map:
            return
        conv_id = self.conversation_id_map[selected_index]
        if conv_id == self.current_conversation_id and event is not None:
            return
        self.current_conversation_id = conv_id
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT llm_model, system_prompt FROM conversations WHERE id = ?", (self.current_conversation_id,))
        conv_data = cursor.fetchone()
        conn.close()
        if conv_data:
            loaded_model, loaded_system_prompt = conv_data
            if loaded_model and loaded_model != "Loading models..." and self.model_var.get() != loaded_model:
                if self.available_models and loaded_model in self.available_models:
                    self.model_var.set(loaded_model)
            if loaded_system_prompt:
                self.system_prompt_text_widget.delete(1.0, tk.END)
                self.system_prompt_text_widget.insert(tk.END, loaded_system_prompt)
        
        for frame in self.message_frames:
            frame.destroy()
        self.message_frames = []
        self.status_window.delete(1.0, tk.END)
        
        messages = fetch_messages_from_db(self.current_conversation_id)
        self.conversation_log = []
        for role, content, timestamp_str in messages:
            self.add_log_message(content, role, timestamp_str)

    def update_conversation_title_from_message(self, message_content):
        if not self.current_conversation_id:
            return
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT title FROM conversations WHERE id = ?", (self.current_conversation_id,))
        current_title_tuple = cursor.fetchone()
        conn.close()
        if current_title_tuple:
            current_title = current_title_tuple[0]
            if current_title.startswith("New Chat"):
                words = message_content.split()
                potential_title = " ".join(words[:5])
                if len(potential_title) > 50:
                    potential_title = potential_title[:47] + "..."
                if potential_title:
                    update_conversation_title_in_db(self.current_conversation_id, potential_title)
                    self.refresh_chat_list()

    def show_chat_list_context_menu(self, event):
        if not self.chat_listbox.curselection():
            return
        selected_index = self.chat_listbox.curselection()[0]
        conv_id = self.conversation_id_map.get(selected_index)
        if conv_id is None:
            return
        context_menu = tkMenu(self, tearoff=0)
        context_menu.add_command(label="Edit Title", command=lambda: self.edit_conversation_title(conv_id, selected_index))
        context_menu.add_command(label="Delete Chat", command=lambda: self.delete_conversation(conv_id))
        context_menu.tk_popup(event.x_root, event.y_root)

    def edit_conversation_title(self, conv_id, listbox_index):
        current_title = self.chat_listbox.get(listbox_index)
        new_title = simpledialog.askstring("Edit Title", "Enter new title:", initialvalue=current_title, parent=self)
        if new_title and new_title.strip():
            update_conversation_title_in_db(conv_id, new_title.strip())
            self.refresh_chat_list()

    def delete_conversation(self, conv_id):
        if not messagebox.askyesno("Delete Chat", "Are you sure you want to delete this chat and all its messages? This cannot be undone.", parent=self):
            return
        delete_conversation_in_db(conv_id)
        if self.current_conversation_id == conv_id:
            self.current_conversation_id = None
            for frame in self.message_frames:
                frame.destroy()
            self.message_frames = []
            self.conversation_log = []
            self.status_window.delete(1.0, tk.END)
            self.load_or_create_conversation()
        self.refresh_chat_list()

    def update_temp_display(self, value):
        self.temp_display.config(text=f"{float(value):.2f}")

    def set_max_tokens_from_preset(self, value):
        if value != "Custom":
            try:
                self.max_tokens_var.set(int(value))
            except ValueError:
                print(f"Error: Could not convert preset '{value}' to int.")

    def reset_presence_penalty(self):
        self.presence_penalty_var.set(0.0)
        self.presence_display.config(text=f"{self.presence_penalty_var.get():.1f}")

    def reset_frequency_penalty(self):
        self.frequency_penalty_var.set(0.0)
        self.frequency_display.config(text=f"{self.frequency_penalty_var.get():.1f}")

    def reset_top_p(self):
        self.top_p_var.set(1.0)
        self.top_p_display.config(text=f"{self.top_p_var.get():.2f}")

    def reset_top_k(self):
        self.top_k_var.set(40)

    def create_tooltip(self, widget, text):
        tooltip = tk.Toplevel(widget)
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{widget.winfo_rootx()+20}+{widget.winfo_rooty()+20}")
        label = ttk.Label(tooltip, text=text, background="#FFFFE0", relief=tk.SOLID, borderwidth=1, font=(FONT_FAMILY, 14))
        label.pack()
        tooltip.withdraw()

        def show(event):
            tooltip.deiconify()
        def hide(event):
            tooltip.withdraw()

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)

    def add_log_message(self, message_text, level="system", timestamp_str=None):
        if timestamp_str is None:
            timestamp = datetime.now().strftime("[%H:%M:%S]")
        else:
            try:
                timestamp = datetime.fromisoformat(timestamp_str).strftime("[%H:%M:%S]")
            except ValueError:
                timestamp = f"[{timestamp_str}]"
        
        if level in ["system", "error"]:
            self.status_window.config(state=tk.NORMAL)
            self.status_window.insert(tk.END, f"\n{timestamp} {level.capitalize()}: {message_text}", level)
            self.status_window.insert(tk.END, "\n")
            self.status_window.see(tk.END)
            self.status_window.config(state=tk.NORMAL)
            return

        message_frame = ttk.Frame(self.chat_scrollable_frame, style="MainDark.TFrame" if self.is_dark_mode.get() else "MainLight.TFrame")
        message_frame.pack(fill=tk.X, padx=15, pady=10, anchor="w")
        self.message_frames.append(message_frame)
        if len(self.message_frames) > 100:
            oldest_frame = self.message_frames.pop(0)
            oldest_frame.destroy()

        message_label = ttk.Label(
            message_frame,
            text=f"{level.capitalize()}: {message_text}",
            style="MainDark.TLabel" if self.is_dark_mode.get() else "MainLight.TLabel",
            wraplength=900,
            justify=tk.LEFT,
            foreground={
                "user": ACCENT_COLOR_USER if self.is_dark_mode.get() else LIGHT_ACCENT_USER,
                "assistant": ACCENT_COLOR_ASSISTANT if self.is_dark_mode.get() else LIGHT_ACCENT_ASSISTANT,
                "system": SYSTEM_TEXT,
                "error": ERROR_TEXT
            }.get(level, LIGHT_TEXT if self.is_dark_mode.get() else LIGHT_TEXT_DARK),
            font=(FONT_FAMILY, 18, "bold" if level == "user" else "normal")
        )
        message_label.pack(side=tk.LEFT, anchor="w")
        self.create_tooltip(message_label, timestamp)

        button_frame = ttk.Frame(message_frame, style="MainDark.TFrame" if self.is_dark_mode.get() else "MainLight.TFrame")
        button_frame.pack(side=tk.RIGHT, anchor="e")

        if level == "assistant":  # Actions only for assistant messages
            # Show play button based on TTS provider
            can_play = False
            provider = self.tts_provider.get()
            if provider == "ElevenLabs" and self.voice_id:
                can_play = True
            elif provider == "macOS Native" and self.macos_tts and self.macos_tts.synthesizer:
                can_play = True
            # Disabled Sesame CSM for now
            # elif provider == "Sesame CSM" and self.sesame_csm and self.sesame_csm.generator:
            #     can_play = True

            if can_play:
                play_button = ttk.Button(
                    button_frame,
                    text="▷",
                    command=lambda: self.play_message(message_text),
                    style="Dark.TButton" if self.is_dark_mode.get() else "Light.TButton",
                    width=1
                )
                play_button.pack(side=tk.LEFT, padx=3)

            copy_button = ttk.Button(
                button_frame,
                text="📋",
                command=lambda: pyperclip.copy(message_text),
                style="Dark.TButton" if self.is_dark_mode.get() else "Light.TButton",
                width=1
            )
            copy_button.pack(side=tk.LEFT, padx=3)

            refresh_button = ttk.Button(
                button_frame,
                text="↻",
                command=self.refresh_conversation,
                style="Dark.TButton" if self.is_dark_mode.get() else "Light.TButton",
                width=1
            )
            refresh_button.pack(side=tk.LEFT, padx=3)

            thumbs_up = ttk.Button(
                button_frame,
                text="👍",
                command=lambda: self.add_log_message("👍 Reaction added!", "system"),
                style="Dark.TButton" if self.is_dark_mode.get() else "Light.TButton",
                width=1
            )
            thumbs_up.pack(side=tk.LEFT, padx=3)

            thumbs_down = ttk.Button(
                button_frame,
                text="👎",
                command=lambda: self.add_log_message("👎 Reaction added!", "system"),
                style="Dark.TButton" if self.is_dark_mode.get() else "Light.TButton",
                width=1
            )
            thumbs_down.pack(side=tk.LEFT, padx=3)

        if level in ["user", "assistant"]:
            self.conversation_log.append({"role": level, "content": message_text})
        if self.current_conversation_id and level in ["user", "assistant"]:
            add_message_to_db(self.current_conversation_id, level, message_text)
            if level == "user":
                self.update_conversation_title_from_message(message_text)

        self.chat_canvas.update_idletasks()
        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        self.chat_canvas.yview_moveto(1.0)

    def edit_message(self, message_frame, message_label, original_text, role):
        message_label.pack_forget()
        edit_text = Text(message_frame, height=3, width=50, bg=MEDIUM_DARK_BG if self.is_dark_mode.get() else LIGHT_MEDIUM_BG, fg=LIGHT_TEXT if self.is_dark_mode.get() else LIGHT_TEXT_DARK, font=(FONT_FAMILY, 18), wrap=tk.WORD)
        edit_text.insert(tk.END, original_text)
        edit_text.pack(side=tk.LEFT, anchor="w")

        def save_edit():
            new_text = edit_text.get("1.0", tk.END).strip()
            edit_text.pack_forget()
            save_button.pack_forget()
            message_label.config(text=f"{role.capitalize()}: {new_text}")
            message_label.pack(side=tk.LEFT, anchor="w")
            if self.current_conversation_id:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("UPDATE messages SET content = ? WHERE conversation_id = ? AND role = ? AND content = ?",
                               (new_text, self.current_conversation_id, role, original_text))
                conn.commit()
                conn.close()
                self.conversation_log[-1]["content"] = new_text

        save_button = ttk.Button(
            message_frame,
            text="Save",
            command=save_edit,
            style="Dark.TButton" if self.is_dark_mode.get() else "Light.TButton"
        )
        save_button.pack(side=tk.LEFT, padx=5)

    def refresh_conversation(self):
        if self.current_conversation_id:
            self.on_chat_select(None)

    def play_message(self, message_text):
        provider = self.tts_provider.get()
        if provider == "None":
            self.add_log_message("TTS is disabled. Select a provider in the settings to play audio.", "system")
            return
        elif provider == "ElevenLabs":
            asyncio.run_coroutine_threadsafe(
                generate_and_play_audio_elevenlabs(message_text, self.voice_id, self.stability_var.get(), self.similarity_var.get(), self.add_log_message),
                self.loop
            )
        # Disabled Sesame CSM for now
        # elif provider == "Sesame CSM" and self.sesame_csm:
        #     context = self.sesame_csm.create_context(self.conversation_log)
        #     asyncio.run_coroutine_threadsafe(
        #         self.sesame_csm.generate_and_play_audio(message_text, speaker=self.sesame_speaker.get(), context=context),
        #         self.loop
        #     )
        elif provider == "macOS Native" and self.macos_tts:
            asyncio.run_coroutine_threadsafe(
                self.macos_tts.generate_and_play_audio(message_text),
                self.loop
            )
        else:
            self.add_log_message(f"TTS provider {provider} is not available.", "error")

    def load_initial_models(self):
        self.add_log_message("Fetching models...", "system")
        self.refresh_button.config(state=tk.DISABLED, text="Refreshing...")
        self.after(100, self._fetch_all_models_thread)

    def _fetch_all_models_thread(self):
        self.model_groups = {
            'OpenAI': [], 'OpenRouter': [], 'XAI': [], 'Anthropic': [], 'HuggingFace': [],
            'Google': [], 'Perplexity': [], 'Together': [], 'Groq': [], 'Pi': [],
            'Mistral': [], 'DeepSeek': []
        }
        if openai_api_key:
            openai_models_list = fetch_openai_models(openai_api_key)
            if openai_models_list:
                self.add_log_message(f"Fetched {len(openai_models_list)} OpenAI models", "system")
                self.model_groups['OpenAI'] = sorted(openai_models_list)
            else:
                self.add_log_message("No/Error OpenAI models", "error")
        if openrouter_api_key:
            openrouter_models_list = fetch_openrouter_models(openrouter_api_key)
            if openrouter_models_list:
                self.add_log_message(f"Fetched {len(openrouter_models_list)} OpenRouter models", "system")
                self.model_groups['OpenRouter'] = sorted(openrouter_models_list)
            else:
                self.add_log_message("No/Error OpenRouter models", "error")
        if xai_api_key:
            xai_models_list = fetch_xai_models(xai_api_key)
            if xai_models_list:
                self.add_log_message(f"Fetched {len(xai_models_list)} XAI models", "system")
                self.model_groups['XAI'] = sorted(xai_models_list)
            else:
                self.add_log_message("No/Error XAI models", "error")
        if anthropic_api_key:
            anthropic_models_list = fetch_anthropic_models(anthropic_api_key)
            if anthropic_models_list:
                self.add_log_message(f"Fetched {len(anthropic_models_list)} Anthropic models", "system")
                self.model_groups['Anthropic'] = sorted(anthropic_models_list)
            else:
                self.add_log_message("No/Error Anthropic models", "error")
        if huggingface_api_key:
            huggingface_models_list = fetch_huggingface_models(huggingface_api_key)
            if huggingface_models_list:
                self.add_log_message(f"Fetched {len(huggingface_models_list)} HuggingFace models", "system")
                self.model_groups['HuggingFace'] = sorted(huggingface_models_list)
            else:
                self.add_log_message("No/Error HuggingFace models", "error")
        if google_api_key:
            google_models_list = fetch_google_models(google_api_key)
            if google_models_list:
                self.add_log_message(f"Fetched {len(google_models_list)} Google Gemini models", "system")
                self.model_groups['Google'] = sorted(google_models_list)
            else:
                self.add_log_message("No/Error Google Gemini models", "error")
        if perplexity_api_key:
            perplexity_models_list = fetch_perplexity_models(perplexity_api_key)
            if perplexity_models_list:
                self.add_log_message(f"Fetched {len(perplexity_models_list)} Perplexity models", "system")
                self.model_groups['Perplexity'] = sorted(perplexity_models_list)
            else:
                self.add_log_message("No/Error Perplexity models", "error")
        if together_api_key:
            together_models_list = fetch_together_models(together_api_key)
            if together_models_list:
                self.add_log_message(f"Fetched {len(together_models_list)} Together.ai models", "system")
                self.model_groups['Together'] = sorted(together_models_list)
            else:
                self.add_log_message("No/Error Together.ai models", "error")
        if groq_api_key:
            groq_models_list = fetch_groq_models(groq_api_key)
            if groq_models_list:
                self.add_log_message(f"Fetched {len(groq_models_list)} Groq models", "system")
                self.model_groups['Groq'] = sorted(groq_models_list)
            else:
                self.add_log_message("No/Error Groq models", "error")
        if pi_api_key:
            pi_models_list = fetch_pi_models(pi_api_key)
            if pi_models_list:
                self.add_log_message(f"Fetched {len(pi_models_list)} Pi.ai models", "system")
                self.model_groups['Pi'] = sorted(pi_models_list)
            else:
                self.add_log_message("No/Error Pi.ai models", "error")
        if mistral_api_key:
            mistral_models_list = fetch_mistral_models(mistral_api_key)
            if mistral_models_list:
                self.add_log_message(f"Fetched {len(mistral_models_list)} Mistral models", "system")
                self.model_groups['Mistral'] = sorted(mistral_models_list)
            else:
                self.add_log_message("No/Error Mistral models", "error")
        if deepseek_api_key:
            deepseek_models_list = fetch_deepseek_models(deepseek_api_key)
            if deepseek_models_list:
                self.add_log_message(f"Fetched {len(deepseek_models_list)} DeepSeek models", "system")
                self.model_groups['DeepSeek'] = sorted(deepseek_models_list)
            else:
                self.add_log_message("No/Error DeepSeek models", "error")
        self.available_models = []
        for provider in self.model_groups.keys():
            if provider in self.model_groups and self.model_groups[provider]:
                for model_id_str in self.model_groups[provider]:
                    self.available_models.append(f"{provider}: {model_id_str}")
        if not self.available_models:
            self.add_log_message("No models available from any provider.", "error")
        self.after(0, self.update_model_list)
        self.refresh_button.config(state=tk.NORMAL, text="Refresh Models")

    def update_model_list(self):
        menu = self.model_menu['menu']
        menu.delete(0, 'end')
        current_selection = self.model_var.get()
        new_selection = None
        if not self.available_models:
            menu.add_command(label="No models available", command=tk._setit(self.model_var, "No models available"))
            new_selection = "No models available"
        else:
            for model_id_str in self.available_models:
                menu.add_command(label=model_id_str, command=tk._setit(self.model_var, model_id_str))
            if current_selection in self.available_models:
                new_selection = current_selection
            else:
                new_selection = self.available_models[0]
        if new_selection and self.model_var.get() != new_selection:
            self.model_var.set(new_selection)

    def get_system_prompt(self):
        custom_prompt = self.system_prompt_text_widget.get("1.0", tk.END).strip()
        if custom_prompt:
            return custom_prompt
        mode = self.current_chat_mode.get()
        prompts = {
            "Normal": "You are a helpful AI assistant.",
            "Assistant": "You are a professional assistant providing detailed and accurate responses.",
            "Code Assistant": "You are a coding expert. Provide code snippets and explanations.",
            "Sarcastic Assistant": "You are a witty and sarcastic assistant, still helpful but with an edge."
        }
        return prompts.get(mode, config.get("default_system_prompt", "You are a helpful AI assistant."))

    def get_context_limit_messages(self):
        context_limit = self.context_limit_var.get()
        if context_limit == "No Limit":
            return self.conversation_log
        try:
            num_messages = int(context_limit.split()[1])
            return self.conversation_log[-num_messages:]
        except:
            return self.conversation_log[-50:]

    def send_message(self):
        user_text = self.user_input.get("1.0", tk.END).strip()
        if not user_text or self.placeholder_visible:
            return
        self.add_log_message(user_text, "user")
        self.user_input.delete("1.0", tk.END)
        self.after(100, self.process_ai_response)

    def send_message_on_enter(self, event):
        self.send_message()
        return 'break'

    def refresh_models(self):
        self.add_log_message("Refreshing models...", "system")
        self.refresh_button.config(state=tk.DISABLED, text="Refreshing...")
        self.after(100, self._fetch_all_models_thread)

    def delete_selected_thread(self):
        selection = self.chat_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a conversation thread to delete.")
            return
        conv_index = selection[0]
        conv_id = self.conversation_id_map.get(conv_index)
        if conv_id and messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this conversation thread?"):
            delete_conversation_in_db(conv_id)
            if conv_id == self.current_conversation_id:
                self.current_conversation_id = None
            del self.conversation_id_map[conv_index]
            new_map = {}
            for idx in range(self.chat_listbox.size()):
                if idx < conv_index:
                    new_map[idx] = self.conversation_id_map.get(idx)
                elif idx > conv_index and (idx - 1) in self.conversation_id_map:
                    new_map[idx - 1] = self.conversation_id_map.get(idx)
            self.conversation_id_map = new_map
            self.refresh_chat_list()
            self.load_or_create_conversation()

    def clear_search_placeholder(self, event=None):
        if self.search_entry.get() == "Search chats...":
            self.search_entry.delete(0, tk.END)
        return "break"

    def restore_search_placeholder(self, event=None):
        if not self.search_entry.get().strip():
            self.search_entry.insert(0, "Search chats...")
        return "break"

    def clear_placeholder_text(self, event=None):
        if self.placeholder_visible:
            self.user_input.delete("1.0", tk.END)
            self.placeholder_visible = False
        return "break"

    def restore_placeholder_text(self, event=None):
        if not self.user_input.get("1.0", tk.END).strip():
            self.user_input.insert("1.0", "Type a message...")
            self.placeholder_visible = True
        else:
            self.placeholder_visible = False
        return "break"

    def add_newline(self, event):
        self.user_input.insert(tk.INSERT, "\n")
        return 'break'

    def process_ai_response(self):
        selected_model_full = self.model_var.get()
        if not selected_model_full or "No models" in selected_model_full or "Loading" in selected_model_full:
            self.add_log_message("Error: No model selected/available.", "error")
            return
        try:
            provider, model_id = selected_model_full.split(": ", 1)
        except ValueError:
            self.add_log_message(f"Error: Invalid model format '{selected_model_full}'.", "error")
            return
        api_key = None
        client_config = {}
        base_url = None
        headers = {}
        if provider == "OpenAI":
            api_key = openai_api_key
            if not api_key:
                self.add_log_message("Error: OpenAI API key not set.", "error")
                return
            client_config = {"api_key": api_key}
        elif provider == "OpenRouter":
            api_key = openrouter_api_key
            if not api_key:
                self.add_log_message("Error: OpenRouter API key not set.", "error")
                return
            client_config = {"api_key": api_key, "base_url": "https://openrouter.ai/api/v1"}
        elif provider == "XAI":
            api_key = xai_api_key
            if not api_key:
                self.add_log_message("Error: XAI API key not set.", "error")
                return
            client_config = {"api_key": api_key, "base_url": "https://api.x.ai/v1"}
        elif provider == "Anthropic":
            api_key = anthropic_api_key
            if not api_key:
                self.add_log_message("Error: Anthropic API key not set.", "error")
                return
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
            base_url = "https://api.anthropic.com/v1/messages"
        elif provider == "HuggingFace":
            api_key = huggingface_api_key
            if not api_key:
                self.add_log_message("Error: HuggingFace API key not set.", "error")
                return
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            base_url = f"https://api-inference.huggingface.co/models/{model_id}"
        elif provider == "Google":
            api_key = google_api_key
            if not api_key:
                self.add_log_message("Error: Google API key not set.", "error")
                return
            headers = {"Content-Type": "application/json"}
            base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
        elif provider == "Perplexity":
            api_key = perplexity_api_key
            if not api_key:
                self.add_log_message("Error: Perplexity API key not set.", "error")
                return
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            base_url = "https://api.perplexity.ai/chat/completions"
        elif provider == "Together":
            api_key = together_api_key
            if not api_key:
                self.add_log_message("Error: Together.ai API key not set.", "error")
                return
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            base_url = "https://api.together.ai/v1/chat/completions"
        elif provider == "Groq":
            api_key = groq_api_key
            if not api_key:
                self.add_log_message("Error: Groq API key not set.", "error")
                return
            client_config = {"api_key": api_key, "base_url": "https://api.groq.com/openai/v1"}
        elif provider == "Pi":
            api_key = pi_api_key
            if not api_key:
                self.add_log_message("Error: Pi.ai API key not set.", "error")
                return
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            base_url = "https://api.pi.ai/v1/chat/completions"
        elif provider == "Mistral":
            api_key = mistral_api_key
            if not api_key:
                self.add_log_message("Error: Mistral API key not set.", "error")
                return
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            base_url = "https://api.mixtral.ai/v1/chat/completions"
        elif provider == "DeepSeek":
            api_key = deepseek_api_key
            if not api_key:
                self.add_log_message("Error: DeepSeek API key not set.", "error")
                return
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            base_url = "https://api.deepseek.com/v1/chat/completions"
        else:
            self.add_log_message(f"Error: Unknown provider '{provider}'.", "error")
            return

        system_prompt = self.get_system_prompt()
        messages = [{"role": "system", "content": system_prompt}] + self.get_context_limit_messages()

        try:
            if provider in ["OpenAI", "OpenRouter", "XAI", "Groq"]:
                client = openai.OpenAI(**client_config)
                response_stream = client.chat.completions.create(
                    model=model_id, messages=messages,
                    temperature=self.temperature_var.get(), max_tokens=self.max_tokens_var.get(),
                    presence_penalty=self.presence_penalty_var.get(), frequency_penalty=self.frequency_penalty_var.get(),
                    top_p=self.top_p_var.get(), stream=True
                )
                full_response = ""
                message_frame = None
                label = None
                for chunk in response_stream:
                    text = chunk.choices[0].delta.content or ""
                    if text:
                        full_response += text
                        if not message_frame:
                            message_frame = ttk.Frame(self.chat_scrollable_frame, style="MainDark.TFrame" if self.is_dark_mode.get() else "MainLight.TFrame")
                            message_frame.pack(fill=tk.X, padx=15, pady=10, anchor="w")
                            self.message_frames.append(message_frame)
                            if len(self.message_frames) > 100:
                                oldest_frame = self.message_frames.pop(0)
                                oldest_frame.destroy()
                            label = ttk.Label(
                                message_frame,
                                text="",
                                style="MainDark.TLabel" if self.is_dark_mode.get() else "MainLight.TLabel",
                                wraplength=900,
                                justify=tk.LEFT,
                                foreground=ACCENT_COLOR_ASSISTANT if self.is_dark_mode.get() else LIGHT_ACCENT_ASSISTANT,
                                font=(FONT_FAMILY, 18)
                            )
                            label.pack(side=tk.LEFT, anchor="w")
                        label.config(text=f"Assistant: {full_response}")
                        self.chat_canvas.update_idletasks()
                        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
                        self.chat_canvas.yview_moveto(1.0)
                        self.update()
            else:
                # Non-OpenAI compatible APIs
                if provider == "Anthropic":
                    data = {
                        "model": model_id,
                        "messages": messages,
                        "max_tokens": self.max_tokens_var.get(),
                        "temperature": self.temperature_var.get(),
                        "top_p": self.top_p_var.get()
                    }
                    stream = False  # Anthropic doesn't support streaming in the same way
                    response = requests.post(base_url, headers=headers, json=data)
                    response.raise_for_status()
                    response_data = response.json()
                    full_response = response_data["content"][0]["text"]
                elif provider == "HuggingFace":
                    data = {
                        "inputs": "\n".join([msg["content"] for msg in messages]),
                        "parameters": {
                            "max_length": self.max_tokens_var.get(),
                            "temperature": self.temperature_var.get(),
                            "top_p": self.top_p_var.get()
                        }
                    }
                    response = requests.post(base_url, headers=headers, json=data)
                    response.raise_for_status()
                    response_data = response.json()
                    full_response = response_data[0]["generated_text"]
                elif provider == "Google":
                    data = {
                        "contents": [{"parts": [{"text": msg["content"]} for msg in messages]}],
                        "generationConfig": {
                            "maxOutputTokens": self.max_tokens_var.get(),
                            "temperature": self.temperature_var.get(),
                            "topP": self.top_p_var.get()
                        }
                    }
                    response = requests.post(base_url, headers=headers, json=data)
                    response.raise_for_status()
                    response_data = response.json()
                    full_response = response_data["candidates"][0]["content"]["parts"][0]["text"]
                elif provider in ["Perplexity", "Together", "Pi", "Mistral", "DeepSeek"]:
                    data = {
                        "model": model_id,
                        "messages": messages,
                        "max_tokens": self.max_tokens_var.get(),
                        "temperature": self.temperature_var.get(),
                        "top_p": self.top_p_var.get(),
                        "stream": True
                    }
                    response = requests.post(base_url, headers=headers, json=data, stream=True)
                    response.raise_for_status()
                    full_response = ""
                    message_frame = None
                    label = None
                    for line in response.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith("data:"):
                                data = json.loads(decoded_line[5:])
                                if "choices" in data and data["choices"]:
                                    text = data["choices"][0].get("delta", {}).get("content", "") or data["choices"][0].get("message", {}).get("content", "")
                                    if text:
                                        full_response += text
                                        if not message_frame:
                                            message_frame = ttk.Frame(self.chat_scrollable_frame, style="MainDark.TFrame" if self.is_dark_mode.get() else "MainLight.TFrame")
                                            message_frame.pack(fill=tk.X, padx=15, pady=10, anchor="w")
                                            self.message_frames.append(message_frame)
                                            if len(self.message_frames) > 100:
                                                oldest_frame = self.message_frames.pop(0)
                                                oldest_frame.destroy()
                                            label = ttk.Label(
                                                message_frame,
                                                text="",
                                                style="MainDark.TLabel" if self.is_dark_mode.get() else "MainLight.TLabel",
                                                wraplength=900,
                                                justify=tk.LEFT,
                                                foreground=ACCENT_COLOR_ASSISTANT if self.is_dark_mode.get() else LIGHT_ACCENT_ASSISTANT,
                                                font=(FONT_FAMILY, 18)
                                            )
                                            label.pack(side=tk.LEFT, anchor="w")
                                        label.config(text=f"Assistant: {full_response}")
                                        self.chat_canvas.update_idletasks()
                                        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
                                        self.chat_canvas.yview_moveto(1.0)
                                        self.update()

            if full_response.strip() and self.current_conversation_id:
                self.conversation_log.append({"role": "assistant", "content": full_response})
                add_message_to_db(self.current_conversation_id, "assistant", full_response)
                # Play audio if TTS provider is configured
                provider = self.tts_provider.get()
                if provider == "ElevenLabs" and self.voice_id:
                    self.play_message(full_response)
                # Disabled Sesame CSM for now
                # elif provider == "Sesame CSM" and self.sesame_csm and self.sesame_csm.generator:
                #     self.play_message(full_response)
                elif provider == "macOS Native" and self.macos_tts and self.macos_tts.synthesizer:
                    self.play_message(full_response)
                elif provider != "None":
                    self.add_log_message(f"TTS provider {provider} is not available.", "error")
        except Exception as e:
            error_msg = f"API Error ({provider} {model_id}): {str(e)}"
            self.add_log_message(error_msg, "error")

    def configure_api_keys(self):
        global openai_api_key, openrouter_api_key, xai_api_key, anthropic_api_key, huggingface_api_key
        global google_api_key, perplexity_api_key, together_api_key, groq_api_key, pi_api_key
        global mistral_api_key, deepseek_api_key, config
        new_openai = simpledialog.askstring("API Key", "OpenAI API Key:", initialvalue=openai_api_key or "", parent=self)
        if new_openai is not None:
            config["openai_api_key"] = new_openai
            openai_api_key = new_openai
        if openai_api_key:
            openai.api_key = openai_api_key
        new_openrouter = simpledialog.askstring("API Key", "OpenRouter API Key:", initialvalue=openrouter_api_key or "", parent=self)
        if new_openrouter is not None:
            config["openrouter_api_key"] = new_openrouter
            openrouter_api_key = new_openrouter
        new_xai = simpledialog.askstring("API Key", "XAI API Key:", initialvalue=xai_api_key or "", parent=self)
        if new_xai is not None:
            config["xai_api_key"] = new_xai
            xai_api_key = new_xai
        new_anthropic = simpledialog.askstring("API Key", "Anthropic API Key:", initialvalue=anthropic_api_key or "", parent=self)
        if new_anthropic is not None:
            config["anthropic_api_key"] = new_anthropic
            anthropic_api_key = new_anthropic
        new_huggingface = simpledialog.askstring("API Key", "HuggingFace API Key:", initialvalue=huggingface_api_key or "", parent=self)
        if new_huggingface is not None:
            config["huggingface_api_key"] = new_huggingface
            huggingface_api_key = new_huggingface
        new_google = simpledialog.askstring("API Key", "Google API Key:", initialvalue=google_api_key or "", parent=self)
        if new_google is not None:
            config["google_api_key"] = new_google
            google_api_key = new_google
        new_perplexity = simpledialog.askstring("API Key", "Perplexity API Key:", initialvalue=perplexity_api_key or "", parent=self)
        if new_perplexity is not None:
            config["perplexity_api_key"] = new_perplexity
            perplexity_api_key = new_perplexity
        new_together = simpledialog.askstring("API Key", "Together.ai API Key:", initialvalue=together_api_key or "", parent=self)
        if new_together is not None:
            config["together_api_key"] = new_together
            together_api_key = new_together
        new_groq = simpledialog.askstring("API Key", "Groq API Key:", initialvalue=groq_api_key or "", parent=self)
        if new_groq is not None:
            config["groq_api_key"] = new_groq
            groq_api_key = new_groq
        new_pi = simpledialog.askstring("API Key", "Pi.ai API Key:", initialvalue=pi_api_key or "", parent=self)
        if new_pi is not None:
            config["pi_api_key"] = new_pi
            pi_api_key = new_pi
        new_mistral = simpledialog.askstring("API Key", "Mistral API Key:", initialvalue=mistral_api_key or "", parent=self)
        if new_mistral is not None:
            config["mistral_api_key"] = new_mistral
            mistral_api_key = new_mistral
        new_deepseek = simpledialog.askstring("API Key", "DeepSeek API Key:", initialvalue=deepseek_api_key or "", parent=self)
        if new_deepseek is not None:
            config["deepseek_api_key"] = new_deepseek
            deepseek_api_key = new_deepseek
        save_config(config)
        self.add_log_message("API keys updated. Refreshing models...", "system")
        self.load_initial_models()

    def on_model_change(self, *args):
        if self.current_conversation_id:
            new_model = self.model_var.get()
            if new_model and new_model != "No models available" and new_model != "Loading models...":
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("UPDATE conversations SET llm_model = ? WHERE id = ?", (new_model, self.current_conversation_id))
                conn.commit()
                conn.close()
                self.add_log_message(f"Model updated to {new_model} for this conversation.", "system")

    def on_chat_mode_change(self, *args):
        self.add_log_message(f"Chat mode changed to {self.current_chat_mode.get()}.", "system")

    def on_closing(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join()
        self.destroy()

if __name__ == "__main__":
    app = VoyeurChat()
    app.mainloop()