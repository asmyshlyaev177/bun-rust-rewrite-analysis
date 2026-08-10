#!/bin/bash
set -e
CURSOR=""; OUT=../data/bodies.jsonl; : > $OUT
while : ; do
  if [ -z "$CURSOR" ]; then AFTER="null"; else AFTER="\"$CURSOR\""; fi
  RESP=$(gh api graphql -f query="
  { repository(owner: \"oven-sh\", name: \"bun\") {
      issues(first: 60, orderBy: {field: CREATED_AT, direction: DESC}, after: $AFTER) {
        pageInfo { hasNextPage endCursor }
        nodes { number createdAt title bodyText }
      } } }")
  echo "$RESP" | jq -c '.data.repository.issues.nodes[] | {n:.number,d:.createdAt,t:.title,b:(.bodyText // "" | .[0:2500])}' >> $OUT
  OLDEST=$(echo "$RESP" | jq -r '.data.repository.issues.nodes[-1].createdAt')
  HASNEXT=$(echo "$RESP" | jq -r '.data.repository.issues.pageInfo.hasNextPage')
  CURSOR=$(echo "$RESP" | jq -r '.data.repository.issues.pageInfo.endCursor')
  if [[ "$OLDEST" < "2025-11-10" ]] || [ "$HASNEXT" != "true" ]; then break; fi
done
echo "fetched $(wc -l < $OUT), oldest $OLDEST"
