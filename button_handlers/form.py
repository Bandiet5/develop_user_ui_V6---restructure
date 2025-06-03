import os
import pandas as pd
from flask import Blueprint, request, jsonify
from sqlalchemy import text
from db_config import create_company_engine
from button_handlers.base import BaseButtonHandler

form_bp = Blueprint('form_bp', __name__)

class FormHandler(BaseButtonHandler):
    supported_versions = [1]

    def run_current(self):
        return self.run_v1()

    def run_v1(self):
        print('Start run_v1 FormHandler')
        print("DEBUG: config payload =", self.config)

        db = self.config.get("database")
        table = self.config.get("table")
        key_column = self.config.get("key_column", "system_id")
        filter_mode = self.config.get("filter_mode", "simple")
        sql_filter = self.config.get("sql_filter", "")
        python_filter = self.config.get("python_filter") or self.config.get("code", "")
        python_filter = python_filter.strip()

        edit_fields = self.config.get("edit_fields", [])
        lookup_db = self.config.get("lookup_database", "")
        lookup_table = self.config.get("lookup_table", "")
        lookup_key_column = self.config.get("lookup_key_column", "")
        lookup_fields = self.config.get("lookup_fields", [])

        if not db or not table:
            return {"status": "error", "message": "Missing database or table."}

        try:
            # Load base table
            engine = create_company_engine(db.replace(".db", ""))
            with engine.connect() as conn:
                df = pd.read_sql_query(text(f'SELECT * FROM "{table}"'), conn)

            if lookup_key_column and lookup_key_column in df.columns:
                df[lookup_key_column] = df[lookup_key_column].astype(str)

            # Apply filter
            if filter_mode == "simple" and sql_filter:
                try:
                    df = df.query(sql_filter)
                except Exception as e:
                    return {"status": "error", "message": f"SQL filter error: {e}"}
            elif filter_mode == "python" and python_filter:
                try:
                    print("Running Python filter")
                    local_vars = {"df": df}
                    exec(python_filter, {}, local_vars)
                    df = local_vars.get("df", df)
                except Exception as e:
                    return {"status": "error", "message": f"Python filter error: {e}"}

            selected_cols = list(dict.fromkeys(
                [key_column] + edit_fields + ([lookup_key_column] if lookup_key_column and lookup_key_column not in edit_fields else [])
            ))
            df = df[selected_cols]
            rows = df.to_dict(orient="records")

            # Optional lookup
            lookup_data = {}
            if lookup_db and lookup_table and lookup_key_column and lookup_fields:
                engine_lookup = create_company_engine(lookup_db.replace(".db", ""))
                with engine_lookup.connect() as conn:
                    lookup_df = pd.read_sql_query(text(f'SELECT * FROM "{lookup_table}"'), conn)

                if lookup_key_column in lookup_df.columns:
                    lookup_df[lookup_key_column] = lookup_df[lookup_key_column].astype(str)

                lookup_keys = df[lookup_key_column].dropna().unique().tolist()
                lookup_df = lookup_df[lookup_df[lookup_key_column].isin(lookup_keys)]

                lookup_cols = list(dict.fromkeys([lookup_key_column] + lookup_fields))
                lookup_df = lookup_df[lookup_cols]

                lookup_data = {
                    "data": lookup_df.to_dict(orient="records"),
                    "key_column": lookup_key_column,
                    "fields": lookup_fields
                }

            print("✅ FormHandler return:", f"{len(rows)} rows")
            return {
                "status": "ok",
                "rows": rows,
                "lookup": lookup_data
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}


@form_bp.route('/submit_form_update', methods=['POST'])
def submit_form_update():
    data = request.json
    db = data.get('db')  # e.g., "client_a.db"
    table = data.get('table')
    updates = data.get('updates', {})

    if not db or not table:
        return jsonify({'status': 'error', 'message': 'Missing database or table name'})

    try:
        db_name = db.replace('.db', '')  # sanitize input
        engine = create_company_engine(db_name)

        changes = {}
        for field_plus_id, value in updates.items():
            if '_' not in field_plus_id:
                continue
            field, record_id = field_plus_id.rsplit('_', 1)
            if record_id not in changes:
                changes[record_id] = {}
            changes[record_id][field] = value

        with engine.begin() as conn:  # 🔒 handles commit/rollback
            for record_id, fields in changes.items():
                if not fields:
                    continue
                set_clause = ', '.join([f'"{field}" = :{field}' for field in fields.keys()])
                sql = text(f'UPDATE "{table}" SET {set_clause} WHERE system_id = :system_id')
                conn.execute(sql, {**fields, 'system_id': record_id})

        return jsonify({'status': 'ok'})

    except Exception as e:
        print(f"❌ Error updating form data: {e}")
        return jsonify({'status': 'error', 'message': str(e)})
