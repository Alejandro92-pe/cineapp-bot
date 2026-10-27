"""Render DDL only. Does not connect to any database."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import postgresql
from security_store import metadata
from billing.schema import orders, access, receipts, assets, review_events

chosen = {orders, access, receipts, assets, review_events}
sql = ["-- Local review only. Apply AFTER 001_security.sql, never automatically.\nBEGIN;"]
for table in metadata.sorted_tables:
    if table not in chosen:
        continue
    sql.append(str(CreateTable(table, if_not_exists=True).compile(dialect=postgresql.dialect()))+";")
    for index in table.indexes:
        sql.append(str(CreateIndex(index, if_not_exists=True).compile(dialect=postgresql.dialect()))+";")
    sql.append(f"ALTER TABLE cine_security.{table.name} ENABLE ROW LEVEL SECURITY;")
    sql.append(f"REVOKE ALL ON cine_security.{table.name} FROM PUBLIC, anon, authenticated;")
sql.append("COMMIT;\n")
target = Path(__file__).resolve().parents[1]/"migrations"/"003_monthly_payments.sql"
target.write_text("\n".join(sql), encoding="utf-8")
print("Generated",target.name)
