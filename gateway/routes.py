"""Route table: longest-prefix match from request path to upstream base URL."""
from __future__ import annotations

import os
from dataclasses import dataclass
from string import Template

import yaml

DEFAULT_ENV = {"DEMO_UPSTREAM": "http://localhost:9000"}


@dataclass(frozen=True)
class Route:
    prefix: str
    upstream: str


class RouteTable:
    def __init__(self, routes: list[Route]) -> None:
        # Longest prefix first so /orders/special beats /orders.
        self._routes = sorted(routes, key=lambda r: len(r.prefix), reverse=True)

    @classmethod
    def from_file(cls, path: str, env: dict[str, str] | None = None) -> RouteTable:
        values = {**DEFAULT_ENV, **(os.environ if env is None else env)}
        with open(path, encoding="utf-8") as fh:
            raw = Template(fh.read()).safe_substitute(values)
        data = yaml.safe_load(raw) or {}
        routes = [
            Route(prefix=item["prefix"].rstrip("/") or "/", upstream=item["upstream"].rstrip("/"))
            for item in data.get("routes", [])
        ]
        if not routes:
            raise ValueError(f"No routes defined in {path}")
        return cls(routes)

    def match(self, path: str) -> Route | None:
        for route in self._routes:
            if route.prefix == "/" or path == route.prefix or path.startswith(route.prefix + "/"):
                return route
        return None
