#!/usr/bin/env python3
"""Fire many concurrent requests and summarize the status codes.

  python scripts/load_test.py http://localhost:9000/orders -n 200        # unprotected service
  python scripts/load_test.py http://localhost:8000/orders -n 200 --user alice --plan free
"""
import argparse
import asyncio
import collections
import statistics
import time

import httpx


async def get_token(base: str, user: str, plan: str) -> str:
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{base}/auth/demo-token", json={"sub": user, "plan": plan})
        r.raise_for_status()
        return r.json()["access_token"]


async def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("url")
    p.add_argument("-n", type=int, default=200, help="total requests")
    p.add_argument("-c", type=int, default=50, help="concurrency")
    p.add_argument("--user", help="get a demo token for this user (gateway must run with DEMO_MODE)")
    p.add_argument("--plan", default="free", choices=["free", "pro"])
    args = p.parse_args()

    headers = {}
    if args.user:
        base = args.url.split("/", 3)
        base = "/".join(base[:3])
        headers["Authorization"] = f"Bearer {await get_token(base, args.user, args.plan)}"

    codes: collections.Counter = collections.Counter()
    latencies: list[float] = []
    sem = asyncio.Semaphore(args.c)

    async with httpx.AsyncClient(headers=headers, timeout=10) as client:

        async def one() -> None:
            async with sem:
                t = time.perf_counter()
                try:
                    status = (await client.get(args.url)).status_code
                except httpx.HTTPError:
                    status = "error"
                latencies.append((time.perf_counter() - t) * 1000)
                codes[status] += 1

        start = time.perf_counter()
        await asyncio.gather(*[one() for _ in range(args.n)])
        elapsed = time.perf_counter() - start

    print(f"{args.n} requests, concurrency {args.c}, {elapsed:.2f}s ({args.n / elapsed:.0f} req/s)")
    for code, count in sorted(codes.items(), key=lambda kv: str(kv[0])):
        print(f"  HTTP {code}: {count}")
    latencies.sort()
    print(f"  latency ms: p50={statistics.median(latencies):.1f} "
          f"p95={latencies[int(len(latencies) * 0.95) - 1]:.1f}")


if __name__ == "__main__":
    asyncio.run(main())
