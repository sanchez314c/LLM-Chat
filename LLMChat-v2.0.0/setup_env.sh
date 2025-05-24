#!/bin/bash
#!/bin/bash
#!/bin/bash
# IMPORTANT: This is a Bash script. Run it with 'bash setup_env.sh' or './setup_env.sh' after 'chmod +x setup_env.sh'. Do NOT run with Python.

# Reset and rebuild vCHAT Conda env for LLM Chat with TensorFlow Metal

set -e
set -x  # Enable debugging to trace commands

# Paths
PROJECT_DIR="$(dirname "$(realpath "$0")")"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_NAME="FASTCHAT-METAL"
echo "Debug: PROJECT_DIR set to $PROJECT_DIR"
CONDA_ENV_PATH="/Users/heathen-admin/miniconda3/envs/$ENV_NAME"
LLVM_VERSION="14.0.6"
LLVM_DIR="/usr/local/opt/llvm@$LLVM_VERSION"
LLVM_URL="https://github.com/ptillet/triton-llvm-releases/releases/download/llvm-$LLVM_VERSION-f28c006a5895/llvm+mlir-$LLVM_VERSION-x86_64-apple-darwin-release.tar.xz"
EXTRACTED_LLVM_DIR_NAME="llvm+mlir-$LLVM_VERSION-x86_64-apple-darwin-release"

# Log
LOG_FILE="$PROJECT_DIR/setup_env.log"
mkdir -p "$PROJECT_DIR" || { echo "ERROR: Cannot create directory $PROJECT_DIR"; exit 1; }
exec > >(tee -a "$LOG_FILE") 2>&1
echo "Starting setup at $(date)"

# Conda permissions
echo "Checking Conda permissions"
if [ ! -w "$CONDA_ENV_PATH" ] && [ -d "$CONDA_ENV_PATH" ]; then
    sudo chown -R heathen-admin:staff "$CONDA_ENV_PATH"
fi

# Init Conda
echo "Initializing Conda"
source ~/miniconda3/etc/profile.d/conda.sh
conda init zsh
echo "Before sourcing temporary zshrc"
# Temporarily disable nvm initialization to avoid conflicts when sourcing .zshrc
echo 'Skipping nvm initialization to prevent .npmrc conflict...'
# Avoid sourcing zsh-specific plugins or incompatible syntax, extract only necessary env vars
echo 'Loading only necessary environment variables for Conda...'
# Directly activate Conda base environment without sourcing full zshrc
conda activate base
echo "After sourcing temporary zshrc"

# Deactivate env
echo "Deactivating Conda env"
conda deactivate || true

# Delete old env
echo "Deleting $ENV_NAME env"
conda env remove -n "$ENV_NAME" -y || true

# Conda channels
echo "Configuring Conda channels"
conda config --add channels apple
conda config --add channels pytorch
conda config --add channels conda-forge
conda config --set channel_priority flexible

# Create env with Python 3.9 for triton
echo "Creating $ENV_NAME with Python 3.9"
conda create -n "$ENV_NAME" python=3.9 -y
conda activate "$ENV_NAME"

# Verify Python version
PYTHON_VERSION=$(python --version 2>&1 | grep -o "3\.[0-9]")
if [ "$PYTHON_VERSION" != "3.9" ]; then
    echo "ERROR: Python version is $PYTHON_VERSION, expected 3.9"
    exit 1
fi

# Homebrew deps
echo "Installing Homebrew deps"
brew install portaudio

# Remove old LLVM (Homebrew only)
echo "Removing old LLVM via Homebrew"
brew uninstall llvm@15 llvm@16 --ignore-dependencies || true

# Check LLVM
echo "Checking LLVM $LLVM_VERSION"
if [ -d "$LLVM_DIR" ] && [ -f "$LLVM_DIR/bin/llc" ] && [ -d "$LLVM_DIR/lib/cmake/llvm" ] && [ -d "$LLVM_DIR/lib/cmake/mlir" ]; then
    echo "Valid LLVM $LLVM_VERSION at $LLVM_DIR"
else
    if [ -d "$LLVM_DIR" ]; then
        echo "WARNING: Incomplete LLVM at $LLVM_DIR"
        read -p "Remove $LLVM_DIR and reinstall LLVM $LLVM_VERSION? (y/n): " confirm
        if [ "$confirm" = "y" ]; then
            sudo rm -rf "$LLVM_DIR" || {
                echo "ERROR: Failed to remove $LLVM_DIR"
                exit 1
            }
        else
            echo "ERROR: Cannot proceed with incomplete LLVM"
            exit 1
        fi
    fi

    echo "Installing LLVM $LLVM_VERSION"
    LOCAL_TEMP_DIR="/tmp/llvm-install-$LLVM_VERSION"
    LOCAL_LLVM_FILE="$LOCAL_TEMP_DIR/llvm+mlir-$LLVM_VERSION-x86_64-apple-darwin-release.tar.xz"
    mkdir -p "$LOCAL_TEMP_DIR"

    echo "Removing old download: $LOCAL_LLVM_FILE"
    rm -rf "$LOCAL_TEMP_DIR" || {
        echo "WARNING: Failed to remove $LOCAL_TEMP_DIR"
    }

    for i in {1..3}; do
        echo "--- LLVM Download/Extract Attempt $i of 3 ---"
        mkdir -p "$LOCAL_TEMP_DIR"
        if curl -L --max-time 600 --progress-bar -o "$LOCAL_LLVM_FILE" "$LLVM_URL"; then
            if xz -t "$LOCAL_LLVM_FILE" >/dev/null 2>&1; then
                echo "Extracting LLVM $LLVM_VERSION"
                if tar -xvf "$LOCAL_LLVM_FILE" -C "$LOCAL_TEMP_DIR" >> "$LOG_FILE" 2>&1; then
                    if [ -d "$LOCAL_TEMP_DIR/$EXTRACTED_LLVM_DIR_NAME" ]; then
                        sudo mkdir -p "$LLVM_DIR" || {
                            echo "ERROR: Failed to create $LLVM_DIR"
                            exit 1
                        }
                        sudo mv "$LOCAL_TEMP_DIR/$EXTRACTED_LLVM_DIR_NAME"/* "$LLVM_DIR/" || {
                            echo "ERROR: Failed to move LLVM to $LLVM_DIR"
                            rm -rf "$LOCAL_LLVM_FILE" "$LOCAL_TEMP_DIR"
                            exit 1
                        }
                        rm -rf "$LOCAL_TEMP_DIR"
                        echo "--- LLVM Installation successful ---"
                        break
                    else
                        echo "ERROR: Directory $EXTRACTED_LLVM_DIR_NAME not found"
                        rm -rf "$LOCAL_LLVM_FILE" "$LOCAL_TEMP_DIR"
                        exit 1
                    fi
                else
                    echo "ERROR: Tar extraction failed"
                    rm -rf "$LOCAL_LLVM_FILE" "$LOCAL_TEMP_DIR"
                fi
            else
                echo "ERROR: Corrupted file $LOCAL_LLVM_FILE"
                rm -rf "$LOCAL_LLVM_FILE" "$LOCAL_TEMP_DIR"
            fi
        else
            echo "ERROR: Download failed from $LLVM_URL"
            rm -rf "$LOCAL_TEMP_DIR"
        fi

        if [ $i -eq 3 ]; then
            echo "ERROR: Failed LLVM install after 3 attempts"
            exit 1
        fi
        echo "Retrying in 10 seconds..."
        sleep 10
    done
fi

# Set LLVM env vars
export LLVM_DIR="$LLVM_DIR/lib/cmake/llvm"
export MLIR_DIR="$LLVM_DIR/lib/cmake/mlir"
export PATH="$LLVM_DIR/bin:$PATH"

# Conda deps (add mkl for faiss-cpu)
echo "Installing Conda deps"
conda install -y \
    mkl \
    pyperclip \
    faiss-cpu \
    numpy=1.24.3 \
    pypdf2 \
    aiosqlite \
    requests \
    pydub \
    google-cloud-texttospeech \
    google-cloud-speech \
    pytorch=2.0.1 \
    torchaudio=2.0.2 \
    torchvision \
    transformers=4.36.2 \
    huggingface_hub=0.20.3 \
    ffmpeg-python \
    tenacity \
    -c apple -c pytorch -c conda-forge

# Set LD_LIBRARY_PATH for MKL
export LD_LIBRARY_PATH="$CONDA_ENV_PATH/lib:$LD_LIBRARY_PATH"

# Pip simpleaudio
echo "Installing simpleaudio"
pip install simpleaudio || {
    echo "WARNING: Failed to install simpleaudio"
}

# TensorFlow (use version compatible with Python 3.9)
echo "Installing TensorFlow"
pip install tensorflow-macos==2.9.0
pip install tensorflow-metal==0.5.0

# Fix deps
echo "Fixing deps"
pip install --force-reinstall numpy==1.24.3 typing_extensions>=4.0 six>=1.15.0

# Silentcipher requirements
echo "Modifying silentcipher requirements"
SILENTCIPHER_DIR="$PROJECT_DIR/silentcipher"
if [ ! -d "$SILENTCIPHER_DIR" ]; then
    echo "ERROR: $SILENTCIPHER_DIR missing"
    exit 1
fi
cd "$SILENTCIPHER_DIR" || {
    echo "ERROR: Failed to cd to $SILENTCIPHER_DIR"
    exit 1
}
echo "tensorflow-macos==2.9.0" > requirements.txt
echo "tensorflow-metal==0.5.0" >> requirements.txt
echo "torch>=2.0.1" >> requirements.txt
echo "torchaudio>=2.0.2" >> requirements.txt
echo "torchvision" >> requirements.txt
echo "Modified $SILENTCIPHER_DIR/requirements.txt"

# Pip deps
echo "Installing pip deps"
pip install \
    pyttsx3 \
    pyannote-audio==3.1.1 \
    soundfile \
    torchtune==0.1.0 \
    openai==0.28.0 \
    ctranslate2==3.24.0 \
    whisperx==3.1.1 || {
    echo "ERROR: Failed to install pip deps"
    exit 1
}
pip install litellm==1.49.0 || {
    echo "WARNING: Failed to install litellm"
}

# Check triton setup.py
echo "Checking triton setup.py"
if [ ! -f "$PROJECT_DIR/triton/setup.py" ]; then
    echo "ERROR: setup.py missing in $PROJECT_DIR/triton"
    exit 1
fi

# Check for python folder in triton
echo "Checking for python folder in triton"
if [ ! -d "$PROJECT_DIR/triton/python" ]; then
    echo "ERROR: Missing python folder in $PROJECT_DIR/triton"
    echo "Your custom triton directory must have a python folder with build_helpers.py"
    echo "Please add the python folder from the official triton repo (https://github.com/triton-lang/triton) or adjust setup.py to not require it"
    exit 1
fi

# Check for build_helpers.py
if [ ! -f "$PROJECT_DIR/triton/python/build_helpers.py" ]; then
    echo "ERROR: Missing build_helpers.py in $PROJECT_DIR/triton/python"
    echo "Your custom triton directory must have build_helpers.py in the python folder"
    exit 1
fi

# Install custom triton
echo "Installing custom triton"
cd "$PROJECT_DIR/triton"
rm -rf build CMakeCache.txt CMakeFiles
CMAKE_ARGS="-DTRITON_BUILD_UT=OFF -DTRITON_BUILD_TESTING=OFF -DLLVM_DIR=$LLVM_DIR/lib/cmake/llvm -DMLIR_DIR=$LLVM_DIR/lib/cmake/mlir -DPython3_EXECUTABLE=$(which python)" pip install .

# Install silentcipher
echo "Installing silentcipher"
cd "$PROJECT_DIR"
pip install ./silentcipher

# Test Metal
echo "Testing Metal support"
python -c "import tensorflow as tf; print('TensorFlow GPUs:', tf.config.list_physical_devices('GPU'))"
python -c "import torch; print('PyTorch MPS available:', torch.backends.mps.is_available())"

# Run app
echo "Running Presence"
cd "$PROJECT_DIR"
python main.py

echo "Setup completed at $(date)"