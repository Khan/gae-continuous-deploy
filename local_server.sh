#!/bin/bash

# Runs Mr Deploy with her assistant and their web UI locally

# Kill all child processes on script exit or abort
trap "kill 0" SIGINT SIGTERM EXIT

echo "Starting redis server"
redis-server &

export PYTHONUNBUFFERED=1

# Start up deploy assistant that communicates between server processes and Mr
# Deploy
echo "Starting Mr Deploy's assistant"
python mr_assistant.py &

# Start up gunicorn server with multiple Flask workers as the foreground process
echo "Starting app server"
FLASK_CONFIG=flask_debug_config.py gunicorn \
  --debug \
  --worker-class=gevent \
  -t 99999 \
  -b localhost:5000 \
  -w 8 \
  server:app
