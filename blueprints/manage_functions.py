from flask import Blueprint, render_template, request, redirect, url_for, flash
import os

manage_functions_bp = Blueprint("manage_functions", __name__)
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploaded_code")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@manage_functions_bp.route('/developer/manage_functions')
def manage_functions():
    files = [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith('.py')]
    return render_template('manage_functions.html', files=files)

@manage_functions_bp.route('/developer/upload_function', methods=["POST"])
def upload_function():
    file = request.files.get("file")
    if not file or not file.filename.endswith(".py"):
        flash("Please upload a valid .py file")
        return redirect(url_for("manage_functions.manage_functions"))

    file.save(os.path.join(UPLOAD_FOLDER, file.filename))
    flash("✅ Python file uploaded.")
    return redirect(url_for("manage_functions.manage_functions"))

@manage_functions_bp.route('/developer/edit_function/<filename>')
def edit_function(filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.isfile(file_path):
        return f"File not found: {filename}", 404

    with open(file_path, 'r') as f:
        code = f.read()
    return render_template('edit_function.html', filename=filename, code=code)

@manage_functions_bp.route('/developer/save_function/<filename>', methods=["POST"])
def save_function(filename):
    code = request.form.get("code", "")
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    try:
        with open(file_path, 'w') as f:
            f.write(code)
        flash("✅ File saved.")
    except Exception as e:
        flash(f"❌ Failed to save: {e}")
    return redirect(url_for("manage_functions.manage_functions"))
