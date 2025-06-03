# blueprints/user_page.py

from flask import Blueprint, request, jsonify

import os
import pandas as pd
from multiprocessing import Process, Manager
import traceback
from sqlalchemy import create_engine, text
from db_config import create_company_engine

from button_handlers.mini_analytics import MiniAnalyticsHandler


user_page_bp = Blueprint('user_page', __name__)
DATA_FOLDER = os.path.join(os.getcwd(), 'data')

@user_page_bp.route('/run_mini_analytics', methods=['POST'])
def run_mini_analytics():
    print('Start mini_analytics')
    try:
        data = request.json
        version = data.get("version", 1)  # ✅ get the correct version
        config = {
            "database": data.get("database"),
            "table": data.get("table"),
            "code": data.get("code"),
            "show_chart": data.get("return_chart", False)
        }

        if not config["database"] or not config["table"] or not config["code"]:
            return jsonify({'status': 'error', 'message': 'Missing required fields.'})

        handler = MiniAnalyticsHandler(version=version, config=config)
        result = handler.run()
        return jsonify(result)

    except Exception as e:
        print('❌ Error running mini analytics:', e)
        return jsonify({'status': 'error', 'message': str(e)})



def process_mini_analytics(db_file, table, code, return_chart, result_holder):
    try:
        db_name = db_file.replace('.db', '')
        engine = create_company_engine(db_name)

        # 🔄 Load table into DataFrame
        with engine.connect() as conn:
            df = pd.read_sql_query(text(f'SELECT * FROM "{table}"'), conn)

        # 🧠 Run user-provided code (in-memory)
        local_vars = {'df': df}
        exec(code, {}, local_vars)

        df = local_vars.get('df', df)
        result_text = local_vars.get('result', '')

        result_holder['status'] = 'ok'
        result_holder['result'] = str(result_text)

        if return_chart and 'chart' in local_vars:
            result_holder['chart'] = local_vars['chart']  # chart = dict with labels, values, etc.

    except Exception as e:
        traceback.print_exc()
        result_holder['status'] = 'error'
        result_holder['message'] = str(e)

