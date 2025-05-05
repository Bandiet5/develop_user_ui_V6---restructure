# blueprints/edit_page.py

from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
import os, json
import sqlite3


edit_page_bp = Blueprint('edit_page', __name__)

PAGES_FOLDER = os.path.join(os.getcwd(), 'pages')
os.makedirs(PAGES_FOLDER, exist_ok=True)

@edit_page_bp.route('/edit/<page_name>')
def edit_page(page_name):
    if session.get('username') != 'developer':
        return redirect(url_for('login'))

    filepath = os.path.join(PAGES_FOLDER, f"{page_name}.json")
    layout = []
    workspace_height = 800  # ⬅️ Default starting height

    if os.path.exists(filepath):
        with open(filepath) as f:
            data = json.load(f)

        # 🔥 New: support both old and new file formats
        if isinstance(data, dict) and 'layout' in data:
            layout = data.get('layout', [])
            workspace_height = data.get('workspace_height', 800)
        else:
            layout = data  # legacy support (pure list)

    # 📄 List all existing pages (for link dropdown)
    pages = [f.replace('.json', '') for f in os.listdir(PAGES_FOLDER) if f.endswith('.json') and f.replace('.json', '') != page_name]

    # 🗃️ List databases and their tables
    DB_FOLDER = os.path.join(os.getcwd(), 'data')
    databases = [f for f in os.listdir(DB_FOLDER) if f.endswith('.db')]

    db_tables = {}
    for db in databases:
        try:
            conn = sqlite3.connect(os.path.join(DB_FOLDER, db))
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table'")
            db_tables[db] = [t[0] for t in c.fetchall()]
            conn.close()
        except Exception as e:
            print(f"❌ Error reading {db}: {e}")
            db_tables[db] = []

    # ✅ Pass everything to the template
    return render_template(
        'edit_page.html',
        page_name=page_name,
        layout=layout,
        workspace_height=workspace_height,  # ⬅️ now we pass it!
        pages=pages,
        databases=databases,
        db_tables=db_tables
    )


@edit_page_bp.route('/save_page/<page_name>', methods=['POST'])
def save_page(page_name):
    if session.get('username') != 'developer':
        return jsonify({'status': 'unauthorized'}), 403

    layout = request.json.get('layout', [])
    workspace_height = request.json.get('workspace_height', 800)  # Default 800 if missing
    filepath = os.path.join(PAGES_FOLDER, f"{page_name}.json")

    data = {
        "layout": layout,
        "workspace_height": workspace_height
    }

    with open(filepath, 'w') as f:
        json.dump(data, f)

    return jsonify({'status': 'success'})




# Load database & table list
DB_FOLDER = os.path.join(os.getcwd(), 'data')
databases = [f for f in os.listdir(DB_FOLDER) if f.endswith('.db')]

db_tables = {}
for db in databases:
    try:
        conn = sqlite3.connect(os.path.join(DB_FOLDER, db))
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        db_tables[db] = [t[0] for t in c.fetchall()]
        conn.close()
    except:
        db_tables[db] = []


@edit_page_bp.route('/get_table_columns')
def get_table_columns():
    db_name = request.args.get('db')
    table_name = request.args.get('table')

    if not db_name or not table_name:
        return jsonify({'error': 'Missing parameters'}), 400

    db_path = os.path.join(os.getcwd(), 'data', db_name)
    if not os.path.isfile(db_path):
        return jsonify({'error': 'Database not found'}), 404

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns_info = cursor.fetchall()
        conn.close()

        columns = [col[1] for col in columns_info]  # 2nd item is column name
        return jsonify({'columns': columns})

    except Exception as e:
        print("❌ Error fetching columns:", str(e))
        return jsonify({'error': str(e)}), 500