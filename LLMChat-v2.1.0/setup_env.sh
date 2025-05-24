#!/bin/bash

# Script to reset and rebuild the vCHAT Conda environment for Presence

# Exit on any error
set -e

# Define paths and environment name
PROJECT_DIR="/Users/heathen-admin/Desktop/Claude/LLMChat/r2"
ENV_NAME="vCHAT"
CONDA_ENV_PATH="/Users/heathen-admin/miniconda3/envs/$ENV_NAME"
LLVM_VERSION="14.0.6"
LLVM_DIR="/usr/local/opt/llvm@$LLVM_VERSION"
LLVM_URL="https://github.com/ptillet/triton-llvm-releases/releases/download/llvm-$LLVM_VERSION-f28c006a5895/llvm+mlir-$LLVM_VERSION-x86_64-apple-darwin-release.tar.xz"
LLVM_FILE="$PROJECT_DIR/llvm+mlir-$LLVM_VERSION-x86_64-apple-darwin-release.tar.xz"

# Log output
LOG_FILE="$PROJECT_DIR/setup_env.log"
exec > >(tee -a "$LOG_FILE") 2>&1
echo "Starting setup at $(date)"

# Check Conda permissions
echo "Checking Conda permissions"
if [ ! -w "$CONDA_ENV_PATH" ] && [ -d "$CONDA_ENV_PATH" ]; then
    echo "Fixing permissions for $CONDA_ENV_PATH"
    sudo chown -R heathen-admin:staff "$CONDA_ENV_PATH"
fi

# Check project directory permissions
echo "Checking project directory permissions"
ls -ld "$PROJECT_DIR" >> "$LOG_FILE"
if ! ls -ld "$PROJECT_DIR" | grep -q "heathen-admin.*drwxr"; then
    echo "Error: No write permissions in $PROJECT_DIR. Run: sudo chown -R heathen-admin:staff $PROJECT_DIR"
    exit 1
fi

# Initialize Conda
echo "Initializing Conda for zsh"
source ~/miniconda3/etc/profile.d/conda.sh
conda init zsh
source ~/.zshrc

# Deactivate any active environment
echo "Deactivating Conda environment"
conda deactivate || true

# Delete existing environment
echo "Deleting $ENV_NAME environment"
conda env remove -n "$ENV_NAME" -y || true

# Create new environment
echo "Creating $ENV_NAME with Python 3.10"
conda create -n "$ENV_NAME" python=3.10 -y
conda activate "$ENV_NAME"

# Install system dependencies
echo "Installing Homebrew dependencies"
brew install portaudio

# Remove old LLVM
echo "Removing old LLVM installations"
brew uninstall llvm@15 llvm@16 --ignore-dependencies || true
rm -rf "$LLVM_DIR"

# Check disk space
echo "Checking disk space"
df -h "$PROJECT_DIR" >> "$LOG_FILE"
if ! df -h "$PROJECT_DIR" | grep -q "1\.[0-9]G"; then
    echo "Error: Insufficient disk space (<1GB) in $PROJECT_DIR"
    exit 1
fi

# Install LLVM 14
echo "Installing LLVM $LLVM_VERSION"
cd "$PROJECT_DIR"
rm -f "$LLVM_FILE"
for i in {1..3}; do
    echo "Attempt $i to download LLVM $LLVM_VERSION"
    if curl -L --max-time 300 --progress-bar -o "$LLVM_FILE" "$LLVM_URL"; then
        echo "Verifying file integrity"
        if xz -t "$LLVM_FILE" >/dev/null 2>&1; then
            echo "Download successful"
            echo "Extracting LLVM $LLVM_VERSION"
            if timeout 300 tar -xvf "$LLVM_FILE" 2>> "$LOG_FILE"; then
                mv llvm+mlir-$LLVM_VERSION-x86_64-apple-darwin-release "$LLVM_DIR"
                rm -f "$LLVM_FILE"
                break
            else
                echo "Extraction timed out or failed"
                rm -f "$LLVM_FILE"
            fi
        else
            echo "Downloaded file is corrupted"
            rm -f "$LLVM_FILE"
        fi
    fi
    echo "Download/extraction failed, retrying..."
    sleep 5
    [ $i -eq 3 ] && { echo "Failed to install LLVM after 3 attempts"; exit 1; }
done

# Set LLVM environment variables
export LLVM_DIR="$LLVM_DIR/lib/cmake/llvm"
export MLIR_DIR="$LLVM_DIR/lib/cmake/mlir"
export PATH="$LLVM_DIR/bin:$PATH"

# Install Conda dependencies
echo "Installing Conda dependencies"
conda install -y \
    pyperclip \
    faiss-cpu \
    numpy=1.26.4 \
    pypdf2 \
    aiosqlite \
    requests \
    pydub \
    simpleaudio \
    google-cloud-texttospeech \
    google-cloud-speech \
    pytorch=2.2.2 \
    torchaudio=2.2.2 \
    transformers=4.44.0 \
    huggingface_hub=0.28.1 \
    ffmpeg-python \
    tenacity \
    -c pytorch -c conda-forge

# Install pip dependencies
echo "Installing pip dependencies"
pip install \
    pyttsx3 \
    whisperx \
    pyannote-audio==3.3.2 \
    soundfile \
    torchtune \
    torchao==0.0.3 \
    moshi==0.2.4 \
    litellm \
    openai

# Modify silentcipher requirements.txt
echo "Modifying silentcipher requirements.txt"
cd "$PROJECT_DIR/silentcipher"
echo "torch>=2.2.2" > requirements.txt
echo "torchaudio>=2.2.2" >> requirements.txt

# Check for setup.py
echo "Checking for setup.py in triton directory"
if [ ! -f "$PROJECT_DIR/triton/setup.py" ]; then
    echo "Error: setup.py not found in $PROJECT_DIR/triton"
    exit 1
fi
echo "Checking setup.py for problematic imports"
grep -n "import python" "$PROJECT_DIR/triton/setup.py" >> "$LOG_FILE" || echo "No 'import python' found" >> "$LOG_FILE"
echo "Logging setup.py contents for debugging"
cat "$PROJECT_DIR/triton/setup.py" >> "$LOG_FILE"

# Install triton
echo "Installing triton"
cd "$PROJECT_DIR/triton"
rm -rf build CMakeCache.txt CMakeFiles
CMAKE_ARGS="-DTRITON_BUILD_UT=OFF -DTRITON_BUILD_TESTING=OFF -DLLVM_DIR=$LLVM_DIR/lib/cmake/llvm -DMLIR_DIR=$LLVM_DIR/lib/cmake/mlir -DPython3_EXECUTABLE=$(which python)" pip install .

# Install silentcipher
echo "Installing silentcipher"
cd "$PROJECT_DIR"
pip install ./silentcipher

# Run the app
echo "Running Presence"
cd "$PROJECT_DIR"
python main.py

echo "Setup completed at $(date)"