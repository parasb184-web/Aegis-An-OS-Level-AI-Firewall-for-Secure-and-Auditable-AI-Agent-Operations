#!/bin/bash
cd ~/aegis
python3 -m uvicorn api:app --port 8765 > /tmp/uvicorn.log 2>&1 &
pid=$!
sleep 3
echo '$ curl -s localhost:8765/counts'
curl -s localhost:8765/counts; echo
kill $pid
