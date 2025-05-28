import os
import json

# Path to the configuration file
CONFIG_FILE = os.path.expanduser("~/.voyeur_chat_config.json")

# Environment variable names for API keys (industry-standard names)
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"
XAI_API_KEY_ENV = "XAI_API_KEY"
HF_TOKEN_ENV = "HF_TOKEN"
GOOGLE_GENERATIVE_AI_API_KEY_ENV = "GOOGLE_GENERATIVE_AI_API_KEY"
PERPLEXITY_API_KEY_ENV = "PERPLEXITY_API_KEY"
GROQ_API_KEY_ENV = "GROQ_API_KEY"
ELEVENLABS_API_KEY_ENV = "ELEVENLABS_API_KEY"
PI_API_KEY_ENV = "PI_API_KEY"
MISTRAL_API_KEY_ENV = "MISTRAL_API_KEY"
DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
TOGETHER_API_KEY_ENV = "TOGETHER_API_KEY"
GOOGLE_APPLICATION_CREDENTIALS_ENV = "GOOGLE_APPLICATION_CREDENTIALS"

def load_config():
    """Load configuration from JSON file, falling back to environment variables."""
    default_config = {
        # Default settings
        "tts_provider": "None",
        "voice_id": "",  # ElevenLabs Voice ID (to be configured by user)
        "macos_voice": "Allison",
        "sesame_speaker": 0,
        "google_voice": "en-US-Chirp3-HD-Sulafat",  # Default Google Cloud TTS voice
        "piper_model": "en_US-lessac-medium",  # Default Piper TTS model
        
        # API keys from environment variables with empty defaults
        "anthropic_api_key": os.getenv(ANTHROPIC_API_KEY_ENV, ""),
        "openai_api_key": os.getenv(OPENAI_API_KEY_ENV, ""),
        "openrouter_api_key": os.getenv(OPENROUTER_API_KEY_ENV, ""),
        "xai_api_key": os.getenv(XAI_API_KEY_ENV, ""),
        "huggingface_api_key": os.getenv(HF_TOKEN_ENV, ""),
        "google_generative_ai_api_key": os.getenv(GOOGLE_GENERATIVE_AI_API_KEY_ENV, ""),
        "perplexity_api_key": os.getenv(PERPLEXITY_API_KEY_ENV, ""),
        "groq_api_key": os.getenv(GROQ_API_KEY_ENV, ""),
        "elevenlabs_api_key": os.getenv(ELEVENLABS_API_KEY_ENV, ""),
        "pi_api_key": os.getenv(PI_API_KEY_ENV, ""),
        "mistral_api_key": os.getenv(MISTRAL_API_KEY_ENV, ""),
        "deepseek_api_key": os.getenv(DEEPSEEK_API_KEY_ENV, ""),
        "together_api_key": os.getenv(TOGETHER_API_KEY_ENV, ""),
        "google_application_credentials": os.getenv(GOOGLE_APPLICATION_CREDENTIALS_ENV, ""),
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            default_config.update(config)  # Merge with env vars, preserving user settings
    return default_config

def save_config(config_data):
    """Save configuration to JSON file."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f)