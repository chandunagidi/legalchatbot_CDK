#!/bin/bash
URL="https://2gkz4tdltabermoj7qkyt5mkrq0qblru.lambda-url.ap-southeast-2.on.aws/"
C="ENERGOUSCORP_03_16_2017-EX-10.24-STRATEGIC ALLIANCE AGREEMENT"

ask() {
  local payload
  payload=$(python3 -c 'import json,sys; print(json.dumps({"question": sys.argv[1], "contract": sys.argv[2]}))' "$1" "$2")
  echo "Q: $1  [contract: ${2:-none}]"
  curl -s -X POST "$URL" -H "Content-Type: application/json" -d "$payload" \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print("A:", d.get("answer") or d)'
  echo "------------------------------------------"
}

ask "Does this agreement allow termination for convenience? Under what notice?" "$C"
ask "Does this agreement include a most favored nation clause?" "$C"
ask "Is there a liquidated damages provision?" "$C"
ask "Does this agreement include source code escrow?" "$C"
ask "What is the capital of France?" "$C"
ask "What is the governing law?" "DOES_NOT_EXIST"
ask "What is the governing law of the EDGE and FTE Networks Strategic Alliance Agreement?" ""