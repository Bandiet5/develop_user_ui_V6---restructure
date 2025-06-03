# blueprints/database.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
import pandas as pd
import re
from sqlalchemy import inspect, text
from db_config import get_postgres_admin_engine, create_company_engine
from sqlalchemy.exc import SQLAlchemyError
import traceback

database_bp = Blueprint('database', __name__)

@database_bp.route('/database')
def database_dashboard():
    databases = {}

    try:
        admin_engine = get_postgres_admin_engine()
        with admin_engine.connect() as conn:
            result = conn.execute(text("SELECT datname FROM pg_database WHERE datistemplate = false"))
            db_names = [row[0] for row in result.fetchall() if row[0] not in ['postgres']]

        for db_name in db_names:
            try:
                engine = create_company_engine(db_name)

                with engine.connect() as conn:
                    inspector = inspect(conn)  # ✅ Refresh inspector per connection
                    table_names = inspector.get_table_names(schema='public')
                    table_info = []

                    for table_name in table_names:
                        columns = [col['name'] for col in inspector.get_columns(table_name)]
                        row_count = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar()
                        table_info.append({
                            "name": table_name,
                            "columns": columns,
                            "rows": row_count
                        })

                databases[db_name] = table_info

            except Exception as table_err:
                databases[db_name] = {"error": str(table_err)}

    except Exception as e:
        flash(f"❌ Failed to load databases: {e}")

    return render_template('database.html', databases=databases)


@database_bp.route('/create_database', methods=['POST'])
def create_database():
    db_name = request.form.get('new_database', '').strip()

    if not db_name:
        flash("Database name required.")
        return redirect(url_for('database.database_dashboard'))

    try:
        admin_engine = get_postgres_admin_engine().execution_options(isolation_level="AUTOCOMMIT")

        with admin_engine.connect() as conn:
            result = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"), {'name': db_name}).scalar()
            if result:
                flash("Database already exists.")
            else:
                print(f"[DEBUG] Creating database: {db_name}")
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                flash(f"✅ Database '{db_name}' created.")

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"❌ Error creating database: {str(e)}")

    return redirect(url_for('database.database_dashboard'))



@database_bp.route('/create_table', methods=['POST'])
def create_table():
    db_name = request.form.get('database')
    table_name = request.form.get('table_name', '').strip()
    column_names = request.form.getlist('column_names[]')
    column_types = request.form.getlist('column_types[]')

    if not db_name or not table_name or not column_names or not column_types:
        flash("Missing input.")
        return redirect(url_for('database.database_dashboard'))

    if len(column_names) != len(column_types):
        flash("Column names and types mismatch.")
        return redirect(url_for('database.database_dashboard'))

    # 🛡️ Always add a system_id column FIRST
    system_column = "system_id TEXT PRIMARY KEY"
    custom_columns = ', '.join(f'"{name}" {dtype}' for name, dtype in zip(column_names, column_types))
    full_columns = f"{system_column}, {custom_columns}"

    try:
        engine = create_company_engine(db_name)

        # ✅ Use engine.begin() to ensure transaction is committed properly
        with engine.begin() as conn:
            sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({full_columns})'
            print(f"[DEBUG] Executing SQL: {sql}")
            conn.execute(text(sql))

        flash(f"✅ Table '{table_name}' created with system_id in '{db_name}'")

    except SQLAlchemyError as e:
        print("❌ SQLAlchemy Error occurred while creating table:")
        traceback.print_exc()
        flash(f"❌ Error creating table: {str(e)}")

    except Exception as e:
        print("❌ General Exception occurred while creating table:")
        traceback.print_exc()
        flash(f"❌ Error creating table: {str(e)}")

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
        col = re.sub(r'[^a-z0-9_]', '_', col)
        if not col or col[0].isdigit():
            col = f"col_{col}"
        return col

    # You could enhance by auto-guessing SQL types later
    columns = [{"name": normalize(col), "type": "TEXT"} for col in df.columns]
    return jsonify({"columns": columns})


# --- NEW ROUTES ---


@database_bp.route('/list_tables/<db_name>')
def list_tables(db_name):
    try:
        engine = create_company_engine(db_name)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        return jsonify({"tables": tables})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@database_bp.route('/table_info/<db_name>/<table_name>')
def table_info(db_name, table_name):
    try:
        engine = create_company_engine(db_name)
        inspector = inspect(engine)
        columns_info = inspector.get_columns(table_name)
        columns = [col['name'] for col in columns_info]

        with engine.connect() as conn:
            row_count = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar()

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
        engine = create_company_engine(db)
        with engine.begin() as conn:  # ✅ Ensures the DROP TABLE is committed
            print(f"[DEBUG] Dropping table: {table} from {db}")
            conn.execute(text(f'DROP TABLE IF EXISTS "{table}"'))

        flash(f"✅ Table '{table}' deleted from '{db}'")
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f"❌ Error deleting table: {str(e)}")

    return redirect(url_for('database.database_dashboard'))



@database_bp.route('/delete_database', methods=['POST'])
def delete_database():
    db = request.form.get('db_name')
    if not db:
        flash("Missing database name.")
        return redirect(url_for('database.database_dashboard'))

    try:
        admin_engine = get_postgres_admin_engine()
        with admin_engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                text(f'DROP DATABASE IF EXISTS "{db}"')
            )
        flash(f"✅ Database '{db}' deleted.")
    except Exception as e:
        flash(f"❌ Error deleting database: {str(e)}")

    return redirect(url_for('database.database_dashboard'))

