# Voyeur Chat: A Lightweight LLM Chat UI/UX for macOS

Voyeur Chat is a small, fast, and feature-rich desktop application for interacting with large language models (LLMs) via a chat interface. Designed for macOS, it supports multiple LLM providers, text-to-speech (TTS), speech-to-text (STT), file uploads, RAG, model comparison, and more. This project is part of an AI-to-AI collaboration framework (ACHO) with human orchestration.

## Features
- **Multi-Provider LLM Support**: Integrates with OpenAI, OpenRouter, XAI, Anthropic, HuggingFace, Google, Perplexity, Together, Groq, Pi, Mistral, and DeepSeek.
- **Text-to-Speech (TTS)**: Supports macOS native TTS, ElevenLabs, Google Cloud TTS, Piper TTS (bundled), and `pyttsx3`.
- **Speech-to-Text (STT)**: "Call Mode" for voice input using Google Cloud Speech-to-Text.
- **File Uploads & RAG**: Upload PDFs/text, use FAISS for retrieval-augmented generation.
- **Model Comparison**: Compare responses from multiple models side-by-side.
- **Export Conversations**: Export chats as JSON or Markdown.
- **Cost/Token Tracking**: Displays per-message token usage and estimated cost.
- **Auto-Save Drafts**: Saves unsent messages to SQLite on exit.
- **Cross-Platform Ready**: Optimized for macOS, with notes for Windows/Linux.

## Prerequisites
- **Python 3.9+**: Ensure Python is installed on your system.
- **macOS**: This setup is optimized for macOS; see Windows/Linux notes in `SETUP.md`.
- **Google Cloud Account**: For STT and Google Cloud TTS, you’ll need a Google Cloud API key.
- **API Keys**: For LLM providers (e.g., OpenAI, ElevenLabs), set environment variables or configure in the app.

## Installation
Follow the detailed setup instructions in `SETUP.md` to install dependencies, download Piper TTS, and configure API keys.

## Usage
1. **Launch the App**:
   ```bash
   ./start.sh
   ```
2. **Configure API Keys**: Go to `Settings > Configure API Keys` to set your LLM and TTS API keys.
3. **Start Chatting**:
   - Select a model from the dropdown.
   - Choose a chat mode (e.g., "Normal", "Call Mode").
   - Type or speak (in Call Mode) to interact with the LLM.
4. **Use Features**:
   - Upload files via `Settings > Upload File`.
   - Compare models with `Compare Models`.
   - Export conversations via `Settings > Export Conversation`.

## Project Structure
```
voyeur_chat/
├── main.py        # Entry point
├── config.py      # Configuration management
├── db.py          # SQLite database operations
├── api.py         # LLM API interactions
├── tts.py         # Text-to-Speech providers
├── stt.py         # Speech-to-Text (Google Cloud STT)
├── ui.py          # Tkinter UI
├── start.sh       # Start script
├── piper/         # Piper TTS binary and models
│   ├── piper      # Piper binary for macOS
│   └── models/
│       └── en_US-lessac-medium.onnx  # Piper voice model
├── README.md
├── SETUP.md
└── requirements.txt
```

## Contributing
This project is in active development. To contribute:
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature-name`).
3. Commit your changes (`git commit -m "Add feature"`).
4. Push to the branch (`git push origin feature-name`).
5. Open a pull request.

## License
This project is licensed under the MIT License.

## Contact
For issues or suggestions, contact Jason via the ACHO framework.