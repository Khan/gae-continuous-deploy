#!/usr/bin/env python

"""Mr Deploy's office assistant. Controls the execution of Mr Deploy and relays
messages via Redis Pub/Sub.
"""

import subprocess
import threading
import time

import redis


red = redis.StrictRedis()


class MrDeploy(object):
    """Class wrapper to control the running of Mr Deploy via a subprocess.
    Asks Redis for commands and streams deploy output to Redis Pub/Sub.
    """

    def __init__(self, publish_channel):
        self.proc = None
        self.publish_channel = publish_channel

    def is_running(self):
        return self.proc and self.proc.poll() is None

    def start(self):
        if self.is_running():
            print "Mr Deploy already running; stop first."
            return

        self.proc = subprocess.Popen(
            ["python", "-u", "mr_deploy.py"],
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,  # buffer by line
        )

        red.set('mr_deploy_running', self.is_running())

        threading.Thread(target=self._publish_stream).start()
        threading.Thread(target=self._log_to_file).start()
        threading.Thread(target=self._update_status).start()

    def stop(self):
        if self.is_running():
            self.proc.terminate()
            self.proc.wait()

    def restart(self):
        self.stop()
        time.sleep(1)
        self.start()

    def _update_status(self):
        self.proc.wait()
        red.set('mr_deploy_running', False)

    def _publish_stream(self):
        """Continuously publishes to Redis mr_deploy's output. Intended to be
        run in a separate thread.
        """
        while self.is_running():
            line = ""
            for data in self.proc.stdout.readline():
                line += data
                if not line:
                    break

            red.publish(self.publish_channel, line)

    def _log_to_file(self):
        pubsub = red.pubsub()
        pubsub.subscribe(self.publish_channel)

        # TODO(david): Append to file and have cron job move each day's log to
        #     its own named file to keep log from growing too large.
        # TODO(david): Finish thread on stop for now.
        BY_LINE = 1
        with open('log/mr_deploy.log', 'w+', buffering=BY_LINE) as log_file:
            for item in pubsub.listen():
                if item['type'] == 'message':
                    log_file.write(item['data'])

    def subscribe(self, channel):
        pubsub = red.pubsub()
        pubsub.subscribe(channel)

        for item in pubsub.listen():
            if item['type'] == 'message':
                cmd = item['data']
                print 'Received command %s' % cmd
                if cmd == "start":
                    self.start()
                elif cmd == "restart":
                    self.restart()
                elif cmd == "stop":
                    self.stop()
                else:
                    print "Unknown command. Ignoring."


def main():
    mr_deploy = MrDeploy('mr_deploy_output')
    mr_deploy.start()
    mr_deploy.subscribe('mr_deploy_commands')


if __name__ == "__main__":
    main()
