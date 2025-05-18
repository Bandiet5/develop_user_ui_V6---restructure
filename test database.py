import sqlite3
conn = sqlite3.connect("data/Supreme.db")
cursor = conn.execute("PRAGMA table_info(bank_master)")
for row in cursor.fetchall():
    print(row)
conn.close()
