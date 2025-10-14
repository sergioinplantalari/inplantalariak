#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import base64
import io
import zipfile
import secrets
import datetime as dt
from pathlib import Path
from functools import wraps

from flask import (
    Flask, request, redirect, url_for, render_template, session,
    send_from_directory, abort, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# --------------------------------------------------------------------------------------
# App setup
# --------------------------------------------------------------------------------------
APP_NAME = "Consulta Psicológica"
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
DRAWINGS_DIR = DATA_DIR / "drawings"
DB_PATH = DATA_DIR / "db.sqlite3"
SECRET_FILE = DATA_DIR / "secret_key.txt"

ALLOWED_EXTENSIONS = {
    "pdf", "png", "jpg", "jpeg", "gif", "txt", "doc", "docx", "xls", "xlsx", "csv"
}

app = Flask(__name__)


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    DRAWINGS_DIR.mkdir(parents=True, exist_ok=True)
    if not SECRET_FILE.exists():
        SECRET_FILE.write_text(secrets.token_hex(32), encoding="utf-8")


ensure_dirs()
app.secret_key = SECRET_FILE.read_text(encoding="utf-8").strip()

# --------------------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            dob TEXT,
            gender TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            tags TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            title TEXT,
            content_html TEXT,
            content_text TEXT,
            duration_minutes INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            content_type TEXT,
            size_bytes INTEGER,
            description TEXT,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS drawings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            title TEXT,
            file_path TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE
        )
        """
    )

    conn.commit()
    conn.close()


init_db()

# --------------------------------------------------------------------------------------
# Auth utilities
# --------------------------------------------------------------------------------------

def current_user():
    return session.get("user")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------

def now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat()


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# --------------------------------------------------------------------------------------
# Templates (single-file app uses inline templates)
# --------------------------------------------------------------------------------------

BASE_HTML = r"""
<!doctype html>
<html lang="es" data-theme="auto">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{{ title or 'Consulta Psicológica' }}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css" />
    <style>
      :root { --brand: #6f6cc1; }
      header nav { border-bottom: 1px solid #eee; margin-bottom: 1rem; }
      .brand { color: var(--brand) !important; font-weight: 600; }
      .pill { display: inline-block; padding: .2rem .5rem; background: #eef; color: #334; border-radius: 999px; margin-right: .25rem; }
      .tabs { display: flex; gap: .5rem; margin-top: 1rem; }
      .tabs a { padding: .4rem .8rem; border-radius: .5rem; border: 1px solid #e6e6e6; text-decoration: none; color: inherit; }
      .tabs a.active { background: var(--brand); color: white; border-color: var(--brand); }
      .muted { color: #666; }
      .grid { display: grid; gap: 1rem; }
      .grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .grid-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
      .card { border: 1px solid #eaeaea; border-radius: .6rem; padding: 1rem; }
      .right { text-align: right; }
      .nowrap { white-space: nowrap; }
      .toolbar { display:flex; gap:.5rem; align-items:center; flex-wrap: wrap; }
      img.thumb { max-width: 160px; height: auto; border: 1px solid #eee; border-radius: .4rem; }
      .quill { height: 280px; }
      canvas.whiteboard { border: 1px solid #ddd; border-radius: .5rem; touch-action: none; }
      .sticky { position: sticky; top: .75rem; }
      .danger { color: #b00020; }
      .success { color: #1a7f37; }
      @media (prefers-color-scheme: dark) {
        html[data-theme='auto'] { color-scheme: dark; }
      }
      .theme-toggle { cursor: pointer; }
    </style>
    {% block head %}{% endblock %}
  </head>
  <body>
    <header class="container">
      <nav>
        <ul>
          <li><strong class="brand">🧠 {{ app_name }}</strong></li>
        </ul>
        <ul>
          {% if user %}
          <li><a href="{{ url_for('patients') }}">Pacientes</a></li>
          <li><a href="{{ url_for('backup') }}">Copia de seguridad</a></li>
          <li class="muted">{{ user }}</li>
          <li><a href="{{ url_for('logout') }}">Salir</a></li>
          {% endif %}
          <li><a href="#" id="themeToggle" class="theme-toggle" onclick="toggleTheme();return false;" title="Cambiar tema">🌓</a></li>
        </ul>
      </nav>
    </header>

    <main class="container">
      {% block content %}{% endblock %}
    </main>

    <footer class="container muted" style="margin-top:3rem;">
      <small>© {{ year }} {{ app_name }} · Datos almacenados localmente</small>
    </footer>
  </body>
  <script>
    function toggleTheme() {
      const html = document.documentElement;
      const cur = html.getAttribute('data-theme') || 'auto';
      const next = cur === 'light' ? 'dark' : cur === 'dark' ? 'auto' : 'light';
      html.setAttribute('data-theme', next);
      try { localStorage.setItem('theme', next); } catch (e) {}
    }
    try {
      const saved = localStorage.getItem('theme');
      if (saved) document.documentElement.setAttribute('data-theme', saved);
    } catch (e) {}
  </script>
</html>
"""

LOGIN_HTML = r"""
{% extends 'base.html' %}
{% block content %}
  <article class="card" style="max-width: 520px; margin: 2rem auto;">
    <h2>Acceder</h2>
    <form method="post">
      <label>Usuario
        <input name="username" placeholder="admin" required />
      </label>
      <label>Contraseña
        <input type="password" name="password" required />
      </label>
      <button type="submit">Entrar</button>
    </form>
    <p class="muted">¿Primera vez? Cree su cuenta en <a href="{{ url_for('setup') }}">configuración inicial</a>.</p>
  </article>
{% endblock %}
"""

SETUP_HTML = r"""
{% extends 'base.html' %}
{% block content %}
  <article class="card" style="max-width: 560px; margin: 2rem auto;">
    <h2>Configuración inicial</h2>
    <p>Cree la contraseña de administrador para proteger sus datos.</p>
    <form method="post">
      <input type="hidden" name="create" value="1" />
      <label>Usuario
        <input name="username" value="admin" required />
      </label>
      <label>Contraseña
        <input type="password" name="password" required />
      </label>
      <button type="submit">Guardar</button>
    </form>
  </article>
{% endblock %}
"""

PATIENTS_HTML = r"""
{% extends 'base.html' %}
{% block content %}
  <h2>Pacientes</h2>
  <form method="get" class="toolbar" style="margin-bottom: 1rem;">
    <input name="q" placeholder="Buscar por nombre, email o etiquetas" value="{{ q or '' }}" />
    <button type="submit">Buscar</button>
    <a href="#" role="button" class="contrast" onclick="document.getElementById('newPatient').showModal();return false;">➕ Nuevo paciente</a>
  </form>

  <dialog id="newPatient">
    <article>
      <header><strong>Nuevo paciente</strong></header>
      <form method="post" action="{{ url_for('create_patient') }}">
        <label>Nombre completo<input name="full_name" required /></label>
        <div class="grid grid-2">
          <label>Fecha de nacimiento<input type="date" name="dob" /></label>
          <label>Género<select name="gender"><option value="">—</option><option>Femenino</option><option>Masculino</option><option>No binario</option><option>Otro</option></select></label>
        </div>
        <div class="grid grid-2">
          <label>Teléfono<input name="phone" /></label>
          <label>Email<input type="email" name="email" /></label>
        </div>
        <label>Dirección<textarea name="address" rows="2"></textarea></label>
        <label>Etiquetas (separadas por comas)<input name="tags" placeholder="ansiedad, TCC" /></label>
        <label>Notas iniciales<textarea name="notes" rows="3"></textarea></label>
        <footer>
          <button type="submit">Crear</button>
          <button type="button" class="secondary" onclick="document.getElementById('newPatient').close()">Cancelar</button>
        </footer>
      </form>
    </article>
  </dialog>

  {% if patients %}
    <div class="grid grid-3">
      {% for p in patients %}
        <a class="card" href="{{ url_for('patient_detail', patient_id=p['id']) }}" style="text-decoration:none; color:inherit;">
          <header style="display:flex; justify-content:space-between; align-items:center;">
            <strong>{{ p['full_name'] }}</strong>
            {% if p['tags'] %}
              <span class="pill">{{ p['tags'] }}</span>
            {% endif %}
          </header>
          <small class="muted">{{ p['email'] or '' }} {{ p['phone'] and '· ' ~ p['phone'] or '' }}</small>
          <small class="muted">Creado {{ p['created_at'][:10] }}</small>
        </a>
      {% endfor %}
    </div>
  {% else %}
    <p class="muted">No hay pacientes aún.</p>
  {% endif %}
{% endblock %}
"""

PATIENT_DETAIL_HTML = r"""
{% extends 'base.html' %}
{% block head %}
  <link href="https://cdn.jsdelivr.net/npm/quill@1.3.7/dist/quill.snow.css" rel="stylesheet" />
  <style> .ql-toolbar, .ql-container { background:white; } </style>
{% endblock %}
{% block content %}
  <div class="toolbar" style="justify-content: space-between;">
    <div>
      <a href="{{ url_for('patients') }}">← Volver</a>
      <strong style="margin-left:.5rem;">{{ patient['full_name'] }}</strong>
      {% if patient['tags'] %}<span class="pill">{{ patient['tags'] }}</span>{% endif %}
    </div>
    <div class="toolbar">
      <a href="#" role="button" class="secondary" onclick="document.getElementById('editPatient').showModal();return false;">Editar</a>
      <form method="post" action="{{ url_for('delete_patient', patient_id=patient['id']) }}" onsubmit="return confirm('¿Eliminar paciente y todo su contenido?');">
        <button class="contrast" type="submit">Eliminar</button>
      </form>
      <a href="{{ url_for('export_patient', patient_id=patient['id']) }}" role="button">Exportar</a>
    </div>
  </div>

  <dialog id="editPatient">
    <article>
      <header><strong>Editar paciente</strong></header>
      <form method="post" action="{{ url_for('edit_patient', patient_id=patient['id']) }}">
        <label>Nombre completo<input name="full_name" value="{{ patient['full_name'] }}" required /></label>
        <div class="grid grid-2">
          <label>Fecha de nacimiento<input type="date" name="dob" value="{{ patient['dob'] }}"/></label>
          <label>Género<select name="gender"><option value="" {% if not patient['gender'] %}selected{% endif %}>—</option><option {% if patient['gender']=='Femenino' %}selected{% endif %}>Femenino</option><option {% if patient['gender']=='Masculino' %}selected{% endif %}>Masculino</option><option {% if patient['gender']=='No binario' %}selected{% endif %}>No binario</option><option {% if patient['gender']=='Otro' %}selected{% endif %}>Otro</option></select></label>
        </div>
        <div class="grid grid-2">
          <label>Teléfono<input name="phone" value="{{ patient['phone'] or '' }}"/></label>
          <label>Email<input type="email" name="email" value="{{ patient['email'] or '' }}"/></label>
        </div>
        <label>Dirección<textarea name="address" rows="2">{{ patient['address'] or '' }}</textarea></label>
        <label>Etiquetas<input name="tags" value="{{ patient['tags'] or '' }}"/></label>
        <label>Notas<textarea name="notes" rows="3">{{ patient['notes'] or '' }}</textarea></label>
        <footer>
          <button type="submit">Guardar</button>
          <button type="button" class="secondary" onclick="document.getElementById('editPatient').close()">Cancelar</button>
        </footer>
      </form>
    </article>
  </dialog>

  <div class="tabs">
    <a href="#datos" class="active" onclick="showTab(event,'tab-datos')">Datos</a>
    <a href="#sesiones" onclick="showTab(event,'tab-sesiones')">Sesiones</a>
    <a href="#documentos" onclick="showTab(event,'tab-documentos')">Documentos</a>
    <a href="#pizarra" onclick="showTab(event,'tab-pizarra')">Pizarra</a>
  </div>

  <section id="tab-datos" style="margin-top:1rem;">
    <article class="card">
      <div class="grid grid-2">
        <div>
          <strong>Contacto</strong>
          <p class="muted">Email: {{ patient['email'] or '—' }}<br>Tel: {{ patient['phone'] or '—' }}</p>
          <strong>Dirección</strong>
          <p class="muted">{{ patient['address'] or '—' }}</p>
        </div>
        <div>
          <strong>Notas</strong>
          <p class="muted">{{ patient['notes'] or '—' }}</p>
        </div>
      </div>
    </article>
  </section>

  <section id="tab-sesiones" style="display:none; margin-top:1rem;">
    <article class="card">
      <header style="display:flex; justify-content: space-between; align-items:center;">
        <strong>Nueva sesión</strong>
        <small class="muted" id="timer">00:00</small>
      </header>
      <form method="post" action="{{ url_for('create_session', patient_id=patient['id']) }}" onsubmit="submitSession(event)">
        <div class="grid grid-2">
          <label>Título<input name="title" placeholder="Sesión {{ now[:10] }}"/></label>
          <label>Fecha<input type="datetime-local" name="date" value="{{ now.replace('Z','') }}"/></label>
        </div>
        <div id="editor" class="quill"></div>
        <input type="hidden" name="content_html" id="content_html" />
        <input type="hidden" name="content_text" id="content_text" />
        <input type="hidden" name="duration_minutes" id="duration_minutes" value="0" />
        <div class="toolbar" style="margin-top:.5rem;">
          <button type="button" class="secondary" onclick="startStopTimer()" id="timerBtn">Iniciar temporizador</button>
          <button type="button" class="secondary" onclick="toggleDictation()">Dictado</button>
          <span id="dictationStatus" class="muted">Apagado</span>
          <span class="right" style="flex:1"></span>
          <button type="submit">Guardar sesión</button>
        </div>
      </form>
    </article>

    <div style="margin-top:1rem;">
      {% if sessions %}
        <h4>Historial</h4>
        <details open>
          <summary>Últimas sesiones</summary>
          <div class="grid">
            {% for s in sessions %}
            <article class="card">
              <header style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                  <strong>{{ s['title'] or 'Sesión' }}</strong>
                  <small class="muted">{{ s['date'].replace('T',' ')[:16] }}</small>
                </div>
                <form method="post" action="{{ url_for('delete_session', session_id=s['id'], patient_id=patient['id']) }}" onsubmit="return confirm('¿Eliminar esta sesión?');">
                  <button class="contrast" type="submit">Eliminar</button>
                </form>
              </header>
              <div class="muted">Duración: {{ s['duration_minutes'] or 0 }} min</div>
              <div style="border-top:1px dashed #eee; margin-top:.5rem; padding-top:.5rem;">
                {{ s['content_html']|safe }}
              </div>
            </article>
            {% endfor %}
          </div>
        </details>
      {% else %}
        <p class="muted">Sin sesiones aún.</p>
      {% endif %}
    </div>
  </section>

  <section id="tab-documentos" style="display:none; margin-top:1rem;">
    <article class="card">
      <form method="post" action="{{ url_for('upload_document', patient_id=patient['id']) }}" enctype="multipart/form-data" class="toolbar">
        <input type="file" name="file" required />
        <input name="description" placeholder="Descripción (opcional)" />
        <button type="submit">Subir</button>
      </form>
    </article>

    <div class="grid grid-3" style="margin-top:1rem;">
      {% for d in documents %}
        <article class="card">
          <header style="display:flex; justify-content:space-between; align-items:center;">
            <strong class="nowrap" title="{{ d['original_filename'] }}">{{ d['original_filename'] }}</strong>
            <small class="muted">{{ d['uploaded_at'][:16].replace('T',' ') }}</small>
          </header>
          {% if d['content_type'].startswith('image/') %}
            <img class="thumb" src="{{ url_for('serve_upload', patient_id=patient['id'], filename=d['filename']) }}" alt="{{ d['original_filename'] }}" />
          {% endif %}
          <p class="muted">{{ d['description'] or '' }}</p>
          <div class="toolbar">
            <a role="button" href="{{ url_for('serve_upload', patient_id=patient['id'], filename=d['filename']) }}">Descargar</a>
            <form method="post" action="{{ url_for('delete_document', doc_id=d['id'], patient_id=patient['id']) }}" onsubmit="return confirm('¿Eliminar documento?');">
              <button class="contrast" type="submit">Eliminar</button>
            </form>
          </div>
        </article>
      {% endfor %}
    </div>
  </section>

  <section id="tab-pizarra" style="display:none; margin-top:1rem;">
    <article class="card">
      <div class="grid grid-4">
        <label>Color<input type="color" id="penColor" value="#111111"/></label>
        <label>Grosor<input type="range" id="penWidth" min="1" max="20" value="3"/></label>
        <button type="button" class="secondary" onclick="clearCanvas()">Limpiar</button>
        <button type="button" onclick="saveDrawing()">Guardar dibujo</button>
      </div>
      <canvas id="whiteboard" class="whiteboard" width="1000" height="600"></canvas>
    </article>

    <div style="margin-top:1rem;">
      {% if drawings %}
        <h4>Guardados</h4>
        <div class="grid grid-4">
          {% for img in drawings %}
            <article class="card">
              <img class="thumb" src="{{ url_for('serve_drawing', patient_id=patient['id'], filename=img['file_path'].split('/')[-1]) }}" alt="Dibujo" />
              <small class="muted">{{ img['created_at'][:16].replace('T',' ') }}</small>
              <form method="post" action="{{ url_for('delete_drawing', drawing_id=img['id'], patient_id=patient['id']) }}" onsubmit="return confirm('¿Eliminar dibujo?');">
                <button class="contrast" type="submit">Eliminar</button>
              </form>
            </article>
          {% endfor %}
        </div>
      {% else %}
        <p class="muted">No hay dibujos aún.</p>
      {% endif %}
    </div>
  </section>

  <script src="https://cdn.jsdelivr.net/npm/quill@1.3.7/dist/quill.min.js"></script>
  <script>
    // Tabs
    function showTab(ev, id) {
      ev.preventDefault();
      for (const el of document.querySelectorAll('[id^=tab-]')) { el.style.display = 'none'; }
      document.getElementById(id).style.display = '';
      for (const a of document.querySelectorAll('.tabs a')) a.classList.remove('active');
      ev.target.classList.add('active');
    }

    // Quill
    const quill = new Quill('#editor', { theme: 'snow' });

    // Timer
    let timerRunning = false;
    let timerStart = null;
    let timerInterval = null;
    function startStopTimer() {
      const btn = document.getElementById('timerBtn');
      if (!timerRunning) {
        timerRunning = true; timerStart = Date.now();
        btn.textContent = 'Detener temporizador';
        timerInterval = setInterval(() => {
          const diff = Date.now() - timerStart;
          const mm = Math.floor(diff / 60000);
          const ss = Math.floor((diff % 60000) / 1000);
          document.getElementById('timer').textContent = String(mm).padStart(2,'0')+":"+String(ss).padStart(2,'0');
        }, 500);
      } else {
        timerRunning = false; clearInterval(timerInterval);
        btn.textContent = 'Iniciar temporizador';
      }
    }

    // Dictation (browser-dependent)
    let recognition = null;
    function toggleDictation() {
      const status = document.getElementById('dictationStatus');
      if (!('webkitSpeechRecognition' in window)) {
        alert('El dictado no está disponible en este navegador.');
        return;
      }
      if (!recognition) {
        const R = window.webkitSpeechRecognition;
        recognition = new R();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'es-ES';
        recognition.onresult = (event) => {
          let transcript = '';
          for (let i=event.resultIndex; i<event.results.length; i++) {
            const res = event.results[i];
            transcript += res[0].transcript;
          }
          const range = quill.getSelection(true);
          quill.insertText(range.index, transcript + ' ');
          quill.setSelection(range.index + transcript.length + 1);
        };
        recognition.onend = () => { status.textContent = 'Apagado'; };
      }
      if (status.textContent === 'Apagado') {
        recognition.start(); status.textContent = 'Escuchando…';
      } else {
        recognition.stop(); status.textContent = 'Apagado';
      }
    }

    function submitSession(ev) {
      const html = quill.root.innerHTML;
      const text = quill.getText();
      document.getElementById('content_html').value = html;
      document.getElementById('content_text').value = text;
      if (timerRunning) {
        const diff = Date.now() - timerStart;
        document.getElementById('duration_minutes').value = Math.round(diff / 60000);
      }
    }

    // Whiteboard
    const canvas = document.getElementById('whiteboard');
    const ctx = canvas.getContext('2d');
    let drawing = false;
    function getPos(e) {
      if (e.touches && e.touches.length) {
        const rect = canvas.getBoundingClientRect();
        return { x: e.touches[0].clientX - rect.left, y: e.touches[0].clientY - rect.top };
      }
      const rect = canvas.getBoundingClientRect();
      return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }
    function startDraw(e) { drawing = true; const p = getPos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y); e.preventDefault(); }
    function moveDraw(e) { if (!drawing) return; const p = getPos(e); ctx.lineTo(p.x, p.y); ctx.strokeStyle = document.getElementById('penColor').value; ctx.lineWidth = document.getElementById('penWidth').value; ctx.lineCap = 'round'; ctx.stroke(); e.preventDefault(); }
    function endDraw(e) { drawing = false; e.preventDefault(); }
    canvas.addEventListener('mousedown', startDraw); canvas.addEventListener('mousemove', moveDraw); canvas.addEventListener('mouseup', endDraw); canvas.addEventListener('mouseleave', endDraw);
    canvas.addEventListener('touchstart', startDraw, {passive:false}); canvas.addEventListener('touchmove', moveDraw, {passive:false}); canvas.addEventListener('touchend', endDraw);
    function clearCanvas() { ctx.clearRect(0,0,canvas.width,canvas.height); }
    async function saveDrawing() {
      const dataURL = canvas.toDataURL('image/png');
      const res = await fetch('{{ url_for('save_drawing', patient_id=patient['id']) }}', { method:'POST', headers: { 'Content-Type':'application/json' }, body: JSON.stringify({ data_url: dataURL }) });
      if (res.ok) location.reload(); else alert('Error al guardar');
    }
  </script>
{% endblock %}
"""

# --------------------------------------------------------------------------------------
# Template registration
# --------------------------------------------------------------------------------------
from jinja2 import DictLoader

app.jinja_loader = DictLoader({
    'base.html': BASE_HTML,
    'login.html': LOGIN_HTML,
    'setup.html': SETUP_HTML,
    'patients.html': PATIENTS_HTML,
    'patient_detail.html': PATIENT_DETAIL_HTML,
})

# --------------------------------------------------------------------------------------
# Routes: auth & setup
# --------------------------------------------------------------------------------------

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) as c FROM users')
    c = cur.fetchone()['c']
    if c > 0:
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form.get('username', 'admin').strip() or 'admin'
        password = request.form.get('password', '').strip()
        if not password:
            return render_template('setup.html', title='Configuración', app_name=APP_NAME, user=current_user(), year=dt.datetime.now().year)
        cur.execute(
            'INSERT INTO users(username, password_hash, created_at) VALUES(?,?,?)',
            (username, generate_password_hash(password), now_iso())
        )
        conn.commit()
        conn.close()
        return redirect(url_for('login'))

    return render_template('setup.html', title='Configuración', app_name=APP_NAME, user=current_user(), year=dt.datetime.now().year)


@app.route('/login', methods=['GET', 'POST'])
def login():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) as c FROM users')
    c = cur.fetchone()['c']
    if c == 0:
        return redirect(url_for('setup'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        cur.execute('SELECT * FROM users WHERE username=?', (username,))
        user = cur.fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session['user'] = username
            return redirect(request.args.get('next') or url_for('patients'))
        error = 'Credenciales inválidas'

    return render_template('login.html', title='Acceder', app_name=APP_NAME, user=current_user(), year=dt.datetime.now().year)


@app.route('/logout')
@login_required
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))


# --------------------------------------------------------------------------------------
# Routes: Patients
# --------------------------------------------------------------------------------------

@app.route('/')
@login_required
def index():
    return redirect(url_for('patients'))


@app.route('/patients')
@login_required
def patients():
    q = request.args.get('q', '').strip()
    conn = get_db()
    cur = conn.cursor()
    if q:
        like = f"%{q}%"
        cur.execute(
            'SELECT * FROM patients WHERE full_name LIKE ? OR email LIKE ? OR tags LIKE ? ORDER BY updated_at DESC',
            (like, like, like)
        )
    else:
        cur.execute('SELECT * FROM patients ORDER BY updated_at DESC')
    rows = cur.fetchall()
    conn.close()
    return render_template('patients.html', title='Pacientes', app_name=APP_NAME, user=current_user(), year=dt.datetime.now().year, patients=rows, q=q)


@app.route('/patients/new', methods=['POST'])
@login_required
def create_patient():
    f = request.form
    now = now_iso()
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO patients(full_name, dob, gender, phone, email, address, tags, notes, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
        (
            f.get('full_name').strip(), f.get('dob') or None, f.get('gender') or None, f.get('phone') or None,
            f.get('email') or None, f.get('address') or None, f.get('tags') or None, f.get('notes') or None,
            now, now
        )
    )
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    # Ensure patient upload/drawing dirs
    (UPLOADS_DIR / str(pid)).mkdir(parents=True, exist_ok=True)
    (DRAWINGS_DIR / str(pid)).mkdir(parents=True, exist_ok=True)
    return redirect(url_for('patient_detail', patient_id=pid))


@app.route('/patients/<int:patient_id>')
@login_required
def patient_detail(patient_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM patients WHERE id=?', (patient_id,))
    patient = cur.fetchone()
    if not patient:
        conn.close(); abort(404)
    cur.execute('SELECT * FROM sessions WHERE patient_id=? ORDER BY date DESC', (patient_id,))
    sessions = cur.fetchall()
    cur.execute('SELECT * FROM documents WHERE patient_id=? ORDER BY uploaded_at DESC', (patient_id,))
    documents = cur.fetchall()
    cur.execute('SELECT * FROM drawings WHERE patient_id=? ORDER BY created_at DESC', (patient_id,))
    drawings = cur.fetchall()
    conn.close()
    return render_template('patient_detail.html', title=patient['full_name'], app_name=APP_NAME, user=current_user(), year=dt.datetime.now().year, patient=patient, sessions=sessions, documents=documents, drawings=drawings, now=now_iso())


@app.route('/patients/<int:patient_id>/edit', methods=['POST'])
@login_required
def edit_patient(patient_id):
    f = request.form
    now = now_iso()
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        'UPDATE patients SET full_name=?, dob=?, gender=?, phone=?, email=?, address=?, tags=?, notes=?, updated_at=? WHERE id=?',
        (
            f.get('full_name').strip(), f.get('dob') or None, f.get('gender') or None, f.get('phone') or None,
            f.get('email') or None, f.get('address') or None, f.get('tags') or None, f.get('notes') or None,
            now, patient_id
        )
    )
    conn.commit(); conn.close()
    return redirect(url_for('patient_detail', patient_id=patient_id))


@app.route('/patients/<int:patient_id>/delete', methods=['POST'])
@login_required
def delete_patient(patient_id):
    # Delete files on disk
    up_dir = UPLOADS_DIR / str(patient_id)
    dr_dir = DRAWINGS_DIR / str(patient_id)
    if up_dir.exists():
        for p in up_dir.glob('*'):
            try: p.unlink()
            except Exception: pass
        try: up_dir.rmdir()
        except Exception: pass
    if dr_dir.exists():
        for p in dr_dir.glob('*'):
            try: p.unlink()
            except Exception: pass
        try: dr_dir.rmdir()
        except Exception: pass
    # Delete from DB
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM sessions WHERE patient_id=?', (patient_id,))
    cur.execute('DELETE FROM documents WHERE patient_id=?', (patient_id,))
    cur.execute('DELETE FROM drawings WHERE patient_id=?', (patient_id,))
    cur.execute('DELETE FROM patients WHERE id=?', (patient_id,))
    conn.commit(); conn.close()
    return redirect(url_for('patients'))


# --------------------------------------------------------------------------------------
# Routes: Sessions
# --------------------------------------------------------------------------------------

@app.route('/patients/<int:patient_id>/sessions/new', methods=['POST'])
@login_required
def create_session(patient_id):
    f = request.form
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT id FROM patients WHERE id=?', (patient_id,))
    if not cur.fetchone():
        conn.close(); abort(404)
    cur.execute(
        'INSERT INTO sessions(patient_id, date, title, content_html, content_text, duration_minutes, created_at) VALUES(?,?,?,?,?,?,?)',
        (
            patient_id,
            (f.get('date') or now_iso()),
            f.get('title') or None,
            f.get('content_html') or None,
            f.get('content_text') or None,
            int(f.get('duration_minutes') or 0),
            now_iso()
        )
    )
    conn.commit(); conn.close()
    return redirect(url_for('patient_detail', patient_id=patient_id))


@app.route('/patients/<int:patient_id>/sessions/<int:session_id>/delete', methods=['POST'])
@login_required
def delete_session(patient_id, session_id):
    conn = get_db(); cur = conn.cursor()
    cur.execute('DELETE FROM sessions WHERE id=? AND patient_id=?', (session_id, patient_id))
    conn.commit(); conn.close()
    return redirect(url_for('patient_detail', patient_id=patient_id))


# --------------------------------------------------------------------------------------
# Routes: Documents
# --------------------------------------------------------------------------------------

@app.route('/patients/<int:patient_id>/documents/upload', methods=['POST'])
@login_required
def upload_document(patient_id):
    if 'file' not in request.files:
        abort(400)
    file = request.files['file']
    if file.filename == '':
        abort(400)
    if not allowed_file(file.filename):
        abort(400)
    filename = secure_filename(file.filename)
    patient_dir = UPLOADS_DIR / str(patient_id)
    patient_dir.mkdir(parents=True, exist_ok=True)
    save_path = patient_dir / filename
    # Ensure unique filename
    base, ext = os.path.splitext(filename)
    i = 1
    while save_path.exists():
        filename = f"{base}_{i}{ext}"
        save_path = patient_dir / filename
        i += 1
    file.save(str(save_path))

    conn = get_db(); cur = conn.cursor()
    cur.execute('INSERT INTO documents(patient_id, filename, original_filename, content_type, size_bytes, description, uploaded_at) VALUES(?,?,?,?,?,?,?)',
                (patient_id, filename, file.filename, file.mimetype or '', save_path.stat().st_size, request.form.get('description'), now_iso()))
    conn.commit(); conn.close()
    return redirect(url_for('patient_detail', patient_id=patient_id))


@app.route('/patients/<int:patient_id>/documents/file/<path:filename>')
@login_required
def serve_upload(patient_id, filename):
    directory = UPLOADS_DIR / str(patient_id)
    return send_from_directory(directory, filename, as_attachment=False)


@app.route('/patients/<int:patient_id>/documents/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete_document(patient_id, doc_id):
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT filename FROM documents WHERE id=? AND patient_id=?', (doc_id, patient_id))
    row = cur.fetchone()
    if row:
        path = UPLOADS_DIR / str(patient_id) / row['filename']
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass
        cur.execute('DELETE FROM documents WHERE id=?', (doc_id,))
        conn.commit()
    conn.close()
    return redirect(url_for('patient_detail', patient_id=patient_id))


# --------------------------------------------------------------------------------------
# Routes: Drawings (Whiteboard)
# --------------------------------------------------------------------------------------

@app.route('/patients/<int:patient_id>/drawings/save', methods=['POST'])
@login_required
def save_drawing(patient_id):
    data = request.get_json(silent=True) or {}
    data_url = data.get('data_url')
    if not data_url or not data_url.startswith('data:image/png;base64,'):
        abort(400)
    b64 = data_url.split(',', 1)[1]
    raw = base64.b64decode(b64)
    patient_dir = DRAWINGS_DIR / str(patient_id)
    patient_dir.mkdir(parents=True, exist_ok=True)
    filename = f"drawing_{dt.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
    file_path = patient_dir / filename
    with open(file_path, 'wb') as f:
        f.write(raw)
    conn = get_db(); cur = conn.cursor()
    cur.execute('INSERT INTO drawings(patient_id, title, file_path, created_at) VALUES(?,?,?,?)',
                (patient_id, None, str(file_path), now_iso()))
    conn.commit(); conn.close()
    return jsonify({ 'ok': True })


@app.route('/patients/<int:patient_id>/drawings/file/<path:filename>')
@login_required
def serve_drawing(patient_id, filename):
    directory = DRAWINGS_DIR / str(patient_id)
    return send_from_directory(directory, filename, as_attachment=False)


@app.route('/patients/<int:patient_id>/drawings/<int:drawing_id>/delete', methods=['POST'])
@login_required
def delete_drawing(patient_id, drawing_id):
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT file_path FROM drawings WHERE id=? AND patient_id=?', (drawing_id, patient_id))
    row = cur.fetchone()
    if row:
        try:
            p = Path(row['file_path'])
            if p.exists():
                p.unlink()
        except Exception:
            pass
        cur.execute('DELETE FROM drawings WHERE id=?', (drawing_id,))
        conn.commit()
    conn.close()
    return redirect(url_for('patient_detail', patient_id=patient_id))


# --------------------------------------------------------------------------------------
# Routes: Backup & Export
# --------------------------------------------------------------------------------------

@app.route('/backup')
@login_required
def backup():
    # Provide a ZIP of DB and all files
    tmp_name = f"backup_{dt.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"
    tmp_path = DATA_DIR / tmp_name
    with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as z:
        if DB_PATH.exists():
            z.write(DB_PATH, arcname='db.sqlite3')
        for root, _, files in os.walk(UPLOADS_DIR):
            for fn in files:
                full = Path(root) / fn
                z.write(full, arcname=str(full.relative_to(DATA_DIR)))
        for root, _, files in os.walk(DRAWINGS_DIR):
            for fn in files:
                full = Path(root) / fn
                z.write(full, arcname=str(full.relative_to(DATA_DIR)))
    return send_from_directory(DATA_DIR, tmp_name, as_attachment=True)


@app.route('/patients/<int:patient_id>/export')
@login_required
def export_patient(patient_id):
    # Export a single patient's data and files as ZIP
    conn = get_db(); cur = conn.cursor()
    cur.execute('SELECT * FROM patients WHERE id=?', (patient_id,))
    patient = cur.fetchone()
    if not patient:
        conn.close(); abort(404)

    cur.execute('SELECT * FROM sessions WHERE patient_id=?', (patient_id,))
    sessions = cur.fetchall()
    cur.execute('SELECT * FROM documents WHERE patient_id=?', (patient_id,))
    documents = cur.fetchall()
    cur.execute('SELECT * FROM drawings WHERE patient_id=?', (patient_id,))
    drawings = cur.fetchall()
    conn.close()

    safe_name = secure_filename(patient['full_name']) or f"paciente_{patient_id}"
    tmp_name = f"export_{safe_name}_{dt.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"
    tmp_path = DATA_DIR / tmp_name

    with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as z:
        # patient info
        info = [
            f"Nombre: {patient['full_name']}",
            f"Fecha nacimiento: {patient['dob'] or ''}",
            f"Género: {patient['gender'] or ''}",
            f"Email: {patient['email'] or ''}",
            f"Teléfono: {patient['phone'] or ''}",
            f"Dirección: {patient['address'] or ''}",
            f"Etiquetas: {patient['tags'] or ''}",
            f"Notas: {patient['notes'] or ''}",
            f"Creado: {patient['created_at']}",
            f"Actualizado: {patient['updated_at']}",
        ]
        z.writestr(f"{safe_name}/info.txt", "\n".join(info))

        # sessions
        for s in sessions:
            date = (s['date'] or '').replace(':','-').replace(' ','_')
            title = secure_filename(s['title'] or 'sesion')
            html = f"""
<!doctype html><meta charset='utf-8'>
<h3>{s['title'] or 'Sesión'}</h3>
<small>{s['date']} · {s['duration_minutes'] or 0} min</small>
<hr>
{(s['content_html'] or '')}
"""
            z.writestr(f"{safe_name}/sesiones/{date}_{title}.html", html)

        # documents files
        for d in documents:
            path = UPLOADS_DIR / str(patient_id) / d['filename']
            if path.exists():
                z.write(path, arcname=f"{safe_name}/documentos/{d['original_filename']}")

        # drawings files
        for dr in drawings:
            path = Path(dr['file_path'])
            if path.exists():
                z.write(path, arcname=f"{safe_name}/pizarra/{path.name}")

    return send_from_directory(DATA_DIR, tmp_name, as_attachment=True)


# --------------------------------------------------------------------------------------
# Minimal error handlers
# --------------------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template('base.html', title='No encontrado', app_name=APP_NAME, user=current_user(), year=dt.datetime.now().year) + "<main class='container'><h3>No encontrado</h3></main>", 404


# --------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=True)
