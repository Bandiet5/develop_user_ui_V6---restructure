# button_handlers/ai_chat.py

import os
import sqlite3
import pandas as pd
from button_handlers.base import BaseButtonHandler
from blueprints.ai_tools import read_excel_files, summarize_data, run_generated_code

class AiChatHandler(BaseButtonHandler):
    supported_versions = [1]

    def run_current(self):
        return self.run_v1()

    def run_v1(self):
        prompt = self.config.get("prompt", "").strip()
        database = self.config.get("database", "").strip()
        tables = self.config.get("tables", [])
        files = self.config.get("files", {}) or {}

        if not prompt:
            return {"status": "error", "message": "Missing prompt."}

        dfs = []

        file1 = files.get("file1")
        file2 = files.get("file2")

        try:
            # Load data
            if file1 or file2:
                dfs = read_excel_files(file1, file2)
            elif database and tables:
                db_path = os.path.join("data", database)
                if not os.path.isfile(db_path):
                    return {"status": "error", "message": f"Database '{database}' not found."}

                conn = sqlite3.connect(db_path)
                for table in tables[:2]:
                    try:
                        df = pd.read_sql(f"SELECT * FROM {table} LIMIT 500", conn)
                        dfs.append(df)
                    except Exception as table_err:
                        print(f"[TABLE LOAD ERROR] {table}: {table_err}")
                conn.close()
            else:
                return {
                    "status": "error",
                    "message": "Please upload a file or select database table(s)."
                }

            if not dfs:
                return {"status": "error", "message": "No usable data found."}

            df1 = dfs[0]
            df2 = dfs[1] if len(dfs) > 1 else None

            code = summarize_data(df1, df2, prompt, table_names=tables)
            result_html, result_df, code_used = run_generated_code(df1, df2, code)

            download_path = None
            if isinstance(result_df, pd.DataFrame):
                output_path = os.path.join("static", "output.xlsx")
                result_df.to_excel(output_path, index=False)
                download_path = "/static/output.xlsx"

            return {
                "status": "ok",
                "message": result_html,
                "code": code_used,
                "download": download_path
            }

        except Exception as e:
            print("[AI CHAT ERROR]", str(e))
            return {"status": "error", "message": str(e)}
