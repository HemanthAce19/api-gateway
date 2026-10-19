import asyncio

from gateway.ratelimit import TokenBucketLimiter


async def test_allows_up_to_capacity_then_denies(redis):
    limiter = TokenBucketLimiter(redis)
    results = [await limiter.acquire("user:a", 3, 60) for _ in range(5)]
    assert [d.allowed for d in results] == [True, True, True, False, False]
    assert [d.remaining for d in results[:3]] == [2, 1, 0]


async def test_denied_decision_has_retry_after(redis):
    limiter = TokenBucketLimiter(redis)
    for _ in range(2):
        await limiter.acquire("user:a", 2, 6)  # 6/min = 1 token per 10 seconds
    denied = await limiter.acquire("user:a", 2, 6)
    assert not denied.allowed
    assert 1 <= denied.retry_after <= 10


async def test_tokens_refill_over_time(redis):
    limiter = TokenBucketLimiter(redis)
    # 600/min = 10 tokens per second, so a short sleep restores at least one token
    assert (await limiter.acquire("user:a", 1, 600)).allowed
    assert not (await limiter.acquire("user:a", 1, 600)).allowed
    await asyncio.sleep(0.25)
    assert (await limiter.acquire("user:a", 1, 600)).allowed


async def test_refill_never_exceeds_capacity(redis):
    limiter = TokenBucketLimiter(redis)
    await limiter.acquire("user:a", 2, 6000)
    await asyncio.sleep(0.2)
    decision = await limiter.acquire("user:a", 2, 6000)
    assert decision.remaining <= 1  # capacity 2 minus the one just taken


async def test_keys_are_independent(redis):
    limiter = TokenBucketLimiter(redis)
    assert (await limiter.acquire("user:a", 1, 60)).allowed
    assert not (await limiter.acquire("user:a", 1, 60)).allowed
    assert (await limiter.acquire("user:b", 1, 60)).allowed


async def test_burst_of_200_concurrent_requests_admits_exactly_capacity(redis):
    """The reason for the Lua script: concurrency must not over-admit."""
    limiter = TokenBucketLimiter(redis)
    results = await asyncio.gather(*[limiter.acquire("user:a", 10, 10) for _ in range(200)])
    assert sum(d.allowed for d in results) == 10


async def test_two_limiter_instances_share_one_bucket(redis):
    """Models two gateway instances talking to the same Redis."""
    one, two = TokenBucketLimiter(redis), TokenBucketLimiter(redis)
    results = await asyncio.gather(
        *[(one if i % 2 else two).acquire("user:a", 10, 10) for i in range(100)]
    )
    assert sum(d.allowed for d in results) == 10


async def test_bucket_has_ttl(redis):
    limiter = TokenBucketLimiter(redis)
    await limiter.acquire("user:a", 10, 60)
    # capacity 10 at 1 token/second refills in 10s, so the TTL is 2 * 10 = 20s
    assert 0 < await redis.ttl("rl:user:a") <= 20
