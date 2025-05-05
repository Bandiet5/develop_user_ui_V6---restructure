from flask import Blueprint, request, jsonify, send_file, session
import sqlite3, pandas as pd, os, tempfile
from multiprocessing import Process
import chardet
import getpass
import uuid  # add this import at the top
from button_registry import get_handler

# 👇 This is what was missing
data_routes_bp = Blueprint('data_routes', __name__)

DB_FOLDER = os.path.join(os.getcwd(), 'data')

@data_routes_bp.route('/upload_data', methods=['POST'])
def upload_data():
    file = request.files.get("file")
    if not file:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400

    db = request.form.get("database")
    table = request.form.get("table")
    code = request.form.get("code", "")
    mode = request.form.get("upload_mode", "append")
    background = request.form.get("background") == "true"

    if not db or not table:
        return jsonify({"status": "error", "message": "Missing database or table"}), 400

    # Save temp file
    ext = os.path.splitext(file.filename)[1]
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    file.save(temp_file.name)

    # Build config
    config = {
        "database": db,
        "table": table,
        "upload_mode": mode,
        "code": code,
        "file": temp_file.name,
    }

    if background:
        from multiprocessing import Process
        handler_class = get_handler("upload")
        p = Process(target=run_upload_handler, args=(handler_class, config))
        p.start()
        return jsonify({"status": "ok", "background": True})
    else:
        handler_class = get_handler("upload")
        handler = handler_class(version=1, config=config)
        result = handler.run()
        return jsonify(result), 200 if result["status"] == "ok" else 400

def run_upload_handler(handler_class, config):
    handler = handler_class(version=1, config=config)
    handler.run()


# Use user's Downloads folder
def get_download_folder():
    username = getpass.getuser()
    if os.name == 'nt':
        return os.path.join("C:\\Users", username, "Downloads")
    else:
        return os.path.join(os.path.expanduser("~"), "Downloads")

DOWNLOAD_FOLDER = get_download_folder()


def process_file_download(db_name, table_name, file_format, python_code=None):
    try:
        db_path = os.path.join(DB_FOLDER, db_name)
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        conn.close()

        if python_code:
            local_vars = {"df": df}
            exec(python_code, {}, local_vars)
            df = local_vars.get("df", df)

        suffix = '.csv' if file_format == 'csv' else '.xlsx'
        filename = f"{table_name}_download{suffix}"
        full_path = os.path.join(DOWNLOAD_FOLDER, filename)

        if file_format == 'csv':
            df.to_csv(full_path, index=False)
        else:
            df.to_excel(full_path, index=False)

        print(f"✅ File saved to Downloads: {full_path}")
        return full_path

    except Exception as e:
        print(f"❌ Download failed: {e}")
        return None


@data_routes_bp.route('/download_data', methods=['POST'])
def download_data():
    data = request.json
    db_name = data.get('database')
    table_name = data.get('table')
    python_code = data.get('code', '')
    file_format = data.get('file_format', 'csv')
    background = data.get('background', False)

    if not db_name or not table_name:
        return jsonify({'status': 'error', 'message': 'Missing database or table'}), 400

    if background:
        p = Process(target=process_file_download, args=(db_name, table_name, file_format, python_code))
        p.start()
        return jsonify({'status': 'ok', 'background': True})

    file_path = process_file_download(db_name, table_name, file_format, python_code)
    if not file_path:
        return jsonify({'status': 'error', 'message': 'Download failed'}), 500

    return send_file(file_path, as_attachment=True)


