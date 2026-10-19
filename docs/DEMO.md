# How to demo this project

A 3 minute walkthrough for an interview, a call, or a screen share.

## Before you start (once)

- Run `docker compose up --build` and wait for the gateway to report healthy.
- Open two terminal windows side by side: one for `bash scripts/demo.sh`, one for `docker compose logs -f gateway`.
- Increase the terminal font size. Do a dry run so nothing surprises you.
- Have `gateway/token_bucket.lua` open in your editor, scrolled to the top.

## Talk track

**0:00 to 0:20. The problem.** "APIs need protection from too many requests. I built a gateway that
sits in front of a service, checks who you are with a JWT, and limits how fast you can call it."

**0:20 to 0:50. Scene 1, the unprotected service.** Run the demo. "Thirty requests straight to the
service, all succeed. Nothing stops a client from hammering it."

**0:50 to 1:30. Scenes 2 to 4, the gateway at work.** "Through the gateway, an anonymous caller gets
five requests and then a 429 with a Retry-After header. A bad token gets a 401 and never touches
Redis. A free user gets ten, a pro user gets a hundred, because the plan lives inside the token."

**1:30 to 2:30. Scene 6, the part that matters.** "Now 200 requests at once from one user. Exactly ten
succeed. Most naive limiters let more through here, because several requests read the same count
before any of them writes." Switch to the Lua file. "I do the refill, check and decrement inside one
Lua script, and Redis runs a script without interleaving anything else. I also use Redis's own clock,
so several gateway instances cannot disagree about time."

**2:30 to 3:00. Quality.** Show the green CI badge and run `pytest -q`. "47 tests, including a 200
concurrent request test and JWT forgery attempts. I broke the Lua on purpose to confirm those tests
fail when they should. CI runs them against a real Redis."

## Likely questions, and honest answers

**Why a token bucket and not a fixed window?** A fixed window allows a double burst at the boundary
(10 at 11:59:59 and 10 at 12:00:00). A bucket refills smoothly and still allows a controlled burst.

**What if Redis goes down?** It is configurable. Default is fail open, which keeps the API available
and marks responses `X-RateLimit-Status: degraded`. Fail closed returns 503. Which is right depends
on whether availability or abuse protection matters more. There is a test for both.

**How would this scale?** The gateway is stateless, so add instances. All state is one hash per
caller in Redis, and the script touches one key, so it also works on Redis Cluster.

**Why not use Kong or Nginx?** For production, probably use one of those. This project is about
understanding what they do internally. Be upfront about that.

**What would you change for production?** RS256 with a key set instead of a shared secret, a trusted
proxy setting for client IPs, streaming responses, metrics (Prometheus), and per-route limits.

**What was the hardest part?** Pick something real from the build. Good candidates: Redis truncating
floats returned from Lua (so they are returned as strings), and deciding that auth runs before the
rate limit so invalid tokens cost nothing.

## Things to avoid

- Do not claim performance numbers you did not measure on your own hardware.
- Do not say it is "production ready". Say it is production shaped, and name the limitations.
