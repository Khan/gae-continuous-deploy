#!/bin/sh

# Updates and restarts Mr Deploy webapp on the machine.
# Can be run either directly on the machine, or by running
#
# $ cat update_and_restart.sh | ssh ka-ci sh
#

cd $HOME/gae-continuous-deploy
git pull
sudo service mr-deploy-daemon restart
