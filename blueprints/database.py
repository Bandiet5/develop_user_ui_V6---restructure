# blueprints/database.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
import os
import sqlite3
import pandas as pd
import re

# Blueprint and paths
database_bp = Blueprint('database', __name__)
DB_FOLDER = os.path.join(os.getcwd(), 'data')
os.makedirs(DB_FOLDER, exist_ok=True)

@database_bp.route('/database')
def database_dashboard():
    databases = {}
    for db_file in os.listdir(DB_FOLDER):
        if db_file.endswith('.db'):
            db_path = os.path.join(DB_FOLDER, db_file)
            try:
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                c.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = c.fetchall()
                table_info = []

                for (table_name,) in tables:
                    c.execute(f"PRAGMA table_info({table_name})")
                    columns = [col[1] for col in c.fetchall()]
                    c.execute(f"SELECT COUNT(*) FROM {table_name}")
                    rows = c.fetchone()[0]
                    table_info.append({
                        "name": table_name,
                        "columns": columns,
                        "rows": rows
                    })

                conn.close()
                databases[db_file] = table_info
            except Exception as e:
                databases[db_file] = {"error": str(e)}

    return render_template('database.html', databases=databases)

@database_bp.route('/create_database', methods=['POST'])
def create_database():
    db_name = request.form.get('new_database').strip()
    if not db_name:
        flash("Database name required.")
    else:
        db_path = os.path.join(DB_FOLDER, f"{db_name}.db")
        if not os.path.exists(db_path):
            open(db_path, 'a').close()
            flash(f"Database '{db_name}' created.")
        else:
            flash("Database already exists.")
    return redirect(url_for('database.database_dashboard'))

@database_bp.route('/create_table', methods=['POST'])
def create_table():
    db_name = request.form.get('database')
    table_name = request.form.get('table_name').strip()
    column_names = request.form.getlist('column_names[]')
    column_types = request.form.getlist('column_types[]')

    if not db_name or not table_name or not column_names or not column_types:
        flash("Missing input.")
        return redirect(url_for('database.database_dashboard'))

    if len(column_names) != len(column_types):
        flash("Column names and types mismatch.")
        return redirect(url_for('database.database_dashboard'))

    db_path = os.path.join(DB_FOLDER, db_name)

    # 🛡️ Always add a system_id column FIRST
    system_column = "system_id TEXT PRIMARY KEY"
    custom_columns = ', '.join(f"{name} {dtype}" for name, dtype in zip(column_names, column_types))
    full_columns = f"{system_column}, {custom_columns}"

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({full_columns})")
        conn.commit()
        conn.close()
        flash(f"✅ Table '{table_name}' created with a system_id in '{db_name}'")
    except Exception as e:
        flash(f"❌ Error: {str(e)}")

    return redirect(url_for('database.database_dashboard'))


@database_bp.route('/upload_table_columns', methods=['POST'])
def upload_table_columns():
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "No file selected."}), 400

    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file, nrows=0)
        else:
            df = pd.read_excel(file, nrows=0)
    except Exception as e:
        return jsonify({"error": f"File read error: {str(e)}"}), 500

    def normalize(col):
        col = str(col).strip().lower()
        col = re.sub(r'[^a-z0-9_]', '_', col)  # Only allow a-z, 0-9, and underscore
        if not col or col[0].isdigit():
            col = f"col_{col}"  # If starts with number, add col_
        return col

    columns = [{"name": normalize(col), "type": "TEXT"} for col in df.columns]
    return jsonify({"columns": columns})

# --- NEW ROUTES ---

@database_bp.route('/list_tables/<db_name>')
def list_tables(db_name):
    db_path = os.path.join(DB_FOLDER, db_name)
    if not os.path.exists(db_path):
        return jsonify({"error": "Database not found"}), 404

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in c.fetchall()]
        conn.close()
        return jsonify({"tables": tables})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@database_bp.route('/table_info/<db_name>/<table_name>')
def table_info(db_name, table_name):
    db_path = os.path.join(DB_FOLDER, db_name)
    if not os.path.exists(db_path):
        return jsonify({"error": "Database not found"}), 404

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in c.fetchall()]
        c.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = c.fetchone()[0]
        conn.close()
        return jsonify({"columns": columns, "row_count": row_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@database_bp.route('/delete_table', methods=['POST'])
def delete_table():
    db = request.form.get('db_name')
    table = request.form.get('table_name')

    if not db or not table:
        flash("Missing table or database.")
        return redirect(url_for('database.database_dashboard'))

    try:
        conn = sqlite3.connect(os.path.join(DB_FOLDER, db))
        c = conn.cursor()
        c.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
        conn.close()
        flash(f"Table '{table}' deleted from '{db}'")
    except Exception as e:
        flash(f"Error: {str(e)}")

    return redirect(url_for('database.database_dashboard'))


@database_bp.route('/delete_database', methods=['POST'])
def delete_database():
    db = request.form.get('db_name')
    if not db:
        flash("Missing database name.")
        return redirect(url_for('database.database_dashboard'))

    path = os.path.join(DB_FOLDER, db)
    try:
        os.remove(path)
        flash(f"Database '{db}' deleted.")
    except Exception as e:
        flash(f"Error deleting database: {str(e)}")

    return redirect(url_for('database.database_dashboard'))
