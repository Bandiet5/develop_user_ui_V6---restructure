import os
import pandas as pd
from io import StringIO
from contextlib import redirect_stdout
from sqlalchemy import text
from db_config import create_company_engine
from button_handlers.base import BaseButtonHandler

class SmartTableHandler(BaseButtonHandler):
    supported_versions = [1]

    def run_v1(self):
        export_db = self.config.get("database")           # ✅ Now treated as export target
        export_table = self.config.get("table")           # ✅ User-provided name
        cell_code = self.config.get("cell_code", {})
        compare_rules = self.config.get("compare_rules", [])
        rows = int(self.config.get("rows", 3))
        columns = int(self.config.get("columns", 3))

        if not export_db or not export_table:
            return {"status": "error", "message": "Missing export database or table name."}

        try:
            db_name = export_db.replace(".db", "")
            engine = create_company_engine(db_name)

            df_dummy = pd.DataFrame({"placeholder": [1]})  # empty df for logic context
            cell_outputs = {}
            highlight_cells = set()

            # ✅ Step 1: Evaluate cells top-to-bottom left-to-right
            ordered_cells = sorted(cell_code.keys(), key=lambda cid: (int(cid[1]), int(cid[3])))

            for cell_id in ordered_cells:
                code = cell_code.get(cell_id, "").strip()
                if not code:
                    continue

                # Build local namespace with previous cell outputs as R1C1, R2C2, etc.
                local_vars = {"df": df_dummy.copy()}
                for ref_id, val in cell_outputs.items():
                    try:
                        local_vars[ref_id] = float(val)
                    except:
                        local_vars[ref_id] = val

                f = StringIO()
                try:
                    with redirect_stdout(f):
                        exec(code, {}, local_vars)
                    output = f.getvalue().strip()
                    cell_outputs[cell_id] = output or "✅"
                except Exception as e:
                    cell_outputs[cell_id] = f"❌ {str(e)}"

            # ✅ Step 2: Highlight mismatched cells
            for rule in compare_rules:
                if isinstance(rule, list) and len(rule) == 2:
                    val1 = str(cell_outputs.get(rule[0], "")).strip()
                    val2 = str(cell_outputs.get(rule[1], "")).strip()
                    if val1 != val2:
                        highlight_cells.add(rule[0])
                        highlight_cells.add(rule[1])

            # ✅ Step 3: Export summary to DB
            export_data = []
            for cell_id, value in cell_outputs.items():
                export_data.append({
                    "cell": cell_id,
                    "value": value,
                    "highlight": cell_id in highlight_cells
                })

            df_export = pd.DataFrame(export_data)
            df_export.to_sql(export_table, engine, if_exists="replace", index=False)

            return {
                "status": "ok",
                "result": f"{len(cell_outputs)} cells evaluated and exported",
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
