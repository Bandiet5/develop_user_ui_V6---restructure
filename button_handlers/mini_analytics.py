import os
import sqlite3
import pandas as pd
from button_handlers.base import BaseButtonHandler

class MiniAnalyticsHandler(BaseButtonHandler):
    supported_versions = [1]

    def run_v1(self):
        database = self.config.get("database")
        table = self.config.get("table")
        code = self.config.get("code", "")
        show_chart = self.config.get("show_chart", False)

        if not database or not table:
            return {"status": "error", "message": "Missing database or table."}

        try:
            db_path = os.path.join("data", database)
            conn = sqlite3.connect(db_path)
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
            conn.close()

            # Optional user code
            if code:
                local_vars = {"df": df}
                exec(code, {}, local_vars)
                df = local_vars.get("df", df)

            result_text = f"{len(df)} rows processed."

            chart_data = {}
            if show_chart and isinstance(df, pd.DataFrame):
                value_counts = df.iloc[:, 0].value_counts().head(5)
                chart_data = value_counts.to_dict()

            return {
                "status": "ok",
                "result": result_text,
                "chart": chart_data if chart_data else None
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ✅ Add this so it works with /run_action
    def run_current(self):
        return self.run_v1()
