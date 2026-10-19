#!/usr/bin/env bash
# Guided demo. Start the stack first:  docker compose up --build
set -u
GW="${GATEWAY_URL:-http://localhost:8000}"
UP="${UPSTREAM_URL:-http://localhost:9000}"
RUN="$RANDOM"

bold() { printf "\n\033[1m== %s ==\033[0m\n" "$*"; }

# Print the status codes of N requests on one line.
codes() {
  local n="$1" url="$2"; shift 2
  for _ in $(seq "$n"); do printf "%s " "$(curl -s -o /dev/null -w '%{http_code}' "$@" "$url")"; done
  echo
}

token() { # token <user> <plan>
  curl -s -X POST "$GW/auth/demo-token" -H 'Content-Type: application/json' \
    -d "{\"sub\":\"$1\",\"plan\":\"$2\"}" | sed -E 's/.*"access_token":"([^"]+)".*/\1/'
}

# Start from empty buckets so the demo is repeatable (needs docker compose; ignored otherwise).
docker compose exec -T redis redis-cli flushall >/dev/null 2>&1 || true

bold "1. The demo service on its own has no protection (30 requests, straight to :9000)"
codes 30 "$UP/orders"

bold "2. Same API through the gateway, anonymous (limit: 5 per IP)"
codes 8 "$GW/orders"
echo "Headers on a blocked request:"
curl -s -D - -o /dev/null "$GW/orders" | grep -iE '^(HTTP|retry-after|x-ratelimit)'

bold "3. A bad token is rejected before it costs a rate limit token"
curl -s -w '  -> HTTP %{http_code}\n' "$GW/orders" -H 'Authorization: Bearer not.a.real.token'

bold "4. Plans: free allows 10 requests per minute, pro allows 100 (12 requests each)"
FREE=$(token "alice-$RUN" free); PRO=$(token "carol-$RUN" pro)
printf "free: "; codes 12 "$GW/orders" -H "Authorization: Bearer $FREE"
printf "pro:  "; codes 12 "$GW/orders" -H "Authorization: Bearer $PRO"

bold "5. What the upstream sees: identity headers added, the token itself stripped"
curl -s "$GW/orders/whoami" -H "Authorization: Bearer $PRO"; echo

bold "6. Concurrency: 200 simultaneous requests from one free user"
python3 "$(dirname "$0")/load_test.py" "$GW/orders" -n 200 -c 50 --user "bob-$RUN" --plan free

echo
echo "Expect exactly 10 x HTTP 200 above. That is the atomic Lua token bucket at work."
