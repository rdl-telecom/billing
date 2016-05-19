#!bin/python
# -*- coding: utf-8 -*-

from billing import get_active_sessions, start_session, stop_session, end_session
#from pprint import pprint
import datetime
import time
import signal
from threading import Thread
#import sched


def shutdown(signum, frame):
    import sys
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    while True:
        # getting active sessions (with state 1 (RUNNING))
        sessions = get_active_sessions()
        
        for order_id in sessions:
            # calculating delta between now and start_time considering session_time
            time_delta = datetime.datetime.now() - sessions[order_id]['start_time'] + sessions[order_id]['session_time']
            if time_delta > sessions[order_id]['duration']:
                # if delta is bigger than a session dutation then we need to end it anyway
                thread = Thread(target=end_session, args=(int(order_id),))
                thread.daemon = True
                thread.start()
                continue
            # if not we need to start scheduler
        time.sleep(5)
