import tkinter as tk
from tkinter import ttk, scrolledtext, simpledialog, Menu as tkMenu, messagebox
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
import base64

# --- Dark Theme Colors (Updated to Match Grok UI) ---
DARK_BG = "#1C2526"          # Main background (slightly lighter dark gray)
LEFT_PANEL_BG = "#2A3439"    # Side panels (lighter dark gray)
MEDIUM_DARK_BG = "#3E4A50"   # Interactive elements (buttons, inputs)
LIGHT_TEXT = "#E0E6E9"       # Primary text (off-white)
MEDIUM_TEXT = "#A0A7AB"      # Secondary text (medium gray)
ACCENT_COLOR_USER = "#D4D8DA" # User messages (light gray)
ACCENT_COLOR_ASSISTANT = "#F0F4F5" # Assistant messages (bright white)
BORDER_COLOR = "#3A444A"      # Borders (slightly lighter than side panels)
SELECT_BG_COLOR = "#4A6A74"   # Selection/highlight (subtle teal)
ERROR_TEXT = "#F44336"        # Reddish for errors
SYSTEM_TEXT = "#FFFFFF"      # White for system messages

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
    return {}

def save_config(config_data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f)

config = load_config()
openai_api_key = config.get("openai_api_key", os.getenv(OPENAI_API_KEY_ENV))
openrouter_api_key = config.get("openrouter_api_key", os.getenv(OPENROUTER_API_KEY_ENV))
xai_api_key = config.get("xai_api_key", os.getenv(XAI_API_KEY_ENV))
elevenlabs_api_key = config.get("elevenlabs_api_key", os.getenv(ELEVENLABS_API_KEY_ENV))

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
    
    # Create conversations table if it doesn't exist
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
    
    # Check if voice_id column exists, and add it if it doesn't
    cursor.execute("PRAGMA table_info(conversations)")
    columns = [info[1] for info in cursor.fetchall()]
    if "voice_id" not in columns:
        cursor.execute("ALTER TABLE conversations ADD COLUMN voice_id TEXT")
    
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

def create_conversation_in_db(title="New Chat", model="", system_prompt="", voice_id=""):
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO conversations (title, created_at, last_active_at, llm_model, system_prompt, voice_id) VALUES (?, ?, ?, ?, ?, ?)",
                   (title, now, now, model, system_prompt, voice_id))
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
    cursor.execute("SELECT id, title, last_active_at, voice_id FROM conversations ORDER BY last_active_at DESC")
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

def update_conversation_voice_id_in_db(conversation_id, voice_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE conversations SET voice_id = ? WHERE id = ?", (voice_id, conversation_id))
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
    print("XAI model fetching uses a placeholder list.")
    return ["grok-1", "grok-1.5", "grok-1.5-lora", "grok-1.5-vision", "grok-2", "grok-3-beta", "grok-3-mini-beta", "grok-vision-beta"]

# --- ElevenLabs TTS Function ---
async def generate_and_play_audio(text, voice_id):
    if not elevenlabs_api_key:
        print("Error: ElevenLabs API key not set.")
        return
    if not voice_id:
        print("Error: No voice ID set for this conversation.")
        return

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
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        
        # Convert audio data to pygame-compatible format
        audio_data = io.BytesIO(response.content)
        pygame.mixer.init()
        pygame.mixer.music.load(audio_data)
        pygame.mixer.music.play()
        
        # Wait for playback to finish
        while pygame.mixer.music.get_busy():
            await asyncio.sleep(0.1)
            
    except Exception as e:
        print(f"Error generating audio: {str(e)}")

class VoyeurChat(tk.Tk):
    def __init__(self):
        super().__init__()
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        
        # --- TTK Style Definitions (Updated Colors) ---
        self.style.configure("MainDark.TFrame", background=DARK_BG, borderwidth=0)
        self.style.configure("Dark.TFrame", background=DARK_BG)
        self.style.configure("Secondary.TFrame", background=LEFT_PANEL_BG, borderwidth=0)
        self.style.configure("Secondary.Dark.TLabel", background=LEFT_PANEL_BG, foreground=LIGHT_TEXT, font=("SF Pro Display", 16))
        self.style.configure("Dark.TLabel", background=LEFT_PANEL_BG, foreground=LIGHT_TEXT, font=("SF Pro Display", 16))
        self.style.configure("MainDark.TLabel", background=DARK_BG, foreground=LIGHT_TEXT, font=("SF Pro Display", 16))
        self.style.configure("Section.TLabel", background=LEFT_PANEL_BG, foreground=LIGHT_TEXT, font=("SF Pro Display", 18, "bold"))
        self.style.configure("Dark.TButton", background=MEDIUM_DARK_BG, foreground=LIGHT_TEXT, bordercolor=BORDER_COLOR, borderwidth=0, relief=tk.FLAT, padding=2, font=("SF Pro Display", 16))
        self.style.map("Dark.TButton", background=[('active', '#48555C')], relief=[('pressed', tk.FLAT), ('active', tk.FLAT)])
        self.style.configure("Dark.TMenubutton", background=MEDIUM_DARK_BG, foreground=LIGHT_TEXT, bordercolor=BORDER_COLOR, borderwidth=0, relief=tk.FLAT, arrowcolor=LIGHT_TEXT, padding=2, font=("SF Pro Display", 16))
        self.style.map("Dark.TMenubutton", background=[('active', '#48555C')])
        self.style.configure("Secondary.Dark.Horizontal.TScale", background=DARK_BG, troughcolor="#3A3A3C", sliderrelief=tk.FLAT, sliderthickness=8, bordercolor=BORDER_COLOR)
        self.style.map("Secondary.Dark.Horizontal.TScale", background=[('active', MEDIUM_DARK_BG)], troughcolor=[('active', SELECT_BG_COLOR)])
        self.style.configure("Dark.TEntry", fieldbackground=MEDIUM_DARK_BG, foreground=LIGHT_TEXT, bordercolor=BORDER_COLOR, borderwidth=0, relief=tk.FLAT, insertcolor=LIGHT_TEXT, padding=2, font=("SF Pro Display", 16))
        self.style.configure("TScrollbar", troughcolor=DARK_BG, background=MEDIUM_DARK_BG, bordercolor=BORDER_COLOR, arrowcolor=LIGHT_TEXT, relief=tk.FLAT, arrowsize=12)
        self.style.map("TScrollbar", background=[('active', SELECT_BG_COLOR)])

        print("[DEBUG INIT] VoyeurChat __init__ START")
        self.title("Voyeur Chat")
        self.geometry("1600x1200")

        self.conversation_id_map = {}
        self.current_conversation_id = None
        self.current_voice_id = None
        self.available_models = []
        self.model_groups = {'OpenAI': [], 'OpenRouter': [], 'XAI': []}
        self.chat_modes = ["Normal", "Assistant", "Code Assistant", "Sarcastic Assistant"]
        self.current_chat_mode = tk.StringVar(self)
        self.current_chat_mode.set(self.chat_modes[0])
        self.conversation_log = []
        self.placeholder_visible = True
        self.message_frames = []  # To store message frames for clearing

        init_database()
        self._init_ui()
        self.load_initial_models()
        self.load_or_create_conversation()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        print("[DEBUG INIT] VoyeurChat __init__ END")

    def _init_ui(self):
        print("[DEBUG _init_ui] START")
        self.configure(bg=DARK_BG)
        self.config_menu = tkMenu(self, tearoff=0, bg=MEDIUM_DARK_BG, fg=LIGHT_TEXT, activebackground=SELECT_BG_COLOR, activeforeground=LIGHT_TEXT, relief=tk.FLAT, bd=0, font=("SF Pro Display", 16))
        self.settings_menu = tkMenu(self.config_menu, tearoff=0, bg=MEDIUM_DARK_BG, fg=LIGHT_TEXT, activebackground=SELECT_BG_COLOR, activeforeground=LIGHT_TEXT, relief=tk.FLAT, bd=0, font=("SF Pro Display", 16))
        self.settings_menu.add_command(label="Configure API Keys", command=self.configure_api_keys)
        self.settings_menu.add_command(label="Rename Thread", command=self.rename_selected_thread)
        self.settings_menu.add_command(label="Set ElevenLabs ID", command=self.set_elevenlabs_id)
        self.config_menu.add_cascade(label="Settings", menu=self.settings_menu)
        self.config(menu=self.config_menu)

        main_frame = ttk.Frame(self, style="MainDark.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Left Panel: Chat List (Dark Blue, Adjusted Width)
        chat_list_panel = ttk.Frame(main_frame, width=300, style="Secondary.TFrame")  # Increased from 220 to 300
        chat_list_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 1))
        chat_list_panel.pack_propagate(False)
        ttk.Label(chat_list_panel, text="Chats", style="Section.TLabel").pack(pady=(8, 4), anchor="w", padx=8)
        self.search_entry = ttk.Entry(chat_list_panel, style="Dark.TEntry")
        self.search_entry.pack(fill=tk.X, pady=4, padx=8)
        self.search_entry.insert(0, "Search chats...")
        self.search_entry.bind("<FocusIn>", self.clear_search_placeholder)
        self.search_entry.bind("<FocusOut>", self.restore_search_placeholder)
        self.chat_listbox = tk.Listbox(chat_list_panel, height=30, bg=LEFT_PANEL_BG, fg=LIGHT_TEXT,
                                       selectbackground=SELECT_BG_COLOR, selectforeground=LIGHT_TEXT,
                                       relief=tk.FLAT, bd=0, highlightthickness=0, exportselection=False, font=("SF Pro Display", 16))
        self.chat_listbox.pack(fill=tk.BOTH, expand=True, pady=4, padx=4)
        self.chat_listbox.bind("<<ListboxSelect>>", self.on_chat_select)
        self.chat_listbox.bind("<Button-3>", self.show_chat_list_context_menu)
        ttk.Button(chat_list_panel, text="Delete Chat", command=self.delete_selected_thread, style="Dark.TButton").pack(fill=tk.X, pady=(0, 4), padx=8, side=tk.BOTTOM)
        ttk.Button(chat_list_panel, text="New Chat", command=self.create_new_conversation, style="Dark.TButton").pack(fill=tk.X, pady=(0, 8), padx=8, side=tk.BOTTOM)

        # Center Panel: Chat Display and Input
        center_panel = ttk.Frame(main_frame, style="MainDark.TFrame")
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 1))

        # Canvas for scrollable message area
        self.chat_canvas = tk.Canvas(center_panel, bg=DARK_BG, highlightthickness=0)
        self.chat_scrollbar = ttk.Scrollbar(center_panel, orient=tk.VERTICAL, command=self.chat_canvas.yview)
        self.chat_scrollable_frame = ttk.Frame(self.chat_canvas, style="MainDark.TFrame")

        self.chat_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        )

        self.chat_canvas.configure(yscrollcommand=self.chat_scrollbar.set)

        self.chat_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(0, 4))
        self.chat_canvas.create_window((0, 0), window=self.chat_scrollable_frame, anchor="nw")

        # Bind mouse wheel for scrolling
        self.chat_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        input_area_frame = ttk.Frame(center_panel, style="MainDark.TFrame")
        input_area_frame.pack(fill=tk.X, pady=(0, 4))
        self.user_input = scrolledtext.ScrolledText(input_area_frame, height=2, bg=MEDIUM_DARK_BG, fg=LIGHT_TEXT,  # Increased height to 2
                                                   insertbackground=LIGHT_TEXT, wrap=tk.WORD, relief=tk.FLAT,
                                                   bd=0, highlightthickness=0, font=("SF Pro Display", 16), padx=8, pady=4,
                                                   selectbackground=SELECT_BG_COLOR)
        self.user_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 2))
        self.user_input.insert("1.0", "Type a message...")
        self.user_input.bind("<FocusIn>", self.clear_placeholder_text)
        self.user_input.bind("<FocusOut>", self.restore_placeholder_text)
        self.user_input.bind("<Return>", self.send_message_on_enter)
        self.user_input.bind("<Shift-Return>", self.add_newline)
        self.send_button = ttk.Button(input_area_frame, text="✈", width=2, command=self.send_message, style="Dark.TButton")
        self.send_button.pack(side=tk.RIGHT, fill=tk.Y, padx=(2, 4))

        # Right Panel: Settings (Dark Blue, Adjusted Width)
        settings_panel = ttk.Frame(main_frame, width=250, style="Secondary.TFrame")  # Decreased from 300 to 250
        settings_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 0))
        settings_panel.pack_propagate(False)

        controls_frame = settings_panel
        ttk.Label(controls_frame, text="Model", style="Section.TLabel").pack(pady=(8, 4), anchor="w", padx=8)
        self.model_var = tk.StringVar(self)
        self.model_menu = ttk.OptionMenu(controls_frame, self.model_var, "Loading models...", style="Dark.TMenubutton")
        self.model_menu.pack(fill=tk.X, pady=2, padx=8)
        self.model_var.trace_add("write", self.on_model_change)
        ttk.Button(controls_frame, text="Refresh Models", command=self.refresh_models, style="Dark.TButton").pack(fill=tk.X, pady=(0, 8), padx=8)

        ttk.Label(controls_frame, text="Chat Mode", style="Section.TLabel").pack(pady=(8, 4), anchor="w", padx=8)
        ttk.Label(controls_frame, text="Personality", style="Secondary.Dark.TLabel").pack(pady=(4, 0), anchor="w", padx=8)
        self.chat_mode_menu = ttk.OptionMenu(controls_frame, self.current_chat_mode, self.current_chat_mode.get(), *self.chat_modes, style="Dark.TMenubutton")
        self.chat_mode_menu.pack(fill=tk.X, pady=2, padx=8)
        self.current_chat_mode.trace_add("write", self.on_chat_mode_change)

        ttk.Label(controls_frame, text="Voice ID", style="Secondary.Dark.TLabel").pack(pady=(4, 0), anchor="w", padx=8)
        self.voice_id_var = tk.StringVar(self)
        self.voice_id_entry = ttk.Entry(controls_frame, textvariable=self.voice_id_var, style="Dark.TEntry")
        self.voice_id_entry.pack(fill=tk.X, pady=2, padx=8)
        ttk.Button(controls_frame, text="Save Voice ID", command=self.save_voice_id, style="Dark.TButton").pack(fill=tk.X, pady=(0, 8), padx=8)

        ttk.Label(controls_frame, text="Temp", style="Secondary.Dark.TLabel").pack(pady=(4, 0), anchor="w", padx=8)
        temp_frame = ttk.Frame(controls_frame, style="Secondary.TFrame")
        temp_frame.pack(fill=tk.X, pady=2, padx=8)
        self.temperature_var = tk.DoubleVar(value=0.7)
        self.temp_slider = ttk.Scale(temp_frame, from_=0, to_=1, orient=tk.HORIZONTAL, variable=self.temperature_var, command=self.update_temp_display, style="Secondary.Dark.Horizontal.TScale")
        self.temp_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.temp_display = ttk.Label(temp_frame, text=f"{self.temperature_var.get():.2f}", style="Secondary.Dark.TLabel", font=("SF Pro Display", 14))
        self.temp_display.pack(side=tk.RIGHT, padx=4)

        ttk.Label(controls_frame, text="Max Tokens", style="Secondary.Dark.TLabel").pack(pady=(4, 0), anchor="w", padx=8)
        self.max_tokens_var = tk.IntVar(value=1024)
        self.max_tokens_entry = ttk.Entry(controls_frame, textvariable=self.max_tokens_var, style="Dark.TEntry")
        self.max_tokens_entry.pack(fill=tk.X, pady=2, padx=8)
        max_tokens_presets_options = ["1024", "2048", "4096", "8192", "16000", "Custom"]
        self.max_tokens_preset_var = tk.StringVar(value="Custom")
        self.max_tokens_preset_menu = ttk.OptionMenu(controls_frame, self.max_tokens_preset_var, self.max_tokens_preset_var.get(), *max_tokens_presets_options, command=self.set_max_tokens_from_preset, style="Dark.TMenubutton")
        self.max_tokens_preset_menu.pack(fill=tk.X, pady=2, padx=8)

        ttk.Label(controls_frame, text="Context Limit", style="Secondary.Dark.TLabel").pack(pady=(4, 0), anchor="w", padx=8)
        context_options = ["Last 10 Messages", "Last 20 Messages", "Last 50 Messages", "No Limit"]
        self.context_limit_var = tk.StringVar(value="Last 50 Messages")
        ttk.OptionMenu(controls_frame, self.context_limit_var, self.context_limit_var.get(), *context_options, style="Dark.TMenubutton").pack(fill=tk.X, pady=2, padx=8)

        ttk.Label(controls_frame, text="Presence", style="Secondary.Dark.TLabel").pack(pady=(4, 0), anchor="w", padx=8)
        presence_frame = ttk.Frame(controls_frame, style="Secondary.TFrame")
        presence_frame.pack(fill=tk.X, pady=2, padx=8)
        self.presence_penalty_var = tk.DoubleVar(value=0.0)
        self.presence_penalty_slider = ttk.Scale(presence_frame, from_=-2.0, to_=2.0, orient=tk.HORIZONTAL, variable=self.presence_penalty_var, command=lambda v: self.presence_display.config(text=f"{self.presence_penalty_var.get():.1f}"), style="Secondary.Dark.Horizontal.TScale")
        self.presence_penalty_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.presence_display = ttk.Label(presence_frame, text=f"{self.presence_penalty_var.get():.1f}", style="Secondary.Dark.TLabel", font=("SF Pro Display", 14))
        self.presence_display.pack(side=tk.RIGHT, padx=4)
        ttk.Button(controls_frame, text="Reset", command=self.reset_presence_penalty, style="Dark.TButton").pack(fill=tk.X, pady=2, padx=8)

        ttk.Label(controls_frame, text="Frequency", style="Secondary.Dark.TLabel").pack(pady=(4, 0), anchor="w", padx=8)
        frequency_frame = ttk.Frame(controls_frame, style="Secondary.TFrame")
        frequency_frame.pack(fill=tk.X, pady=2, padx=8)
        self.frequency_penalty_var = tk.DoubleVar(value=0.0)
        self.frequency_penalty_slider = ttk.Scale(frequency_frame, from_=-2.0, to_=2.0, orient=tk.HORIZONTAL, variable=self.frequency_penalty_var, command=lambda v: self.frequency_display.config(text=f"{self.frequency_penalty_var.get():.1f}"), style="Secondary.Dark.Horizontal.TScale")
        self.frequency_penalty_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.frequency_display = ttk.Label(frequency_frame, text=f"{self.frequency_penalty_var.get():.1f}", style="Secondary.Dark.TLabel", font=("SF Pro Display", 14))
        self.frequency_display.pack(side=tk.RIGHT, padx=4)
        ttk.Button(controls_frame, text="Reset", command=self.reset_frequency_penalty, style="Dark.TButton").pack(fill=tk.X, pady=2, padx=8)

        ttk.Label(controls_frame, text="Top P", style="Secondary.Dark.TLabel").pack(pady=(4, 0), anchor="w", padx=8)
        top_p_frame = ttk.Frame(controls_frame, style="Secondary.TFrame")
        top_p_frame.pack(fill=tk.X, pady=2, padx=8)
        self.top_p_var = tk.DoubleVar(value=1.0)
        self.top_p_slider = ttk.Scale(top_p_frame, from_=0.0, to_=1.0, orient=tk.HORIZONTAL, variable=self.top_p_var, command=lambda v: self.top_p_display.config(text=f"{self.top_p_var.get():.2f}"), style="Secondary.Dark.Horizontal.TScale")
        self.top_p_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.top_p_display = ttk.Label(top_p_frame, text=f"{self.top_p_var.get():.2f}", style="Secondary.Dark.TLabel", font=("SF Pro Display", 14))
        self.top_p_display.pack(side=tk.RIGHT, padx=4)
        ttk.Button(controls_frame, text="Reset", command=self.reset_top_p, style="Dark.TButton").pack(fill=tk.X, pady=2, padx=8)

        ttk.Label(controls_frame, text="Top K", style="Secondary.Dark.TLabel").pack(pady=(4, 0), anchor="w", padx=8)
        self.top_k_var = tk.IntVar(value=40)
        self.top_k_entry = ttk.Entry(controls_frame, textvariable=self.top_k_var, style="Dark.TEntry")
        self.top_k_entry.pack(fill=tk.X, pady=2, padx=8)
        ttk.Button(controls_frame, text="Reset", command=self.reset_top_k, style="Dark.TButton").pack(fill=tk.X, pady=2, padx=8)

        ttk.Label(controls_frame, text="Reasoning", style="Secondary.Dark.TLabel").pack(pady=(4, 0), anchor="w", padx=8)
        reasoning_options = ["None", "Low", "Medium", "High"]
        self.reasoning_effort_var = tk.StringVar(value="Medium")
        self.reasoning_effort_menu = ttk.OptionMenu(controls_frame, self.reasoning_effort_var, self.reasoning_effort_var.get(), *reasoning_options, style="Dark.TMenubutton")
        self.reasoning_effort_menu.pack(fill=tk.X, pady=2, padx=8)

        ttk.Label(controls_frame, text="System Prompt", style="Secondary.Dark.TLabel").pack(pady=(4, 0), anchor="w", padx=8)
        self.system_prompt_text_widget = scrolledtext.ScrolledText(controls_frame, height=6, wrap=tk.WORD,
                                                                 bg=MEDIUM_DARK_BG, fg=LIGHT_TEXT, insertbackground=LIGHT_TEXT,
                                                                 relief=tk.FLAT, bd=0, font=("SF Pro Display", 16), selectbackground=SELECT_BG_COLOR)
        self.system_prompt_text_widget.pack(fill=tk.X, pady=2, padx=8)
        self.refresh_button = ttk.Button(controls_frame, text="Refresh Models", command=self.load_initial_models, style="Dark.TButton")
        self.refresh_button.pack(pady=8, fill=tk.X, padx=8)
        print("[DEBUG _init_ui] END")

    def _on_mousewheel(self, event):
        self.chat_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def set_elevenlabs_id(self):
        global elevenlabs_api_key, config
        new_elevenlabs = simpledialog.askstring("ElevenLabs ID", "Enter your ElevenLabs API Key:", initialvalue=elevenlabs_api_key or "", parent=self)
        if new_elevenlabs is not None:
            config["elevenlabs_api_key"] = new_elevenlabs
            elevenlabs_api_key = new_elevenlabs
            save_config(config)
            self.add_log_message("ElevenLabs API key updated.", "system")

    def save_voice_id(self):
        if self.current_conversation_id is None:
            messagebox.showwarning("No Selection", "Please select a conversation to set the voice ID.")
            return
        voice_id = self.voice_id_var.get().strip()
        update_conversation_voice_id_in_db(self.current_conversation_id, voice_id)
        self.current_voice_id = voice_id
        self.add_log_message(f"Voice ID updated to: {voice_id}", "system")

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
        print("[DEBUG] Creating new conversation")
        system_prompt = self.system_prompt_text_widget.get(1.0, tk.END).strip()
        model_selection = self.model_var.get()
        current_model = "" if not model_selection or model_selection == "Loading models..." else model_selection
        new_title = f"New Chat {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        self.current_conversation_id = create_conversation_in_db(title=new_title, model=current_model, system_prompt=system_prompt, voice_id="")
        # Clear existing message frames
        for frame in self.message_frames:
            frame.destroy()
        self.message_frames = []
        self.conversation_log = []
        self.current_voice_id = None
        self.voice_id_var.set("")
        self.refresh_chat_list()
        print(f"[DEBUG] New conversation created with ID: {self.current_conversation_id}")

    def refresh_chat_list(self):
        print("[DEBUG] Refreshing chat list")
        self.chat_listbox.delete(0, tk.END)
        conversations = fetch_conversations_from_db()
        self.conversation_id_map.clear()
        for index, (conv_id, title, _, _) in enumerate(conversations):
            display_title = title if title else f"Conversation {conv_id}"
            self.chat_listbox.insert(tk.END, display_title)
            self.conversation_id_map[index] = conv_id
            if conv_id == self.current_conversation_id:
                self.chat_listbox.selection_clear(0, tk.END)
                self.chat_listbox.selection_set(index)
                self.chat_listbox.activate(index)
                self.chat_listbox.see(index)
        print(f"[DEBUG] Chat list refreshed. Current ID: {self.current_conversation_id}. Map: {self.conversation_id_map}")

    def on_chat_select(self, event):
        print("[DEBUG] on_chat_select triggered")
        if not self.chat_listbox.curselection():
            print("[DEBUG] on_chat_select: no selection")
            return
        selected_index = self.chat_listbox.curselection()[0]
        if selected_index not in self.conversation_id_map:
            print(f"[DEBUG] Error: Index {selected_index} not in conversation_id_map.")
            return
        conv_id = self.conversation_id_map[selected_index]
        if conv_id == self.current_conversation_id and event is not None:
            print(f"[DEBUG] Same chat selected ({conv_id}), no reload.")
            return
        print(f"[DEBUG] Selecting conversation ID: {conv_id}")
        self.current_conversation_id = conv_id
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT llm_model, system_prompt, voice_id FROM conversations WHERE id = ?", (self.current_conversation_id,))
        conv_data = cursor.fetchone()
        conn.close()
        if conv_data:
            loaded_model, loaded_system_prompt, loaded_voice_id = conv_data
            if loaded_model and loaded_model != "Loading models..." and self.model_var.get() != loaded_model:
                if self.available_models and loaded_model in self.available_models:
                    self.model_var.set(loaded_model)
                elif self.available_models:
                    print(f"[DEBUG] Stored model '{loaded_model}' not in available list, using first available.")
                else:
                    print(f"[DEBUG] Stored model '{loaded_model}' but no models available in UI yet.")
            if loaded_system_prompt:
                self.system_prompt_text_widget.delete(1.0, tk.END)
                self.system_prompt_text_widget.insert(tk.END, loaded_system_prompt)
            self.current_voice_id = loaded_voice_id if loaded_voice_id else ""
            self.voice_id_var.set(self.current_voice_id)
        
        # Clear existing message frames
        for frame in self.message_frames:
            frame.destroy()
        self.message_frames = []
        
        messages = fetch_messages_from_db(self.current_conversation_id)
        self.conversation_log = []
        for role, content, timestamp_str in messages:
            try:
                formatted_time = datetime.fromisoformat(timestamp_str).strftime("[%H:%M:%S]")
            except ValueError:
                formatted_time = f"[{timestamp_str}]"
            self.add_log_message(content, role, timestamp_str)
        print(f"[DEBUG] Loaded messages for conversation ID: {self.current_conversation_id}")

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
            # Clear message frames
            for frame in self.message_frames:
                frame.destroy()
            self.message_frames = []
            self.conversation_log = []
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

    def add_log_message(self, message_text, level="system", timestamp_str=None):
        # Format timestamp
        if timestamp_str is None:
            timestamp = datetime.now().strftime("[%H:%M:%S]")
        else:
            try:
                timestamp = datetime.fromisoformat(timestamp_str).strftime("[%H:%M:%S]")
            except ValueError:
                timestamp = f"[{timestamp_str}]"
        
        # Create a frame for the message and play button
        message_frame = ttk.Frame(self.chat_scrollable_frame, style="MainDark.TFrame")
        message_frame.pack(fill=tk.X, padx=15, pady=10, anchor="w")  # Adjusted padding
        self.message_frames.append(message_frame)

        # Create the message label
        message_label = ttk.Label(
            message_frame,
            text=f"{timestamp} {level.capitalize()}: {message_text}",
            style="MainDark.TLabel",
            wraplength=800,  # Adjusted for wider center panel
            justify=tk.LEFT,
            foreground={
                "user": ACCENT_COLOR_USER,
                "assistant": ACCENT_COLOR_ASSISTANT,
                "system": SYSTEM_TEXT,
                "error": ERROR_TEXT
            }.get(level, LIGHT_TEXT),
            font=("SF Pro Display", 16, "bold" if level == "user" else "normal")
        )
        message_label.pack(side=tk.LEFT, anchor="w")

        # Add Play button for user and assistant messages
        if level in ["user", "assistant"]:
            play_button = ttk.Button(
                message_frame,
                text="▶",
                command=lambda: self.play_message(message_text),
                style="Dark.TButton",
                width=2
            )
            play_button.pack(side=tk.RIGHT, padx=5)

        # Update conversation log and database
        if level in ["user", "assistant"]:
            self.conversation_log.append({"role": level, "content": message_text})
        if self.current_conversation_id and level in ["user", "assistant"]:
            add_message_to_db(self.current_conversation_id, level, message_text)
            if level == "user":
                self.update_conversation_title_from_message(message_text)

        # Scroll to the bottom
        self.chat_canvas.yview_moveto(1.0)

    def play_message(self, message_text):
        # Schedule the async task within Tkinter's event loop
        asyncio.get_event_loop().create_task(generate_and_play_audio(message_text, self.current_voice_id))

    def load_initial_models(self):
        self.add_log_message("Fetching models...", "system")
        self.refresh_button.config(state=tk.DISABLED, text="Refreshing...")
        self.after(100, self._fetch_all_models_thread)

    def _fetch_all_models_thread(self):
        print(f"[DEBUG _fetch_all_models_thread] START")
        self.model_groups = {'OpenAI': [], 'OpenRouter': [], 'XAI': []}
        if openai_api_key:
            openai_models_list = fetch_openai_models(openai_api_key)
            if openai_models_list:
                self.add_log_message(f"Fetched {len(openai_models_list)} OpenAI models", "system")
                self.model_groups['OpenAI'] = sorted(openai_models_list)
            else:
                self.add_log_message("No/Error OpenAI models", "error")
        else:
            self.add_log_message("OpenAI key not set", "error")
        if openrouter_api_key:
            openrouter_models_list = fetch_openrouter_models(openrouter_api_key)
            if openrouter_models_list:
                self.add_log_message(f"Fetched {len(openrouter_models_list)} OpenRouter models", "system")
                self.model_groups['OpenRouter'] = sorted(openrouter_models_list)
            else:
                self.add_log_message("No/Error OpenRouter models", "error")
        else:
            self.add_log_message("OpenRouter key not set", "error")
        if xai_api_key:
            xai_models_list = fetch_xai_models(xai_api_key)
            if xai_models_list:
                self.add_log_message(f"Fetched {len(xai_models_list)} XAI models", "system")
                self.model_groups['XAI'] = sorted(xai_models_list)
            else:
                self.add_log_message("No/Error XAI models", "error")
        else:
            self.add_log_message("XAI key not set", "error")
        self.available_models = []
        for provider in ['OpenAI', 'OpenRouter', 'XAI']:
            if provider in self.model_groups and self.model_groups[provider]:
                for model_id_str in self.model_groups[provider]:
                    self.available_models.append(f"{provider}: {model_id_str}")
        if not self.available_models:
            self.add_log_message("No models available from any provider.", "error")
        self.after(0, self.update_model_list)
        self.refresh_button.config(state=tk.NORMAL, text="Refresh Models")
        print(f"[DEBUG _fetch_all_models_thread] END - Models: {self.available_models}")

    def update_model_list(self):
        print("[DEBUG] Updating model list in UI")
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
        print(f"[DEBUG] Model list updated. Selected: {self.model_var.get()}")

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
        return prompts.get(mode, "You are a helpful AI assistant.")

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
        print("[DEBUG process_ai_response] START")
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
        else:
            self.add_log_message(f"Error: Unknown provider '{provider}'.", "error")
            return
        client = openai.OpenAI(**client_config)
        system_prompt = self.get_system_prompt()
        messages = [{"role": "system", "content": system_prompt}] + self.get_context_limit_messages()
        try:
            print(f"[DEBUG] Calling API for {provider}: {model_id}")
            response_stream = client.chat.completions.create(
                model=model_id, messages=messages,
                temperature=self.temperature_var.get(), max_tokens=self.max_tokens_var.get(),
                presence_penalty=self.presence_penalty_var.get(), frequency_penalty=self.frequency_penalty_var.get(),
                top_p=self.top_p_var.get(), stream=True
            )
            full_response = ""
            for chunk in response_stream:
                text = chunk.choices[0].delta.content or ""
                if text:
                    full_response += text
            if full_response.strip() and self.current_conversation_id:
                self.add_log_message(full_response, "assistant")
            print(f"[DEBUG process_ai_response] END - Response received from {provider}")
        except Exception as e:
            error_msg = f"API Error ({provider} {model_id}): {str(e)}"
            print(error_msg)
            self.add_log_message(error_msg, "error")

    def configure_api_keys(self):
        global openai_api_key, openrouter_api_key, xai_api_key, elevenlabs_api_key, config
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
        new_elevenlabs = simpledialog.askstring("API Key", "ElevenLabs API Key:", initialvalue=elevenlabs_api_key or "", parent=self)
        if new_elevenlabs is not None:
            config["elevenlabs_api_key"] = new_elevenlabs
            elevenlabs_api_key = new_elevenlabs
        save_config(config)
        self.add_log_message("API keys updated. Refreshing models...", "system")
        self.load_initial_models()

    def on_model_change(self, *args):
        print(f"Model changed to: {self.model_var.get()}")

    def on_chat_mode_change(self, *args):
        print(f"Chat mode: {self.current_chat_mode.get()}")

    def on_closing(self):
        self.destroy()

if __name__ == "__main__":
    print("[DEBUG MAIN] App starting...")
    app = VoyeurChat()
    app.mainloop()
    print("[DEBUG MAIN] App finished.")