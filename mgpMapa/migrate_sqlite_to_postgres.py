"""
One-time migration script: SQLite → PostgreSQL
Usage:
    SQLITE_PATH=./instance/database.db DATABASE_URL=postgresql://... python migrate_sqlite_to_postgres.py
"""
import os
import sqlite3

import psycopg2
from dotenv import load_dotenv

load_dotenv()

SQLITE_PATH = os.getenv('SQLITE_PATH', './instance/database.db')
DATABASE_URL = os.getenv('DATABASE_URL', '')

if not DATABASE_URL or not DATABASE_URL.startswith('postgresql'):
    print('ERROR: Set DATABASE_URL to a postgresql:// connection string')
    exit(1)

if not os.path.exists(SQLITE_PATH):
    print(f'ERROR: SQLite file not found at {SQLITE_PATH}')
    exit(1)

TABLES = [
    'organizacao',
    'usuario',
    'registos',
    'servicos',
    'tipos_servico',
    'faturas',
    'ferias',
    'mensagens',
    'horastrabalhadas',
    'orcamentos',
    'push_subscriptions',
    'obras',
    'obra_funcionario',
    'notificacoes',
    'config_ferias_ano',
]

sqlite_conn = sqlite3.connect(SQLITE_PATH)
sqlite_conn.row_factory = sqlite3.Row
sqlite_cur = sqlite_conn.cursor()

pg_conn = psycopg2.connect(DATABASE_URL)
pg_conn.autocommit = False
pg_cur = pg_conn.cursor()


def get_boolean_columns(pg_cur, table):
    """Return set of column names that are boolean in Postgres."""
    pg_cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s AND data_type = 'boolean'
    """, (table,))
    return {row[0] for row in pg_cur.fetchall()}


def cast_row(row, columns, bool_cols):
    """Cast 0/1 integers to True/False for boolean columns."""
    result = []
    for col, val in zip(columns, row):
        if col in bool_cols and val is not None:
            result.append(bool(val))
        else:
            result.append(val)
    return result


print('Starting migration...')

# Disable FK checks for the session so we can insert in any order
pg_cur.execute('SET session_replication_role = replica;')
pg_conn.commit()

for table in TABLES:
    sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    if not sqlite_cur.fetchone():
        print(f'  Skipping {table} (not in SQLite)')
        continue

    pg_cur.execute("SELECT to_regclass(%s)", (f'public.{table}',))
    if not pg_cur.fetchone()[0]:
        print(f'  Skipping {table} (not in Postgres)')
        continue

    # Clear existing data to avoid conflicts on re-run
    pg_cur.execute(f'TRUNCATE TABLE {table} CASCADE')
    pg_conn.commit()

    sqlite_cur.execute(f'SELECT * FROM {table}')
    rows = sqlite_cur.fetchall()
    if not rows:
        print(f'  {table}: empty, skipping')
        continue

    columns = [desc[0] for desc in sqlite_cur.description]
    bool_cols = get_boolean_columns(pg_cur, table)
    placeholders = ', '.join(['%s'] * len(columns))
    cols_str = ', '.join(f'"{c}"' for c in columns)
    insert_sql = f'INSERT INTO {table} ({cols_str}) VALUES ({placeholders})'

    count = 0
    errors = 0
    for row in rows:
        try:
            casted = cast_row(list(row), columns, bool_cols)
            pg_cur.execute(insert_sql, casted)
            count += 1
        except Exception as e:
            print(f'    Row error in {table}: {e}')
            pg_conn.rollback()
            errors += 1

    pg_conn.commit()
    print(f'  {table}: {count} rows migrated{f", {errors} errors" if errors else ""}')

    # Reset auto-increment sequences
    pg_cur.execute(f"""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = '{table}' AND column_default LIKE 'nextval%%'
    """)
    for (col,) in pg_cur.fetchall():
        pg_cur.execute(f"SELECT setval(pg_get_serial_sequence('{table}', '{col}'), COALESCE((SELECT MAX({col}) FROM {table}), 1))")
    pg_conn.commit()

# Re-enable FK checks
pg_cur.execute('SET session_replication_role = DEFAULT;')
pg_conn.commit()

sqlite_conn.close()
pg_conn.close()
print('\nMigration complete.')