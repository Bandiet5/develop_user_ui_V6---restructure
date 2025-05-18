import os
import uuid
import pandas as pd
import sqlite3
import chardet

DB_FOLDER = os.path.join(os.getcwd(), "data")

class UploadHandler:
    def __init__(self, version, config):
        self.version = version
        self.config = config

    def detect_encoding(self, file_path, num_bytes=20000):
        with open(file_path, 'rb') as f:
            raw_data = f.read(num_bytes)
            result = chardet.detect(raw_data)
            encoding = result['encoding']
            confidence = result['confidence']
            if encoding in [None, 'ascii'] or confidence < 0.7:
                return 'ISO-8859-1'
            return encoding

    def detect_header_row(self, file_path, encoding, table_columns):
        def normalize(col):
            return str(col).strip().lower().replace(" ", "_").replace(".", "_")

        table_cols_normalized = set(normalize(c) for c in table_columns)

        try:
            preview = (
                pd.read_excel(file_path, header=None, nrows=10, dtype=str)
                if file_path.endswith(('.xlsx', '.xls'))
                else pd.read_csv(file_path, encoding=encoding, header=None, nrows=10, engine='python', on_bad_lines='skip', dtype=str)
            )
        except Exception as e:
            print(f"[HEADER DETECTION] Failed to read preview: {e}")
            return 0

        best_row = 0
        max_matches = 0

        for idx, row in preview.iterrows():
            matches = sum(1 for cell in row if isinstance(cell, str) and normalize(cell) in table_cols_normalized)
            if matches > max_matches:
                max_matches = matches
                best_row = idx

        return best_row if max_matches >= 2 else 0


    def run(self):
        try:
            db_name = self.config.get('database')
            table_name = self.config.get('table')
            file_path = self.config.get('file')
            python_code = self.config.get('code', '')
            upload_mode = self.config.get('upload_mode', 'append')

            if not db_name or not table_name or not file_path:
                return {'status': 'error', 'message': 'Missing required parameters'}

            print(f"[UPLOAD] {file_path} -> {db_name}.{table_name} (mode: {upload_mode})")

            db_path = os.path.join(DB_FOLDER, db_name)
            conn = sqlite3.connect(db_path)
            cursor = conn.execute(f"PRAGMA table_info({table_name})")
            table_columns = [row[1] for row in cursor.fetchall()]
            conn.close()

            encoding = self.detect_encoding(file_path)
            header_row = self.detect_header_row(file_path, encoding, table_columns)

            # ✅ Force read all values as strings
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path, dtype=str, encoding=encoding, skiprows=header_row, engine='python', on_bad_lines='skip')
            else:
                df = pd.read_excel(file_path, dtype=str, skiprows=header_row)

            def normalize(col):
                return str(col).strip().lower().replace(" ", "_").replace(".", "_")

            df.columns = [normalize(c) for c in df.columns]

            # ✅ Ensure system_id is present and valid
            if 'system_id' not in df.columns:
                df['system_id'] = [str(uuid.uuid4()) for _ in range(len(df))]
            else:
                df['system_id'] = df['system_id'].apply(
                    lambda x: str(x) if pd.notnull(x) and str(x).strip() else str(uuid.uuid4())
                )

            # ✅ Optional: run any injected code
            if python_code:
                print(f"[DEBUG] Running injected code:\n{python_code}")
                local_vars = {'df': df}        
                try:
                    exec(python_code, {}, local_vars)
                    df = local_vars.get('df', df)
                except Exception as e:
                    print(f"[EXEC ERROR] {e}")

            # ✅ Filter only matching columns, keep all as strings
            columns_to_insert = [col for col in table_columns if col in df.columns]
            df = df[columns_to_insert].astype(str)

            # 🔧 Fix string 'nan' before inserting
            df = df.replace(['nan', 'NaN'], '', regex=True)

            print("[DEBUG] Final DataFrame before insert:")
            print(df.dtypes)
            print(df.head(3).to_dict(orient='records'))
            print("Columns to insert:", columns_to_insert)  

            # ✅ Save to database
            conn = sqlite3.connect(db_path)
            if_exists = 'replace' if upload_mode == 'replace' else 'append'
            df.to_sql(table_name, conn, if_exists=if_exists, index=False)
            conn.close()

            print(f"✅ Upload complete ({if_exists})")
            return {'status': 'ok', 'rows': len(df)}

        except Exception as e:
            print(f"❌ Upload failed: {e}")
            return {'status': 'error', 'message': str(e)}
