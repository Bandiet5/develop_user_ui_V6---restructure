import os
import sqlite3
import pandas as pd
from io import StringIO
from contextlib import redirect_stdout
from button_handlers.base import BaseButtonHandler

class SmartTableHandler(BaseButtonHandler):
    supported_versions = [1]

    def run_v1(self):
        db = self.config.get("database")
        table = self.config.get("table")
        cell_code = self.config.get("cell_code", {})
        compare_rules = self.config.get("compare_rules", [])
        rows = int(self.config.get("rows", 3))
        columns = int(self.config.get("columns", 3))

        if not db or not table:
            return {"status": "error", "message": "Missing database or table."}

        try:
            path = os.path.join("data", db)
            conn = sqlite3.connect(path)
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
            conn.close()

            cell_outputs = {}
            highlight_cells = set()

            # ✅ Run each cell's code and capture output
            for cell_id, code in cell_code.items():
                if not code.strip():
                    continue

                local_vars = {"df": df.copy()}
                f = StringIO()

                try:
                    with redirect_stdout(f):
                        exec(code, {}, local_vars)
                    output = f.getvalue().strip()
                    cell_outputs[cell_id] = output or "✅"
                except Exception as e:
                    cell_outputs[cell_id] = f"❌ {str(e)}"

            # ✅ Compare specified cells
            for rule in compare_rules:
                if not isinstance(rule, list) or len(rule) != 2:
                    continue
                cell1, cell2 = rule
                val1 = str(cell_outputs.get(cell1, "")).strip()
                val2 = str(cell_outputs.get(cell2, "")).strip()
                if val1 != val2:
                    highlight_cells.add(cell1)
                    highlight_cells.add(cell2)

            return {
                "status": "ok",
                "result": f"{len(cell_outputs)} cells evaluated",
                "table": {
                    "rows": rows,
                    "columns": columns,
                    "cells": cell_outputs,
                    "highlight": list(highlight_cells)
                }
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def run_current(self):
        return self.run_v1()
