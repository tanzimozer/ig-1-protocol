#!/bin/bash
# IG1 Protocol launcher — spins one process per city
# Usage: bash ig1_launch.sh [city1 city2 ...] or no args for all 14

CITIES=("Melbourne" "Sydney" "London" "Tallinn" "Brisbane" "Anchorage" "Edmonton" "Dallas" "Chicago" "Salt Lake City" "Portland" "Warsaw" "Kyiv" "Moscow")

if [ "$#" -gt 0 ]; then
    CITIES=("$@")
fi

LOG_DIR="$HOME/.hermes/ig1/logs"
mkdir -p "$LOG_DIR"

echo "Launching IG1 — ${#CITIES[@]} cities"

for city in "${CITIES[@]}"; do
    safe="${city// /_}"
    logfile="$LOG_DIR/${safe,,}.log"
    python3 -u "$HOME/.hermes/ig1/ig1_crawl.py" "$city" > "$logfile" 2>&1 &
    echo "  [$!] $city → $logfile"
    sleep 1
done

echo "All agents launched. Monitor with: tail -f ~/.hermes/ig1/logs/*.log"
