"""A tiny in-memory orders API with no authentication or rate limiting of its own.

Run with:  uvicorn demo_service.main:app --port 9000
"""
from __future__ import annotations

import asyncio
import itertools

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Demo Orders Service")

_ids = itertools.count(1)
_orders: dict[int, dict] = {}


class OrderIn(BaseModel):
    item: str
    quantity: int = 1


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/orders")
async def list_orders():
    return list(_orders.values())


@app.post("/orders", status_code=201)
async def create_order(order: OrderIn, x_user_id: str | None = Header(default=None)):
    order_id = next(_ids)
    _orders[order_id] = {"id": order_id, "owner": x_user_id, **order.model_dump()}
    return _orders[order_id]


@app.get("/orders/whoami")
async def whoami(
    x_user_id: str | None = Header(default=None),
    x_user_plan: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    """Shows what identity headers the gateway passed along."""
    return {
        "user": x_user_id,
        "plan": x_user_plan,
        "authorization_header_received": authorization is not None,
    }


@app.get("/orders/slow")
async def slow(delay: float = 1.0):
    await asyncio.sleep(min(delay, 30))
    return {"slept": delay}


@app.get("/orders/{order_id}")
async def get_order(order_id: int):
    if order_id not in _orders:
        raise HTTPException(status_code=404, detail="order not found")
    return _orders[order_id]
