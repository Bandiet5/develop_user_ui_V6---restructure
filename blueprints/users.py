# blueprints/users.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
import sqlite3
import os

users_bp = Blueprint('users', __name__)
DB_PATH = os.path.join(os.getcwd(), 'data', 'app_data.db')

# Ensure the users table exists
def init_users_table():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# View all users
@users_bp.route('/users')
def manage_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, username, role FROM users')
    users = c.fetchall()
    conn.close()
    return render_template('user_list.html', users=users)

# Create a new user
@users_bp.route('/create_user', methods=['GET', 'POST'])
def create_user():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password').strip()
        role = request.form.get('role').strip()

        if not username or not password or not role:
            flash("All fields are required.")
            return redirect(url_for('users.create_user'))

        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', (username, password, role))
            conn.commit()
            conn.close()
            flash("User created successfully.")
            return redirect(url_for('users.manage_users'))
        except sqlite3.IntegrityError:
            flash("Username already exists.")
            return redirect(url_for('users.create_user'))

    return render_template('create_user.html')

# Delete a user
@users_bp.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    flash("User deleted.")
    return redirect(url_for('users.manage_users'))
