import os
import sqlite3
import pandas as pd
from button_handlers.base import BaseButtonHandler

class DownloadHandler(BaseButtonHandler):
    supported_versions = [1]

    def run_current(self):
        return self.run_v1()

    def run_v1(self):
        db_name = self.config.get("database")
        table = self.config.get("table")
        code = self.config.get("code", "")
        file_format = self.config.get("file_format", "csv")

        if not db_name or not table:
            return {"status": "error", "message": "Missing database or table."}

        try:
            db_path = os.path.join("data", db_name)
            conn = sqlite3.connect(db_path)
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
            conn.close()

            # Optional code filter
            if code:
                local_vars = {"df": df}
                exec(code, {}, local_vars)
                df = local_vars.get("df", df)

            # ✅ Convert all columns to string to preserve formats
            df = df.astype(str)

            ext = "xlsx" if file_format == "excel" else "csv"
            file_name = f"{table}_export.{ext}"
            file_path = os.path.join("static", file_name)

            if file_format == "excel":
                # ✅ Use xlsxwriter to format all cells as text
                with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Sheet1')
                    workbook = writer.book
                    worksheet = writer.sheets['Sheet1']
                    text_fmt = workbook.add_format({'num_format': '@'})
                    worksheet.set_column(0, len(df.columns) - 1, 20, text_fmt)
            else:
                df.to_csv(file_path, index=False)

            return {"status": "ok", "download": f"/static/{file_name}"}

        except Exception as e:
            return {"status": "error", "message": str(e)}
