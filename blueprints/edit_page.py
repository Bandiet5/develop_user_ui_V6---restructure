# blueprints/edit_page.py

from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
import os, json
from sqlalchemy import create_engine, text, inspect
from db_config import create_company_engine, get_postgres_admin_engine, get_app_engine

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

        if isinstance(data, dict) and 'layout' in data:
            layout = data.get('layout', [])
            workspace_height = data.get('workspace_height', 800)
        else:
            layout = data  # legacy format

    # 📄 List all existing pages (for link dropdown)
    pages = [
        f.replace('.json', '')
        for f in os.listdir(PAGES_FOLDER)
        if f.endswith('.json') and f.replace('.json', '') != page_name
    ]

    # ✅ NEW: Get live PostgreSQL database + table info
    databases, db_tables = get_postgres_db_and_tables()

    return render_template(
        'edit_page.html',
        page_name=page_name,
        layout=layout,
        workspace_height=workspace_height,
        pages=pages,
        databases=databases,
        db_tables=db_tables
    )

# edit_page.py (top of file)
PAGE_DB_PATH = os.path.join(os.getcwd(), 'data', 'page_data.db')

def init_page_data_db():
    engine = get_app_engine()

    with engine.connect() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS pages (
                page_name TEXT PRIMARY KEY,
                layout_json TEXT,
                workspace_height INTEGER,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))

        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS page_versions (
                id SERIAL PRIMARY KEY,
                page_name TEXT,
                layout_json TEXT,
                workspace_height INTEGER,
                saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''))

        conn.commit()


def check_and_sync_button_schema(layout):
    engine = get_app_engine()
    updated_types = []

    with engine.connect() as conn:
        # 🛠️ Ensure table exists
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS button_config (
                type TEXT PRIMARY KEY,
                config_json TEXT
            )
        '''))

        for button in layout:
            btn_type = button.get("type")
            config = button.get("config", {})

            # 🔍 Fetch saved config
            result = conn.execute(
                text("SELECT config_json FROM button_config WHERE type = :type"),
                {'type': btn_type}
            ).fetchone()

            if not result:
                # First time: insert config
                conn.execute(
                    text("INSERT INTO button_config (type, config_json) VALUES (:type, :config)"),
                    {'type': btn_type, 'config': json.dumps(config)}
                )
            else:
                saved_config = json.loads(result[0])
                new_keys = set(config.keys()) - set(saved_config.keys())

                if new_keys:
                    merged_config = {**saved_config}
                    for k in new_keys:
                        merged_config[k] = ""

                    conn.execute(
                        text("UPDATE button_config SET config_json = :config WHERE type = :type"),
                        {'type': btn_type, 'config': json.dumps(merged_config)}
                    )
                    updated_types.append((btn_type, merged_config))

        conn.commit()

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
        engine = get_app_engine()

        with engine.connect() as conn:
            # ⬆️ UPSERT into `pages` table
            conn.execute(text('''
                INSERT INTO pages (page_name, layout_json, workspace_height)
                VALUES (:page_name, :layout, :height)
                ON CONFLICT (page_name) DO UPDATE SET
                    layout_json = EXCLUDED.layout_json,
                    workspace_height = EXCLUDED.workspace_height,
                    last_updated = CURRENT_TIMESTAMP
            '''), {
                'page_name': page_name,
                'layout': json.dumps(layout),
                'height': workspace_height
            })

            # ➕ Add version entry
            conn.execute(text('''
                INSERT INTO page_versions (page_name, layout_json, workspace_height)
                VALUES (:page_name, :layout, :height)
            '''), {
                'page_name': page_name,
                'layout': json.dumps(layout),
                'height': workspace_height
            })

            # 🔢 Count total versions
            result = conn.execute(text('''
                SELECT COUNT(*) FROM page_versions WHERE page_name = :page_name
            '''), {'page_name': page_name})
            total_versions = result.scalar()

            if total_versions > 5:
                # 🧹 Trim old versions older than today
                old_ids_result = conn.execute(text('''
                    SELECT id FROM page_versions
                    WHERE page_name = :page_name AND saved_at::date < CURRENT_DATE
                    ORDER BY saved_at ASC
                '''), {'page_name': page_name})

                old_ids = [row[0] for row in old_ids_result.fetchall()]
                to_delete = max(0, total_versions - 5)
                ids_to_remove = old_ids[:to_delete]

                if ids_to_remove:
                    placeholders = ','.join([f':id{i}' for i in range(len(ids_to_remove))])
                    param_dict = {f'id{i}': id_ for i, id_ in enumerate(ids_to_remove)}

                    conn.execute(
                        text(f'DELETE FROM page_versions WHERE id IN ({placeholders})'),
                        param_dict
                    )

            conn.commit()

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

from db_config import get_postgres_admin_engine

def get_postgres_db_and_tables():
    result = {}
    try:
        admin_engine = get_postgres_admin_engine()
        with admin_engine.connect() as conn:
            db_rows = conn.execute(text("SELECT datname FROM pg_database WHERE datistemplate = false"))
            db_names = [row[0] for row in db_rows.fetchall() if row[0] != 'postgres']

        for db in db_names:
            try:
                engine = create_company_engine(db)
                inspector = inspect(engine)
                result[db] = inspector.get_table_names()
            except Exception as e:
                print(f"❌ Error reading tables in {db}: {e}")
                result[db] = []

        return db_names, result
    except Exception as e:
        print("❌ Failed to load PostgreSQL databases:", e)
        return [], {}



@edit_page_bp.route('/get_table_columns')
def get_table_columns():
    db_name = request.args.get('db')  # no .db anymore
    table_name = request.args.get('table')

    if not db_name or not table_name:
        return jsonify({'error': 'Missing parameters'}), 400

    try:
        engine = create_company_engine(db_name)
        inspector = inspect(engine)
        columns_info = inspector.get_columns(table_name)
        columns = [col['name'] for col in columns_info]
        return jsonify({'columns': columns})

    except Exception as e:
        print("❌ Error fetching columns:", str(e))
        return jsonify({'error': str(e)}), 500
