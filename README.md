# 🤖 LLMChat - Comprehensive AI Conversation Platform

<p align="center">
  <img src="https://raw.githubusercontent.com/sanchez314c/LLM-Chat/main/.images/llmchat-hero.png" alt="LLMChat Hero" width="600" />
</p>

**A comprehensive AI conversation platform that evolved from basic two-agent chat to a full-featured modular system with TTS/STT support.**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT_Compatible-green.svg)](https://openai.com/)
[![Anthropic](https://img.shields.io/badge/Anthropic-Claude-orange.svg)](https://anthropic.com/)
[![xAI](https://img.shields.io/badge/xAI-GROK-purple.svg)](https://x.ai/)

## 🎯 Overview

LLMChat represents the complete evolution of AI conversation platforms, from simple proof-of-concept to production-ready enterprise solutions. This repository showcases the entire development journey, providing multiple versions optimized for different use cases, from basic two-agent conversations to advanced multi-modal AI interactions with speech capabilities.

Whether you're building AI assistants, research platforms, customer service bots, or experimental conversation systems, LLMChat provides the foundation and examples you need.

## ✨ Version Overview

### 🏆 **Production Releases**

#### 🆕 [v2.0.0](./LLMChat-v2.0.0) - Modular Architecture (Latest Stable)
**Recommended for:** Production use, enterprise deployments, scalable applications

**🌟 Key Features:**
- **Modular Design**: Clean separation of concerns with pluggable components
- **Multi-Provider Support**: OpenAI, Anthropic Claude, xAI GROK, and custom APIs
- **Optional Dependencies**: Install only what you need for your use case
- **Configuration Management**: YAML-based configuration with environment overrides
- **Database Integration**: SQLite and PostgreSQL support for conversation persistence
- **API Framework**: FastAPI-based REST API with OpenAPI documentation
- **Authentication**: JWT-based authentication with role-based access control
- **Real-time Features**: WebSocket support for live conversations

```bash
cd LLMChat-v2.0.0
pip install -r requirements_core.txt
python main.py
```

#### 🚀 [v1.0.0](./LLMChat-v1.0.0) - Feature Complete Monolith
**Recommended for:** All-in-one deployments, feature-rich applications, quick setup

**🌟 Key Features:**
- **Complete TTS/STT**: Full speech-to-text and text-to-speech integration
- **Multi-Provider AI**: Support for all major AI providers in one package
- **Rich UI**: Comprehensive web interface with all features enabled
- **Single File Deployment**: Everything in one executable package
- **Voice Conversations**: Natural voice-based AI interactions
- **Audio Processing**: Advanced audio processing and enhancement

```bash
cd LLMChat-v1.0.0
pip install -r requirements.txt
python LightLLM_chat-r1.py
```

#### 🧪 [v0.1.0](./LLMChat-v0.1.0) - Basic Two-Agent System
**Recommended for:** Learning, prototyping, educational purposes, simple demos

**🌟 Key Features:**
- **Simple Architecture**: Easy to understand and modify
- **Two-Agent Conversation**: Automated AI-to-AI conversations
- **Minimal Dependencies**: Lightweight with basic requirements
- **Educational Value**: Perfect for understanding conversation systems
- **Quick Setup**: Running in minutes with minimal configuration

```bash
cd LLMChat-v0.1.0
pip install -r requirements.txt
export XAI_API_KEY=your_key
python voyeur_chat.py
```

### 🔬 **Development & Research**

#### 📚 [Alpha Versions](./Alpha-Versions) - Complete Development Timeline
**Purpose:** Study software evolution, development methodology, research

**🌟 Features:**
- **Complete Evolution**: All 11 development iterations (v0.0.1 - v0.0.11)
- **Development Insights**: See how complex software evolves incrementally
- **Historical Reference**: Perfect for research and learning
- **Methodology Study**: Understand iterative development processes
- **Code Archaeology**: Explore decision-making and architectural evolution

#### ⚠️ [v2.1.0-experimental](./LLMChat-v2.1.0) - Advanced Research Build
**Warning:** Experimental build, NOT for production

**🌟 Features:**
- **Heavy ML Dependencies**: GPU-accelerated processing with PyTorch/TensorFlow
- **Research Features**: Experimental conversation analysis and generation
- **Advanced Audio**: Real-time speech processing with noise cancellation
- **Computer Vision**: Visual understanding and multimodal conversations
- **Academic Research**: Features designed for research and experimentation

## 🚀 Quick Start Guide

### Choose Your Path

#### 🎯 **For Production Use**
```bash
# Modern modular architecture
git clone https://github.com/sanchez314c/LLM-Chat.git
cd LLM-Chat/LLMChat-v2.0.0

# Install core dependencies
pip install -r requirements_core.txt

# Configure your API keys
cp config.example.yaml config.yaml
# Edit config.yaml with your API keys

# Launch the application
python main.py

# Access web interface at http://localhost:8000
```

#### 🎪 **For Full Features**
```bash
# All-in-one feature-complete version
cd LLM-Chat/LLMChat-v1.0.0

# Install all dependencies
pip install -r requirements.txt

# Set environment variables
export XAI_API_KEY=your_xai_key
export OPENAI_API_KEY=your_openai_key
export ANTHROPIC_API_KEY=your_anthropic_key

# Launch with full features
python LightLLM_chat-r1.py
```

#### 🎓 **For Learning**
```bash
# Simple two-agent conversation
cd LLM-Chat/LLMChat-v0.1.0

# Minimal setup
pip install -r requirements.txt
export XAI_API_KEY=your_key

# Start basic conversation
python voyeur_chat.py
```

## 🏗️ Architecture Deep Dive

### v2.0.0 Modular Architecture
```
LLMChat-v2.0.0/
├── main.py                    # Application entry point
├── config.py                  # Configuration management
├── api.py                     # FastAPI REST endpoints
├── db.py                      # Database models and operations
├── ui.py                      # Web interface (Streamlit/FastAPI)
├── stt.py                     # Speech-to-text processing
├── tts.py                     # Text-to-speech synthesis
├── requirements_core.txt      # Essential dependencies
├── requirements.txt           # Full feature dependencies
├── config.example.yaml        # Configuration template
└── static/                    # Web assets and templates
```

### v1.0.0 Monolithic Architecture
```
LLMChat-v1.0.0/
├── LightLLM_chat-r1.py       # Complete application (2000+ lines)
├── requirements.txt           # All dependencies
├── version.py                 # Version information
├── csm/                       # Cryptographic signing module
└── README.md                  # Documentation
```

### Development Evolution
```
Alpha-Versions/
├── LightLLM_chat-r0/         # v0.0.1 - Initial concept
├── LightLLM_chat-r1/         # v0.0.2 - Basic chat
├── LightLLM_chat-r1-2/       # v0.0.3 - UI improvements
├── LightLLM_chat-r1-3/       # v0.0.4 - Multi-provider support
├── LightLLM_chat-r1-4/       # v0.0.5 - Configuration system
├── LightLLM_chat-r1-5/       # v0.0.6 - Database integration
├── LightLLM_chat-r1-6/       # v0.0.7 - API endpoints
├── LightLLM_chat-r1-7/       # v0.0.8 - Authentication
├── LightLLM_chat-r1-8/       # v0.0.9 - Real-time features
├── LightLLM_chat-r1-9/       # v0.0.10 - Voice integration
└── LightLLM_chat-r1-10/      # v0.0.11 - Final alpha
```

## 🎮 Usage Examples

### Basic AI Conversation (v0.1.0)
```python
# Simple two-agent conversation
from voyeur_chat import AIConversation

# Initialize conversation
conversation = AIConversation(
    agent1_model="grok-beta",
    agent2_model="gpt-4",
    topic="The future of artificial intelligence"
)

# Start automated conversation
conversation.start(max_turns=10)

# Save conversation log
conversation.save("ai_discussion.json")
```

### Advanced Multi-Modal Chat (v2.0.0)
```python
from llmchat import LLMChat, Config
from llmchat.providers import OpenAIProvider, ClaudeProvider, GrokProvider

# Initialize with configuration
config = Config.from_yaml("config.yaml")
chat = LLMChat(config)

# Add multiple AI providers
chat.add_provider("openai", OpenAIProvider(api_key=config.openai_key))
chat.add_provider("claude", ClaudeProvider(api_key=config.anthropic_key))
chat.add_provider("grok", GrokProvider(api_key=config.xai_key))

# Start conversation with voice support
conversation = chat.new_conversation(
    model="claude-3-sonnet",
    voice_enabled=True,
    language="en-US"
)

# Send text message
response = conversation.send("Explain quantum computing")

# Send voice message
audio_file = "question.wav"
response = conversation.send_voice(audio_file)

# Get voice response
audio_response = conversation.get_voice_response(response)
```

### REST API Usage (v2.0.0)
```python
import requests

# API endpoints
base_url = "http://localhost:8000/api/v1"

# Create new conversation
conversation = requests.post(f"{base_url}/conversations", json={
    "model": "gpt-4",
    "system_prompt": "You are a helpful AI assistant",
    "temperature": 0.7
}).json()

conversation_id = conversation["id"]

# Send message
response = requests.post(f"{base_url}/conversations/{conversation_id}/messages", json={
    "content": "What's the weather like today?",
    "role": "user"
}).json()

print(response["content"])

# Get conversation history
history = requests.get(f"{base_url}/conversations/{conversation_id}/history").json()
```

### Voice-Enabled Chat (v1.0.0)
```python
from LightLLM_chat import VoiceChat

# Initialize voice-enabled chat
voice_chat = VoiceChat(
    ai_provider="openai",
    model="gpt-4",
    voice_input=True,
    voice_output=True,
    language="en-US"
)

# Start voice conversation
voice_chat.listen_and_respond()

# Process audio file
response = voice_chat.process_audio_file("user_question.wav")
voice_chat.speak_response(response)

# Real-time voice chat
voice_chat.start_real_time_conversation()
```

## 🔧 Advanced Configuration

### v2.0.0 Configuration (config.yaml)
```yaml
# Application settings
app:
  name: "LLMChat"
  version: "2.0.0"
  debug: false
  host: "0.0.0.0"
  port: 8000

# AI Provider configurations
providers:
  openai:
    api_key: "${OPENAI_API_KEY}"
    base_url: "https://api.openai.com/v1"
    models: ["gpt-4", "gpt-3.5-turbo"]
    
  anthropic:
    api_key: "${ANTHROPIC_API_KEY}"
    base_url: "https://api.anthropic.com"
    models: ["claude-3-sonnet", "claude-3-haiku"]
    
  xai:
    api_key: "${XAI_API_KEY}"
    base_url: "https://api.x.ai/v1"
    models: ["grok-beta"]

# Database configuration
database:
  type: "sqlite"  # or "postgresql"
  url: "sqlite:///conversations.db"
  # For PostgreSQL: "postgresql://user:pass@localhost/dbname"

# Voice processing
voice:
  stt_provider: "openai"  # or "google", "azure"
  tts_provider: "elevenlabs"  # or "openai", "azure"
  default_voice: "alloy"
  language: "en-US"

# Security
security:
  jwt_secret: "${JWT_SECRET}"
  token_expiry: 86400  # 24 hours
  rate_limiting: true
  max_requests_per_minute: 60

# Features
features:
  voice_enabled: true
  file_upload: true
  conversation_export: true
  real_time_chat: true
  multi_user: true
```

### Environment Variables
```bash
# Core API Keys
export OPENAI_API_KEY="sk-your-openai-key"
export ANTHROPIC_API_KEY="sk-ant-your-anthropic-key" 
export XAI_API_KEY="xai-your-xai-key"

# Voice Services
export ELEVENLABS_API_KEY="your-elevenlabs-key"
export GOOGLE_CLOUD_KEY="your-google-cloud-key"

# Database (for production)
export DATABASE_URL="postgresql://user:pass@localhost/llmchat"
export JWT_SECRET="your-jwt-secret-key"

# Optional Services
export REDIS_URL="redis://localhost:6379"
export SENTRY_DSN="your-sentry-dsn"
```

## 📊 Performance & Scalability

### Benchmarks by Version

| Version | Setup Time | Memory Usage | Response Time | Concurrent Users |
|---------|------------|--------------|---------------|------------------|
| v0.1.0 | <1 min | 50MB | 1-3s | 1 |
| v1.0.0 | 2-5 min | 200-500MB | 1-2s | 5-10 |
| v2.0.0 | 3-10 min | 100-300MB | 0.5-1.5s | 50-100+ |
| v2.1.0-exp | 10-30 min | 2-8GB | 0.5-2s | 10-20 |

### Scalability Features (v2.0.0)
```python
# Horizontal scaling with Redis
from llmchat.scaling import RedisManager, LoadBalancer

# Redis for session management
redis_manager = RedisManager(
    host="redis-cluster.example.com",
    port=6379,
    cluster_mode=True
)

# Load balancer for multiple instances
load_balancer = LoadBalancer([
    "http://llmchat-1.example.com:8000",
    "http://llmchat-2.example.com:8000",
    "http://llmchat-3.example.com:8000"
])

# Auto-scaling configuration
auto_scaler = AutoScaler(
    min_instances=2,
    max_instances=10,
    target_cpu_percent=70,
    scale_up_cooldown=300,  # 5 minutes
    scale_down_cooldown=600  # 10 minutes
)
```

## 🔒 Security Features

### Authentication & Authorization (v2.0.0)
```python
from llmchat.auth import JWTAuth, RoleBasedAccess

# JWT authentication
auth = JWTAuth(
    secret_key="your-secret-key",
    algorithm="HS256",
    token_expiry=86400
)

# Role-based access control
rbac = RoleBasedAccess({
    "admin": ["read", "write", "delete", "manage_users"],
    "user": ["read", "write"],
    "guest": ["read"]
})

# Secure API endpoint
@app.post("/api/v1/conversations")
@auth.require_token
@rbac.require_permission("write")
async def create_conversation(request: Request):
    user = auth.get_current_user(request)
    # Handle conversation creation
```

### Data Protection
```python
# Encryption for sensitive data
from llmchat.security import DataEncryption

encryption = DataEncryption(key="your-encryption-key")

# Encrypt conversation data
encrypted_content = encryption.encrypt(conversation_data)

# Store with encryption
conversation.content = encrypted_content
conversation.save()

# Decrypt when retrieving
decrypted_content = encryption.decrypt(conversation.content)
```

## 🤝 Contributing

### Development Setup
```bash
# Clone repository
git clone https://github.com/sanchez314c/LLM-Chat.git
cd LLM-Chat

# Set up development environment
python -m venv dev_env
source dev_env/bin/activate  # or dev_env\Scripts\activate on Windows

# Install development dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run tests
pytest tests/ -v --cov=src

# Code quality checks
black . && flake8 . && mypy .
```

### Contributing Guidelines
1. **Fork the repository**
2. **Choose the right version**: Contribute to the appropriate version directory
3. **Create feature branch**: `git checkout -b feature/amazing-feature`
4. **Write tests**: Ensure your code is well-tested
5. **Update documentation**: Include relevant documentation updates
6. **Submit pull request**: Describe your changes clearly

### Areas for Contribution
- **New AI Providers**: Integration with additional AI services
- **Voice Improvements**: Enhanced speech processing capabilities
- **UI/UX Enhancements**: Better user interfaces and experiences
- **Performance Optimization**: Speed and efficiency improvements
- **Security Features**: Enhanced authentication and data protection
- **Mobile Support**: React Native or Flutter applications

## 📈 Roadmap

### Upcoming Features
- [ ] **Mobile Applications**: Native iOS and Android apps
- [ ] **Plugin System**: Third-party extensions and integrations
- [ ] **Advanced Analytics**: Conversation insights and analytics
- [ ] **Team Collaboration**: Multi-user workspaces and sharing
- [ ] **Enterprise SSO**: SAML, OIDC, and Active Directory integration

### Long-term Vision
- [ ] **AI Agent Framework**: Build custom AI agents and workflows
- [ ] **Marketplace**: Community-driven plugins and models
- [ ] **Enterprise Suite**: Advanced features for large organizations
- [ ] **Edge Computing**: On-device AI processing capabilities
- [ ] **Blockchain Integration**: Decentralized conversation verification

## 📞 Support & Community

### Getting Help
- **Documentation**: [Complete Wiki](https://github.com/sanchez314c/LLM-Chat/wiki)
- **Issues**: [Report Problems](https://github.com/sanchez314c/LLM-Chat/issues)
- **Discussions**: [Community Forum](https://github.com/sanchez314c/LLM-Chat/discussions)

### Community Resources
- **Discord**: [LLMChat Community](https://discord.gg/llmchat)
- **Reddit**: [r/LLMChat](https://reddit.com/r/llmchat)
- **Twitter**: [@LLMChatPlatform](https://twitter.com/llmchatplatform)

### Professional Services
- **Custom Development**: Tailored AI conversation solutions
- **Enterprise Support**: Priority assistance for business users
- **Training & Consulting**: Implementation guidance and best practices

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **OpenAI**: For GPT models and API services
- **Anthropic**: For Claude AI and excellent API design
- **xAI**: For GROK and innovative AI approaches
- **Open Source Community**: For libraries, frameworks, and inspiration
- **Contributors**: Everyone who has helped improve this project

## 🔗 Related Projects

- [OpenAI Python](https://github.com/openai/openai-python) - Official OpenAI Python client
- [LangChain](https://github.com/hwchase17/langchain) - Building applications with LLMs
- [Streamlit](https://github.com/streamlit/streamlit) - Web app framework for ML

---

<p align="center">
  <strong>Evolving AI conversations from concept to production 🤖</strong><br>
  <sub>Where every conversation is a step toward the future</sub>
</p>

---

**⭐ Star this repository if LLMChat enhances your AI conversation experiences!**