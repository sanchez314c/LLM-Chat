# Setup Instructions for Voyeur Chat

This guide provides step-by-step instructions to set up Voyeur Chat on macOS, including downloading Piper TTS, installing dependencies, and configuring API keys. Notes for Windows/Linux are provided at the end.

## Step 1: Clone the Repository
Clone the project to your local machine:
```bash
git clone <repository-url>
cd voyeur_chat
```

## Step 2: Set Up a Python Environment
1. **Install Python 3.9+**: Ensure Python is installed. Check with:
   ```bash
   python3 --version
   ```
   If not installed, download from [python.org](https://www.python.org/downloads/) or use Homebrew:
   ```bash
   brew install python
   ```
2. **Create a Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Step 3: Download and Configure Piper TTS
Piper TTS is a lightweight, serverless TTS engine bundled with the app.

1. **Download Piper Binary**:
   - Visit [Piper’s GitHub Releases](https://github.com/rhasspy/piper/releases).
   - Download the macOS binary (e.g., `piper_macos_x64.tar.gz`).
   - Extract the archive:
     ```bash
     tar -xzf piper_macos_x64.tar.gz
     ```
   - Move the `piper` binary to the `piper/` directory in your project:
     ```bash
     mkdir -p piper
     mv piper piper/piper
     chmod +x piper/piper
     ```

2. **Download a Piper Voice Model**:
   - Visit [Piper’s Voices](https://github.com/rhasspy/piper/releases) or [Hugging Face](https://huggingface.co/rhasspy/piper-voices).
   - Download a voice model (e.g., `en_US-lessac-medium.onnx` and its `.json` file).
   - Place the model files in `piper/models/`:
     ```bash
     mkdir -p piper/models
     mv en_US-lessac-medium.onnx piper/models/
     mv en_US-lessac-medium.onnx.json piper/models/
     ```

## Step 4: Configure API Keys
Voyeur Chat supports multiple LLM and TTS/STT providers. API keys can be set via environment variables or in the app.

1. **Set Environment Variables (Optional)**:
   ```bash
   export OPENAI_API_KEY="your-openai-key"
   export GOOGLE_CLOUD_API_KEY="your-google-key"
   export ELEVENLABS_API_KEY="your-elevenlabs-key"
   ```
   Add these to your `~/.zshrc` or `~/.bashrc` to persist across sessions.

2. **Configure in the App**:
   - Launch the app:
     ```bash
     ./start.sh
     ```
   - Go to `Settings > Configure API Keys` and enter your API keys.
   - Keys are saved to `~/.voyeur_chat_config.json`.

3. **Google Cloud Setup** (for STT and Google Cloud TTS):
   - Create a Google Cloud project at [console.cloud.google.com](https://console.cloud.google.com).
   - Enable the Speech-to-Text and Text-to-Speech APIs.
   - Create an API key in `APIs & Services > Credentials`.
   - Set the `GOOGLE_CLOUD_API_KEY` environment variable or enter it in the app.

## Step 5: Launch the App
Use the provided start script:
```bash
chmod +x start.sh
./start.sh
```

## Step 6: Bundle into a `.app` (Optional)
To create a macOS application bundle:
1. Install `PyInstaller`:
   ```bash
   pip install pyinstaller
   ```
2. Bundle the app:
   ```bash
   pyinstaller --noconfirm --onefile --windowed --add-data "piper:piper" main.py
   ```
   - The `--add-data` separator is `:` on macOS/Linux, `;` on Windows.
3. Find the `.app` in `dist/`. Move it to `/Applications` or run directly.

## Windows/Linux Notes
- **Piper TTS**:
  - Download the appropriate binary (`piper_windows_amd64.zip` or `piper_linux_x86_64.tar.gz`) from [Piper’s GitHub](https://github.com/rhasspy/piper/releases).
  - Update `tts.py` to adjust the `PIPER_BINARY` path if needed.
- **Dependencies**:
  - On Linux, `faiss-cpu` may require `libomp`:
    ```bash
    sudo apt-get install libomp-dev
    ```
  - `pyaudio` requires `portaudio`:
    ```bash
    sudo apt-get install portaudio19-dev  # Linux
    brew install portaudio  # macOS (if not already installed)
    ```
- **Tkinter Scaling**:
  - Windows: Tkinter may require manual DPI scaling adjustments.
  - Linux: Ensure `tkinter` is installed (`sudo apt-get install python3-tk`).
- **Bundling**:
  - Use `PyInstaller` with the same command, adjusting the `--add-data` separator (`;` on Windows).

## Troubleshooting
- **Piper TTS Not Working**:
  - Ensure the `piper` binary is executable and the model files are in `piper/models/`.
  - Check the logs in the app’s status window for errors.
- **Google Cloud Errors**:
  - Verify your API key and ensure the Speech-to-Text and Text-to-Speech APIs are enabled.
- **Dependency Issues**:
  - Ensure your virtual environment is active (`source venv/bin/activate`).
  - Reinstall dependencies: `pip install -r requirements.txt`.

For further assistance, contact Jason via the ACHO framework.