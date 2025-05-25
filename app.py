from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
import json
import sqlite3
from multiprocessing import Process
import time
from flask import request, jsonify
import time
import pandas as pd
from blueprints.users import init_users_table
from button_handlers.ai_chat import AiChatHandler  # 👈 Top of your app.py
from button_registry import get_handler  # 👈 ensure this is imported
from button_handlers.multi_upload import MultiUploadHandler

# Blueprints 
from button_handlers.form import form_bp
from blueprints.developer import developer_bp
from blueprints.edit_page import edit_page_bp
from blueprints.users import users_bp
from blueprints.database import database_bp
from blueprints.data_routes import data_routes_bp
from blueprints.ai_tools import read_excel_files, summarize_data
from blueprints.user_page import user_page_bp
from blueprints.page_restore import page_restore_bp
from blueprints.manage_functions import manage_functions_bp

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Register blueprints
app.register_blueprint(developer_bp)
app.register_blueprint(edit_page_bp)
app.register_blueprint(users_bp)
app.register_blueprint(database_bp)
app.register_blueprint(data_routes_bp)
app.register_blueprint(user_page_bp)
app.register_blueprint(form_bp)
app.register_blueprint(page_restore_bp)
app.register_blueprint(manage_functions_bp)

DB_PATH = os.path.join(os.getcwd(), 'data', 'app_data.db') 

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    print('[ROUTE] login')

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        print(f"[LOGIN] Attempt login for user: '{username}'")

        # Hardcoded developer login
        if username == 'developer' and password == 'dev123':
            session['username'] = 'developer'
            session['role'] = 'developer'
            print("[LOGIN] Logged in as hardcoded developer")
            return redirect(url_for('developer.developer_dashboard'))

        # Database user login
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT role FROM users WHERE username=? AND password=?", (username, password))
            result = c.fetchone()
            conn.close()
        except Exception as e:
            print("[ERROR] DB login check failed:", e)
            return render_template('login.html', error="Server error")

        if result:
            role = result[0]
            session['username'] = username
            session['role'] = role
            print(f"[LOGIN] DB user '{username}' logged in with role: {role}")
            print(f"[DEBUG] Session after login: {dict(session)}")
            # ✅ Redirect to user-facing page view route
            return redirect(url_for('user_page', page_name='Home'))

        print("[LOGIN] Invalid credentials for user:", username)
        return render_template('login.html', error="Invalid credentials")

    return render_template('login.html')


@app.route('/logout')
def logout():
    print(f"[LOGOUT] Logging out user: {session.get('username')}")
    session.clear()
    return redirect(url_for('login'))

@app.route('/page/<page_name>')
def user_page(page_name):
    print(f"[ROUTE] user_page: {page_name}")
    print(f"[DEBUG] Session: {dict(session)}")

    if 'username' not in session:
        print("[BLOCKED] No session found. Redirecting to login.")
        return redirect(url_for('login'))

    filepath = os.path.join('pages', f'{page_name}.json')
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            layout = json.load(f)
        print(f"[PAGE] Loaded layout from {filepath}")
    else:
        layout = []
        print(f"[PAGE] File not found: {filepath}")

    # 🧠 Load databases and their tables
    db_tables = {}
    db_dir = "data"
    try:
        for file in os.listdir(db_dir):
            if file.endswith(".db"):
                db_path = os.path.join(db_dir, file)
                import sqlite3
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [row[0] for row in cursor.fetchall()]
                db_tables[file] = tables
                conn.close()
        print("[DB TABLES] Loaded database tables:", db_tables)
    except Exception as e:
        print("[ERROR] Failed loading database tables:", str(e))

    # 🛠 Pass db_tables into template
    return render_template('user_page.html', layout=layout, page_name=page_name, db_tables=db_tables)

# ✅ Top-level function for background-safe multiprocessing
def run_task(code):
    print("[TASK] Running:", code)

    import importlib.util
    import os
    from contextlib import redirect_stdout
    from io import StringIO

    def import_uploaded_modules():
        context = {}
        code_dir = os.path.join(os.getcwd(), "uploaded_code")
        if not os.path.exists(code_dir):
            return context

        for fname in os.listdir(code_dir):
            if fname.endswith(".py"):
                name = fname[:-3]
                fpath = os.path.join(code_dir, fname)

                try:
                    spec = importlib.util.spec_from_file_location(name, fpath)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    context[name] = mod
                    print(f"[IMPORT] Loaded module: {name}")
                except Exception as e:
                    print(f"[IMPORT ERROR] Could not load {fname}: {e}")
        return context

    # ✅ Safe base imports available to the user's code
    safe_imports = """
import sqlite3
import pandas as pd
import os
import getpass
"""

    final_code = safe_imports + "\n" + code

    try:
        context = import_uploaded_modules()
        f = StringIO()
        with redirect_stdout(f):  # Capture output for logging
            exec(final_code, context, context)
        output = f.getvalue().strip()
        print("[TASK OUTPUT]", output or "✅ Done.")
    except Exception as e:
        print("[TASK ERROR]", e)



@app.route('/run_action', methods=['POST'])
def run_action():
    data = request.json
    button_type = data.get("type", "code")
    config = data.get("config", {})
    version = data.get("version", 1)
    background = data.get("background", False)
    print(f"[DEBUG] Received button version: {version}")

    # 🧠 Handle raw Python code buttons
    if button_type == "code":
        code = data.get("action", "") or config.get("code", "")
        if not code:
            return jsonify({'status': 'error', 'message': 'No code provided'}), 400

        if background:
            print("[BACKGROUND] Running raw code...")
            Process(target=run_task, args=(code,)).start()
            return jsonify({'status': 'ok', 'message': 'Started in background'})

        run_task(code)
        return jsonify({'status': 'ok', 'message': 'Ran in foreground'})

    # ✅ Handle all other registered buttons
    handler_class = get_handler(button_type)
    if not handler_class:
        return jsonify({'status': 'error', 'message': f"Unknown button type: {button_type}"}), 400

    try:
        handler = handler_class(version=version, config=config)

        if background:
            print(f"[BACKGROUND] Running handler: {button_type}")
            Process(target=handler.run_current).start()
            return jsonify({'status': 'ok', 'message': f'{button_type} running in background'})

        result = handler.run()
        return jsonify(result), 200 if result.get("status") == "ok" else 400
    except Exception as e:
        print("[RUN ACTION ERROR]", str(e))
        return jsonify({'status': 'error', 'message': str(e)}), 500


from flask import request, jsonify
from blueprints.ai_tools import read_excel_files, summarize_data

@app.route('/ai_chat', methods=['POST'])
def ai_chat():
    try:
        files = {
            "file1": request.files.get("file1"),
            "file2": request.files.get("file2")
        }

        config = {
            "prompt": request.form.get("prompt"),
            "database": request.form.get("database"),
            "tables": request.form.getlist("tables")
        }

        handler = AiChatHandler(version=1, config=config)
        handler.files = files  # ✅ Assign files after handler creation
        result = handler.run()

        return jsonify(result), 200 if result["status"] == "ok" else 400

    except Exception as e:
        print("[AI CHAT ERROR]", str(e))
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.before_request
def debug_session():
    print(f"[SESSION DEBUG] Path: {request.path} | Session: {dict(session)}")


# Updated for GitHub test - 2025-05-05
# another test update
if __name__ == '__main__':
    init_users_table()
    app.run(debug=True)

