from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

# Replace with your actual credentials
BASE_URL = "postgresql://postgres:P!et25904558@localhost:5432/"
admin_engine = create_engine(f"{BASE_URL}postgres", echo=False)

def list_all_databases_and_tables():
    try:
        with admin_engine.connect() as conn:
            result = conn.execute(text("SELECT datname FROM pg_database WHERE datistemplate = false"))
            db_names = [row[0] for row in result if row[0] not in ['postgres']]

        for db_name in db_names:
            print(f"\n📁 Database: {db_name}")
            try:
                engine = create_engine(f"{BASE_URL}{db_name}", echo=False)
                inspector = inspect(engine)
                table_names = inspector.get_table_names(schema="public")

                if not table_names:
                    print("  (no tables)")
                for table in table_names:
                    print(f"  📄 Table: {table}")
            except SQLAlchemyError as e:
                print(f"  ⚠️ Error accessing {db_name}: {e}")

    except Exception as e:
        print(f"❌ Failed to list databases: {e}")

list_all_databases_and_tables()
