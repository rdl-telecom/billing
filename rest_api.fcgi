#!/usr/bin/env python2
from flup.server.fcgi import WSGIServer
from app import app

if __name__ == '__main__':
    WSGIServer(app).run()
