#!/usr/bin/env python

"""Continuous deploy script: deploys a staging version of Khan Academy whenever
a changeset is pushed to the website stable repository.
"""

# TODO(david): Integrate with Jenkins
# TODO(david): Proper logging with timestamps.

import os
import shutil
import subprocess
import time

import hipchat.config
import hipchat.room
import pexpect

import secrets

hipchat.config.token = secrets.hipchat_token


POLL_INVERVAL_SECS = 20
REPO_NAME = "stable"
REPO_DIR = os.path.join(os.path.dirname(__file__), REPO_NAME)
CLONE_URL = "https://khanacademy.kilnhg.com/Code/Website/Group/%s" % REPO_NAME


def check_incoming():
    # TODO(david): Suppress output?
    return subprocess.call(["hg", "incoming"], cwd=REPO_DIR) == 0


def decrypt_secrets():
    print "Decrypting secrets"
    # Using pexpect because openssl directly connects to the tty instead of
    # stdin/out
    child = pexpect.spawn('make secrets_decrypt', cwd=REPO_DIR)
    child.expect('enter .* password:')
    child.sendline(secrets.secrets_decrypt_key)
    child.expect(pexpect.EOF)
    child.close()
    if child.exitstatus != 0:
        print "Unable to decrypt secrets. Bailing."
        exit(1)


def clone_repo():
    print "Cloning %s" % CLONE_URL
    # TODO(david): Clone only latest revision to be faster?
    subprocess.check_call(["hg", "clone", CLONE_URL])


def update_repo():
    """Attempt to update the repository by hg pull, but clone if that fails."""
    print "Updating %s" % REPO_DIR
    try:
        subprocess.check_call(["hg", "pull"], cwd=REPO_DIR)
        # Not doing hg pull -u because that returns 0 for some failed updates
        subprocess.check_call(["hg", "update"], cwd=REPO_DIR)
    except subprocess.CalledProcessError as e:
        print "hg pull && hg up failed: %s" % e
        print "Removing %s and re-cloning" % REPO_DIR

        # TODO(david): Try pulling subrepos before falling back to clone.
        shutil.rmtree(REPO_DIR)
        clone_repo()


def notify_hipchat(room_id, message):
    # Pure kwargs don't work here because 'from' is a Python keyword...
    hipchat.room.Room.message(**{
        'room_id': room_id,
        'from': 'Mr Deploy',
        'message': message,
        'color': 'red',
        'message_format': 'text',
    })


def deploy_to_staging():
    update_repo()
    decrypt_secrets()
    shutil.copy2("secrets_dev.py", REPO_DIR)
    subprocess.check_call(["pip", "install", "-r", "requirements.txt"],
            cwd=REPO_DIR)

    print "Deploying!"

    try:

        subprocess.check_call([
            "python", "deploy/deploy.py",
            "--version", "staging",
            "--no-up",
            # TODO(david): Notify on test fails or restore/integrate w/ Jenkins
            "--no-tests",
            "--no-hipchat",
            "--no-browser",
        ], cwd=REPO_DIR)

        print "Deploy succeeded!"

    except subprocess.CalledProcessError as e:

        print "Deploy failed :("
        print "ERROR: %s" % e

        # TODO(david): Give more info in hipchat message
        notify_hipchat(secrets.hipchat_room_id,
                "(poo), automated staging deploy failed. "
                "@david, could you check the logs on ci.khanacademy.org? "
                "Thanks. :)")

        # Exit for now so we don't spam the 1s and 0s room
        print "Quitting. Please restart this script once issue has been fixed."
        exit(1)


# TODO(david): Ask a Kiln admin to add a webhook on stable instead of polling
def main():
    if not os.path.exists(REPO_DIR):
        clone_repo()

    # Poll to see if there are any new changesets
    while True:
        if check_incoming():
            deploy_to_staging()

        time.sleep(POLL_INVERVAL_SECS)


if __name__ == "__main__":
    main()
