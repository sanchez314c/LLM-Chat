import tkinter as tk
from tkinter import ttk, scrolledtext, simpledialog, Menu as tkMenu, messagebox, Text, filedialog
import asyncio
import threading
import platform
import pyperclip
import json
import faiss
import numpy as np
from PyPDF2 import PdfReader
from config import load_config, save_config
from db import init_database, create_conversation_in_db, add_message_to_db, fetch_conversations_from_db, fetch_messages_from_db, update_conversation_title_in_db, delete_conversation_in_db, save_draft, load_draft
from api import fetch_all_models, process_ai_response
from tts import MacOSTTS, generate_and_play_audio_elevenlabs, GoogleCloudTTS, PiperTTS, Pyttsx3TTS, OpenAITTS, SesameCSMTTS
from stt import GoogleCloudSTT, OpenAIWhisperSTT, WhisperXSTT
import os
import aiosqlite
from datetime import datetime

# Add path to Sesame CSM for Segment import
SESAME_CSM_DIR = os.path.join(os.path.dirname(__file__), "csm")
import sys
sys.path.append(SESAME_CSM_DIR)
from generator import Segment

# Colors (aligned with Grok UI)
DARK_BG = "#181B1C"
LEFT_PANEL_BG = "#202426"
MEDIUM_DARK_BG = "#2E3436"
LIGHT_TEXT = "#D9E0E3"
MEDIUM_TEXT = "#8A9396"
ACCENT_COLOR_USER = "#C8CED1"
ACCENT_COLOR_ASSISTANT = "#F5F8FA"
BORDER_COLOR = "#2A2F31"
SELECT_BG_COLOR = "#37474F"
ERROR_TEXT = "#F44336"
SYSTEM_TEXT = "#FFFFFF"
LIGHT_BG = "#F5F5F5"
LIGHT_LEFT_PANEL_BG = "#E0E0E0"
LIGHT_MEDIUM_BG = "#D0D0D0"
LIGHT_TEXT_DARK = "#333333"
LIGHT_ACCENT_USER = "#666666"
LIGHT_ACCENT_ASSISTANT = "#000000"

FONT_FAMILY = "SF Pro Display" if platform.system() == "Darwin" else "Segoe UI"

# Define DB_PATH at the top level
DB_PATH = "voyeur_chat.db"

class PlaceholderEntry(ttk.Entry):
    def __init__(self, parent, placeholder, style="Dark.TEntry", **kwargs):
        super().__init__(parent, style=style, **kwargs)
        self.placeholder = placeholder
        self.insert(0, placeholder)
        self.bind("<FocusIn>", self._clear_placeholder)
        self.bind("<FocusOut>", self._restore_placeholder)
    def _clear_placeholder(self, event):
        if self.get() == self.placeholder:
            self.delete(0, tk.END)
    def _restore_placeholder(self, event):
        if not self.get():
            self.insert(0, self.placeholder)

class VoyeurChat(tk.Tk):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self.is_dark_mode = tk.BooleanVar(value=True)
        self.tts_provider = tk.StringVar(value=self.config.get("tts_provider", "None"))
        self.stt_provider = tk.StringVar(value=self.config.get("stt_provider", "Google Cloud"))
        self.macos_voice = tk.StringVar(value=self.config.get("macos_voice", "Alex"))
        self.google_voice = tk.StringVar(value=self.config.get("google_voice", "en-US-Standard-A"))
        self.openai_voice = tk.StringVar(value=self.config.get("openai_voice", "alloy"))
        self.piper_model = tk.StringVar(value=self.config.get("piper_model", "en_US-lessac-medium"))
        self.sesame_speaker = tk.StringVar(value=self.config.get("sesame_speaker", "0"))
        self.stability_var = tk.DoubleVar(value=0.5)
        self.similarity_var = tk.DoubleVar(value=0.5)
        
        # TTS/STT providers
        self.macos_tts = None
        self.google_tts = None
        self.openai_tts = None
        self.piper_tts = None
        self.pyttsx3_tts = None
        self.sesame_csm = None
        self.google_stt = GoogleCloudSTT(self.add_log_message)
        self.whisperx_stt = WhisperXSTT(model_size="large-v2", device="cpu", batch_size=16, compute_type="float16", hf_token=self.config.get("huggingface_api_key", ""), log_callback=self.add_log_message)
        self.openai_whisper_stt = OpenAIWhisperSTT(self.config["openai_api_key"], log_callback=self.add_log_message)
        
        # RAG setup
        self.faiss_index = faiss.IndexFlatL2(768)
        self.documents = []
        
        self._configure_styles()
        self._fix_dpi_scaling()
        
        self.title("Voyeur Chat")
        self.geometry("1600x1200")

        self.conversation_id_map = {}
        self.current_conversation_id = None
        self.available_models = []
        self.model_groups = {
            'OpenAI': [], 'OpenRouter': [], 'XAI': [], 'Anthropic': [], 'HuggingFace': [],
            'Google': [], 'Perplexity': [], 'Together': [], 'Groq': [], 'Pi': [],
            'Mistral': [], 'DeepSeek': []
        }
        self.chat_modes = ["Normal", "Assistant", "Code Assistant", "Sarcastic Assistant", "Call Mode"]
        self.current_chat_mode = tk.StringVar(value=self.chat_modes[0])
        self.conversation_log = []
        self.placeholder_visible = True
        self.message_frames = []

        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.run_loop, daemon=True)
        self.thread.start()

        asyncio.run_coroutine_threadsafe(init_database(), self.loop).result()
        self._init_ui()
        
        # Initialize TTS providers
        if MACOS_TTS_AVAILABLE and platform.system() == "Darwin":
            self.macos_tts = MacOSTTS(self.macos_voice.get(), self.add_log_message)
            self.macos_voices = self.macos_tts.get_available_voices()
            self.macos_voice_menu['menu'].delete(0, 'end')
            for voice in self.macos_voices:
                self.macos_voice_menu['menu'].add_command(label=voice, command=tk._setit(self.macos_voice, voice))
            if self.macos_voice.get() not in self.macos_voices:
                self.macos_voice.set(self.macos_voices[0] if self.macos_voices else "Alex")
        if self.config["google_api_key"]:
            self.google_tts = GoogleCloudTTS(self.google_voice.get(), self.add_log_message)
            self.google_voices = self.google_tts.get_available_voices()
            self.google_voice_menu['menu'].delete(0, 'end')
            for voice in self.google_voices:
                self.google_voice_menu['menu'].add_command(label=voice, command=tk._setit(self.google_voice, voice))
        if self.config["openai_api_key"]:
            self.openai_tts = OpenAITTS(self.config["openai_api_key"], self.openai_voice.get(), self.add_log_message)
            self.openai_voices = self.openai_tts.get_available_voices()
            self.openai_voice_menu['menu'].delete(0, 'end')
            for voice in self.openai_voices:
                self.openai_voice_menu['menu'].add_command(label=voice, command=tk._setit(self.openai_voice, voice))
        self.piper_tts = PiperTTS(self.piper_model.get(), self.add_log_message)
        self.piper_models = self.piper_tts.get_available_voices()
        self.piper_model_menu['menu'].delete(0, 'end')
        for model in self.piper_models:
            self.piper_model_menu['menu'].add_command(label=model, command=tk._setit(self.piper_model, model))
        self.pyttsx3_tts = Pyttsx3TTS("com.apple.speech.synthesis.voice.Alex", self.add_log_message)
        self.sesame_csm = SesameCSMTTS(int(self.sesame_speaker.get()), self.add_log_message)
        self.sesame_speakers = self.sesame_csm.get_available_voices()
        self.sesame_speaker_menu['menu'].delete(0, 'end')
        for speaker in self.sesame_speakers:
            self.sesame_speaker_menu['menu'].add_command(label=speaker, command=tk._setit(self.sesame_speaker, speaker))
        
        self.load_initial_models()
        self.load_or_create_conversation()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _fix_dpi_scaling(self):
        if platform.system() == "Darwin":
            self.tk.call('tk', 'scaling', 2.0)
            self.tk.call('::tk::unsupported::MacWindowStyle', 'style', self._w, 'unified')

    def _configure_styles(self):
        self.style.configure("MainDark.TFrame", background=DARK_BG, borderwidth=0)
        self.style.configure("Dark.TFrame", background=DARK_BG)
        self.style.configure("Secondary.TFrame", background=LEFT_PANEL_BG, borderwidth=0)
        self.style.configure("Secondary.Dark.TLabel", background=LEFT_PANEL_BG, foreground=LIGHT_TEXT, font=(FONT_FAMILY, 18))
        self.style.configure("Dark.TLabel", background=LEFT_PANEL_BG, foreground=LIGHT_TEXT, font=(FONT_FAMILY, 18))
        self.style.configure("MainDark.TLabel", background=DARK_BG, foreground=LIGHT_TEXT, font=(FONT_FAMILY, 18))
        self.style.configure("Section.TLabel", background=LEFT_PANEL_BG, foreground=LIGHT_TEXT, font=(FONT_FAMILY, 20, "bold"))
        self.style.configure("Dark.TButton", background=MEDIUM_DARK_BG, foreground=LIGHT_TEXT, bordercolor=BORDER_COLOR, borderwidth=0, relief=tk.FLAT, padding=4, font=(FONT_FAMILY, 14))
        self.style.map("Dark.TButton", background=[('active', '#3A4042')], relief=[('pressed', tk.FLAT), ('active', tk.FLAT)])
        self.style.configure("Dark.TCheckbutton", background=LEFT_PANEL_BG, foreground=LIGHT_TEXT, font=(FONT_FAMILY, 14))
        self.style.map("Dark.TCheckbutton", background=[('active', SELECT_BG_COLOR)], foreground=[('active', LIGHT_TEXT)])
        self.style.configure("Dark.TMenubutton", background=MEDIUM_DARK_BG, foreground=LIGHT_TEXT, bordercolor=BORDER_COLOR, borderwidth=0, relief=tk.FLAT, arrowcolor=LIGHT_TEXT, padding=4, font=(FONT_FAMILY, 18))
        self.style.map("Dark.TMenubutton", background=[('active', '#3A4042')])
        self.style.configure("Secondary.Dark.Horizontal.TScale", background=DARK_BG, troughcolor="#3A3A3C", sliderrelief=tk.FLAT, sliderthickness=8, bordercolor=BORDER_COLOR)
        self.style.map("Secondary.Dark.Horizontal.TScale", background=[('active', MEDIUM_DARK_BG)], troughcolor=[('active', SELECT_BG_COLOR)])
        self.style.configure("Dark.TEntry", fieldbackground=MEDIUM_DARK_BG, foreground=LIGHT_TEXT, bordercolor=BORDER_COLOR, borderwidth=0, relief=tk.FLAT, insertcolor=LIGHT_TEXT, padding=4, font=(FONT_FAMILY, 18))
        self.style.configure("TScrollbar", troughcolor=DARK_BG, background=MEDIUM_DARK_BG, bordercolor=BORDER_COLOR, arrowcolor=LIGHT_TEXT, relief=tk.FLAT, arrowsize=14)
        self.style.map("TScrollbar", background=[('active', SELECT_BG_COLOR)])

    def update_theme(self):
        theme = "MainDark.TFrame" if self.is_dark_mode.get() else "MainLight.TFrame"
        self.main_frame.configure(style=theme)
        self.chat_frame.configure(style=theme)
        self.input_area_frame.configure(style=theme)
        self.status_frame.configure(style="Secondary.TFrame" if self.is_dark_mode.get() else "Secondary.Light.TFrame")
        self.chat_list_panel.configure(style="Secondary.TFrame" if self.is_dark_mode.get() else "Secondary.Light.TFrame")
        self.settings_panel.configure(style="Secondary.TFrame" if self.is_dark_mode.get() else "Secondary.Light.TFrame")
        self.chat_canvas.configure(bg=DARK_BG if self.is_dark_mode.get() else LIGHT_BG)
        self.chat_listbox.configure(bg=LEFT_PANEL_BG if self.is_dark_mode.get() else LIGHT_LEFT_PANEL_BG, fg=LIGHT_TEXT if self.is_dark_mode.get() else LIGHT_TEXT_DARK)
        self.user_input.configure(bg=MEDIUM_DARK_BG if self.is_dark_mode.get() else LIGHT_MEDIUM_BG, fg=LIGHT_TEXT if self.is_dark_mode.get() else LIGHT_TEXT_DARK, insertbackground=LIGHT_TEXT if self.is_dark_mode.get() else LIGHT_TEXT_DARK)
        self.status_window.configure(bg=DARK_BG if self.is_dark_mode.get() else LIGHT_BG, fg=LIGHT_TEXT if self.is_dark_mode.get() else LIGHT_TEXT_DARK)
        for frame in self.message_frames:
            frame.configure(style=theme)
            for widget in frame.winfo_children():
                if isinstance(widget, ttk.Label):
                    widget.configure(style="MainDark.TLabel" if self.is_dark_mode.get() else "MainLight.TLabel")
                elif isinstance(widget, ttk.Button):
                    widget.configure(style="Dark.TButton" if self.is_dark_mode.get() else "Light.TButton")

    def save_tts_config(self):
        self.config["tts_provider"] = self.tts_provider.get()
        self.config["stt_provider"] = self.stt_provider.get()
        self.config["voice_id"] = self.config.get("voice_id", "")
        self.config["macos_voice"] = self.macos_voice.get()
        self.config["google_voice"] = self.google_voice.get()
        self.config["openai_voice"] = self.openai_voice.get()
        self.config["piper_model"] = self.piper_model.get()
        self.config["sesame_speaker"] = self.sesame_speaker.get()
        save_config(self.config)
        if self.macos_tts and self.tts_provider.get() == "macOS Native":
            self.macos_tts.set_voice(self.macos_voice.get())
        if self.openai_tts and self.tts_provider.get() == "OpenAI TTS":
            self.openai_tts = OpenAITTS(self.config["openai_api_key"], self.openai_voice.get(), self.add_log_message)
        if self.sesame_csm and self.tts_provider.get() == "Sesame CSM":
            self.sesame_csm = SesameCSMTTS(int(self.sesame_speaker.get()), self.add_log_message)
        self.refresh_conversation()

    def run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _init_ui(self):
        self.configure(bg=DARK_BG if self.is_dark_mode.get() else LIGHT_BG)
        self.config_menu = tkMenu(self, tearoff=0, bg=MEDIUM_DARK_BG, fg=LIGHT_TEXT, activebackground=SELECT_BG_COLOR, activeforeground=LIGHT_TEXT, relief=tk.FLAT, bd=0, font=(FONT_FAMILY, 18))
        self.settings_menu = tkMenu(self.config_menu, tearoff=0, bg=MEDIUM_DARK_BG, fg=LIGHT_TEXT, activebackground=SELECT_BG_COLOR, activeforeground=LIGHT_TEXT, relief=tk.FLAT, bd=0, font=(FONT_FAMILY, 18))
        self.settings_menu.add_command(label="Configure API Keys", command=self.configure_api_keys)
        self.settings_menu.add_command(label="Rename Thread", command=self.rename_selected_thread)
        self.settings_menu.add_command(label="Set ElevenLabs Voice ID", command=self.set_elevenlabs_voice_id)
        self.settings_menu.add_command(label="Set Default System Prompt", command=self.set_default_system_prompt)
        self.settings_menu.add_command(label="Upload File", command=self.upload_file)
        self.settings_menu.add_command(label="Export Conversation", command=self.export_conversation)
        self.config_menu.add_cascade(label="Settings", menu=self.settings_menu)
        self.config(menu=self.config_menu)

        self.main_frame = ttk.Frame(self, style="MainDark.TFrame")
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Left Panel: Chat List
        self.chat_list_panel = ttk.Frame(self.main_frame, width=300, style="Secondary.TFrame")
        self.chat_list_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 2))
        self.chat_list_panel.pack_propagate(False)
        ttk.Label(self.chat_list_panel, text="Chats", style="Section.TLabel").pack(pady=(10, 5), anchor="w", padx=10)
        self.search_entry = PlaceholderEntry(self.chat_list_panel, "Search chats...", style="Dark.TEntry")
        self.search_entry.pack(fill=tk.X, pady=5, padx=10)
        self.search_entry.bind("<KeyRelease>", self.search_chats)
        self.chat_listbox = tk.Listbox(self.chat_list_panel, height=30, bg=LEFT_PANEL_BG, fg=LIGHT_TEXT,
                                       selectbackground=SELECT_BG_COLOR, selectforeground=LIGHT_TEXT,
                                       relief=tk.FLAT, bd=0, highlightthickness=0, exportselection=False, font=(FONT_FAMILY, 18))
        self.chat_listbox.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)
        self.chat_listbox.bind("<<ListboxSelect>>", self.on_chat_select)
        self.chat_listbox.bind("<Button-3>", self.show_chat_list_context_menu)
        ttk.Button(self.chat_list_panel, text="Delete Chat", command=self.delete_selected_thread, style="Dark.TButton").pack(fill=tk.X, pady=(0, 5), padx=10, side=tk.BOTTOM)
        ttk.Button(self.chat_list_panel, text="New Chat", command=self.create_new_conversation, style="Dark.TButton").pack(fill=tk.X, pady=(0, 10), padx=10, side=tk.BOTTOM)

        # Center Panel
        center_panel = ttk.Frame(self.main_frame, style="MainDark.TFrame")
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 2))

        # Chat Canvas
        self.chat_frame = ttk.Frame(center_panel, style="MainDark.TFrame")
        self.chat_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(5, 0))
        self.chat_canvas = tk.Canvas(self.chat_frame, bg=DARK_BG, highlightthickness=0)
        self.chat_scrollbar = ttk.Scrollbar(self.chat_frame, orient=tk.VERTICAL, command=self.chat_canvas.yview)
        self.chat_scrollable_frame = ttk.Frame(self.chat_canvas, style="MainDark.TFrame")
        self.chat_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        )
        self.chat_canvas.configure(yscrollcommand=self.chat_scrollbar.set)
        self.chat_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.chat_window = self.chat_canvas.create_window((0, 0), window=self.chat_scrollable_frame, anchor="nw")
        self.chat_canvas.bind("<Configure>", lambda e: self.chat_canvas.itemconfig(self.chat_window, width=e.width))
        self.chat_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Input Area
        self.input_area_frame = ttk.Frame(center_panel, style="MainDark.TFrame")
        self.input_area_frame.place(relx=0.5, rely=0.5, relwidth=1.0, anchor="center")
        self.user_input = scrolledtext.ScrolledText(
            self.input_area_frame, height=3, bg=MEDIUM_DARK_BG, fg=LIGHT_TEXT,
            insertbackground=LIGHT_TEXT, wrap=tk.WORD, relief=tk.FLAT,
            bd=0, highlightthickness=0, font=(FONT_FAMILY, 18), padx=10, pady=5,
            selectbackground=SELECT_BG_COLOR, insertwidth=4
        )
        self.user_input.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.user_input.insert("1.0", "Type a message...")
        self.user_input.bind("<FocusIn>", self.clear_placeholder_text)
        self.user_input.bind("<FocusOut>", self.restore_placeholder_text)
        self.user_input.bind("<Return>", self.send_message_on_enter)
        self.user_input.bind("<Shift-Return>", self.add_newline)
        self.send_button = ttk.Button(self.input_area_frame, text="▶", width=2, command=self.send_message, style="Dark.TButton")
        self.send_button.pack(side=tk.RIGHT, padx=5)
        self.record_button = ttk.Button(self.input_area_frame, text="🎤", width=2, command=self.start_recording, style="Dark.TButton")
        self.record_button.pack(side=tk.RIGHT, padx=5)

        # Status Window
        self.status_frame = ttk.Frame(center_panel, style="MainDark.TFrame")
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))
        self.status_window = scrolledtext.ScrolledText(self.status_frame, height=5, wrap=tk.WORD, state=tk.NORMAL,
                                                       bg=DARK_BG, fg=LIGHT_TEXT, relief=tk.FLAT, bd=0,
                                                       highlightthickness=0, font=(FONT_FAMILY, 16), padx=14, pady=14,
                                                       selectbackground=SELECT_BG_COLOR)
        self.status_window.pack(fill=tk.X, expand=True)
        self.status_window.tag_configure("system", foreground=SYSTEM_TEXT, font=(FONT_FAMILY, 16))
        self.status_window.tag_configure("error", foreground=ERROR_TEXT, font=(FONT_FAMILY, 16, "bold"))

        # Right Panel: Settings
        self.settings_panel = ttk.Frame(self.main_frame, width=300, style="Secondary.TFrame")
        self.settings_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 0))
        self.settings_panel.pack_propagate(False)
        settings_canvas = tk.Canvas(self.settings_panel, bg=LEFT_PANEL_BG if self.is_dark_mode.get() else LIGHT_LEFT_PANEL_BG, highlightthickness=0)
        settings_scrollbar = ttk.Scrollbar(self.settings_panel, orient=tk.VERTICAL, command=settings_canvas.yview)
        settings_scrollable_frame = ttk.Frame(settings_canvas, style="Secondary.TFrame")
        settings_scrollable_frame.bind(
            "<Configure>",
            lambda e: settings_canvas.configure(scrollregion=settings_canvas.bbox("all"))
        )
        settings_canvas.configure(yscrollcommand=settings_scrollbar.set)
        settings_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        settings_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        settings_canvas.create_window((0, 0), window=settings_scrollable_frame, anchor="nw")
        settings_canvas.bind("<Configure>", lambda e: settings_canvas.itemconfig(settings_canvas.create_window((0, 0), window=settings_scrollable_frame, anchor="nw"), width=e.width))
        settings_canvas.bind_all("<MouseWheel>", self._on_mousewheel_settings)

        controls_frame = settings_scrollable_frame
        ttk.Label(controls_frame, text="Model", style="Section.TLabel").pack(pady=(10, 5), anchor="w", padx=10)
        self.model_var = tk.StringVar(self)
        self.model_menu = ttk.OptionMenu(controls_frame, self.model_var, "Loading models...", style="Dark.TMenubutton")
        self.model_menu.pack(fill=tk.X, pady=3, padx=10)
        self.model_var.trace_add("write", self.on_model_change)
        ttk.Button(controls_frame, text="Refresh Models", command=self.refresh_models, style="Dark.TButton").pack(fill=tk.X, pady=(0, 10), padx=10)
        ttk.Button(controls_frame, text="Compare Models", command=self.compare_models, style="Dark.TButton").pack(fill=tk.X, pady=(0, 10), padx=10)

        ttk.Label(controls_frame, text="Chat Mode", style="Section.TLabel").pack(pady=(10, 5), anchor="w", padx=10)
        ttk.Label(controls_frame, text="Personality", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        self.chat_mode_menu = ttk.OptionMenu(controls_frame, self.current_chat_mode, self.current_chat_mode.get(), *self.chat_modes, style="Dark.TMenubutton")
        self.chat_mode_menu.pack(fill=tk.X, pady=3, padx=10)
        self.current_chat_mode.trace_add("write", self.on_chat_mode_change)

        ttk.Label(controls_frame, text="Theme", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        ttk.Checkbutton(controls_frame, text="Dark Mode", variable=self.is_dark_mode, command=self.update_theme, style="Dark.TButton").pack(fill=tk.X, pady=3, padx=10)

        # TTS Settings
        ttk.Label(controls_frame, text="TTS Settings", style="Section.TLabel").pack(pady=(10, 5), anchor="w", padx=10)
        tts_notebook = ttk.Notebook(controls_frame)
        tts_notebook.pack(fill=tk.X, pady=3, padx=10)
        elevenlabs_tab = ttk.Frame(tts_notebook)
        macos_tab = ttk.Frame(tts_notebook)
        google_tab = ttk.Frame(tts_notebook)
        openai_tab = ttk.Frame(tts_notebook)
        piper_tab = ttk.Frame(tts_notebook)
        pyttsx3_tab = ttk.Frame(tts_notebook)
        sesame_tab = ttk.Frame(tts_notebook)
        tts_notebook.add(elevenlabs_tab, text="ElevenLabs")
        tts_notebook.add(macos_tab, text="macOS Native")
        tts_notebook.add(google_tab, text="Google Cloud")
        tts_notebook.add(openai_tab, text="OpenAI TTS")
        tts_notebook.add(piper_tab, text="Piper")
        tts_notebook.add(pyttsx3_tab, text="pyttsx3")
        tts_notebook.add(sesame_tab, text="Sesame CSM")
        
        # ElevenLabs Settings
        ttk.Label(elevenlabs_tab, text="Voice Stability", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        stability_frame = ttk.Frame(elevenlabs_tab, style="Secondary.TFrame")
        stability_frame.pack(fill=tk.X, pady=3, padx=10)
        self.stability_slider = ttk.Scale(stability_frame, from_=0.0, to_=1.0, orient=tk.HORIZONTAL, variable=self.stability_var, command=lambda v: self.stability_display.config(text=f"{self.stability_var.get():.2f}"), style="Secondary.Dark.Horizontal.TScale")
        self.stability_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.stability_display = ttk.Label(stability_frame, text=f"{self.stability_var.get():.2f}", style="Secondary.Dark.TLabel", font=(FONT_FAMILY, 16))
        self.stability_display.pack(side=tk.RIGHT, padx=5)
        ttk.Label(elevenlabs_tab, text="Voice Similarity", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        similarity_frame = ttk.Frame(elevenlabs_tab, style="Secondary.TFrame")
        similarity_frame.pack(fill=tk.X, pady=3, padx=10)
        self.similarity_slider = ttk.Scale(similarity_frame, from_=0.0, to_=1.0, orient=tk.HORIZONTAL, variable=self.similarity_var, command=lambda v: self.similarity_display.config(text=f"{self.similarity_var.get():.2f}"), style="Secondary.Dark.Horizontal.TScale")
        self.similarity_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.similarity_display = ttk.Label(similarity_frame, text=f"{self.similarity_var.get():.2f}", style="Secondary.Dark.TLabel", font=(FONT_FAMILY, 16))
        self.similarity_display.pack(side=tk.RIGHT, padx=5)

        # macOS Native Settings
        ttk.Label(macos_tab, text="macOS Voice", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        self.macos_voice_menu = ttk.OptionMenu(macos_tab, self.macos_voice, self.macos_voice.get(), *self.macos_voices, command=lambda _: self.save_tts_config(), style="Dark.TMenubutton")
        self.macos_voice_menu.pack(fill=tk.X, pady=3, padx=10)
        ttk.Button(macos_tab, text="Refresh Voices", command=self.refresh_macos_voices, style="Dark.TButton").pack(fill=tk.X, pady=(0, 10), padx=10)

        # Google Cloud TTS Settings
        ttk.Label(google_tab, text="Google Voice", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        self.google_voice_menu = ttk.OptionMenu(google_tab, self.google_voice, self.google_voice.get(), *self.google_voices, command=lambda _: self.save_tts_config(), style="Dark.TMenubutton")
        self.google_voice_menu.pack(fill=tk.X, pady=3, padx=10)

        # OpenAI TTS Settings
        ttk.Label(openai_tab, text="OpenAI Voice", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        self.openai_voice_menu = ttk.OptionMenu(openai_tab, self.openai_voice, self.openai_voice.get(), *self.openai_voices, command=lambda _: self.save_tts_config(), style="Dark.TMenubutton")
        self.openai_voice_menu.pack(fill=tk.X, pady=3, padx=10)

        # Piper TTS Settings
        ttk.Label(piper_tab, text="Piper Model", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        self.piper_model_menu = ttk.OptionMenu(piper_tab, self.piper_model, self.piper_model.get(), *self.piper_models, command=lambda _: self.save_tts_config(), style="Dark.TMenubutton")
        self.piper_model_menu.pack(fill=tk.X, pady=3, padx=10)

        # pyttsx3 Settings
        ttk.Label(pyttsx3_tab, text="pyttsx3 Voice", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        pyttsx3_voices = self.pyttsx3_tts.get_available_voices()
        self.pyttsx3_voice = tk.StringVar(value=pyttsx3_voices[0] if pyttsx3_voices else "com.apple.speech.synthesis.voice.Alex")
        self.pyttsx3_voice_menu = ttk.OptionMenu(pyttsx3_tab, self.pyttsx3_voice, self.pyttsx3_voice.get(), *pyttsx3_voices, command=lambda _: self.save_tts_config(), style="Dark.TMenubutton")
        self.pyttsx3_voice_menu.pack(fill=tk.X, pady=3, padx=10)

        # Sesame CSM Settings
        ttk.Label(sesame_tab, text="Sesame Speaker ID", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        self.sesame_speaker_menu = ttk.OptionMenu(sesame_tab, self.sesame_speaker, self.sesame_speaker.get(), *self.sesame_speakers, command=lambda _: self.save_tts_config(), style="Dark.TMenubutton")
        self.sesame_speaker_menu.pack(fill=tk.X, pady=3, padx=10)

        # TTS Provider Selection
        tts_options = ["None", "ElevenLabs", "macOS Native", "Google Cloud", "OpenAI TTS", "Piper", "pyttsx3", "Sesame CSM"]
        self.tts_provider_menu = ttk.OptionMenu(controls_frame, self.tts_provider, self.tts_provider.get(), *tts_options, command=lambda _: [self.save_tts_config(), tts_notebook.select({"ElevenLabs": elevenlabs_tab, "macOS Native": macos_tab, "Google Cloud": google_tab, "OpenAI TTS": openai_tab, "Piper": piper_tab, "pyttsx3": pyttsx3_tab, "Sesame CSM": sesame_tab}.get(self.tts_provider.get(), elevenlabs_tab))], style="Dark.TMenubutton")
        self.tts_provider_menu.pack(fill=tk.X, pady=3, padx=10)

        # STT Settings
        ttk.Label(controls_frame, text="STT Settings", style="Section.TLabel").pack(pady=(10, 5), anchor="w", padx=10)
        stt_options = ["Google Cloud", "WhisperX", "OpenAI Whisper API"]
        self.stt_provider_menu = ttk.OptionMenu(controls_frame, self.stt_provider, self.stt_provider.get(), *stt_options, command=lambda _: self.save_tts_config(), style="Dark.TMenubutton")
        self.stt_provider_menu.pack(fill=tk.X, pady=3, padx=10)

        # Advanced Settings (Collapsible)
        self.advanced_frame = ttk.Frame(controls_frame, style="Secondary.TFrame")
        self.advanced_button = ttk.Button(controls_frame, text="Advanced Settings ▼", command=self.toggle_advanced, style="Dark.TButton")
        self.advanced_button.pack(fill=tk.X, pady=3, padx=10)
        
        def add_advanced_setting(label, var, default, min_val, max_val, entry=False, reset_cmd=None):
            ttk.Label(self.advanced_frame, text=label, style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
            frame = ttk.Frame(self.advanced_frame, style="Secondary.TFrame")
            frame.pack(fill=tk.X, pady=3, padx=10)
            if entry:
                entry_widget = ttk.Entry(frame, textvariable=var, style="Dark.TEntry")
                entry_widget.pack(side=tk.LEFT, fill=tk.X, expand=True)
                entry_widget.bind("<FocusOut>", lambda e: var.set(self.validate_float(var.get(), default, min_val, max_val)))
            else:
                scale = ttk.Scale(frame, from_=min_val, to_=max_val, orient=tk.HORIZONTAL, variable=var, command=lambda v: display.config(text=f"{var.get():.2f}"), style="Secondary.Dark.Horizontal.TScale")
                scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
            display = ttk.Label(frame, text=f"{var.get():.2f}", style="Secondary.Dark.TLabel", font=(FONT_FAMILY, 16))
            display.pack(side=tk.RIGHT, padx=5)
            if reset_cmd:
                ttk.Button(self.advanced_frame, text="Reset", command=reset_cmd, style="Dark.TButton").pack(fill=tk.X, pady=3, padx=10)

        self.temperature_var = tk.DoubleVar(value=0.7)
        add_advanced_setting("Temp", self.temperature_var, 0.7, 0.0, 1.0)
        self.max_tokens_var = tk.IntVar(value=1024)
        add_advanced_setting("Max Tokens", self.max_tokens_var, 1024, 1, 16000, entry=True)
        self.presence_penalty_var = tk.DoubleVar(value=0.0)
        add_advanced_setting("Presence", self.presence_penalty_var, 0.0, -2.0, 2.0, reset_cmd=self.reset_presence_penalty)
        self.frequency_penalty_var = tk.DoubleVar(value=0.0)
        add_advanced_setting("Frequency", self.frequency_penalty_var, 0.0, -2.0, 2.0, reset_cmd=self.reset_frequency_penalty)
        self.top_p_var = tk.DoubleVar(value=1.0)
        add_advanced_setting("Top P", self.top_p_var, 1.0, 0.0, 1.0, reset_cmd=self.reset_top_p)
        self.top_k_var = tk.IntVar(value=40)
        add_advanced_setting("Top K", self.top_k_var, 40, 1, 100, entry=True, reset_cmd=self.reset_top_k)

        ttk.Label(self.advanced_frame, text="Context Limit", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        context_options = ["Last 10 Messages", "Last 20 Messages", "Last 50 Messages", "No Limit"]
        self.context_limit_var = tk.StringVar(value="Last 50 Messages")
        ttk.OptionMenu(self.advanced_frame, self.context_limit_var, self.context_limit_var.get(), *context_options, style="Dark.TMenubutton").pack(fill=tk.X, pady=3, padx=10)

        ttk.Label(self.advanced_frame, text="Reasoning", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        reasoning_options = ["None", "Low", "Medium", "High"]
        self.reasoning_effort_var = tk.StringVar(value="Medium")
        self.reasoning_effort_menu = ttk.OptionMenu(self.advanced_frame, self.reasoning_effort_var, self.reasoning_effort_var.get(), *reasoning_options, style="Dark.TMenubutton")
        self.reasoning_effort_menu.pack(fill=tk.X, pady=3, padx=10)

        ttk.Label(controls_frame, text="System Prompt", style="Secondary.Dark.TLabel").pack(pady=(5, 0), anchor="w", padx=10)
        self.system_prompt_text_widget = scrolledtext.ScrolledText(controls_frame, height=6, wrap=tk.WORD,
                                                                 bg=MEDIUM_DARK_BG, fg=LIGHT_TEXT, insertbackground=LIGHT_TEXT,
                                                                 relief=tk.FLAT, bd=0, font=(FONT_FAMILY, 18), selectbackground=SELECT_BG_COLOR)
        self.system_prompt_text_widget.pack(fill=tk.X, pady=3, padx=10)

    def toggle_advanced(self):
        if self.advanced_frame.winfo_ismapped():
            self.advanced_frame.pack_forget()
            self.advanced_button.config(text="Advanced Settings ▼")
        else:
            self.advanced_frame.pack(fill=tk.X, pady=3, padx=10)
            self.advanced_button.config(text="Advanced Settings ▲")

    def validate_float(self, value, default, min_val, max_val):
        try:
            val = float(value)
            return max(min_val, min(max_val, val))
        except (ValueError, TypeError):
            return default

    def create_message_frame(self, role, text):
        message_frame = ttk.Frame(self.chat_scrollable_frame, style="MainDark.TFrame" if self.is_dark_mode.get() else "MainLight.TFrame")
        message_frame.pack(fill=tk.X, padx=15, pady=10, anchor="w")
        self.message_frames.append(message_frame)
        if len(self.message_frames) > 100:
            oldest_frame = self.message_frames.pop(0)
            oldest_frame.destroy()
        label = ttk.Label(
            message_frame,
            text=f"{role.capitalize()}: {text}",
            style="MainDark.TLabel" if self.is_dark_mode.get() else "MainLight.TLabel",
            wraplength=900,
            justify=tk.LEFT,
            foreground={
                "user": ACCENT_COLOR_USER if self.is_dark_mode.get() else LIGHT_ACCENT_USER,
                "assistant": ACCENT_COLOR_ASSISTANT if self.is_dark_mode.get() else LIGHT_ACCENT_ASSISTANT,
                "system": SYSTEM_TEXT,
                "error": ERROR_TEXT
            }.get(role, LIGHT_TEXT if self.is_dark_mode.get() else LIGHT_TEXT_DARK),
            font=(FONT_FAMILY, 18, "bold" if role == "user" else "normal")
        )
        label.pack(side=tk.LEFT, anchor="w")
        return message_frame, label

    def debounce_stream_update(self, full_response, message_frame, label):
        if not hasattr(self, '_update_timer'):
            self._update_timer = None
        if self._update_timer:
            self.after_cancel(self._update_timer)
        self._update_timer = self.after(100, lambda: self._commit_stream_update(full_response, message_frame, label))

    def _commit_stream_update(self, full_response, message_frame, label):
        label.config(text=f"Assistant: {full_response}")
        self.chat_canvas.update_idletasks()
        self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        self.chat_canvas.yview_moveto(1.0)

    def _on_mousewheel(self, event):
        self.chat_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_settings(self, event):
        if self.settings_panel.winfo_containing(event.x_root, event.y_root):
            settings_canvas = self.settings_panel.winfo_children()[0]
            settings_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def set_elevenlabs_voice_id(self):
        new_voice_id = simpledialog.askstring("ElevenLabs Voice ID", "Enter the global ElevenLabs Voice ID:", initialvalue=self.config.get("voice_id", ""), parent=self)
        if new_voice_id is not None:
            self.config["voice_id"] = new_voice_id
            save_config(self.config)
            self.add_log_message(f"Global Voice ID set to: {new_voice_id}", "system")
            self.refresh_conversation()

    def set_default_system_prompt(self):
        new_default_prompt = simpledialog.askstring("Default System Prompt", "Enter the default system prompt for new conversations:", initialvalue=self.config.get("default_system_prompt", "You are a helpful AI assistant."), parent=self)
        if new_default_prompt is not None:
            self.config["default_system_prompt"] = new_default_prompt
            save_config(self.config)
            self.add_log_message("Default system prompt updated.", "system")

    def rename_selected_thread(self):
        if self.current_conversation_id is None:
            messagebox.showwarning("No Selection", "Please select a conversation to rename.")
            return
        new_title = simpledialog.askstring("Rename Thread", "Enter new thread name:", parent=self)
        if new_title:
            asyncio.run_coroutine_threadsafe(update_conversation_title_in_db(self.current_conversation_id, new_title), self.loop)
            self.refresh_chat_list()

    def load_or_create_conversation(self):
        conversations = asyncio.run_coroutine_threadsafe(fetch_conversations_from_db(), self.loop).result()
        if conversations:
            self.current_conversation_id = conversations[0]["id"]
            self.on_chat_select(None)
        else:
            self.create_new_conversation()
        self.refresh_chat_list()

    def create_new_conversation(self):
        system_prompt = self.system_prompt_text_widget.get(1.0, tk.END).strip()
        if not system_prompt:
            system_prompt = self.config.get("default_system_prompt", "You are a helpful AI assistant.")
        model_selection = self.model_var.get()
        current_model = "" if not model_selection or model_selection == "Loading models..." else model_selection
        new_title = f"New Chat {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        self.current_conversation_id = asyncio.run_coroutine_threadsafe(
            create_conversation_in_db(title=new_title, model=current_model, system_prompt=system_prompt), self.loop
        ).result()
        for frame in self.message_frames:
            frame.destroy()
        self.message_frames = []
        self.conversation_log = []

    def refresh_chat_list(self):
        self.chat_listbox.delete(0, tk.END)
        conversations = asyncio.run_coroutine_threadsafe(fetch_conversations_from_db(), self.loop).result()
        self.conversation_id_map.clear()
        for index, conv in enumerate(conversations):
            conv_id, title = conv["id"], conv["title"]
            display_title = title if title else f"Conversation {conv_id}"
            self.chat_listbox.insert(tk.END, display_title)
            self.conversation_id_map[index] = conv_id
            if conv_id == self.current_conversation_id:
                self.chat_listbox.selection_clear(0, tk.END)
                self.chat_listbox.selection_set(index)
                self.chat_listbox.activate(index)
                self.chat_listbox.see(index)

    def search_chats(self, event=None):
        query = self.search_entry.get().strip().lower()
        if query == "search chats...":
            query = ""
        self.chat_listbox.delete(0, tk.END)
        self.conversation_id_map.clear()
        conversations = asyncio.run_coroutine_threadsafe(fetch_conversations_from_db(), self.loop).result()
        for index, conv in enumerate(conversations):
            conv_id, title = conv["id"], conv["title"]
            if query in title.lower() or not query:
                display_title = title if title else f"Conversation {conv_id}"
                self.chat_listbox.insert(tk.END, display_title)
                self.conversation_id_map[index] = conv_id
                if conv_id == self.current_conversation_id:
                    self.chat_listbox.selection_set(index)

    async def _on_chat_select_async(self, conv_id):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT llm_model, system_prompt FROM conversations WHERE id = ?", (conv_id,))
            conv_data = await cursor.fetchone()
        return conv_data

    def on_chat_select(self, event):
        if not self.chat_listbox.curselection():
            return
        selected_index = self.chat_listbox.curselection()[0]
        if selected_index not in self.conversation_id_map:
            return
        conv_id = self.conversation_id_map[selected_index]
        if conv_id == self.current_conversation_id and event is not None:
            return
        self.current_conversation_id = conv_id

        # Run async operation in the event loop
        conv_data = asyncio.run_coroutine_threadsafe(self._on_chat_select_async(conv_id), self.loop).result()

        if conv_data:
            loaded_model, loaded_system_prompt = conv_data["llm_model"], conv_data["system_prompt"]
            if loaded_model and loaded_model != "Loading models..." and self.model_var.get() != loaded_model:
                if self.available_models and loaded_model in self.available_models:
                    self.model_var.set(loaded_model)
            if loaded_system_prompt:
                self.system_prompt_text_widget.delete(1.0, tk.END)
                self.system_prompt_text_widget.insert(tk.END, loaded_system_prompt)

        for frame in self.message_frames:
            frame.destroy()
        self.message_frames = []
        self.status_window.delete(1.0, tk.END)

        messages = asyncio.run_coroutine_threadsafe(fetch_messages_from_db(self.current_conversation_id), self.loop).result()
        self.conversation_log = []
        for msg in messages:
            role, content, timestamp, tokens, cost = msg["role"], msg["content"], msg["timestamp"], msg["tokens"], msg["cost"]
            self.add_log_message(content, role, timestamp)
            if tokens and cost:
                self.add_log_message(f"Tokens: {tokens}, Estimated Cost: ${cost:.4f}", "system")

        # Load draft if available
        draft = asyncio.run_coroutine_threadsafe(load_draft(self.current_conversation_id), self.loop).result()
        if draft:
            self.user_input.delete("1.0", tk.END)
            self.user_input.insert("1.0", draft)
            self.placeholder_visible = False

    async def _update_conversation_title_from_message_async(self, message_content):
        if not self.current_conversation_id:
            return
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT title FROM conversations WHERE id = ?", (self.current_conversation_id,))
            current_title = (await cursor.fetchone())[0]
        if current_title.startswith("New Chat"):
            words = message_content.split()
            potential_title = " ".join(words[:5])
            if len(potential_title) > 50:
                potential_title = potential_title[:47] + "..."
            if potential_title:
                await update_conversation_title_in_db(self.current_conversation_id, potential_title)
                self.refresh_chat_list()

    def update_conversation_title_from_message(self, message_content):
        # Run async operation in the event loop
        asyncio.run_coroutine_threadsafe(self._update_conversation_title_from_message_async(message_content), self.loop)

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
            asyncio.run_coroutine_threadsafe(update_conversation_title_in_db(conv_id, new_title.strip()), self.loop)
            self.refresh_chat_list()

    def delete_conversation(self, conv_id):
        if not messagebox.askyesno("Delete Chat", "Are you sure you want to delete this chat and all its messages? This cannot be undone.", parent=self):
            return
        asyncio.run_coroutine_threadsafe(delete_conversation_in_db(conv_id), self.loop)
        if self.current_conversation_id == conv_id:
            self.current_conversation_id = None
            for frame in self.message_frames:
                frame.destroy()
            self.message_frames = []
            self.conversation_log = []
            self.status_window.delete(1.0, tk.END)
            self.load_or_create_conversation()
        self.refresh_chat_list()

    def reset_presence_penalty(self):
        self.presence_penalty_var.set(0.0)

    def reset_frequency_penalty(self):
        self.frequency_penalty_var.set(0.0)

    def reset_top_p(self):
        self.top_p_var.set(1.0)

    def reset_top_k(self):
        self.top_k_var.set(40)

    def add_log_message(self, message_text, level="system", timestamp_str=None):
        if timestamp_str is None:
            timestamp = datetime.now().strftime("[%H:%M:%S]")
        else:
            try:
                timestamp = datetime.fromisoformat(timestamp_str).strftime("[%H:%M:%S]")
            except ValueError:
                timestamp = f"[{timestamp_str}]"
        
        if level in ["system", "error"]:
            self.status_window.config(state=tk.NORMAL)
            self.status_window.insert(tk.END, f"\n{timestamp} {level.capitalize()}: {message_text}", level)
            self.status_window.insert(tk.END, "\n")
            self.status_window.see(tk.END)
            self.status_window.config(state=tk.NORMAL)
            return

        message_frame, label = self.create_message_frame(level, message_text)
        button_frame = ttk.Frame(message_frame, style="MainDark.TFrame" if self.is_dark_mode.get() else "MainLight.TFrame")
        button_frame.pack(side=tk.RIGHT, anchor="e")

        if level == "assistant":
            can_play = False
            provider = self.tts_provider.get()
            if provider == "ElevenLabs" and self.config.get("voice_id"):
                can_play = True
            elif provider == "macOS Native" and self.macos_tts and self.macos_tts.synthesizer:
                can_play = True
            elif provider == "Google Cloud" and self.google_tts:
                can_play = True
            elif provider == "OpenAI TTS" and self.openai_tts:
                can_play = True
            elif provider == "Piper" and self.piper_tts:
                can_play = True
            elif provider == "pyttsx3" and self.pyttsx3_tts:
                can_play = True
            elif provider == "Sesame CSM" and self.sesame_csm:
                can_play = True

            if can_play:
                play_button = ttk.Button(
                    button_frame,
                    text="▷",
                    command=lambda: self.play_message(message_text),
                    style="Dark.TButton" if self.is_dark_mode.get() else "Light.TButton",
                    width=1
                )
                play_button.pack(side=tk.LEFT, padx=3)

            copy_button = ttk.Button(
                button_frame,
                text="📋",
                command=lambda: pyperclip.copy(message_text),
                style="Dark.TButton" if self.is_dark_mode.get() else "Light.TButton",
                width=1
            )
            copy_button.pack(side=tk.LEFT, padx=3)

            refresh_button = ttk.Button(
                button_frame,
                text="↻",
                command=self.refresh_conversation,
                style="Dark.TButton" if self.is_dark_mode.get() else "Light.TButton",
                width=1
            )
            refresh_button.pack(side=tk.LEFT, padx=3)

            thumbs_up = ttk.Button(
                button_frame,
                text="👍",
                command=lambda: self.add_log_message("👍 Reaction added!", "system"),
                style="Dark.TButton" if self.is_dark_mode.get() else "Light.TButton",
                width=1
            )
            thumbs_up.pack(side=tk.LEFT, padx=3)

            thumbs_down = ttk.Button(
                button_frame,
                text="👎",
                command=lambda: self.add_log_message("👎 Reaction added!", "system"),
                style="Dark.TButton" if self.is_dark_mode.get() else "Light.TButton",
                width=1
            )
            thumbs_down.pack(side=tk.LEFT, padx=3)

        if level in ["user", "assistant"]:
            self.conversation_log.append({"role": level, "content": message_text})
        if self.current_conversation_id and level in ["user", "assistant"]:
            asyncio.run_coroutine_threadsafe(
                add_message_to_db(self.current_conversation_id, level, message_text), self.loop
            )
            if level == "user":
                self.update_conversation_title_from_message(message_text)

    def refresh_conversation(self):
        if self.current_conversation_id:
            self.on_chat_select(None)

    def refresh_macos_voices(self):
        if not self.macos_tts:
            self.add_log_message("macOS TTS not available.", "error")
            return
        self.add_log_message("Refreshing macOS voices...", "system")
        self.macos_voices = self.macos_tts.get_available_voices()
        self.macos_voice_menu['menu'].delete(0, 'end')
        for voice in self.macos_voices:
            self.macos_voice_menu['menu'].add_command(label=voice, command=tk._setit(self.macos_voice, voice))
        if self.macos_voice.get() not in self.macos_voices:
            self.macos_voice.set(self.macos_voices[0] if self.macos_voices else "Alex")
        self.add_log_message("macOS voices refreshed.", "system")

    def play_message(self, message_text):
        provider = self.tts_provider.get()
        if provider == "None":
            self.add_log_message("TTS is disabled.", "system")
            return
        elif provider == "ElevenLabs":
            asyncio.run_coroutine_threadsafe(
                generate_and_play_audio_elevenlabs(
                    message_text, self.config.get("voice_id"), self.stability_var.get(),
                    self.similarity_var.get(), self.add_log_message, self.config["elevenlabs_api_key"]
                ),
                self.loop
            )
        elif provider == "macOS Native" and self.macos_tts:
            asyncio.run_coroutine_threadsafe(self.macos_tts.generate_and_play_audio(message_text), self.loop)
        elif provider == "Google Cloud" and self.google_tts:
            asyncio.run_coroutine_threadsafe(self.google_tts.generate_and_play_audio(message_text), self.loop)
        elif provider == "OpenAI TTS" and self.openai_tts:
            asyncio.run_coroutine_threadsafe(self.openai_tts.generate_and_play_audio(message_text), self.loop)
        elif provider == "Piper" and self.piper_tts:
            asyncio.run_coroutine_threadsafe(self.piper_tts.generate_and_play_audio(message_text), self.loop)
        elif provider == "pyttsx3" and self.pyttsx3_tts:
            asyncio.run_coroutine_threadsafe(self.pyttsx3_tts.generate_and_play_audio(message_text), self.loop)
        elif provider == "Sesame CSM" and self.sesame_csm:
            context = self.create_sesame_context(self.conversation_log)
            asyncio.run_coroutine_threadsafe(
                self.sesame_csm.generate_and_play_audio(message_text, context=context),
                self.loop
            )
        else:
            self.add_log_message(f"TTS provider {provider} is not available.", "error")

    def create_sesame_context(self, conversation_log):
        if not self.sesame_csm:
            return []
        context = []
        for msg in conversation_log[-5:]:  # Last 5 messages for context
            role = msg["role"]
            content = msg["content"]
            speaker = 0 if role == "user" else 1
            segment = Segment(text=content, speaker=speaker, audio=None)
            context.append(segment)
        return context

    def load_initial_models(self):
        self.add_log_message("Fetching models...", "system")
        self.refresh_button.config(state=tk.DISABLED, text="Refreshing...")
        self.after(100, lambda: asyncio.run_coroutine_threadsafe(self._fetch_all_models_thread(), self.loop))

    async def _fetch_all_models_thread(self):
        self.model_groups = await fetch_all_models(self.config)
        for provider, models in self.model_groups.items():
            if models:
                self.add_log_message(f"Fetched {len(models)} {provider} models", "system")
                await cache_models(provider, models)
            else:
                self.add_log_message(f"No/Error {provider} models", "error")
        self.available_models = []
        for provider, models in self.model_groups.items():
            if models:
                for model_id in models:
                    self.available_models.append(f"{provider}: {model_id}")
        if not self.available_models:
            self.add_log_message("No models available from any provider.", "error")
        self.after(0, self.update_model_list)
        self.refresh_button.config(state=tk.NORMAL, text="Refresh Models")

    def update_model_list(self):
        menu = self.model_menu['menu']
        menu.delete(0, 'end')
        current_selection = self.model_var.get()
        new_selection = None
        if not self.available_models:
            menu.add_command(label="No models available", command=tk._setit(self.model_var, "No models available"))
            new_selection = "No models available"
        else:
            for model_id in self.available_models:
                menu.add_command(label=model_id, command=tk._setit(self.model_var, model_id))
            if current_selection in self.available_models:
                new_selection = current_selection
            else:
                new_selection = self.available_models[0]
        if new_selection and self.model_var.get() != new_selection:
            self.model_var.set(new_selection)

    def get_system_prompt(self):
        custom_prompt = self.system_prompt_text_widget.get("1.0", tk.END).strip()
        if custom_prompt:
            return custom_prompt
        mode = self.current_chat_mode.get()
        prompts = {
            "Normal": "You are a helpful AI assistant.",
            "Assistant": "You are a professional assistant providing detailed and accurate responses.",
            "Code Assistant": "You are a coding expert. Provide code snippets and explanations.",
            "Sarcastic Assistant": "You are a witty and sarcastic assistant, still helpful but with an edge.",
            "Call Mode": "You are an interactive voice assistant, responding to spoken commands."
        }
        return prompts.get(mode, self.config.get("default_system_prompt", "You are a helpful AI assistant."))

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

    def start_recording(self):
        if self.current_chat_mode.get() != "Call Mode":
            self.add_log_message("Please switch to Call Mode to use voice input.", "system")
            return
        self.record_button.config(text="■", command=self.stop_recording)
        asyncio.run_coroutine_threadsafe(self.record_and_transcribe(), self.loop)

    async def record_and_transcribe(self):
        provider = self.stt_provider.get()
        if provider == "Google Cloud":
            transcript = await self.google_stt.record_and_transcribe(duration=5)
        elif provider == "WhisperX":
            transcript = await self.whisperx_stt.record_and_transcribe(duration=5)
        elif provider == "OpenAI Whisper API":
            transcript = await self.openai_whisper_stt.record_and_transcribe(duration=5)
        else:
            self.add_log_message(f"STT provider {provider} is not available.", "error")
            return
        if transcript:
            self.user_input.delete("1.0", tk.END)
            self.user_input.insert("1.0", transcript)
            self.placeholder_visible = False
            self.send_message()
        self.record_button.config(text="🎤", command=self.start_recording)

    def stop_recording(self):
        provider = self.stt_provider.get()
        if provider == "Google Cloud":
            self.google_stt.stop_recording()
        elif provider == "WhisperX":
            self.whisperx_stt.stop_recording()
        elif provider == "OpenAI Whisper API":
            self.openai_whisper_stt.stop_recording()
        self.record_button.config(text="🎤", command=self.start_recording)

    def process_ai_response(self):
        selected_model_full = self.model_var.get()
        system_prompt = self.get_system_prompt()
        messages = [{"role": "system", "content": system_prompt}] + self.get_context_limit_messages()
        asyncio.run_coroutine_threadsafe(process_ai_response(self, selected_model_full, messages, self.config), self.loop)

    def refresh_models(self):
        self.add_log_message("Refreshing models...", "system")
        self.refresh_button.config(state=tk.DISABLED, text="Refreshing...")
        self.after(100, lambda: asyncio.run_coroutine_threadsafe(self._fetch_all_models_thread(), self.loop))

    def compare_models(self):
        selected_model_full = self.model_var.get()
        if not selected_model_full or "No models" in selected_model_full:
            self.add_log_message("Error: No model selected.", "error")
            return
        comparison_models = [m for m in self.available_models if m != selected_model_full][:2]
        if len(comparison_models) < 2:
            self.add_log_message("Not enough models available for comparison.", "error")
            return
        system_prompt = self.get_system_prompt()
        messages = [{"role": "system", "content": system_prompt}] + self.get_context_limit_messages()
        for model in [selected_model_full] + comparison_models:
            self.add_log_message(f"Generating response with {model}...", "system")
            asyncio.run_coroutine_threadsafe(process_ai_response(self, model, messages, self.config), self.loop)

    def upload_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf"), ("Text files", "*.txt")])
        if not file_path:
            return
        try:
            if file_path.endswith(".pdf"):
                with open(file_path, "rb") as f:
                    pdf = PdfReader(f)
                    text = "".join(page.extract_text() for page in pdf.pages)
            else:
                with open(file_path, "r") as f:
                    text = f.read()
            self.add_log_message(f"Uploaded file: {file_path}", "system")
            embedding = np.array([hash(text) % 768] * 768, dtype=np.float32)  # Simplified embedding
            self.faiss_index.add(np.array([embedding]))
            self.documents.append({"content": text, "filename": os.path.basename(file_path)})
            self.conversation_log.append({"role": "system", "content": f"Uploaded file content: {text}"})
            self.add_log_message("File content added to conversation context.", "system")
        except Exception as e:
            self.add_log_message(f"Error uploading file: {str(e)}", "error")

    def export_conversation(self):
        if not self.current_conversation_id:
            self.add_log_message("No conversation selected.", "error")
            return
        messages = asyncio.run_coroutine_threadsafe(fetch_messages_from_db(self.current_conversation_id), self.loop).result()
        export_data = [{"role": msg["role"], "content": msg["content"], "timestamp": msg["timestamp"]} for msg in messages]
        format_choice = simpledialog.askstring("Export Format", "Enter format (json/md):", initialvalue="json", parent=self)
        file_path = filedialog.asksaveasfilename(defaultextension=f".{format_choice}", filetypes=[(f"{format_choice.upper()} files", f"*.{format_choice}")])
        if not file_path:
            return
        try:
            if format_choice.lower() == "json":
                with open(file_path, "w") as f:
                    json.dump(export_data, f, indent=2)
            else:
                with open(file_path, "w") as f:
                    for msg in export_data:
                        f.write(f"**{msg['role'].capitalize()}** ({msg['timestamp']}): {msg['content']}\n\n")
            self.add_log_message(f"Conversation exported to {file_path}", "system")
        except Exception as e:
            self.add_log_message(f"Error exporting conversation: {str(e)}", "error")

    def delete_selected_thread(self):
        selection = self.chat_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a conversation thread to delete.")
            return
        conv_index = selection[0]
        conv_id = self.conversation_id_map.get(conv_index)
        if conv_id and messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this conversation thread?"):
            asyncio.run_coroutine_threadsafe(delete_conversation_in_db(conv_id), self.loop)
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

    def configure_api_keys(self):
        global openai_api_key, openrouter_api_key, xai_api_key, anthropic_api_key, huggingface_api_key
        global google_api_key, perplexity_api_key, together_api_key, groq_api_key, pi_api_key
        global mistral_api_key, deepseek_api_key
        new_openai = simpledialog.askstring("API Key", "OpenAI API Key:", initialvalue=self.config["openai_api_key"], parent=self)
        if new_openai is not None:
            self.config["openai_api_key"] = new_openai
            openai_api_key = new_openai
        new_openrouter = simpledialog.askstring("API Key", "OpenRouter API Key:", initialvalue=self.config["openrouter_api_key"], parent=self)
        if new_openrouter is not None:
            self.config["openrouter_api_key"] = new_openrouter
            openrouter_api_key = new_openrouter
        new_xai = simpledialog.askstring("API Key", "XAI API Key:", initialvalue=self.config["xai_api_key"], parent=self)
        if new_xai is not None:
            self.config["xai_api_key"] = new_xai
            xai_api_key = new_xai
        new_anthropic = simpledialog.askstring("API Key", "Anthropic API Key:", initialvalue=self.config["anthropic_api_key"], parent=self)
        if new_anthropic is not None:
            self.config["anthropic_api_key"] = new_anthropic
            anthropic_api_key = new_anthropic
        new_huggingface = simpledialog.askstring("API Key", "HuggingFace API Key:", initialvalue=self.config["huggingface_api_key"], parent=self)
        if new_huggingface is not None:
            self.config["huggingface_api_key"] = new_huggingface
            huggingface_api_key = new_huggingface
        new_google = simpledialog.askstring("API Key", "Google API Key:", initialvalue=self.config["google_api_key"], parent=self)
        if new_google is not None:
            self.config["google_api_key"] = new_google
            google_api_key = new_google
        new_perplexity = simpledialog.askstring("API Key", "Perplexity API Key:", initialvalue=self.config["perplexity_api_key"], parent=self)
        if new_perplexity is not None:
            self.config["perplexity_api_key"] = new_perplexity
            perplexity_api_key = new_perplexity
        new_together = simpledialog.askstring("API Key", "Together.ai API Key:", initialvalue=self.config["together_api_key"], parent=self)
        if new_together is not None:
            self.config["together_api_key"] = new_together
            together_api_key = new_together
        new_groq = simpledialog.askstring("API Key", "Groq API Key:", initialvalue=self.config["groq_api_key"], parent=self)
        if new_groq is not None:
            self.config["groq_api_key"] = new_groq
            groq_api_key = new_groq
        new_pi = simpledialog.askstring("API Key", "Pi.ai API Key:", initialvalue=self.config["pi_api_key"], parent=self)
        if new_pi is not None:
            self.config["pi_api_key"] = new_pi
            pi_api_key = new_pi
        new_mistral = simpledialog.askstring("API Key", "Mistral API Key:", initialvalue=self.config["mistral_api_key"], parent=self)
        if new_mistral is not None:
            self.config["mistral_api_key"] = new_mistral
            mistral_api_key = new_mistral
        new_deepseek = simpledialog.askstring("API Key", "DeepSeek API Key:", initialvalue=self.config["deepseek_api_key"], parent=self)
        if new_deepseek is not None:
            self.config["deepseek_api_key"] = new_deepseek
            deepseek_api_key = new_deepseek
        save_config(self.config)
        self.add_log_message("API keys updated. Refreshing models...", "system")
        self.load_initial_models()

    def on_model_change(self, *args):
        if self.current_conversation_id:
            new_model = self.model_var.get()
            if new_model and new_model != "No models available" and new_model != "Loading models...":
                async def update_model():
                    async with aiosqlite.connect(DB_PATH) as db:
                        await db.execute("UPDATE conversations SET llm_model = ? WHERE id = ?", (new_model, self.current_conversation_id))
                        await db.commit()
                asyncio.run_coroutine_threadsafe(update_model(), self.loop)
                self.add_log_message(f"Model updated to {new_model} for this conversation.", "system")

    def on_chat_mode_change(self, *args):
        self.add_log_message(f"Chat mode changed to {self.current_chat_mode.get()}.", "system")

    def on_closing(self):
        content = self.user_input.get("1.0", tk.END).strip()
        if content and not self.placeholder_visible and self.current_conversation_id:
            asyncio.run_coroutine_threadsafe(save_draft(self.current_conversation_id, content), self.loop)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join()
        self.destroy()