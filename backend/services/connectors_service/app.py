from __future__ import annotations

import os
from typing import Any, Dict, List

import psycopg
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field


app = FastAPI(title="Pangents Connectors Service", version="0.1.0")


class PostgresConfig(BaseModel):
    host: str
    port: int = 5432
    database: str
    user: str
    password: str
    sslmode: str | None = Field(default=None, description="prefer, require, disable, etc.")


# In-memory store for demo; replace with DB in production
TENANT_PG: Dict[str, PostgresConfig] = {}


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "tenants": len(TENANT_PG)}


@app.post("/tenants/{tenant_id}/postgres")
async def register_postgres(tenant_id: str, cfg: PostgresConfig):
    TENANT_PG[tenant_id] = cfg
    # attempt a quick connection check
    try:
        await _test_connection(cfg)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Connection failed: {exc}")
    return {"status": "registered"}


async def _test_connection(cfg: PostgresConfig) -> None:
    conn_str = _dsn(cfg)
    async with await psycopg.AsyncConnection.connect(conn_str) as conn:  # type: ignore[attr-defined]
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")


def _dsn(cfg: PostgresConfig) -> str:
    parts = [
        f"host={cfg.host}",
        f"port={cfg.port}",
        f"dbname={cfg.database}",
        f"user={cfg.user}",
        f"password={cfg.password}",
    ]
    if cfg.sslmode:
        parts.append(f"sslmode={cfg.sslmode}")
    return " ".join(parts)


@app.get("/tenants/{tenant_id}/postgres/metadata")
async def metadata(tenant_id: str):
    cfg = TENANT_PG.get(tenant_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="No Postgres registered for tenant")
    conn_str = _dsn(cfg)
    async with await psycopg.AsyncConnection.connect(conn_str) as conn:  # type: ignore[attr-defined]
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT table_schema, table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema NOT IN ('pg_catalog','information_schema')
                ORDER BY table_schema, table_name, ordinal_position
                """
            )
            rows = await cur.fetchall()
    meta: Dict[str, Dict[str, List[Dict[str, str]]]] = {}
    for schema, table, col, dtype in rows:
        meta.setdefault(schema, {}).setdefault(table, []).append({"name": col, "type": dtype})
    return meta


class Query(BaseModel):
    sql: str
    params: Dict[str, Any] | None = None


@app.post("/tenants/{tenant_id}/postgres/query")
async def run_query(tenant_id: str, q: Query, request: Request):
    # In a real system, validate SQL against metadata/allowlist; here we pass-through
    cfg = TENANT_PG.get(tenant_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="No Postgres registered for tenant")
    conn_str = _dsn(cfg)
    async with await psycopg.AsyncConnection.connect(conn_str) as conn:  # type: ignore[attr-defined]
        async with conn.cursor(binary=True) as cur:  # return dict-like rows later if needed
            try:
                await cur.execute(q.sql, q.params or None)
                if cur.description:
                    cols = [d.name for d in cur.description]
                    rows = await cur.fetchall()
                    data = [dict(zip(cols, r)) for r in rows]
                else:
                    data = {"rowcount": cur.rowcount}
            except Exception as exc:  # noqa: BLE001
                raise HTTPException(status_code=400, detail=str(exc))
    return {"data": data}


