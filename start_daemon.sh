#!/bin/sh

# Runs deploy.py as a daemon.

# TODO(david): Actually run as a daemon, this is quick'n'dirty nohup right now.

ln -sfnv "$(pwd)/deploy.log" $HOME
nohup python -u deploy.py > deploy.log &
