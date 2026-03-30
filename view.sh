#!/bin/sh
pip3 install -q markdown 2>/dev/null

python3 build.py "$@"

# Watch for changes and rebuild in the background
(while inotifywait -q -r -e modify,create,delete,move posts/ template.html style.css 2>/dev/null; do
    echo "Change detected, rebuilding..."
    python3 build.py "$@"
done) &
WATCH_PID=$!

python3 -m http.server -d _site 8000

kill $WATCH_PID 2>/dev/null
