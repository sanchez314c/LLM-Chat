# LLMChat v0.1.0 - Basic Two-Agent Conversation

## Overview
Basic implementation of a two-agent AI conversation system using Grok API. Two AI agents engage in open-ended conversations with customizable personas.

## Features
- Two-agent conversation with Grok-3-beta
- Customizable agent personas via JSON files
- Conversation logging and export to Markdown
- Pause/resume functionality
- Conversation history storage

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Set environment variable: `export XAI_API_KEY=your_key_here`
3. Run: `python voyeur_chat.py`

## Usage
1. Load or edit agent personas
2. Enter initial prompt
3. Click Start to begin conversation
4. Use Pause/Resume as needed
5. Export conversations to Markdown

## Files
- `voyeur_chat.py` - Main application
- `agent1_persona.json` - Agent 1 persona template
- `agent2_persona.json` - Agent 2 persona template
- `Logs/` - Conversation logs (auto-created)

## Security
✅ **Fixed**: Removed hardcoded API key (now uses environment variable)