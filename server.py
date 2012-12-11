#!/usr/bin/env python

"""A simple web server to see and control Mr Deploy. Talks to Mr Deploy using
Redis through her assistant, Mr Assistant.
"""

import flask
import json
import redis
import subprocess

import auth


app = flask.Flask(__name__)
app.config.from_envvar('FLASK_CONFIG')
auth.configure_app(app, required=not app.debug)

red = redis.StrictRedis()


def event_stream():
    pubsub = red.pubsub()
    pubsub.subscribe(['mr_deploy_output', 'mr_deploy_status'])
    for item in pubsub.listen():
        if item['type'] == 'message':
            # This is the format for an SSE specifying an event name with data
            # See http://www.html5rocks.com/en/tutorials/eventsource/basics/
            yield 'event: %s\ndata: %s\n\n' % (item['channel'], item['data'])


@app.route('/deploy/status', methods=['GET'])
@auth.login_required
def status():
    # TODO(david): Should return false if mr_assistant.py is not working.
    running = red.get('mr_deploy_running')
    running = running and json.loads(running)
    return flask.jsonify(
        running=running,
    )


@app.route('/deploy/please/<command>', methods=['POST'])
@auth.login_required
def deploy_command(command):
    red.publish('mr_deploy_commands', command)
    return status()


# TODO(david): This blocks the HTTP connection and so we use gunicorn spawning
#     multiple server processes to handle simultaneous connections. Perhaps
#     just rewrite this trivial server in Node + Socket.IO or just poll.
@app.route('/deploy/stream')
@auth.login_required
def stream():
    return flask.Response(event_stream(), mimetype="text/event-stream")


def tail(filename, num_lines):
    return subprocess.check_output(['tail', '-n', str(num_lines), filename])


@app.route('/')
@auth.login_required
def index():
    deploy_log = tail('log/mr_deploy.log', num_lines=12345)
    deploy_log_decoded = unicode(deploy_log, 'utf8')
    return flask.render_template('index.html', deploy_log=deploy_log_decoded)


def main():
    print "Please start this server by running `make local-server`."


if __name__ == '__main__':
    main()
