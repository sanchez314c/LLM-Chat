# LLMChat v2.0.0 - Modular Architecture

## Overview
Modular refactor of the LLM chat application with separated concerns and optional advanced features.

## Architecture
- `main.py` - Application entry point
- `ui.py` - User interface components
- `config.py` - Configuration management
- `db.py` - Database operations
- `api.py` - API integrations
- `tts.py` - Text-to-speech engines
- `stt.py` - Speech-to-text engines

## Features
- All features from r1 but modularized
- Optional advanced features (PDF, FAISS)
- Cleaner separation of concerns
- Easier maintenance and extension

## Setup

### Basic Installation
```bash
pip install -r requirements_core.txt
export XAI_API_KEY=your_key
python main.py
```

### Full Installation (with advanced features)
```bash
pip install -r requirements.txt  # Includes faiss, PyPDF2, etc.
```

## Configuration
- API keys via environment variables or config file
- Settings stored in `~/.voyeur_chat_config.json`
- Database: `voyeur_chat.db`

## Modules
- **config.py**: Load/save configuration, API key management
- **db.py**: SQLite operations, conversation persistence
- **api.py**: Multi-provider API calls (OpenAI, XAI, etc.)
- **tts.py**: Text-to-speech engines (ElevenLabs, macOS, etc.)
- **stt.py**: Speech-to-text engines (Whisper, Google Cloud)
- **ui.py**: Tkinter interface, chat management

## Usage
1. Set environment variables for API keys
2. Run `python main.py`
3. Configure providers in settings
4. Start conversations with modular features

## Benefits
- Easier to maintain and extend
- Optional dependencies for lighter installation
- Better code organization
- Separation of UI, API, and data layers