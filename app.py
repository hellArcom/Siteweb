from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from flask_socketio import SocketIO, send, emit
import os
import sqlite3
import base64
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'code'
app.config['UPLOAD_FOLDER'] = 'uploads'
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialisation du cache
cache = {
    'messages': {
        'data': None,
        'timestamp': 1
    }
}
CACHE_EXPIRATION = 30  # Expiration du cache en secondes

# Initialisation de la base de données
def init_db():
    conn = sqlite3.connect('chat.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def get_messages():
    current_time = time.time()
    if cache['messages']['data'] is not None and (current_time - cache['messages']['timestamp']) < CACHE_EXPIRATION:
        return cache['messages']['data']

    try:
        conn = sqlite3.connect('chat.db')
        c = conn.cursor()
        c.execute('SELECT username, message, created_at FROM messages')
        messages = c.fetchall()
        cache['messages']['data'] = messages
        cache['messages']['timestamp'] = current_time
    except sqlite3.Error as e:
        print(f"Erreur SQLite: {e}")
        return []
    finally:
        conn.close()
    return messages

def add_message(username, message):
    try:
        conn = sqlite3.connect('chat.db')
        c = conn.cursor()
        c.execute('INSERT INTO messages (username, message) VALUES (?, ?)', (username, message))
        conn.commit()
        # Invalider le cache des messages
        cache['messages']['data'] = None
    except sqlite3.Error as e:
        print(f"Erreur SQLite: {e}")
    finally:
        conn.close()

# Initialisation de la base de données
init_db()

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/chat')
def chat():
    username = request.args.get('username')
    if username:
        messages = get_messages()
        return render_template('index.html', username=username, messages=messages)
    return redirect(url_for('login'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@socketio.on('message')
def handle_message(message):
    print('Message reçu : ' + message)
    username, message_text = message.split(': ', 1)
    send(f"<span class='username'>{username}:</span><span class='message-content'>{message_text}</span>", broadcast=True)
    add_message(username, message_text)


@socketio.on('file')
def handle_file(data):
    file_name = data['fileName']
    file_data = base64.b64decode(data['fileData'])
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)

    try:
        with open(file_path, 'wb') as file:
            file.write(file_data)

        file_url = url_for('uploaded_file', filename=file_name)
        emit('file', {
            'username': data['username'],
            'fileName': file_name,
            'filePath': file_url
        }, broadcast=True)
        add_message(data['username'], file_url)  # Enregistrer l'URL du fichier dans la base de données
    except Exception as e:
        print(f"Erreur lors de l'upload du fichier : {e}")

if __name__ == '__main__':
    socketio.run(app, debug=True)
