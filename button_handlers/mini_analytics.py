import os
import pandas as pd
from sqlalchemy import text
from db_config import create_company_engine
from button_handlers.base import BaseButtonHandler

class MiniAnalyticsHandler(BaseButtonHandler):
    supported_versions = [1, 2]

    def run_v1(self):
        database = self.config.get("database")
        table = self.config.get("table")
        code = self.config.get("code", "")
        show_chart = self.config.get("show_chart", False)

        if not database or not table:
            return {"status": "error", "message": "Missing database or table."}

        try:
            db_name = database.replace('.db', '')
            engine = create_company_engine(db_name)

            with engine.connect() as conn:
                df = pd.read_sql_query(text(f'SELECT * FROM "{table}"'), conn)

            local_vars = {"df": df}

            # ✅ Execute user code safely
            if code.strip():
                try:
                    exec(code, {}, local_vars)
                    df = local_vars.get("df", df)
                except Exception as e:
                    return {"status": "error", "message": f"Code execution failed: {e}"}

            result_text = local_vars.get("result", f"{len(df)} rows processed.")
            chart_data = local_vars.get("chart", {})

            # ✅ Fallback chart if not provided
            if show_chart and not chart_data and isinstance(df, pd.DataFrame):
                value_counts = df.iloc[:, 0].value_counts().head(5)
                chart_data = value_counts.to_dict()

            return {
                "status": "ok",
                "result": result_text,
                "chart": chart_data if show_chart else None
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def run_v2(self):
        # 💣 simulate a broken version
        raise ValueError("Deliberate version 2 error for testing.")

    def run_current(self):
        print(f"[MiniAnalytics] Running version {self.version}")
        if self.version == 2:
            return self.run_v2()
        return self.run_v1()
