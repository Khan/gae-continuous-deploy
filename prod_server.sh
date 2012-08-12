#!/bin/bash

# Runs Mr Deploy with her assistant and their web server on production

# Kill all child processes on script exit or abort
trap "kill 0" SIGINT SIGTERM EXIT

export PYTHONUNBUFFERED=1

# Start up deploy assistant that communicates between server processes and Mr
# Deploy
echo "Starting Mr Deploy's assistant"
python mr_assistant.py > log/mr_assistant.log &

# Start up gunicorn server with multiple Flask workers as the foreground process
echo "Starting app server"
FLASK_CONFIG=flask_prod_config.py gunicorn \
  --worker-class=gevent \
  --bind unix:/tmp/gunicorn.sock \
  --workers 24 \
  --access-logfile log/server_access.log \
  --error-logfile log/server_error.log \
  server:app
