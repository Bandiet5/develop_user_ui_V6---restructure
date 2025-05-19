# blueprints/edit_page.py

from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
import os, json
import sqlite3
from button_registry import BUTTON_TYPES
from button_registry import get_handler


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


# edit_page.py (top of file)
PAGE_DB_PATH = os.path.join(os.getcwd(), 'data', 'page_data.db')

def init_page_data_db():
    conn = sqlite3.connect(PAGE_DB_PATH)
    c = conn.cursor()

    # Latest layout per page
    c.execute('''
        CREATE TABLE IF NOT EXISTS pages (
            page_name TEXT PRIMARY KEY,
            layout_json TEXT,
            workspace_height INTEGER,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Version history table with time-based recovery
    c.execute('''
        CREATE TABLE IF NOT EXISTS page_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_name TEXT,
            layout_json TEXT,
            workspace_height INTEGER,
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()


init_page_data_db()

def check_and_sync_button_schema(layout):
    db_path = PAGE_DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create button_config table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS button_config (
            type TEXT PRIMARY KEY,
            config_json TEXT
        )
    ''')

    updated_types = []

    for button in layout:
        btn_type = button.get("type")
        config = button.get("config", {})

        # Lookup current saved config for this type
        cursor.execute("SELECT config_json FROM button_config WHERE type = ?", (btn_type,))
        row = cursor.fetchone()

        if not row:
            # First time we've seen this type → save its schema
            cursor.execute(
                "INSERT INTO button_config (type, config_json) VALUES (?, ?)",
                (btn_type, json.dumps(config))
            )
        else:
            saved_config = json.loads(row[0])
            new_keys = set(config.keys()) - set(saved_config.keys())

            if new_keys:
                # Merge and save the new schema
                merged_config = {**saved_config}
                for k in new_keys:
                    merged_config[k] = ""

                cursor.execute(
                    "UPDATE button_config SET config_json = ? WHERE type = ?",
                    (json.dumps(merged_config), btn_type)
                )
                updated_types.append((btn_type, merged_config))

    conn.commit()
    conn.close()

    if updated_types:
        patch_pages_with_missing_keys(updated_types)


def patch_pages_with_missing_keys(updated_types):
    for filename in os.listdir(PAGES_FOLDER):
        if not filename.endswith('.json'):
            continue

        filepath = os.path.join(PAGES_FOLDER, filename)

        with open(filepath, 'r') as f:
            page_data = json.load(f)

        layout = page_data.get("layout", [])
        updated = False

        for button in layout:
            for btn_type, merged_config in updated_types:
                if button["type"] == btn_type:
                    config = button.get("config", {})
                    for key in merged_config:
                        if key not in config:
                            config[key] = ""
                            updated = True

        if updated:
            print(f"🔄 Patched missing keys in: {filename}")
            with open(filepath, 'w') as f:
                json.dump(page_data, f, indent=2)

#######################################
# save the page
def save_page_to_database(page_name, layout, workspace_height):
    try:
        conn = sqlite3.connect(PAGE_DB_PATH)
        c = conn.cursor()

        # Save latest snapshot
        c.execute('''
            INSERT INTO pages (page_name, layout_json, workspace_height)
            VALUES (?, ?, ?)
            ON CONFLICT(page_name) DO UPDATE SET
                layout_json=excluded.layout_json,
                workspace_height=excluded.workspace_height,
                last_updated=CURRENT_TIMESTAMP
        ''', (page_name, json.dumps(layout), workspace_height))

        # Insert version entry
        c.execute('''
            INSERT INTO page_versions (page_name, layout_json, workspace_height)
            VALUES (?, ?, ?)
        ''', (page_name, json.dumps(layout), workspace_height))

        # Check total version count
        c.execute('SELECT COUNT(*) FROM page_versions WHERE page_name = ?', (page_name,))
        total_versions = c.fetchone()[0]

        if total_versions > 5:
            # ✅ Only consider versions older than today
            c.execute('''
                SELECT id FROM page_versions
                WHERE page_name = ? AND date(saved_at) < date('now')
                ORDER BY saved_at ASC
            ''', (page_name,))
            old_ids = [row[0] for row in c.fetchall()]

            # Only delete enough to keep 5
            to_delete = max(0, total_versions - 5)
            ids_to_remove = old_ids[:to_delete]

            if ids_to_remove:
                c.execute(f'''
                    DELETE FROM page_versions
                    WHERE id IN ({','.join(['?'] * len(ids_to_remove))})
                ''', ids_to_remove)

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"❌ Failed to save page '{page_name}' to DB:", e)


@edit_page_bp.route('/save_page/<page_name>', methods=['POST'])
def save_page(page_name):
    if session.get('username') != 'developer':
        return jsonify({'status': 'unauthorized'}), 403

    layout_raw = request.json.get('layout', [])
    workspace_height = request.json.get('workspace_height', 800)
    filepath = os.path.join(PAGES_FOLDER, f"{page_name}.json")

    layout = []
    for item in layout_raw:
        btn_type = item.get("type", "code")
        handler_class = get_handler(btn_type)

        version = 1
        if handler_class and hasattr(handler_class, "supported_versions"):
            version = max(handler_class.supported_versions)

        normalized = {
            "type": btn_type,
            "label": item.get("label", "Untitled"),
            "version": version,
            "top": item.get("top", 0),
            "left": item.get("left", 0),
            "config": item.get("config", {})
        }
        layout.append(normalized)

    # ✅ Sync and patch if button schemas changed
    check_and_sync_button_schema(layout)

    with open(filepath, 'w') as f:
        json.dump({
            "layout": layout,
            "workspace_height": workspace_height
        }, f, indent=2)

    save_page_to_database(page_name, layout, workspace_height)

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