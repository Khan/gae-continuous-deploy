#!/usr/bin/env python

"""Continuous deploy script: deploys a staging version of Khan Academy whenever
a changeset is pushed to the website stable repository.
"""

# TODO(david): Integrate with Jenkins: only deploy when all tests pass, or just
#     run make allcheck
# TODO(david): Proper logging with timestamps.

import optparse
import os
import signal
import shutil
import subprocess
import sys
import time

import hipchat.config
import hipchat.room

import secrets

hipchat.config.token = secrets.hipchat_token


POLL_INVERVAL_SECS = 15
REPO_NAME = "stable"
REPO_DIR = os.path.join(os.path.dirname(__file__), REPO_NAME)
CLONE_URL = "https://khanacademy.kilnhg.com/Code/Website/Group/%s" % REPO_NAME


def check_incoming():
    # TODO(david): Suppress output?
    return subprocess.call(["hg", "incoming"], cwd=REPO_DIR) == 0


def get_earliest_incoming():
    """Get the earliest incoming changeset hash. Will raise
    subprocess.CalledProcessError if there are no incoming changesets.

    Rant: This function would not be needed and we could just re-use
    get_last_changeset() if hg supported inclusive/exclusive ranges (which
    would also allow us to conveniently express the empty range)
    """
    output = subprocess.check_output([
        "hg", "incoming",
        "-l", "1",
        "--template", "{node}",
    ], cwd=REPO_DIR)

    lines = output.split("\n")
    if len(lines) >= 3 and "searching for changes" in lines[1]:
        return lines[2]
    else:
        raise Exception("Oh crap, getting earliest incoming changeset failed. "
                "Command output: %s" % output)


def decrypt_secrets():
    print "Decrypting secrets"

    # Not running "make decrypt_secrets" because openssl gets input directly
    # from tty instead of stdin.
    p = subprocess.Popen([
        "openssl", "cast5-cbc", "-d",
        "-in", "secrets.py.cast5",
        "-out", "secrets.py",
        "-pass", "stdin",
    ], cwd=REPO_DIR, stdin=subprocess.PIPE)

    p.communicate(secrets.secrets_decrypt_key)
    if p.returncode != 0:
        raise Exception("openssl exited with return code %d" % p.returncode)

    subprocess.check_call(["chmod", "600", "secrets.py"], cwd=REPO_DIR)


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


def get_last_changeset():
    return subprocess.check_output(["hg", "tip", "--template", "{node|short}"],
            cwd=REPO_DIR)


def get_last_author():
    # Not notifying authors for now because it may be annoying. If people
    # request for @mentions, will add that then.
    return subprocess.check_output([
        "hg", "tip",
        "--template", "{author|person}",
    ], cwd=REPO_DIR)


def get_affected_files(first_changeset, last_changeset='tip'):
    """Get all changed, added, or deleted files between two given changesets,
    inclusive.
    """
    files = subprocess.check_output([
        "hg", "log",
        "--rev", "%s:%s" % (first_changeset, last_changeset),
        "--template", "{files} ",
    ], cwd=REPO_DIR)
    return set(files.split())


def notify_hipchat(room_id, color, message):
    # Pure kwargs don't work here because 'from' is a Python keyword...
    hipchat.room.Room.message(**{
        'room_id': room_id,
        'from': 'Mr Deploy',
        'message': message,
        'color': color,
        'message_format': 'text',
    })


def notify_abort(room_id):
    notify_hipchat(room_id, "gray", "/me is taking a "
            "nap until the devs sort things out. (zzz)")


def check_dangerous_files(first_changeset, last_changeset='tip', notify=True):
    dangerous_files = {"cron.yaml", "queue.yaml", "index.yaml"}
    affected_files = get_affected_files(first_changeset, last_changeset)
    dangerous_changes = dangerous_files & affected_files

    if dangerous_changes:
        changes_str = ", ".join(dangerous_changes)
        print("Bailing because of potentially dangerous changes to "
                "cross-version files %s" % changes_str)

        if notify:
            notify_hipchat(secrets.hipchat_room_id, "red", "(boom) Sorry "
                    "y'all, but I'm cowardly refusing to deploy because of "
                    "potentially dangerous cross-version changes to %s. Drop "
                    "by my shack at ci.khanacademy.org when ready!"
                    % changes_str)
            notify_abort(secrets.hipchat_room_id)
        return True

    return False


def deploy_to_staging(notify=True, force=False):
    """Deploys stable to a staging version if there are incoming changes.

    notify - Whether to ping 1s and 0s room about success or failure.
    force - Whether to deploy even if there are no incoming changes.
    """
    try:

        if check_incoming():
            first_changeset = get_earliest_incoming()
            update_repo()

            if check_dangerous_files(first_changeset, notify=notify):
                sys.exit(1)

        elif not force:
            return

        decrypt_secrets()
        shutil.copy2("secrets_dev.py", REPO_DIR)
        # TODO(david): sudo needed because not using virtualenv on EC2. Fix it.
        subprocess.check_call(["sudo", "make", "install_deps"], cwd=REPO_DIR)

        print "Running deploy script!"

        last_changeset = get_last_changeset()
        last_author = get_last_author()

        subprocess.check_call([
            "python", "-u", "deploy/deploy.py",
            "--version", "staging",
            "--no-up",
            "--no-hipchat",
            "--no-browser",
        ], cwd=REPO_DIR)

        print "Deploy script succeeded!"

        if notify:
            notify_hipchat(secrets.hipchat_room_id, "gray", "/me just "
                    "deployed to http://staging.khan-academy.appspot.com with "
                    "last website changeset %s by %s" % (
                        last_changeset, last_author))

    except subprocess.CalledProcessError as e:

        print "Deploy failed :("
        print "ERROR: %s" % e

        if notify:
            # TODO(david): Give more info in hipchat message, like ping
            #     changeset authors and tail deploy.log
            notify_hipchat(secrets.hipchat_room_id, "red",
                    "Oh (poo), I'm borked (sadpanda). Will a kind soul visit "
                    "ci.khanacademy.org and make me feel better? (heart)")
            notify_abort(secrets.hipchat_room_id)

        # Exit for now so we don't spam the 1s and 0s room
        print "Napping. Please wake me up once this issue has been fixed! :)"
        sys.exit(1)


def manual_exit():
    print "Affirmative! I'll take a nap now, commander.\n"
    sys.exit(0)


def get_cmd_line_args():
    parser = optparse.OptionParser()

    parser.add_option('-d', '--deploy_and_quit',
        action="store_true",
        help="Deploy to staging then exit (do not daemonize).", default=False)

    parser.add_option('-n', '--no_notify',
        action="store_true",
        help="Don't notify HipChat.", default=False)

    return parser.parse_args()


# TODO(david): Ask a Kiln admin to add a webhook on stable instead of polling
def main():
    options, _ = get_cmd_line_args()

    if not os.path.exists(REPO_DIR):
        clone_repo()

    if options.deploy_and_quit:
        deploy_to_staging(not options.no_notify, force=True)
        return 0

    # Register a cleanup handler on script termination
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGABRT):
        signal.signal(sig, lambda signal, frame: manual_exit())

    print "I'm awake! Back to work. :)"

    # Poll to see if there are any new changesets
    # TODO(david): Should deploy any undeployed changes pulled from before (eg.
    #     when restarting from error).
    while True:
        deploy_to_staging(not options.no_notify)

        time.sleep(POLL_INVERVAL_SECS)


if __name__ == "__main__":
    sys.exit(main())
