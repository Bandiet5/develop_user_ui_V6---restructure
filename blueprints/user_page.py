# blueprints/user_page.py

from flask import Blueprint, request, jsonify
import sqlite3
import os
import pandas as pd
from multiprocessing import Process, Manager
import traceback


user_page_bp = Blueprint('user_page', __name__)
DATA_FOLDER = os.path.join(os.getcwd(), 'data')

@user_page_bp.route('/run_mini_analytics', methods=['POST'])
def run_mini_analytics():
    """Background process: Run simple Python code on table, return result."""
    print('Start mini_analytics')
    try:
        data = request.json
        db = data.get('database')
        table = data.get('table')
        code = data.get('code')
        return_chart = data.get('return_chart', False)

        if not db or not table or not code:
            return jsonify({'status': 'error', 'message': 'Missing required fields.'})

        db_path = os.path.join(DATA_FOLDER, db)
        if not os.path.isfile(db_path):
            return jsonify({'status': 'error', 'message': 'Database file not found.'})

        # 👨‍💻 Small in-memory background processing
        manager = Manager()
        result_holder = manager.dict()

        p = Process(target=process_mini_analytics, args=(db_path, table, code, return_chart, result_holder))
        p.start()
        p.join(10)  # safety timeout 10 sec

        if p.is_alive():
            p.terminate()
            return jsonify({'status': 'error', 'message': 'Analytics timed out.'})

        return jsonify(result_holder.copy())

    except Exception as e:
        print('❌ Error running mini analytics:', e)
        return jsonify({'status': 'error', 'message': str(e)})



def process_mini_analytics(db_path, table, code, return_chart, result_holder):
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
        conn.close()

        local_vars = {'df': df}
        exec(code, {}, local_vars)

        df = local_vars.get('df', df)
        result_text = local_vars.get('result', '')

        result_holder['status'] = 'ok'
        result_holder['result'] = str(result_text)

        if return_chart and 'chart' in local_vars:
            result_holder['chart'] = local_vars['chart']  # developer must prepare chart data

    except Exception as e:
        traceback.print_exc()
        result_holder['status'] = 'error'
        result_holder['message'] = str(e)



