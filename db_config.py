from sqlalchemy import create_engine

BASE_URL = "postgresql://postgres:P!et25904558@localhost:5432/"

def get_postgres_admin_engine():
    return create_engine(f"{BASE_URL}postgres", isolation_level="AUTOCOMMIT")

def create_company_engine(company_name: str):
    return create_engine(f"{BASE_URL}{company_name}", echo=False)

def get_app_engine():
    return create_engine(f"{BASE_URL}app_data", echo=False)
