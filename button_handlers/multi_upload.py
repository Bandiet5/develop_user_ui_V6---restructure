import os
import uuid
import pandas as pd
from sqlalchemy import text
from db_config import create_company_engine
from button_handlers.base import BaseButtonHandler

class MultiUploadHandler(BaseButtonHandler):
    def run_v1(self):
        print("[MultiUploadHandler] Starting multi-file upload")

        file_paths = self.config.get("file_paths", [])
        db_file = self.config.get("database")
        table = self.config.get("table")
        code = self.config.get("code", "")
        upload_mode = self.config.get("upload_mode", "append")

        if not file_paths or not db_file or not table:
            return {"status": "error", "message": "Missing required fields."}

        try:
            dfs = []
            for path in file_paths:
                if not os.path.isfile(path):
                    return {"status": "error", "message": f"File not found: {path}"}
                if path.endswith(".csv"):
                    dfs.append(pd.read_csv(path, dtype=str, engine="python", on_bad_lines='skip'))
                elif path.endswith((".xls", ".xlsx")):
                    dfs.append(pd.read_excel(path, dtype=str))
                else:
                    return {"status": "error", "message": f"Unsupported file: {path}"}

            df = pd.concat(dfs, ignore_index=True)
            print(f"[MultiUploadHandler] Total rows after concat: {len(df)}")

            # 🔧 Normalize column names
            def normalize(col):
                return str(col).strip().lower().replace(" ", "_").replace(".", "_")
            df.columns = [normalize(c) for c in df.columns]

            # 🆔 Ensure system_id exists
            if 'system_id' not in df.columns:
                df['system_id'] = [str(uuid.uuid4()) for _ in range(len(df))]
            else:
                df['system_id'] = df['system_id'].apply(
                    lambda x: str(x) if pd.notnull(x) and str(x).strip() else str(uuid.uuid4())
                )

            # 🧠 Optional pre-processing code
            if code.strip():
                local_vars = {"df": df}
                try:
                    exec(code, {}, local_vars)
                    df = local_vars.get("df", df)
                except Exception as e:
                    return {"status": "error", "message": f"Code execution failed: {e}"}

            # 🔗 Upload to PostgreSQL
            db_name = db_file.replace(".db", "")
            engine = create_company_engine(db_name)
            if_exists = "replace" if upload_mode == "replace" else "append"
            df.to_sql(table, engine, if_exists=if_exists, index=False, method='multi')

            return {
                "status": "ok",
                "rows": len(df),
                "columns": list(df.columns),
                "mode": upload_mode
            }

        except Exception as e:
            print("[MultiUploadHandler] Error:", e)
            return {"status": "error", "message": str(e)}
