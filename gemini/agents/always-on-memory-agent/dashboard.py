"""
Agent Memory Layer — Flask Dashboard

Flask UI that connects to the always-on memory agent.
Visualizes memories, runs queries, and triggers operations.

Usage:
    # First start the agent:
    python agent.py

    # Then start the dashboard:
    python dashboard.py
"""

import os
from pathlib import Path
from functools import wraps

import requests
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, session
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-key-change-me")

# Default credentials (in a real app, these would be in a DB or env vars)
DASHBOARD_USER = os.getenv("DASHBOARD_USER", "admin")
DASHBOARD_PASS = os.getenv("DASHBOARD_PASS", "password")

# Base directory for the application
BASE_DIR = Path(__file__).resolve().parent

AGENT_URL = os.getenv("AGENT_URL", "http://localhost:8888")
INBOX_DIR = BASE_DIR / "inbox"
DOCS_DIR = BASE_DIR / "docs"

UPLOAD_EXTENSIONS = {
    "txt", "md", "json", "csv", "log", "xml", "yaml", "yml",
    "png", "jpg", "jpeg", "gif", "webp", "bmp", "svg",
    "mp3", "wav", "ogg", "flac", "m4a", "aac",
    "mp4", "webm", "mov", "avi", "mkv",
    "pdf",
}


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "logged_in" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def api_get(path: str) -> dict | None:
    try:
        r = requests.get(f"{AGENT_URL}{path}", timeout=30)
        return r.json()
    except Exception as e:
        print(f"Agent not reachable: {e}")
        return None


def api_post(path: str, data: dict) -> dict | None:
    try:
        r = requests.post(f"{AGENT_URL}{path}", json=data, timeout=60)
        return r.json()
    except Exception as e:
        print(f"Agent not reachable: {e}")
        return None


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == DASHBOARD_USER and password == DASHBOARD_PASS:
            session["logged_in"] = True
            return redirect(url_for("index"))
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(DOCS_DIR, filename)


@app.route("/docs/<path:filename>")
@login_required
def serve_docs(filename):
    return send_from_directory(DOCS_DIR, filename)


@app.route("/api/status")
@login_required
def status():
    return jsonify(api_get("/status") or {"error": "Agent offline"})


@app.route("/api/memories")
@login_required
def memories():
    return jsonify(api_get("/memories") or {"memories": [], "count": 0})


@app.route("/api/ingest", methods=["POST"])
@login_required
def ingest():
    data = request.json
    return jsonify(api_post("/ingest", data) or {"error": "Failed to ingest"})


@app.route("/api/consolidate", methods=["POST"])
@login_required
def consolidate():
    return jsonify(api_post("/consolidate", {}) or {"error": "Failed to consolidate"})


@app.route("/api/query")
@login_required
def query():
    q = request.args.get("q", "")
    return jsonify(api_get(f"/query?q={q}") or {"error": "Failed to query"})


@app.route("/api/delete", methods=["POST"])
@login_required
def delete():
    data = request.json
    return jsonify(api_post("/delete", data) or {"error": "Failed to delete"})


@app.route("/api/clear", methods=["POST"])
@login_required
def clear():
    return jsonify(api_post("/clear", {}) or {"error": "Failed to clear"})


@app.route("/api/upload", methods=["POST"])
@login_required
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        filename = secure_filename(file.filename)
        INBOX_DIR.mkdir(parents=True, exist_ok=True)
        dest = INBOX_DIR / filename
        if dest.exists():
            return jsonify({"status": "exists", "message": f"{filename} already exists"}), 200

        file.save(str(dest))
        return jsonify({"status": "success", "message": f"{filename} saved to inbox"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8501, debug=True)
