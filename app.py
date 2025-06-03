from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import importlib.util
import getpass
import os
import json
from multiprocessing import Process
import time
import pandas as pd

from blueprints.users import init_users_table
from button_handlers.ai_chat import AiChatHandler  # 👈 Top of your app.py
from button_registry import get_handler  # 👈 ensure this is imported
from button_handlers.multi_upload import MultiUploadHandler
from sqlalchemy import text
from db_config import get_app_engine
from db_config import create_company_engine
from sqlalchemy import inspect


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
from blueprints.users import init_users_table, ensure_app_database_exists
from blueprints.edit_page import init_page_data_db
from blueprints.scheduler import scheduler  # This will trigger cleanup + start the scheduler

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


app_engine = get_app_engine()

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

        # PostgreSQL DB user login
        try:
            with app_engine.connect() as conn:
                result = conn.execute(
                    text("SELECT role FROM users WHERE username = :u AND password = :p"),
                    {'u': username, 'p': password}
                ).fetchone()
        except Exception as e:
            print("[ERROR] DB login check failed:", e)
            return render_template('login.html', error="Server error")

        if result:
            role = result[0]
            session['username'] = username
            session['role'] = role
            print(f"[LOGIN] DB user '{username}' logged in with role: {role}")
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

    # 📄 Load layout JSON from disk
    filepath = os.path.join('pages', f'{page_name}.json')
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            layout = json.load(f)
        print(f"[PAGE] Loaded layout from {filepath}")
    else:
        layout = []
        print(f"[PAGE] File not found: {filepath}")

    # 🧠 Load all PostgreSQL databases and their tables
    db_tables = {}
    db_dir = "data"
    try:
        for file in os.listdir(db_dir):
            if file.endswith(".db"):
                db_name = file.replace(".db", "")
                try:
                    engine = create_company_engine(db_name)
                    inspector = inspect(engine)
                    tables = inspector.get_table_names()
                    db_tables[file] = tables
                except Exception as db_err:
                    db_tables[file] = [f"❌ Error: {db_err}"]
        print("[DB TABLES] Loaded database tables:", db_tables)
    except Exception as e:
        print("[ERROR] Failed loading database tables:", str(e))

    # 🎯 Pass everything to the template
    return render_template('user_page.html', layout=layout, page_name=page_name, db_tables=db_tables)


# ✅ Top-level function for background-safe multiprocessing

def import_used_modules(code_string):
    context = {}
    code_dir = os.path.join(os.getcwd(), "uploaded_code")

    if not os.path.exists(code_dir):
        return context

    for fname in os.listdir(code_dir):
        if not fname.endswith(".py"):
            continue

        mod_name = fname[:-3]
        if f"import {mod_name}" in code_string or f"from uploaded_code.{mod_name}" in code_string:
            fpath = os.path.join(code_dir, fname)
            try:
                spec = importlib.util.spec_from_file_location(mod_name, fpath)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                context[mod_name] = mod
                print(f"[IMPORT] Loaded module: {mod_name}")
            except Exception as e:
                print(f"[IMPORT ERROR] Could not load {fname}: {e}")

    return context



def run_task(code):
    print("[TASK] Running:\n", code)
    from sqlalchemy import create_engine, text
    from io import StringIO
    from contextlib import redirect_stdout
    import traceback
    import os
    import importlib.util

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

    # ✅ Safe base imports
    safe_imports = """
from sqlalchemy import create_engine, text
import pandas as pd
import os
import getpass
"""

    final_code = safe_imports + "\n" + code
    context = import_uploaded_modules()

    # Add safe SQLAlchemy functions manually
    context['create_engine'] = create_engine
    context['text'] = text

    f = StringIO()

    try:
        with redirect_stdout(f):
            exec(final_code, context, context)
    except Exception as e:
        output = f.getvalue()
        print("[TASK OUTPUT BEFORE ERROR]")
        print(output.strip())
        print("[TASK ERROR]")
        traceback.print_exc()
        return

    output = f.getvalue().strip()
    print("[TASK OUTPUT]", output or "✅ Done.")


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


if __name__ == '__main__':
    ensure_app_database_exists()       # ✅ Create DB if missing
    init_users_table()                 # ✅ Create users table
    init_page_data_db()                # ✅ Create page tables
    from blueprints.scheduler import scheduler
    app.run(debug=True)



