# LLMChat v1.0.0 - Comprehensive Multi-Provider Chat

## Overview
Full-featured LLM chat application supporting multiple AI providers, TTS, voice input, and advanced conversation management.

## Features
- **Multi-Provider Support**: OpenAI, Anthropic, XAI, OpenRouter, Groq, etc.
- **Text-to-Speech**: ElevenLabs, macOS native, Google Cloud, Sesame CSM
- **Speech-to-Text**: OpenAI Whisper, Google Cloud, WhisperX
- **Database**: SQLite conversation storage
- **UI**: Dark/light themes, conversation management
- **Export**: Various formats including Markdown
- **Audio**: Full audio conversation capabilities

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Set API keys as environment variables:
   ```bash
   export OPENAI_API_KEY=your_key
   export XAI_API_KEY=your_key
   export ELEVENLABS_API_KEY=your_key
   # ... other providers as needed
   ```
3. Run: `python LightLLM_chat-r1.py`

## Architecture
- Single comprehensive file (~3000 lines)
- All features integrated in one application
- Configuration via JSON file
- SQLite database for persistence

## Dependencies
- Core: tkinter, requests, sqlite3
- AI/ML: openai, torch, torchaudio, huggingface_hub
- Audio: pygame, pyobjc (macOS)
- Utils: pyperclip, numpy

## Usage
1. Configure API keys in settings
2. Select AI provider and model
3. Choose TTS/STT options
4. Start chatting with voice or text
5. Manage conversations in sidebar