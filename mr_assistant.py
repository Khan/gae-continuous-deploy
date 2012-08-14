#!/usr/bin/env python

"""Mr Deploy's office assistant. Controls the execution of Mr Deploy and relays
messages via Redis Pub/Sub.
"""

import json
import subprocess
import threading
import time

import redis


red = redis.StrictRedis()


class MrDeploy(object):
    """Class wrapper to control the running of Mr Deploy via a subprocess.
    Asks Redis for commands and streams deploy output to Redis Pub/Sub.
    """

    def __init__(self, output_channel, status_channel):
        self.proc = None
        self.output_channel = output_channel
        self.status_channel = status_channel

        threading.Thread(target=self._log_to_file).start()

    def is_running(self):
        return self.proc and self.proc.poll() is None

    def _set_running(self, status):
        json_status = json.dumps(status)
        red.set('mr_deploy_running', json_status)
        red.publish(self.status_channel, json_status)

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

        self._set_running(True)

        threading.Thread(target=self._publish_stream).start()
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
        self._set_running(False)

    def _publish_stream(self):
        """Continuously publishes to Redis mr_deploy's output. Intended to be
        run in a separate thread.
        """
        while self.is_running():
            line = ""
            for data in self.proc.stdout.readline():
                line += data
                if not data:
                    break

            if line:
                red.publish(self.output_channel, line)

    def _log_to_file(self):
        pubsub = red.pubsub()
        pubsub.subscribe(self.output_channel)

        BY_LINE = 1
        with open('log/mr_deploy.log', 'a+', buffering=BY_LINE) as log_file:
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
    mr_deploy = MrDeploy('mr_deploy_output', 'mr_deploy_status')
    mr_deploy.start()
    mr_deploy.subscribe('mr_deploy_commands')


if __name__ == "__main__":
    main()
