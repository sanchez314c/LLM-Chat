import os
import aiosqlite
import sqlite3

# Define the database directory and path
DB_DIR = os.path.expanduser("~/.lightllm_chat")
DB_PATH = os.path.join(DB_DIR, "voyeur_chat.db")

async def init_database():
    """Initialize the SQLite database and create necessary tables."""
    os.makedirs(DB_DIR, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                llm_model TEXT,
                system_prompt TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tokens INTEGER,
                cost REAL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS drafts (
                conversation_id INTEGER PRIMARY KEY,
                content TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)
        await db.commit()

async def create_conversation_in_db(title, model, system_prompt):
    """Create a new conversation in the database and return its ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO conversations (title, llm_model, system_prompt) VALUES (?, ?, ?)",
            (title, model, system_prompt)
        )
        await db.commit()
        return cursor.lastrowid

async def add_message_to_db(conversation_id, role, content, tokens=None, cost=None):
    """Add a message to a conversation in the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (conversation_id, role, content, tokens, cost) VALUES (?, ?, ?, ?, ?)",
            (conversation_id, role, content, tokens, cost)
        )
        await db.commit()

async def fetch_conversations_from_db():
    """Fetch all conversations from the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM conversations ORDER BY created_at DESC")
        return await cursor.fetchall()

async def fetch_messages_from_db(conversation_id):
    """Fetch all messages for a given conversation from the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC",
            (conversation_id,)
        )
        return await cursor.fetchall()

async def update_conversation_title_in_db(conversation_id, new_title):
    """Update the title of a conversation in the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE conversations SET title = ? WHERE id = ?",
            (new_title, conversation_id)
        )
        await db.commit()

async def delete_conversation_in_db(conversation_id):
    """Delete a conversation and its messages from the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        await db.commit()

async def save_draft(conversation_id, content):
    """Save a draft message for a conversation."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO drafts (conversation_id, content) VALUES (?, ?)",
            (conversation_id, content)
        )
        await db.commit()

async def load_draft(conversation_id):
    """Load a draft message for a conversation."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT content FROM drafts WHERE conversation_id = ?",
            (conversation_id,)
        )
        result = await cursor.fetchone()
        return result[0] if result else None