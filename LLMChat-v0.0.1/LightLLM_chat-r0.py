import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import os
import re
from openai import OpenAI

class VoyeurChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Voyeur Chat")
        self.root.geometry("1200x800")

        # Initialize variables
        self.chat_history = []
        self.is_running = False
        self.user_input_var = tk.StringVar()
        self.model_var = tk.StringVar(value="gpt-4o")
        self.speed_var = tk.StringVar(value="normal")
        self.youtube_subtitles = tk.BooleanVar(value=False)
        self.theme_var = tk.StringVar(value="dark")
        self.chat_mode = tk.StringVar(value="normal")

        # Load API keys from environment variables or prompt for them
        self.openai_api_key = os.environ.get("OPENAI_API_KEY", "")
        if not self.openai_api_key:
            self.prompt_for_api_key("OpenAI")

        # Create GUI elements
        self.create_gui()

        # Setup keyboard shortcuts
        self.setup_shortcuts()

        # Apply initial theme
        self.toggle_theme()

    def create_gui(self):
        # Create main frame with grid layout
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Configure grid for main frame
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)

        # Create left panel for controls
        self.create_left_panel()

        # Create right panel for chat
        self.create_right_panel()

    def create_left_panel(self):
        left_panel = ttk.Frame(self.main_frame)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        left_panel.grid_rowconfigure(0, weight=1)
        left_panel.grid_columnconfigure(0, weight=1)

        # Add model selection dropdown
        ttk.Label(left_panel, text="Model:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        model_menu = ttk.OptionMenu(left_panel, self.model_var, "gpt-4o", "gpt-4o", "gpt-4", "gpt-3.5-turbo")
        model_menu.grid(row=2, column=0, padx=5, pady=5, sticky="ew")

        # Add speed selection
        ttk.Label(left_panel, text="Speed:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        speed_menu = ttk.OptionMenu(left_panel, self.speed_var, "normal", "slow", "normal", "fast")
        speed_menu.grid(row=4, column=0, padx=5, pady=5, sticky="ew")

        # Add YouTube subtitles toggle
        ttk.Checkbutton(left_panel, text="YouTube Subtitles", variable=self.youtube_subtitles).grid(row=5, column=0, padx=5, pady=2, sticky="w")

        # Add theme selection
        ttk.Label(left_panel, text="Theme:").grid(row=6, column=0, padx=5, pady=5, sticky="w")
        theme_menu = ttk.OptionMenu(left_panel, self.theme_var, "dark", "light", "dark", command=lambda _: self.toggle_theme())
        theme_menu.grid(row=7, column=0, padx=5, pady=5, sticky="ew")

        # Add chat mode selection
        ttk.Label(left_panel, text="Chat Mode:").grid(row=8, column=0, padx=5, pady=5, sticky="w")
        mode_menu = ttk.OptionMenu(left_panel, self.chat_mode, "normal", "normal", "voyeur")
        mode_menu.grid(row=9, column=0, padx=5, pady=5, sticky="ew")

        # Add clear history button
        ttk.Button(left_panel, text="Clear History", command=self.clear_history).grid(row=10, column=0, padx=5, pady=10, sticky="ew")

    def create_right_panel(self):
        right_panel = ttk.Frame(self.main_frame)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        right_panel.grid_rowconfigure(0, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)

        # Create chat display area
        self.chat_display = scrolledtext.ScrolledText(
            right_panel, wrap=tk.WORD, height=30, width=80, state="disabled",
            font=("Arial", 12), background="#2b2b2b", foreground="white"
        )
        self.chat_display.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.chat_display.tag_configure("user", foreground="cyan", font=("Arial", 12, "bold"))
        self.chat_display.tag_configure("assistant", foreground="green", font=("Arial", 12, "bold"))
        self.chat_display.tag_configure("system", foreground="yellow", font=("Arial", 12, "italic"))
        self.chat_display.tag_configure("timestamp", foreground="grey", font=("Arial", 10))

        # Create input area frame
        input_frame = ttk.Frame(right_panel)
        input_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        input_frame.grid_columnconfigure(0, weight=1)

        # Create input field
        self.user_input_entry = ttk.Entry(input_frame, textvariable=self.user_input_var, width=70)
        self.user_input_entry.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.user_input_entry.bind("<Return>", lambda event: self.run_conversation())

        # Create send button
        send_button = ttk.Button(input_frame, text="Send", command=self.run_conversation)
        send_button.grid(row=0, column=1, padx=5, pady=5)

    def setup_shortcuts(self):
        self.root.bind("<Control-l>", lambda event: self.clear_history())
        self.root.bind("<Control-s>", lambda event: self.save_chat())
        self.root.bind("<Control-t>", lambda event: self.toggle_theme())

    def toggle_theme(self):
        theme = self.theme_var.get()
        if theme == "dark":
            self.chat_display.configure(background="#2b2b2b", foreground="white")
            self.root.configure(background="#1a1a1a")
        else:
            self.chat_display.configure(background="white", foreground="black")
            self.root.configure(background="white")

    def add_message(self, role, content, is_streaming=False):
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.chat_display.config(state="normal")
        message_id = f"msg_{len(self.chat_history)}"
        formatted_content = f"[{timestamp}] {role}: {content}\n\n"
        tag_role = role.lower()
        self.chat_display.insert(tk.END, formatted_content, (tag_role,))
        self.scroll_to_bottom()
        self.chat_display.config(state="disabled")
        if not is_streaming:
            self.chat_history.append({"role": tag_role, "content": content})
        return message_id

    def update_message(self, message_id, content):
        self.chat_display.config(state="normal")
        self.chat_display.delete("1.0", tk.END)
        for msg in self.chat_history:
            formatted_content = f"[{msg.get('timestamp', '00:00:00')}] {msg['role'].capitalize()}: {msg['content']}\n\n"
            self.chat_display.insert(tk.END, formatted_content, (msg['role'],))
        # Add the current streaming message
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_content = f"[{timestamp}] Assistant: {content}\n\n"
        self.chat_display.insert(tk.END, formatted_content, ("assistant",))
        self.chat_display.config(state="disabled")
        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        self.chat_display.yview(tk.END)

    def clear_history(self):
        self.chat_history = []
        self.chat_display.config(state="normal")
        self.chat_display.delete("1.0", tk.END)
        self.chat_display.config(state="disabled")

    def save_chat(self):
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chat_log_{timestamp}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            for msg in self.chat_history:
                f.write(f"[{msg.get('timestamp', 'N/A')}] {msg['role'].capitalize()}: {msg['content']}\n\n")
        self.add_message("System", f"Chat saved to {filename}")

    def prompt_for_api_key(self, service):
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Enter {service} API Key")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=f"Please enter your {service} API key:").pack(pady=10)
        api_key_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=api_key_var, show="*", width=40).pack(pady=10)

        def submit():
            if service == "OpenAI":
                self.openai_api_key = api_key_var.get()
            dialog.destroy()

        ttk.Button(dialog, text="Submit", command=submit).pack(pady=10)
        self.root.wait_window(dialog)
        return api_key_var.get()

    def remove_typing_message(self):
        self.chat_display.config(state="normal")
        content = self.chat_display.get("1.0", tk.END)
        lines = content.splitlines()
        if lines and "User is typing..." in lines[-1]:
            self.chat_display.delete("1.0", tk.END)
            for line in lines[:-1]:
                if line.strip():
                    self.chat_display.insert(tk.END, line + "\n")
        self.chat_display.config(state="disabled")

    def run_conversation(self):
        user_input = self.user_input_var.get().strip()
        if not user_input or self.is_running:
            return

        self.is_running = True
        self.user_input_entry.config(state="disabled")
        self.user_input_var.set("")

        # Clear any "User is typing..." message if it exists
        self.remove_typing_message()

        # Add user message to chat
        self.add_message("User", user_input)

        # Start a new thread for the API call to keep the UI responsive
        conversation_thread = threading.Thread(target=self.stream_response, args=(user_input,))
        conversation_thread.daemon = True
        conversation_thread.start()

    def stream_response(self, user_input):
        model = self.model_var.get()
        speed = self.speed_var.get()
        context = self.build_context()

        # Prepare the message list with system message and chat history
        messages = [
            {"role": "system", "content": "You are a helpful AI assistant. Respond with clear paragraphs separated by two newlines (\n\n). Use bullet points (starting with '-') for lists, one per line."}
        ]

        # Add the condensed chat history
        for msg in context:
            messages.append(msg)

        # Add the user input as the last message
        messages.append({"role": "user", "content": user_input})

        try:
            client = OpenAI(api_key=self.openai_api_key)
            full_response = ""
            assistant_message_id = self.add_message("Assistant", "", True)

            for chunk in client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                temperature=0.7 if speed == "normal" else (0.9 if speed == "fast" else 0.5),
            ):
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    self.update_message(assistant_message_id, full_response)
                    self.scroll_to_bottom()

            self.chat_history.append({"role": "assistant", "content": full_response})
        except Exception as e:
            error_message = f"Error: {str(e)}"
            self.add_message("System", error_message)
            self.chat_history.append({"role": "system", "content": error_message})
        finally:
            self.is_running = False
            self.user_input_entry.config(state="normal")
            self.user_input_entry.focus()

    def build_context(self):
        """Build the context for the API call."""
        context = []
        if self.chat_mode.get() == "voyeur":
            # In voyeur mode, don't include previous messages
            return context

        total_length = 0
        max_length = 12000 if self.model_var.get() == "gpt-4o" else 8000

        # Add messages in reverse order until we hit the token limit
        for msg in reversed(self.chat_history[-10:]):  # Limit to last 10 messages
            content_length = len(msg["content"])
            if total_length + content_length > max_length:
                break
            total_length += content_length
            context.insert(0, msg)

        return context

if __name__ == "__main__":
    root = tk.Tk()
    app = VoyeurChatApp(root)
    root.mainloop()
