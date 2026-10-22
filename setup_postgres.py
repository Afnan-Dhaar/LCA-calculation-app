import psycopg

print("Connecting to PostgreSQL without password...")
conn = psycopg.connect("postgresql://postgres@127.0.0.1:5432/postgres")
conn.autocommit = True
with conn.cursor() as cur:
    print("1. Updating password for user postgres to 'afnandhaar@786'...")
    cur.execute("ALTER USER postgres WITH PASSWORD 'afnandhaar@786';")
    print("Password updated successfully!")

    print("2. Checking/creating database 'lca_db'...")
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'lca_db';")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE lca_db;")
        print("Database 'lca_db' created successfully!")
    else:
        print("Database 'lca_db' already exists!")

conn.close()

print("3. Testing direct connection to lca_db with new password...")
conn2 = psycopg.connect(
    dbname="lca_db",
    user="postgres",
    password="afnandhaar@786",
    host="127.0.0.1",
    port=5432,
)
print("SUCCESS: Authenticated and connected to lca_db with password!")
conn2.close()
