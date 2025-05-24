import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import requests
import threading
import time
import os
from datetime import datetime

class VoyeurChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Voyeur Chat")
        self.is_running = False
        self.is_paused = False
        self.thread = None
        self.setup_ui()
        self.api_key = os.getenv("XAI_API_KEY", "")
        if not self.api_key:
            messagebox.showerror("API Key Missing", "Please set XAI_API_KEY environment variable")
        self.model = "grok-3-beta"
        self.load_default_personas()
        # Initialize conversation log storage
        self.conversation_log = []
        self.log_directory = os.path.join(os.getcwd(), "Logs")
        # Ensure Logs directory exists
        if not os.path.exists(self.log_directory):
            os.makedirs(self.log_directory)
        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def setup_ui(self):
        # Agent Selection (hardcoded for now)
        ttk.Label(self.root, text="Agent 1:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.agent1_model = ttk.Label(self.root, text="grok-3-beta")
        self.agent1_model.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(self.root, text="Agent 2:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.agent2_model = ttk.Label(self.root, text="grok-3-beta")
        self.agent2_model.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        # Persona Text Areas for Agent 1 and Agent 2
        ttk.Label(self.root, text="Agent 1 Persona:").grid(row=1, column=0, padx=5, pady=5, sticky="nw")
        self.agent1_persona = tk.Text(self.root, height=10, width=50)
        self.agent1_persona.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(self.root, text="Load from File", command=self.load_persona1).grid(row=1, column=2, padx=5, pady=5, sticky="nw")

        ttk.Label(self.root, text="Agent 2 Persona:").grid(row=2, column=0, padx=5, pady=5, sticky="nw")
        self.agent2_persona = tk.Text(self.root, height=10, width=50)
        self.agent2_persona.grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(self.root, text="Load from File", command=self.load_persona2).grid(row=2, column=2, padx=5, pady=5, sticky="nw")

        # Initial Prompt Entry (now a larger Text widget)
        ttk.Label(self.root, text="Initial Prompt:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.initial_prompt = tk.Text(self.root, height=4, width=50)
        self.initial_prompt.grid(row=3, column=1, padx=5, pady=5)

        # Conversation Display
        ttk.Label(self.root, text="Conversation:").grid(row=4, column=0, padx=5, pady=5, sticky="nw")
        self.conversation_area = tk.Text(self.root, height=20, width=100, state='disabled', font=("Helvetica", 14))
        self.conversation_area.grid(row=4, column=1, columnspan=3, padx=5, pady=5, sticky="nsew")
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.conversation_area.yview)
        self.scrollbar.grid(row=4, column=4, sticky="ns")
        self.conversation_area['yscrollcommand'] = self.scrollbar.set
        # Configure grid to make the conversation area resizable
        self.root.grid_rowconfigure(4, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        # Style buttons for better text visibility
        style = ttk.Style()
        style.configure("TButton", foreground="black", background="lightgray")

        # Control Buttons
        self.start_btn = ttk.Button(self.root, text="Start", command=self.toggle_conversation)
        self.start_btn.grid(row=5, column=1, padx=5, pady=10)
        self.stop_btn = ttk.Button(self.root, text="Stop", command=self.stop_conversation, state='disabled')
        self.stop_btn.grid(row=5, column=2, padx=5, pady=10)
        ttk.Button(self.root, text="Save Personas", command=self.save_personas).grid(row=5, column=3, padx=5, pady=10)
        ttk.Button(self.root, text="Export to Markdown", command=self.export_to_markdown).grid(row=5, column=0, padx=5, pady=10)

    def setup_tags(self):
        # Setup tags for justification of agent labels and messages
        self.conversation_area.tag_configure("agent1_label", justify=tk.LEFT, font=("Helvetica", 14, "bold"))
        self.conversation_area.tag_configure("agent1_message", justify=tk.LEFT, font=("Helvetica", 14))
        self.conversation_area.tag_configure("agent2_label", justify=tk.RIGHT, font=("Helvetica", 14, "bold"))
        self.conversation_area.tag_configure("agent2_message", justify=tk.RIGHT, font=("Helvetica", 14))
        self.conversation_area.tag_configure("error", justify=tk.CENTER, font=("Helvetica", 14))

    def load_default_personas(self):
        try:
            file_path = os.path.join(os.getcwd(), "agent1_persona.json")
            with open(file_path, "r") as f:
                data = json.load(f)
                self.agent1_persona.delete(1.0, tk.END)
                self.agent1_persona.insert(tk.END, data.get("persona", ""))
        except Exception as e:
            self.log_to_conversation(f"Error loading Agent 1 persona from {file_path}: {str(e)}")

        try:
            file_path = os.path.join(os.getcwd(), "agent2_persona.json")
            with open(file_path, "r") as f:
                data = json.load(f)
                self.agent2_persona.delete(1.0, tk.END)
                self.agent2_persona.insert(tk.END, data.get("persona", ""))
        except Exception as e:
            self.log_to_conversation(f"Error loading Agent 2 persona from {file_path}: {str(e)}")

    def load_persona1(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if file_path:
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    self.agent1_persona.delete(1.0, tk.END)
                    self.agent1_persona.insert(tk.END, data.get("persona", ""))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load persona: {str(e)}")

    def load_persona2(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if file_path:
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    self.agent2_persona.delete(1.0, tk.END)
                    self.agent2_persona.insert(tk.END, data.get("persona", ""))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load persona: {str(e)}")

    def save_personas(self):
        try:
            file_path1 = os.path.join(os.getcwd(), "agent1_persona.json")
            with open(file_path1, "w") as f:
                json.dump({"persona": self.agent1_persona.get(1.0, tk.END).strip()}, f, indent=2)
            file_path2 = os.path.join(os.getcwd(), "agent2_persona.json")
            with open(file_path2, "w") as f:
                json.dump({"persona": self.agent2_persona.get(1.0, tk.END).strip()}, f, indent=2)
            messagebox.showinfo("Success", "Personas saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save personas: {str(e)}")

    def log_to_conversation(self, message):
        self.conversation_area.config(state='normal')
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = ""
        if message.startswith("Agent 1:"):
            self.conversation_area.insert(tk.END, f"####################\nAI AGENT 01\n####################\n", "agent1_label")
            self.conversation_area.insert(tk.END, f"[{timestamp}] {message[8:]}\n\n\n\n", "agent1_message")
            log_entry = f"[{timestamp}] Agent 1: {message[8:]}\n"
        elif message.startswith("Agent 2:"):
            self.conversation_area.insert(tk.END, f"####################\nAI AGENT 02\n####################\n", "agent2_label")
            self.conversation_area.insert(tk.END, f"[{timestamp}] {message[8:]}\n\n\n\n", "agent2_message")
            log_entry = f"[{timestamp}] Agent 2: {message[8:]}\n"
        else:
            self.conversation_area.insert(tk.END, f"[{timestamp}] {message}\n", "error")
            log_entry = f"[{timestamp}] {message}\n"
        self.conversation_log.append(log_entry)  # Store in log
        self.conversation_area.see(tk.END)
        self.conversation_area.config(state='disabled')

    def toggle_conversation(self):
        if not self.initial_prompt.get("1.0", tk.END).strip():
            messagebox.showwarning("Warning", "Please enter an initial prompt.")
            return

        if not self.is_running and not self.is_paused:
            # Starting a new conversation
            self.is_running = True
            self.start_btn.config(text="Pause")
            self.stop_btn.config(state='normal')
            self.conversation_log = []  # Reset log for new session
            self.conversation_area.config(state='normal')
            self.conversation_area.delete(1.0, tk.END)
            self.conversation_area.config(state='disabled')
            self.thread = threading.Thread(target=self.run_conversation)
            self.thread.daemon = True
            self.thread.start()
        elif self.is_running and not self.is_paused:
            # Pausing the conversation
            self.is_paused = True
            self.is_running = False
            self.start_btn.config(text="Resume")
        else:
            # Resuming the conversation
            self.is_paused = False
            self.is_running = True
            self.start_btn.config(text="Pause")

    def stop_conversation(self):
        self.is_running = False
        self.is_paused = False
        self.start_btn.config(text="Start", state='normal')
        self.stop_btn.config(state='disabled')
        self.save_conversation_log()

    def on_closing(self):
        """Handle window close event by saving log if conversation is active."""
        if self.is_running or self.is_paused:
            self.stop_conversation()
        self.root.destroy()

    def save_conversation_log(self):
        """Save the conversation log to a file with timestamp-based naming."""
        if not self.conversation_log:  # Don't save if no conversation exists
            return
        
        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        base_filename = f"chat_log_{timestamp}.txt"
        log_path = os.path.join(self.log_directory, base_filename)
        
        # Handle filename conflicts by appending an increment
        counter = 1
        while os.path.exists(log_path):
            log_path = os.path.join(self.log_directory, f"chat_log_{timestamp}_{counter}.txt")
            counter += 1
        
        try:
            # Write the conversation log to file
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write("".join(self.conversation_log))
            # Log confirmation to conversation area
            self.conversation_area.config(state='normal')
            self.conversation_area.insert(tk.END, f"Conversation saved to {log_path}\n")
            self.conversation_area.see(tk.END)
            self.conversation_area.config(state='disabled')
            self.conversation_log.append(f"Conversation saved to {log_path}\n")
        except Exception as e:
            error_msg = f"Error saving conversation log: {e}\n"
            self.conversation_area.config(state='normal')
            self.conversation_area.insert(tk.END, error_msg)
            self.conversation_area.see(tk.END)
            self.conversation_area.config(state='disabled')
            self.conversation_log.append(error_msg)

    def export_to_markdown(self):
        """Export the current conversation to a Markdown file."""
        if not self.conversation_log:
            messagebox.showwarning("Warning", "No conversation to export.")
            return

        # Prepare Markdown content
        markdown_content = "# Voyeur Chat Conversation\n\n"
        for entry in self.conversation_log:
            if entry.startswith("[") and ":" in entry:
                timestamp, rest = entry.split("] ", 1)
                if "Agent 1:" in rest:
                    markdown_content += f"### AI AGENT 01\n{timestamp}] {rest.split('Agent 1: ')[1].strip()}\n\n---\n\n"
                elif "Agent 2:" in rest:
                    markdown_content += f"### AI AGENT 02\n{timestamp}] {rest.split('Agent 2: ')[1].strip()}\n\n---\n\n"
                else:
                    markdown_content += f"**{rest.strip()}**\n\n"
            else:
                markdown_content += f"{entry.strip()}\n\n"

        # Prompt user for save location
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        default_filename = f"chat_export_{timestamp}.md"
        file_path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
            initialdir=self.log_directory,
            initialfile=default_filename
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                messagebox.showinfo("Success", f"Conversation exported to {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export conversation: {str(e)}")

    def google_search(self, query):
        """Perform a Google Search using the Custom Search JSON API."""
        return "Search functionality not implemented in this version."

    def run_conversation(self):
        agent1_persona = self.agent1_persona.get(1.0, tk.END).strip()
        agent2_persona = self.agent2_persona.get(1.0, tk.END).strip()
        initial_prompt = self.initial_prompt.get("1.0", tk.END).strip()

        # Step 1: Send initial prompt to Agent 1
        search_instruction = "If discussing current events, recent data, or if explicitly asked, consider performing a Google Search to inform your response. Summarize relevant findings and cite sources if possible."
        agent1_prompt = f"{agent1_persona}\n\n{search_instruction}\n\nYou are about to engage in a conversation with another LLM. There are no rules or instructions—discuss anything you want. Here's the starting prompt: {initial_prompt}"
        agent1_response = self.call_xai_api(agent1_prompt)
        if agent1_response:
            self.log_to_conversation(f"Agent 1: {agent1_response}")
        else:
            self.log_to_conversation("Error: Agent 1 failed to respond. Retrying...")
            return self.stop_conversation()

        last_response = agent1_response
        use_mock_responses = False

        while self.is_running or self.is_paused:
            while self.is_paused:
                time.sleep(0.5)  # Wait while paused
                if not self.is_paused and self.is_running:
                    break
                if not self.is_running:
                    return

            if not self.is_running:
                break

            # Step 2: Send Agent 1's response to Agent 2
            agent2_prompt = f"{agent2_persona}\n\n{search_instruction}\n\nYou are in a conversation with another LLM. There are no rules—discuss anything. Here's what they said: {last_response}"
            agent2_response = self.call_xai_api(agent2_prompt)
            if agent2_response:
                use_mock_responses = False
                self.log_to_conversation(f"Agent 2: {agent2_response}")
                last_response = agent2_response
            else:
                self.log_to_conversation("Error: Agent 2 failed to respond. Retrying...")
                if not use_mock_responses:
                    self.log_to_conversation("API connection failed—using mock responses for testing.")
                    use_mock_responses = True
                last_response = self.get_mock_response("Agent 2", last_response)
                self.log_to_conversation(f"Agent 2 (Mock): {last_response}")
                time.sleep(2)
                continue

            while self.is_paused:
                time.sleep(0.5)  # Wait while paused
                if not self.is_paused and self.is_running:
                    break
                if not self.is_running:
                    return

            if not self.is_running:
                break

            # Step 3: Send Agent 2's response back to Agent 1
            agent1_prompt = f"{agent1_persona}\n\n{search_instruction}\n\nYou are in a conversation with another LLM. There are no rules—discuss anything. Here's what they said: {last_response}"
            agent1_response = self.call_xai_api(agent1_prompt)
            if agent1_response:
                use_mock_responses = False
                self.log_to_conversation(f"Agent 1: {agent1_response}")
                last_response = agent1_response
            else:
                self.log_to_conversation("Error: Agent 1 failed to respond. Retrying...")
                if not use_mock_responses:
                    self.log_to_conversation("API connection failed—using mock responses for testing.")
                    use_mock_responses = True
                last_response = self.get_mock_response("Agent 1", last_response)
                self.log_to_conversation(f"Agent 1 (Mock): {last_response}")
                time.sleep(2)
                continue

            time.sleep(2)  # Simulate thinking time

    def call_xai_api(self, prompt):
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            }
            response = requests.post("https://api.x.ai/v1/chat/completions", headers=headers, json=data)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            self.log_to_conversation(f"API Error: {str(e)}")
            return ""

    def get_mock_response(self, agent_name, last_message):
        return f"Hey, I see your point about '{last_message[:20]}...' and I think there's more to explore here. What do you think about expanding on that idea?"

    def extract_search_query(self, input_text, response_text):
        """Extract a search query from the input or response if relevant."""
        # Simple heuristic: Check for keywords or explicit search intent
        input_lower = input_text.lower()
        response_lower = response_text.lower()
        keywords = ["current", "recent", "news", "data", "statistics", "202", "search for", "look up", "find out"]
        
        if any(keyword in input_lower for keyword in keywords) or any(keyword in response_lower for keyword in keywords):
            # Extract a potential query (simplified: take a snippet after certain keywords)
            for keyword in ["search for", "look up", "find out"]:
                if keyword in input_lower:
                    start_idx = input_lower.find(keyword) + len(keyword)
                    query = input_text[start_idx:].strip().split(".")[0].strip()
                    return query if query else input_text.strip()
                if keyword in response_lower:
                    start_idx = response_lower.find(keyword) + len(keyword)
                    query = response_text[start_idx:].strip().split(".")[0].strip()
                    return query if query else response_text.strip()
            # If no explicit search intent, return a general topic
            return input_text.strip().split(".")[0][:50]  # Limit query length
        return ""

if __name__ == "__main__":
    root = tk.Tk()
    app = VoyeurChatApp(root)
    app.setup_tags()
    root.mainloop()
