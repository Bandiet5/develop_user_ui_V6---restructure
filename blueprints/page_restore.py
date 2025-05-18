from flask import Blueprint, render_template, request, jsonify, redirect, url_for
import sqlite3, os, json

page_restore_bp = Blueprint('page_restore', __name__)

PAGE_DB_PATH = os.path.join(os.getcwd(), 'data', 'page_data.db')
PAGES_FOLDER = os.path.join(os.getcwd(), 'pages')
os.makedirs(PAGES_FOLDER, exist_ok=True)

@page_restore_bp.route('/restore_page')
def restore_page_view():
    conn = sqlite3.connect(PAGE_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT DISTINCT page_name FROM page_versions")
    pages = sorted(row[0] for row in c.fetchall())
    conn.close()
    return render_template('page_restore.html', pages=pages)


@page_restore_bp.route('/get_versions')
def get_versions():
    page_name = request.args.get('page')
    if not page_name:
        return jsonify({'error': 'Missing page name'}), 400

    conn = sqlite3.connect(PAGE_DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, saved_at FROM page_versions
        WHERE page_name = ?
        ORDER BY saved_at DESC
    """, (page_name,))
    versions = [{'id': row[0], 'saved_at': row[1]} for row in c.fetchall()]
    conn.close()
    return jsonify(versions)


@page_restore_bp.route('/get_buttons_from_version')
def get_buttons_from_version():
    version_id = request.args.get('id')
    page_name = request.args.get('page')  # added

    if not version_id or not page_name:
        return jsonify({'error': 'Missing data'}), 400

    conn = sqlite3.connect(PAGE_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT layout_json FROM page_versions WHERE id = ? AND page_name = ?", (version_id, page_name))
    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({'error': 'Version not found for given page'}), 404

    try:
        layout = json.loads(row[0])
        labels = [item.get('label', 'Unnamed') for item in layout]
        return jsonify(labels)
    except Exception as e:
        return jsonify({'error': 'Failed to parse layout', 'details': str(e)}), 500


@page_restore_bp.route('/restore_version', methods=['POST'])
def restore_version():
    version_id = request.form.get('version_id')
    page_name = request.form.get('page_name')

    if not version_id or not page_name:
        return "Missing data", 400

    conn = sqlite3.connect(PAGE_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT layout_json FROM page_versions WHERE id = ?", (version_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return "Version not found", 404

    # Save over .json file
    layout_json = row[0]
    try:
        with open(os.path.join(PAGES_FOLDER, f"{page_name}.json"), 'w') as f:
            json.dump({"layout": json.loads(layout_json), "workspace_height": 800}, f, indent=2)
        return redirect(url_for('developer.developer_dashboard'))
    except Exception as e:
        return f"Failed to restore: {str(e)}", 500