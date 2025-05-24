import tkinter as tk
from tkinter import ttk, scrolledtext, simpledialog, Menu as tkMenu, messagebox
import openai
import requests
import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime
 # --- Dark Theme Colors ---
DARK_BG = "#262626"          # Very dark gray, slightly lighter than pure black
MEDIUM_DARK_BG = "#333333"   # For input fields or secondary panels
LIGHT_TEXT = "#E0E0E0"       # Off-white for primary text
MEDIUM_TEXT = "#A0A0A0"      # Medium gray for secondary text or timestamps
ACCENT_COLOR_USER = "#4CAF50" # Greenish for user messages
ACCENT_COLOR_ASSISTANT = "#2196F3" # Bluish for assistant messages
BORDER_COLOR = "#404040"      # Subtle border color
SELECT_BG_COLOR = "#4A4A4A"   # Selection background for listbox/menus
ERROR_TEXT = "#F44336"        # Reddish color for error messages
SYSTEM_TEXT = "#FFC107"       # Yellowish color for system messages
 # --- End Dark Theme Colors ---

# --- Configuration and API Key Management ---
CONFIG_FILE = os.path.expanduser("~/.voyeur_chat_config.json")
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"
XAI_API_KEY_ENV = "XAI_API_KEY"

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

if openai_api_key:
    openai.api_key = openai_api_key

# --- SQLite Database Setup for Conversation History ---
DB_DIR = os.path.expanduser("~/.lightllm_chat")
DB_PATH = os.path.join(DB_DIR, "lightllm_chat.db")

def ensure_db_directory():
    Path(DB_DIR).mkdir(parents=True, exist_ok=True)

def init_database():
    ensure_db_directory()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_active_at TEXT NOT NULL,
        llm_model TEXT,
        system_prompt TEXT
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        api_response_json TEXT,
        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
    )""")
    conn.commit()
    conn.close()

def create_conversation_in_db(title="New Chat", model="", system_prompt=""): # Renamed from global create_conversation
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO conversations (title, created_at, last_active_at, llm_model, system_prompt) VALUES (?, ?, ?, ?, ?)",
                   (title, now, now, model, system_prompt))
    conn.commit()
    conv_id = cursor.lastrowid
    conn.close()
    return conv_id

def add_message_to_db(conversation_id, role, content, api_response_json=None): # Renamed from global add_message
    timestamp = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (conversation_id, role, content, timestamp, api_response_json) VALUES (?, ?, ?, ?, ?)",
                   (conversation_id, role, content, timestamp, api_response_json))
    cursor.execute("UPDATE conversations SET last_active_at = ? WHERE id = ?", (timestamp, conversation_id))
    conn.commit()
    conn.close()

def fetch_conversations_from_db(): # Renamed
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, last_active_at FROM conversations ORDER BY last_active_at DESC")
    conversations = cursor.fetchall()
    conn.close()
    return conversations

def fetch_messages_from_db(conversation_id): # Renamed
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content, timestamp FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC", (conversation_id,))
    messages = cursor.fetchall()
    conn.close()
    return messages

def update_conversation_title_in_db(conversation_id, new_title): # Renamed
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE conversations SET title = ? WHERE id = ?", (new_title, conversation_id))
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
    if not api_key_to_use: return []
    try:
        client = openai.OpenAI(api_key=api_key_to_use)
        models = client.models.list()
        return sorted([model.id for model in models.data if "gpt" in model.id.lower() or "text-" in model.id.lower()], reverse=True) # Broader filter
    except Exception as e:
        print(f"Error fetching OpenAI models: {e}")
        return []

def fetch_openrouter_models(api_key_to_use):
    if not api_key_to_use: return []
    try:
        response = requests.get("https://openrouter.ai/api/v1/models", headers={"Authorization": f"Bearer {api_key_to_use}"})
        response.raise_for_status()
        models_data = response.json()["data"]
        return sorted([model["id"] for model in models_data], key=lambda x: x.lower())
    except Exception as e:
        print(f"Error fetching OpenRouter models: {e}")
        return []

def fetch_xai_models(api_key_to_use):
    if not api_key_to_use: return []
    # Placeholder as XAI doesn't have a public /models endpoint.
    print("XAI model fetching uses a placeholder list.")
    return ["grok-1", "grok-1.5", "grok-1.5-lora", "grok-1.5-vision", "grok-2", "grok-3-beta", "grok-3-mini-beta", "grok-vision-beta"] # Extended list of XAI models

class VoyeurChat(tk.Tk):
    def __init__(self):
        super().__init__()
        # Initialize TTK styling
        self.style = ttk.Style(self)
        self.style.theme_use('clam')  # Applying 'clam' theme for better UI appearance on macOS
        # --- TTK Style Definitions ---
        self.style.configure("MainDark.TFrame", background="#1E1E1E")
        self.style.configure("Dark.TFrame", background=DARK_BG)
        self.style.configure("Secondary.TFrame", background=MEDIUM_DARK_BG)
        self.style.configure("Secondary.Dark.TLabel", background=MEDIUM_DARK_BG, foreground=LIGHT_TEXT, font=("Arial", 10))
        self.style.configure("Dark.TLabel", background=DARK_BG, foreground=LIGHT_TEXT, font=("Arial", 10))
        self.style.configure("MainDark.TLabel", background="#1E1E1E", foreground=LIGHT_TEXT, font=("Arial", 10))

        # Button Style
        self.style.configure("Dark.TButton", background=MEDIUM_DARK_BG, foreground=LIGHT_TEXT, bordercolor=BORDER_COLOR, borderwidth=1, relief=tk.SOLID, padding=5)
        self.style.map("Dark.TButton", background=[('active', '#555555')], relief=[('pressed', tk.SUNKEN), ('active', tk.RAISED)])

        # OptionMenu (Menubutton part) Style
        self.style.configure("Dark.TMenubutton", background=MEDIUM_DARK_BG, foreground=LIGHT_TEXT, bordercolor=BORDER_COLOR, borderwidth=1, relief=tk.SOLID, arrowcolor=LIGHT_TEXT, padding=5)
        self.style.map("Dark.TMenubutton", background=[('active', '#555555')])

        # Scale Style - Ensure background matches parent frame
        self.style.configure("Secondary.Dark.Horizontal.TScale", background=MEDIUM_DARK_BG, troughcolor=BORDER_COLOR, sliderrelief=tk.RAISED, sliderthickness=15, bordercolor=BORDER_COLOR)
        self.style.map("Secondary.Dark.Horizontal.TScale", background=[('active', MEDIUM_DARK_BG)], troughcolor=[('active', SELECT_BG_COLOR)])

        # Entry Style
        self.style.configure("Dark.TEntry", fieldbackground=MEDIUM_DARK_BG, foreground=LIGHT_TEXT, bordercolor=BORDER_COLOR, borderwidth=1, relief=tk.SOLID, insertcolor=LIGHT_TEXT, padding=5)

        # General TScrollbar Style
        self.style.configure("TScrollbar", troughcolor=DARK_BG, background=MEDIUM_DARK_BG, bordercolor=BORDER_COLOR, arrowcolor=LIGHT_TEXT, relief=tk.SOLID, arrowsize=14)
        self.style.map("TScrollbar", background=[('active', SELECT_BG_COLOR)])
        # --- End TTK Style Definitions ---        print("[DEBUG INIT] VoyeurChat __init__ START")
        self.title("Voyeur Chat")
        self.geometry("1600x1200")

        self.conversation_id_map = {}
        self.current_conversation_id = None
        
        self.available_models = []
        self.model_groups = {'OpenAI': [], 'OpenRouter': [], 'XAI': []}
        self.chat_modes = ["Normal", "Assistant", "Code Assistant", "Sarcastic Assistant"]
        self.current_chat_mode = tk.StringVar(self)
        self.current_chat_mode.set(self.chat_modes[0]) # Default to first mode
        self.conversation_log = []

        print("[DEBUG INIT] Calling init_database()")
        init_database()
        print("[DEBUG INIT] Calling _init_ui()")
        self._init_ui()
        print("[DEBUG INIT] Calling load_initial_models()")
        self.load_initial_models() # Fetches models and populates dropdown
        print("[DEBUG INIT] Calling load_or_create_conversation()")
        self.load_or_create_conversation() # Sets up initial chat state
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        print("[DEBUG INIT] VoyeurChat __init__ END")

    def _init_ui(self):
        print("[DEBUG _init_ui] START")
        self.configure(bg=DARK_BG)  # Set root window background

        # Menu
        # Note: Standard tk.Menu styling is limited. These bg/fg might not apply to all parts on all OSes.
        self.config_menu = tkMenu(self, tearoff=0, bg=MEDIUM_DARK_BG, fg=LIGHT_TEXT, activebackground=SELECT_BG_COLOR, activeforeground=LIGHT_TEXT, relief=tk.FLAT, bd=0)
        self.settings_menu = tkMenu(self.config_menu, tearoff=0, bg=MEDIUM_DARK_BG, fg=LIGHT_TEXT, activebackground=SELECT_BG_COLOR, activeforeground=LIGHT_TEXT, relief=tk.FLAT, bd=0)
        self.settings_menu.add_command(label="Configure API Keys", command=self.configure_api_keys) # This will use menu's active colors
        self.config_menu.add_cascade(label="Settings", menu=self.settings_menu)
        self.config(menu=self.config_menu)

        main_frame = ttk.Frame(self, style="MainDark.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Far-Left Pane: Chat List Panel
        chat_list_panel = ttk.Frame(main_frame, width=250, style="Secondary.TFrame")
        chat_list_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        chat_list_panel.pack_propagate(False)
        # Use the label style configured for Secondary.TFrame background
        ttk.Label(chat_list_panel, text="Conversations", style="Secondary.Dark.TLabel").pack(pady=(10, 5), anchor="w", padx=5)
        ttk.Button(chat_list_panel, text="New Chat", command=self.create_new_conversation, style="Dark.TButton").pack(fill=tk.X, pady=5, padx=5)
        self.chat_listbox = tk.Listbox(chat_list_panel, height=30, bg=MEDIUM_DARK_BG, fg=LIGHT_TEXT,
                                        selectbackground=SELECT_BG_COLOR, selectforeground=LIGHT_TEXT,
                                        relief=tk.SOLID, bd=1, highlightthickness=1, highlightbackground=BORDER_COLOR, exportselection=False)
        self.chat_listbox.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)
        self.chat_listbox.bind("<<ListboxSelect>>", self.on_chat_select)
        self.chat_listbox.bind("<Button-3>", self.show_chat_list_context_menu)

        # Center Pane: Chat Display and Input Area
        center_panel = ttk.Frame(main_frame, style="MainDark.TFrame")
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 5))
        self.chat_history = scrolledtext.ScrolledText(center_panel, wrap=tk.WORD, state=tk.DISABLED,
                                                      bg=DARK_BG, fg=LIGHT_TEXT, # DARK_BG for chat history itself
                                                      relief=tk.SOLID, bd=1, highlightthickness=0,
                                                      font=("Arial", 14), padx=10, pady=10, selectbackground=SELECT_BG_COLOR)
        self.chat_history.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self.chat_history.tag_configure("user", foreground=ACCENT_COLOR_USER, font=("Arial", 14, "bold"))
        self.chat_history.tag_configure("assistant", foreground=ACCENT_COLOR_ASSISTANT, font=("Arial", 14))
        self.chat_history.tag_configure("system", foreground=SYSTEM_TEXT, font=("Arial", 14))
        self.chat_history.tag_configure("error", foreground=ERROR_TEXT, font=("Arial", 14, "bold"))

        input_area_frame = ttk.Frame(center_panel, style="MainDark.TFrame") # Parent is MainDark
        input_area_frame.pack(fill=tk.X)
        self.user_input = scrolledtext.ScrolledText(input_area_frame, height=4,
                                                    bg=MEDIUM_DARK_BG, fg=LIGHT_TEXT, # User input field itself
                                                    insertbackground=LIGHT_TEXT, 
                                                    wrap=tk.WORD, relief=tk.SOLID,
                                                    bd=1, highlightthickness=0,
                                                    font=("Arial", 14), padx=10, pady=10, selectbackground=SELECT_BG_COLOR)
        self.user_input.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=(0, 10), padx=(0, 5))
        self.user_input.bind("<Return>", self.send_message_on_enter)
        self.user_input.bind("<Shift-Return>", self.add_newline)
        self.send_button = ttk.Button(input_area_frame, text="Send", command=self.send_message, style="Dark.TButton")
        self.send_button.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10), padx=(0, 5))

        # Far-Right Pane: Settings Panel for configuration controls
        settings_panel = ttk.Frame(main_frame, width=300, style="Secondary.TFrame")
        settings_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        settings_panel.pack_propagate(False)
        
        controls_frame = settings_panel # Alias, parent is Secondary.TFrame

        # Labels in controls_frame should use Secondary.Dark.TLabel
        ttk.Label(controls_frame, text="Model:", style="Secondary.Dark.TLabel").pack(pady=(10,0),anchor="w",padx=5)
        self.model_var = tk.StringVar(self)
        self.model_menu = ttk.OptionMenu(controls_frame, self.model_var, "Loading models...", style="Dark.TMenubutton")
        self.model_menu.pack(fill=tk.X, pady=5, padx=5)
        self.model_var.trace_add("write", self.on_model_change)

        ttk.Label(controls_frame, text="Chat Mode:", style="Secondary.Dark.TLabel").pack(pady=(10,0),anchor="w",padx=5)
        self.chat_mode_menu = ttk.OptionMenu(controls_frame, self.current_chat_mode, self.current_chat_mode.get(), *self.chat_modes, style="Dark.TMenubutton")
        self.chat_mode_menu.pack(fill=tk.X, pady=5, padx=5)
        self.current_chat_mode.trace_add("write", self.on_chat_mode_change)

        ttk.Label(controls_frame, text="Temperature:", style="Secondary.Dark.TLabel").pack(pady=(10,0),anchor="w",padx=5)
        self.temperature_var = tk.DoubleVar(value=0.7)
        # Use the TScale style configured for Secondary.TFrame background
        self.temp_slider = ttk.Scale(controls_frame, from_=0, to_=1, orient=tk.HORIZONTAL, variable=self.temperature_var, command=self.update_temp_display, style="Secondary.Dark.Horizontal.TScale")
        self.temp_slider.pack(fill=tk.X, pady=5, padx=5)
        self.temp_display = ttk.Label(controls_frame, text=f"{self.temperature_var.get():.2f}", style="Secondary.Dark.TLabel")
        self.temp_display.pack(pady=(0,5),padx=5)

        ttk.Label(controls_frame, text="Max Tokens:", style="Secondary.Dark.TLabel").pack(pady=(10,0),anchor="w",padx=5)
        self.max_tokens_var = tk.IntVar(value=1024)
        self.max_tokens_entry = ttk.Entry(controls_frame, textvariable=self.max_tokens_var, style="Dark.TEntry")
        self.max_tokens_entry.pack(fill=tk.X, pady=5, padx=5)
        
        max_tokens_presets_options = ["1024", "2048", "4096", "8192", "16000", "Custom"]
        self.max_tokens_preset_var = tk.StringVar(value="Custom") 
        self.max_tokens_preset_menu = ttk.OptionMenu(controls_frame, self.max_tokens_preset_var, 
                                                     self.max_tokens_preset_var.get(), 
                                                     *max_tokens_presets_options, 
                                                     command=self.set_max_tokens_from_preset, style="Dark.TMenubutton")
        self.max_tokens_preset_menu.pack(fill=tk.X, pady=5, padx=5)

        ttk.Label(controls_frame, text="Context Limit:", style="Secondary.Dark.TLabel").pack(pady=(10,0),anchor="w",padx=5)
        context_options = ["Last 10 Messages", "Last 20 Messages", "Last 50 Messages", "No Limit"]
        self.context_limit_var = tk.StringVar(value="Last 50 Messages")
        ttk.OptionMenu(controls_frame, self.context_limit_var, self.context_limit_var.get(), *context_options, style="Dark.TMenubutton").pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Label(controls_frame, text="Presence Penalty:", style="Secondary.Dark.TLabel").pack(pady=(10,0),anchor="w",padx=5)
        self.presence_penalty_var = tk.DoubleVar(value=0.0)
        self.presence_penalty_slider = ttk.Scale(controls_frame, from_=-2.0, to_=2.0, orient=tk.HORIZONTAL, variable=self.presence_penalty_var, command=lambda v: self.presence_display.config(text=f"{self.presence_penalty_var.get():.1f}"), style="Secondary.Dark.Horizontal.TScale")
        self.presence_penalty_slider.pack(fill=tk.X,pady=5,padx=5)
        self.presence_display = ttk.Label(controls_frame, text=f"{self.presence_penalty_var.get():.1f}", style="Secondary.Dark.TLabel")
        self.presence_display.pack(pady=(0,5),padx=5)
        ttk.Button(controls_frame, text="Reset", command=self.reset_presence_penalty, style="Dark.TButton").pack(fill=tk.X, pady=2, padx=5)

        ttk.Label(controls_frame, text="Frequency Penalty:", style="Secondary.Dark.TLabel").pack(pady=(10,0),anchor="w",padx=5)
        self.frequency_penalty_var = tk.DoubleVar(value=0.0)
        self.frequency_penalty_slider = ttk.Scale(controls_frame, from_=-2.0, to_=2.0, orient=tk.HORIZONTAL, variable=self.frequency_penalty_var, command=lambda v: self.frequency_display.config(text=f"{self.frequency_penalty_var.get():.1f}"), style="Secondary.Dark.Horizontal.TScale")
        self.frequency_penalty_slider.pack(fill=tk.X,pady=5,padx=5)
        self.frequency_display = ttk.Label(controls_frame, text=f"{self.frequency_penalty_var.get():.1f}", style="Secondary.Dark.TLabel")
        self.frequency_display.pack(pady=(0,5),padx=5)
        ttk.Button(controls_frame, text="Reset", command=self.reset_frequency_penalty, style="Dark.TButton").pack(fill=tk.X, pady=2, padx=5)

        ttk.Label(controls_frame, text="Top P:", style="Secondary.Dark.TLabel").pack(pady=(10,0),anchor="w",padx=5)
        self.top_p_var = tk.DoubleVar(value=1.0)
        self.top_p_slider = ttk.Scale(controls_frame, from_=0.0, to_=1.0, orient=tk.HORIZONTAL, variable=self.top_p_var, command=lambda v: self.top_p_display.config(text=f"{self.top_p_var.get():.2f}"), style="Secondary.Dark.Horizontal.TScale")
        self.top_p_slider.pack(fill=tk.X,pady=5,padx=5)
        self.top_p_display = ttk.Label(controls_frame, text=f"{self.top_p_var.get():.2f}", style="Secondary.Dark.TLabel")
        self.top_p_display.pack(pady=(0,5),padx=5)
        ttk.Button(controls_frame, text="Reset", command=self.reset_top_p, style="Dark.TButton").pack(fill=tk.X, pady=2, padx=5)

        ttk.Label(controls_frame, text="Top K:", style="Secondary.Dark.TLabel").pack(pady=(10,0),anchor="w",padx=5)
        self.top_k_var = tk.IntVar(value=40) 
        self.top_k_entry = ttk.Entry(controls_frame, textvariable=self.top_k_var, style="Dark.TEntry")
        self.top_k_entry.pack(fill=tk.X, pady=5, padx=5)
        ttk.Button(controls_frame, text="Reset", command=self.reset_top_k, style="Dark.TButton").pack(fill=tk.X, pady=2, padx=5)
        
        ttk.Label(controls_frame, text="Reasoning Effort:", style="Secondary.Dark.TLabel").pack(pady=(10,0),anchor="w",padx=5)
        reasoning_options = ["None", "Low", "Medium", "High"] 
        self.reasoning_effort_var = tk.StringVar(value="Medium") 
        self.reasoning_effort_menu = ttk.OptionMenu(controls_frame, self.reasoning_effort_var, self.reasoning_effort_var.get(), *reasoning_options, style="Dark.TMenubutton")
        self.reasoning_effort_menu.pack(fill=tk.X, pady=5, padx=5)

        ttk.Label(controls_frame, text="System Prompt:", style="Secondary.Dark.TLabel").pack(pady=(10,0),anchor="w",padx=5)
        self.system_prompt_text_widget = scrolledtext.ScrolledText(controls_frame, height=6, wrap=tk.WORD, 
                                                                  bg=MEDIUM_DARK_BG, fg=LIGHT_TEXT, insertbackground=LIGHT_TEXT,
                                                                  relief=tk.SOLID, bd=1, font=("Arial", 10), selectbackground=SELECT_BG_COLOR)
        self.system_prompt_text_widget.pack(fill=tk.X, pady=5, padx=5)
        self.refresh_button = ttk.Button(controls_frame, text="Refresh Models", command=self.load_initial_models, style="Dark.TButton")
        self.refresh_button.pack(pady=20, fill=tk.X, padx=5)
        print("[DEBUG _init_ui] END")
    def load_or_create_conversation(self):
        conversations = fetch_conversations_from_db()
        if conversations:
            self.current_conversation_id = conversations[0][0]
            self.on_chat_select(None) # Load the most recent chat
        else:
            self.create_new_conversation() # Create one if DB is empty
        self.refresh_chat_list()


    def create_new_conversation(self):
        print("[DEBUG] Creating new conversation")
        system_prompt = self.system_prompt_text_widget.get(1.0, tk.END).strip()
        model_selection = self.model_var.get()
        current_model = "" if not model_selection or model_selection == "Loading models..." else model_selection
        new_title = f"New Chat {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        self.current_conversation_id = create_conversation_in_db(title=new_title, model=current_model, system_prompt=system_prompt)
        
        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.delete(1.0, tk.END)
        self.chat_history.config(state=tk.DISABLED)
        self.conversation_log = []
        self.refresh_chat_list() # This will also select the new chat
        print(f"[DEBUG] New conversation created with ID: {self.current_conversation_id}")


    def refresh_chat_list(self):
        print("[DEBUG] Refreshing chat list")
        self.chat_listbox.delete(0, tk.END)
        conversations = fetch_conversations_from_db()
        self.conversation_id_map.clear() # Clear map before repopulating
        for index, (conv_id, title, _) in enumerate(conversations):
            display_title = title if title else f"Conversation {conv_id}"
            self.chat_listbox.insert(tk.END, display_title)
            self.conversation_id_map[index] = conv_id
            if conv_id == self.current_conversation_id:
                self.chat_listbox.selection_clear(0, tk.END) # Clear previous selection
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
        cursor.execute("SELECT llm_model, system_prompt FROM conversations WHERE id = ?", (self.current_conversation_id,))
        conv_data = cursor.fetchone()
        conn.close()

        if conv_data:
            loaded_model, loaded_system_prompt = conv_data
            if loaded_model and loaded_model != "Loading models..." and self.model_var.get() != loaded_model:
                if self.available_models and loaded_model in self.available_models: # Check if model is valid
                     self.model_var.set(loaded_model)
                elif self.available_models: # Fallback to first available if stored one isn't found
                    print(f"[DEBUG] Stored model '{loaded_model}' not in available list, using first available.")
                    # self.model_var.set(self.available_models[0]) # Optional: set to first available
                else: # No models loaded yet
                    print(f"[DEBUG] Stored model '{loaded_model}' but no models available in UI yet.")
                    # self.model_var.set(loaded_model) # Set it anyway, UI will show it when models load
            if loaded_system_prompt:
                self.system_prompt_text_widget.delete(1.0, tk.END)
                self.system_prompt_text_widget.insert(tk.END, loaded_system_prompt)

        self.chat_history.config(state=tk.NORMAL)
        self.chat_history.delete(1.0, tk.END)
        messages = fetch_messages_from_db(self.current_conversation_id)
        self.conversation_log = []
        for role, content, timestamp_str in messages:
            try:
                formatted_time = datetime.fromisoformat(timestamp_str).strftime("[%H:%M:%S]") if timestamp_str else "[No Time]"
            except ValueError:
                formatted_time = f"[{timestamp_str}]"
            self.chat_history.insert(tk.END, f"\n\n{formatted_time} {role.capitalize()}: {content}\n", role)
            self.conversation_log.append({"role": role, "content": content})
        self.chat_history.see(tk.END)
        self.chat_history.config(state=tk.DISABLED)
        print(f"[DEBUG] Loaded messages for conversation ID: {self.current_conversation_id}")

    def update_conversation_title_from_message(self, message_content):
        if not self.current_conversation_id: return
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

    def confirm_delete_conversation(self, event):
        selected_index = self.chat_listbox.nearest(event.y)
        conv_id = self.conversation_id_map.get(selected_index)
        if conv_id and messagebox.askyesno("Delete Chat","Permanently delete this conversation? This action cannot be undone."):
            delete_conversation_in_db(conv_id)
            if conv_id == self.current_conversation_id:
                self.load_or_create_conversation()
            self.update_chat_list()

        self.chat_listbox.bind("<Button-3>", self.confirm_delete_conversation)

        cursor.execute("SELECT title FROM conversations WHERE id = ?", (self.current_conversation_id,))
        current_title_tuple = cursor.fetchone()
        conn.close() # Close connection early
        if current_title_tuple:
            current_title = current_title_tuple[0]
            if current_title.startswith("New Chat"):
                words = message_content.split()
                potential_title = " ".join(words[:5])
                if len(potential_title) > 50: potential_title = potential_title[:47] + "..."
                if potential_title:
                    update_conversation_title_in_db(self.current_conversation_id, potential_title)
                    self.refresh_chat_list()

    def show_chat_list_context_menu(self, event):
        if not self.chat_listbox.curselection(): return
        selected_index = self.chat_listbox.curselection()[0]
        conv_id = self.conversation_id_map.get(selected_index)
        if conv_id is None: return
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
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
            cursor.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error during deletion: {e}")
            messagebox.showerror("Database Error", f"Could not delete chat: {e}", parent=self)
        finally:
            conn.close()
        
        if self.current_conversation_id == conv_id:
            self.current_conversation_id = None
            self.chat_history.config(state=tk.NORMAL)
            self.chat_history.delete(1.0, tk.END)
            self.chat_history.config(state=tk.DISABLED)
            self.conversation_log = []
            self.load_or_create_conversation() # This will create a new one if no others exist
        self.refresh_chat_list()
        
    def update_temp_display(self, value):
        self.temp_display.config(text=f"{float(value):.2f}")

    def set_max_tokens_from_preset(self, selected_preset_value): # Placeholder
        print(f"Max Tokens Preset selected: {selected_preset_value}")
        if selected_preset_value != "Custom":
            try: self.max_tokens_var.set(int(selected_preset_value))
            except ValueError: print(f"Error: Could not convert preset '{selected_preset_value}' to int.")

    def reset_presence_penalty(self): self.presence_penalty_var.set(0.0) # Placeholder
    def reset_frequency_penalty(self): self.frequency_penalty_var.set(0.0) # Placeholder
    def reset_top_p(self): self.top_p_var.set(1.0) # Placeholder
    def reset_top_k(self): self.top_k_var.set(40) # Placeholder

    def add_log_message(self, message_text, level="system"): # Renamed param
        self.chat_history.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        self.chat_history.insert(tk.END, f"\n\n{timestamp} {level.capitalize()}: {message_text}\n", level)
        
        if self.current_conversation_id and level in ["user", "assistant"]:
            add_message_to_db(self.current_conversation_id, level, message_text)
            if level == "user":
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT title FROM conversations WHERE id = ?", (self.current_conversation_id,))
                title_tuple = cursor.fetchone()
                conn.close()
                if title_tuple and title_tuple[0].startswith("New Chat"):
                     self.update_conversation_title_from_message(message_text)
        
        self.chat_history.see(tk.END)
        self.chat_history.config(state=tk.DISABLED)

    def load_initial_models(self):
        self.add_log_message("Fetching models...", "system")
        if self.refresh_button: self.refresh_button.config(state=tk.DISABLED, text="Refreshing...")
        self.after(100, self._fetch_all_models_thread)

    def _fetch_all_models_thread(self):
        print(f"[DEBUG _fetch_all_models_thread] START")
        print(f"[DEBUG] OpenAI API Key global: {'SET' if openai_api_key else 'NOT SET'}")
        print(f"[DEBUG] OpenRouter API Key global: {'SET' if openrouter_api_key else 'NOT SET'}")
        print(f"[DEBUG] XAI API Key global: {'SET' if xai_api_key else 'NOT SET'}")

        self.model_groups = {'OpenAI': [], 'OpenRouter': [], 'XAI': []} # Reset

        if openai_api_key:
            openai_models_list = fetch_openai_models(openai_api_key)
            if openai_models_list:
                self.add_log_message(f"Fetched {len(openai_models_list)} OpenAI models", "system")
                self.model_groups['OpenAI'] = sorted(openai_models_list)
            else: self.add_log_message("No/Error OpenAI models", "error")
        else: self.add_log_message("OpenAI key not set", "error")

        if openrouter_api_key:
            openrouter_models_list = fetch_openrouter_models(openrouter_api_key)
            if openrouter_models_list:
                self.add_log_message(f"Fetched {len(openrouter_models_list)} OpenRouter models", "system")
                self.model_groups['OpenRouter'] = sorted(openrouter_models_list)
            else: self.add_log_message("No/Error OpenRouter models", "error")
        else: self.add_log_message("OpenRouter key not set", "error")

        if xai_api_key:
            xai_models_list = fetch_xai_models(xai_api_key)
            if xai_models_list:
                self.add_log_message(f"Fetched {len(xai_models_list)} XAI models", "system")
                self.model_groups['XAI'] = sorted(xai_models_list)
            else: self.add_log_message("No/Error XAI models", "error")
        else: self.add_log_message("XAI key not set", "error")
        
        self.available_models = []
        for provider in ['OpenAI', 'OpenRouter', 'XAI']:
            if provider in self.model_groups and self.model_groups[provider]:
                for model_id_str in self.model_groups[provider]: # Renamed
                    self.available_models.append(f"{provider}: {model_id_str}")
        
        if not self.available_models: self.add_log_message("No models available from any provider.", "error")
        
        self.after(0, self.update_model_list) # Schedule UI update on main thread
        if self.refresh_button: self.after(0, lambda: self.refresh_button.config(state=tk.NORMAL, text="Refresh Models"))
        print(f"[DEBUG _fetch_all_models_thread] END - Models: {self.available_models}")

    def update_model_list(self):
        print("[DEBUG] Updating model list in UI")
        menu = self.model_menu['menu']
        menu.delete(0, 'end')
        current_selection = self.model_var.get()
        new_selection_candidate = None

        if not self.available_models:
            menu.add_command(label="No models available", command=tk._setit(self.model_var, "No models available"))
            new_selection_candidate = "No models available"
        else:
            for model_id_str_val in self.available_models: # Renamed
                menu.add_command(label=model_id_str_val, command=tk._setit(self.model_var, model_id_str_val))
            # Try to keep current selection if still valid, else pick first
            if current_selection in self.available_models:
                new_selection_candidate = current_selection
            else:
                new_selection_candidate = self.available_models[0]
        
        if new_selection_candidate and self.model_var.get() != new_selection_candidate:
            self.model_var.set(new_selection_candidate)
        print(f"[DEBUG] Model list updated. Selected: {self.model_var.get()}")

    def get_system_prompt(self):
        custom_prompt = self.system_prompt_text_widget.get("1.0", tk.END).strip()
        if custom_prompt: return custom_prompt
        mode = self.current_chat_mode.get()
        prompts = {
            "Normal": "You are a helpful AI assistant.",
            "Assistant": "You are a professional assistant providing detailed and accurate responses.",
            "Code Assistant": "You are a coding expert. Provide code snippets and explanations.",
            "Sarcastic Assistant": "You are a witty and sarcastic assistant, still helpful but with an edge."
        }
        return prompts.get(mode, "You are a helpful AI assistant.")

    def get_context_limit_messages(self):
        context_limit_str_val = self.context_limit_var.get() # Renamed
        if context_limit_str_val == "No Limit": return self.conversation_log
        try:
            num_messages = int(context_limit_str_val.split()[1])
            return self.conversation_log[-num_messages:]
        except: return self.conversation_log[-50:] # Default

    def send_message(self):
        user_text = self.user_input.get("1.0", tk.END).strip()
        if not user_text: return
        
        self.add_log_message(user_text, "user")
        self.user_input.delete("1.0", tk.END)
        self.after(100, self.process_ai_response)

    def send_message_on_enter(self, event):
        self.send_message(); return 'break'

    def add_newline(self, event):
        self.user_input.insert(tk.INSERT, "\n"); return 'break'

    def process_ai_response(self):
        print("[DEBUG process_ai_response] START")
        selected_model_full_id = self.model_var.get() # Renamed
        if not selected_model_full_id or "No models" in selected_model_full_id or "Loading" in selected_model_full_id:
            self.add_log_message("Error: No model selected/available.", "error"); return

        try:
            provider, model_id_only = selected_model_full_id.split(": ", 1) # Renamed
        except ValueError:
            self.add_log_message(f"Error: Invalid model format '{selected_model_full_id}'.", "error"); return
        
        api_key_for_request = None # Renamed
        client_config = {} # Renamed

        if provider == "OpenAI":
            api_key_for_request = openai_api_key
            if not api_key_for_request: self.add_log_message("Error: OpenAI API key not set.", "error"); return
            client_config = {"api_key": api_key_for_request}
        elif provider == "OpenRouter":
            api_key_for_request = openrouter_api_key
            if not api_key_for_request: self.add_log_message("Error: OpenRouter API key not set.", "error"); return
            client_config = {"api_key": api_key_for_request, "base_url": "https://openrouter.ai/api/v1"}
        elif provider == "XAI":
            api_key_for_request = xai_api_key
            if not api_key_for_request: self.add_log_message("Error: XAI API key not set.", "error"); return
            client_config = {"api_key": api_key_for_request, "base_url": "https://api.x.ai/v1"} # Example
        else:
            self.add_log_message(f"Error: Unknown provider '{provider}'.", "error"); return
        
        active_client = openai.OpenAI(**client_config) # Renamed
        system_prompt_text = self.get_system_prompt() # Renamed
        messages_to_send = [{"role": "system", "content": system_prompt_text}] + self.get_context_limit_messages() # Renamed

        try:
            print(f"[DEBUG] Calling API for {provider}: {model_id_only}")
            response_stream = active_client.chat.completions.create( # Renamed
                model=model_id_only, messages=messages_to_send,
                temperature=self.temperature_var.get(), max_tokens=self.max_tokens_var.get(),
                presence_penalty=self.presence_penalty_var.get(), frequency_penalty=self.frequency_penalty_var.get(),
                top_p=self.top_p_var.get(), stream=True
            )
            full_assistant_response = "" # Renamed
            self.chat_history.config(state=tk.NORMAL)
            self.chat_history.insert(tk.END, f"\n\n[{datetime.now().strftime('%H:%M:%S')}] {provider} Assistant: ", "assistant") # Indicate provider
            self.chat_history.see(tk.END); self.update_idletasks()

            for chunk_item in response_stream: # Renamed
                text_chunk = chunk_item.choices[0].delta.content or "" # Renamed
                full_assistant_response += text_chunk
                self.chat_history.insert(tk.END, text_chunk, "assistant")
                self.chat_history.see(tk.END); self.update_idletasks()
            
            self.chat_history.insert(tk.END, "\n", "assistant")
            self.chat_history.config(state=tk.DISABLED)
            
            if full_assistant_response:
                self.add_log_message(full_assistant_response, "assistant")
            print(f"[DEBUG process_ai_response] END - Response received from {provider}")
        except Exception as e:
            error_detail = f"API Error ({provider} {model_id_only}): {str(e)}" # Renamed
            print(error_detail)
            self.add_log_message(error_detail, "error")

    def configure_api_keys(self):
        global openai_api_key, openrouter_api_key, xai_api_key, config # Ensure globals are modified

        new_openai = simpledialog.askstring("API Key", "OpenAI API Key:", initialvalue=openai_api_key or "", parent=self)
        if new_openai is not None: config["openai_api_key"], openai_api_key = new_openai, new_openai
        if openai_api_key: openai.api_key = openai_api_key

        new_openrouter = simpledialog.askstring("API Key", "OpenRouter API Key:", initialvalue=openrouter_api_key or "", parent=self)
        if new_openrouter is not None: config["openrouter_api_key"], openrouter_api_key = new_openrouter, new_openrouter
            
        new_xai = simpledialog.askstring("API Key", "XAI API Key:", initialvalue=xai_api_key or "", parent=self)
        if new_xai is not None: config["xai_api_key"], xai_api_key = new_xai, new_xai
            
        save_config(config)
        self.add_log_message("API keys updated. Refreshing models...", "system")
        self.load_initial_models()

    def on_model_change(self, *args): print(f"Model changed to: {self.model_var.get()}")
    def on_chat_mode_change(self, *args): print(f"Chat mode: {self.current_chat_mode.get()}")
    def on_closing(self): self.destroy()

if __name__ == "__main__":
    print("[DEBUG MAIN] App starting...")
    app = VoyeurChat()
    app.mainloop()
    print("[DEBUG MAIN] App finished.")
