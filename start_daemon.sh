#!/bin/sh

# Runs Mr Deploy and friends (her assistant and their web server) as a daemon.
# This should not be run directly, and should be
# TODO(david): replaced with a proper daemon script placed in init.d.

nohup ./prod_server.sh &
