from fastmcp import FastMCP
import psycopg2

import dotenv
import os

dotenv.load_dotenv()

mcp = FastMCP("DB-Infrastructure")

DB_URL = os.getenv("DB_URL")

@mcp.tool()
def list_tables():
    """"Lista as tabelas disponíveis no esquema público do banco de dados."""
    conn = psycopg2.connect(DB_URL)
    with conn.cursor() as cur:
        conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        return [row for row in cur.fetchall()]

@mcp.tool()
def get_schema(table_name: str):
    """Retorna o esquema de uma tabela específica."""
    conn = psycopg2.connect(DB_URL)
    with conn.cursor() as cur:
        cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}';")
        return [row for row in cur.fetchall()]
    
if __name__ == "__main__":
    mcp.run()