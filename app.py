"""
ReadyNest Messenger - Fake/Demo Chat App
Runs standalone: Flask + Flask-SocketIO + SQLite (no MongoDB/Node needed).
Built to run inside Google Colab via ngrok tunnel.

Seeds realistic fake users + 30 days of message history on first run,
so the SQLite file (readynest.db) is immediately ready for the
data analytics part (query it with pandas / SQL).
"""
import os
import random
from datetime import datetime, timedelta

from flask import Flask, request, session, redirect, url_for, render_template_string, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, join_room, emit

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'readynest-fake-demo-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'readynest.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ---------------------------------------------------------------- MODELS ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)  # plain text: fake demo only
    is_blocked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    chat_id = db.Column(db.String(80), nullable=False)  # e.g. "dm-1-2" or "group-design"
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User')


# Fixed rooms for this fake demo: a few 1-1 DMs + a couple of group chats
CHAT_ROOMS = ['dm-general', 'group-design', 'group-project']
SAMPLE_LINES = [
    "Hey! How are you?", "I'm good, working on the messenger project.",
    "Great! Don't forget to add file sharing feature.", "Sure, I'll complete it today.",
    "Can you review my PR?", "Sounds good, checking now.", "Meeting at 5?",
    "Yep, see you then.", "Thanks for the update!", "No problem 👍",
    "Let's connect later.", "Okay, sounds good.",
]
NAMES = [
    'John Doe', 'Sneha Verma', 'Rahul Sharma', 'Pooja Iyer', 'Aman Singh',
    'Mehak Gupta', 'Rohit Malhotra', 'Ananya Rao', 'Karan Mehta', 'Divya Nair',
]


def seed_if_empty():
    if User.query.first():
        return
    users = []
    for n in NAMES:
        u = User(
            name=n,
            email=f"{n.lower().replace(' ', '.')}@readynest.in",
            password="password123",
        )
        db.session.add(u)
        users.append(u)
    db.session.commit()

    # 30 days of fake message history, upward trend + weekend dip,
    # same shape the analytics module expects (sender + createdAt).
    for day_offset in range(29, -1, -1):
        day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=day_offset)
        is_weekend = day.weekday() >= 5
        base = 15 + (29 - day_offset) * 1.2
        count = max(3, int(base * (0.6 if is_weekend else 1) + random.randint(-5, 5)))
        for _ in range(count):
            sender = random.choice(users)
            sent_at = day + timedelta(hours=random.randint(7, 22), minutes=random.randint(0, 59))
            msg = Message(
                sender_id=sender.id,
                chat_id=random.choice(CHAT_ROOMS),
                content=random.choice(SAMPLE_LINES),
                created_at=sent_at,
            )
            db.session.add(msg)
    db.session.commit()
    print(f"Seeded {len(users)} users and {Message.query.count()} messages.")


# ----------------------------------------------------------------- AUTH ---

LOGIN_HTML = """
<!doctype html><html><head><title>ReadyNest Messenger - Login</title>
<style>
body{font-family:system-ui;background:#0d1b2e;color:#fff;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
.card{background:#13253d;padding:32px;border-radius:12px;width:320px}
h2{margin-top:0;color:#1fae86}
input{width:100%;padding:10px;margin:6px 0;border-radius:6px;border:1px solid #ffffff30;background:#0d1b2e;color:#fff;box-sizing:border-box}
button{width:100%;padding:10px;margin-top:10px;border:none;border-radius:6px;background:#1fae86;color:#fff;font-weight:600;cursor:pointer}
a{color:#1fae86}
.err{color:#ff8080;font-size:13px}
</style></head><body>
<div class="card">
<h2>ReadyNest Messenger</h2>
<p style="color:#ffffff80;font-size:13px">Demo login — pick any seeded user, password is <code>password123</code></p>
{% if error %}<p class="err">{{ error }}</p>{% endif %}
<form method="POST">
<input name="email" placeholder="Email (e.g. john.doe@readynest.in)" required>
<input name="password" type="password" placeholder="Password" required>
<button type="submit">Log in</button>
</form>
<p style="font-size:12px;color:#ffffff60">Seeded users: {{ users }}</p>
</div></body></html>
"""

CHAT_HTML = """
<!doctype html><html><head><title>ReadyNest Messenger</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.min.js"></script>
<style>
body{font-family:system-ui;margin:0;background:#0d1b2e;color:#fff;display:flex;height:100vh}
.sidebar{width:220px;background:#13253d;padding:16px;box-sizing:border-box}
.sidebar h3{color:#1fae86;font-size:13px;text-transform:uppercase}
.room{padding:8px;border-radius:6px;cursor:pointer;margin-bottom:4px}
.room:hover,.room.active{background:#1fae8630}
.main{flex:1;display:flex;flex-direction:column}
.header{padding:14px 20px;background:#13253d;display:flex;justify-content:space-between;align-items:center}
.messages{flex:1;padding:20px;overflow-y:auto;display:flex;flex-direction:column;gap:10px}
.msg{max-width:60%;padding:8px 12px;border-radius:10px;background:#13253d}
.msg.mine{align-self:flex-end;background:#1fae86;color:#0d1b2e}
.msg .who{font-size:11px;opacity:.7;margin-bottom:2px}
.inputbar{display:flex;padding:14px;background:#13253d;gap:8px}
.inputbar input{flex:1;padding:10px;border-radius:6px;border:none;background:#0d1b2e;color:#fff}
.inputbar button{padding:10px 16px;border:none;border-radius:6px;background:#1fae86;color:#0d1b2e;font-weight:600;cursor:pointer}
.logout{font-size:12px;color:#ffffff80}
</style></head><body>
<div class="sidebar">
  <h3>Chats</h3>
  {% for room in rooms %}
  <div class="room" data-room="{{ room }}" onclick="switchRoom('{{ room }}')">{{ room }}</div>
  {% endfor %}
</div>
<div class="main">
  <div class="header">
    <strong id="roomTitle">dm-general</strong>
    <span>{{ user.name }} &nbsp; <a class="logout" href="/logout">Logout</a></span>
  </div>
  <div class="messages" id="messages"></div>
  <div class="inputbar">
    <input id="msgInput" placeholder="Type a message..." onkeydown="if(event.key==='Enter')sendMsg()">
    <button onclick="sendMsg()">Send</button>
  </div>
</div>
<script>
const socket = io();
const myId = {{ user.id }};
let currentRoom = "dm-general";

function renderMsg(m) {
  const div = document.createElement('div');
  div.className = 'msg' + (m.sender_id === myId ? ' mine' : '');
  div.innerHTML = `<div class="who">${m.sender_name}</div>${m.content}`;
  document.getElementById('messages').appendChild(div);
  document.getElementById('messages').scrollTop = 1e9;
}

function loadHistory(room) {
  document.getElementById('messages').innerHTML = '';
  fetch('/api/history/' + room).then(r => r.json()).then(msgs => msgs.forEach(renderMsg));
}

function switchRoom(room) {
  socket.emit('leave', { room: currentRoom });
  currentRoom = room;
  document.getElementById('roomTitle').innerText = room;
  socket.emit('join', { room });
  loadHistory(room);
}

function sendMsg() {
  const input = document.getElementById('msgInput');
  if (!input.value.trim()) return;
  socket.emit('send_message', { room: currentRoom, content: input.value });
  input.value = '';
}

socket.on('connect', () => socket.emit('join', { room: currentRoom }));
socket.on('receive_message', (m) => { if (m.chat_id === currentRoom) renderMsg(m); });
loadHistory(currentRoom);
</script>
</body></html>
"""


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        user = User.query.filter_by(email=email, password=password).first()
        if not user:
            names = ', '.join(u.email for u in User.query.limit(5))
            return render_template_string(LOGIN_HTML, error='Invalid email or password.', users=names)
        session['user_id'] = user.id
        return redirect(url_for('chat'))
    names = ', '.join(u.email for u in User.query.limit(5))
    return render_template_string(LOGIN_HTML, error=None, users=names)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/chat')
def chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template_string(CHAT_HTML, user=user, rooms=CHAT_ROOMS)


@app.route('/api/history/<room>')
def history(room):
    msgs = (Message.query.filter_by(chat_id=room)
            .order_by(Message.created_at.asc()).limit(200).all())
    return jsonify([
        {
            'sender_id': m.sender_id,
            'sender_name': m.sender.name,
            'content': m.content,
            'created_at': m.created_at.isoformat(),
            'chat_id': m.chat_id,
        }
        for m in msgs
    ])


# -------------------------------------------------------------- SOCKETS ---

@socketio.on('join')
def on_join(data):
    join_room(data['room'])


@socketio.on('leave')
def on_leave(data):
    from flask_socketio import leave_room
    leave_room(data['room'])


@socketio.on('send_message')
def on_send_message(data):
    user = User.query.get(session.get('user_id'))
    if not user:
        return
    msg = Message(sender_id=user.id, chat_id=data['room'], content=data['content'])
    db.session.add(msg)
    db.session.commit()
    emit('receive_message', {
        'sender_id': user.id,
        'sender_name': user.name,
        'content': msg.content,
        'created_at': msg.created_at.isoformat(),
        'chat_id': msg.chat_id,
    }, room=data['room'])


with app.app_context():
    db.create_all()
    seed_if_empty()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
