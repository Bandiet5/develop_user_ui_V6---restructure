from sqlalchemy import create_engine, text

engine = create_engine("postgresql://postgres:P!et25904558@localhost:5432/postgres")

#with engine.connect() as conn:
#    dbs = conn.execute(text("SELECT datname FROM pg_database")).fetchall()
#    for db in dbs:
#        print(db[0])


from sqlalchemy import create_engine

BASE_URL = "postgresql://postgres:P!et25904558@localhost:5432/"

#def create_company_engine(company_name: str):
#    return create_engine(f"{BASE_URL}{company_name}", echo=True)

from sqlalchemy import create_engine, inspect

# Define connection
engine = create_engine("postgresql://postgres:P!et25904558@localhost:5432/app_data", echo=True)

# Inspector
inspector = inspect(engine)

# List tables
print("📁 Tables in 'app_data':")
for table in inspector.get_table_names(schema='public'):
    print("  📄", table)
