import sqlite3
from datetime import datetime

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('telegram_users.db')
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                join_date TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_id INTEGER PRIMARY KEY,
                session_string TEXT,
                channel_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        self.conn.commit()

    def add_user(self, user_id, username, first_name, last_name):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, join_date)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, datetime.now()))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error adding user: {e}")
            return False

    def save_session(self, user_id, session_string, channel_id=None):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO user_sessions (user_id, session_string, channel_id)
                VALUES (?, ?, ?)
            ''', (user_id, session_string, channel_id))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error saving session: {e}")
            return False

    def get_session(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT session_string, channel_id FROM user_sessions WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        if result:
            return {'session_string': result[0], 'channel_id': result[1]}
        return None

    def update_channel_id(self, user_id, channel_id):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                UPDATE user_sessions SET channel_id = ? WHERE user_id = ?
            ''', (channel_id, user_id))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error updating channel ID: {e}")
            return False

    def get_all_users(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users')
        return cursor.fetchall()

    def get_total_users(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        return cursor.fetchone()[0]

    def get_all_user_ids(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        return [row[0] for row in cursor.fetchall()]

    def close(self):
        self.conn.close() 
