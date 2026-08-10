#!/bin/bash
set -e
CURSOR=""; OUT=../data/issues.jsonl; : > $OUT; PAGE=0
while : ; do
  PAGE=$((PAGE+1))
  if [ -z "$CURSOR" ]; then AFTER="null"; else AFTER="\"$CURSOR\""; fi
  RESP=$(gh api graphql -f query="
  { repository(owner: \"oven-sh\", name: \"bun\") {
      issues(first: 100, orderBy: {field: CREATED_AT, direction: DESC}, after: $AFTER) {
        pageInfo { hasNextPage endCursor }
        nodes { number createdAt closedAt state stateReason title
                author { login } labels(first: 20) { nodes { name } } }
      } } }")
  echo "$RESP" | jq -c '.data.repository.issues.nodes[]' >> $OUT
  OLDEST=$(echo "$RESP" | jq -r '.data.repository.issues.nodes[-1].createdAt')
  HASNEXT=$(echo "$RESP" | jq -r '.data.repository.issues.pageInfo.hasNextPage')
  CURSOR=$(echo "$RESP" | jq -r '.data.repository.issues.pageInfo.endCursor')
  if [[ "$OLDEST" < "2025-11-01" ]] || [ "$HASNEXT" != "true" ]; then break; fi
done
echo "fetched $(wc -l < $OUT) issues, oldest $OLDEST"
