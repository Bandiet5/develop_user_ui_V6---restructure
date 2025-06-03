from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from db_config import get_app_engine, get_postgres_admin_engine

users_bp = Blueprint('users', __name__)

def ensure_app_database_exists():
    try:
        engine = get_app_engine()
        with engine.connect():
            print("[INIT] app_data DB exists.")
    except OperationalError:
        print("[INIT] app_data DB not found. Creating it...")
        admin_engine = get_postgres_admin_engine()
        with admin_engine.connect() as conn:
            conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                text('CREATE DATABASE app_data')
            )
        print("[INIT] app_data DB created.")

# ✅ Ensure the users table exists
def init_users_table():
    ensure_app_database_exists()
    engine = get_app_engine()
    with engine.connect() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL
            )
        '''))
        conn.commit()

# ✅ View all users
@users_bp.route('/users')
def manage_users():
    engine = get_app_engine()  # now initialized safely
    with engine.connect() as conn:
        result = conn.execute(text('SELECT id, username, role FROM users'))
        users = result.fetchall()
    return render_template('user_list.html', users=users)

# ✅ Create a new user
@users_bp.route('/create_user', methods=['GET', 'POST'])
def create_user():
    engine = get_app_engine()
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        role = request.form.get('role').strip()

        if not username or not password or not role:
            flash("All fields are required.")
            return redirect(url_for('users.create_user'))

        try:
            with engine.connect() as conn:
                conn.execute(text('''
                    INSERT INTO users (username, password, role)
                    VALUES (:username, :password, :role)
                '''), {
                    'username': username,
                    'password': password,
                    'role': role
                })
                conn.commit()
            flash("User created successfully.")
            return redirect(url_for('users.manage_users'))
        except Exception as e:
            if 'duplicate key' in str(e).lower():
                flash("Username already exists.")
            else:
                flash(f"Error: {e}")
            return redirect(url_for('users.create_user'))

    return render_template('create_user.html')

# ✅ Delete a user
@users_bp.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    engine = get_app_engine()
    with engine.connect() as conn:
        conn.execute(text('DELETE FROM users WHERE id = :id'), {'id': user_id})
        conn.commit()
    flash("User deleted.")
    return redirect(url_for('users.manage_users'))
