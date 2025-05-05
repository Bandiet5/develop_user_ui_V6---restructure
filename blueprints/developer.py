# developer.py

from flask import Blueprint, render_template, session, redirect, url_for, request, flash
import os
import json

# Define the folder for storing user-created pages
PAGES_FOLDER = os.path.join(os.getcwd(), 'pages')
os.makedirs(PAGES_FOLDER, exist_ok=True)

# Register blueprint
developer_bp = Blueprint('developer', __name__)

# ------------------ Routes ------------------

@developer_bp.route('/developer')
def developer_dashboard():
    print('[ROUTE] developer_dashboard')
    """ Developer Dashboard - Shows list of available pages """
    if session.get('username') != 'developer':
        flash("Unauthorized access.")
        return redirect(url_for('login'))

    # Load list of saved pages
    pages = [f.replace('.json', '') for f in os.listdir(PAGES_FOLDER) if f.endswith('.json')]
    return render_template('developer.html', pages=pages)


@developer_bp.route('/create_page', methods=['POST'])
def create_page():
    print('[ROUTE] create_page')
    if session.get('username') != 'developer':
        return redirect(url_for('login'))

    page_name = request.form.get('page_name', '').strip().replace(' ', '_')
    if not page_name:
        flash("Page name is required.")
        return redirect(url_for('developer.developer_dashboard'))

    page_path = os.path.join(PAGES_FOLDER, f"{page_name}.json")
    if not os.path.exists(page_path):
        with open(page_path, 'w') as f:
            json.dump([], f)
        flash(f"Page '{page_name}' created.")
    else:
        flash("Page already exists.")

    # ✅ Redirect to the edit page directly after creation
    return redirect(url_for('edit_page.edit_page', page_name=page_name))

@developer_bp.route('/delete_page/<page_name>', methods=['POST'])
def delete_page(page_name):
    print(f"[ROUTE] delete_page: {page_name}")
    if session.get('username') != 'developer':
        flash("Unauthorized.")
        return redirect(url_for('login'))

    file_path = os.path.join(PAGES_FOLDER, f"{page_name}.json")
    if os.path.exists(file_path):
        os.remove(file_path)
        flash(f"Page '{page_name}' deleted.")
    else:
        flash(f"Page '{page_name}' does not exist.")

    return redirect(url_for('developer.developer_dashboard'))
