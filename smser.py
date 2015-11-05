#!bin/python

#import logging
#log_filename = 'smser.log'
#logging.basicConfig(filename=log_filename,level=logging.DEBUG)

import sys
import traceback
import signal
import Queue
import smpplib
import threading
import settings
from time import sleep
import datetime
from billing import get_phones_to_sms, sms_sent
import random

#############################

sms_queue = Queue.Queue(maxsize=0)
exit_event = threading.Event()

#############################
def send_sms(name, queue):
  print name, 'started'
  while True:
    if exit_event.is_set():
      break
    if queue.empty():
      sleep(random.randint(1,5))
      continue

    print
    print '-'*95
    print
    [ order_id, phone, code, attempt ] = queue.get()
    queue.task_done()
    sleep(attempt*10)
    text = (settings.sms_text%(code))
    sent = False
    print datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' > ' + name + ': sms to ' + phone + ' with code "' + code + '". attempt #' + str(attempt+1)
  
    try:
      encoding_flag = 0
      msg_type_flag = 0
      sms_var = random.randint(0,1)
      client = smpplib.client.Client(settings.smpp_hosts[sms_var]['host'], settings.smpp_hosts[sms_var]['port'])
      client.connect()
      client.bind_transmitter(system_id=settings.smpp_user['username'], password=settings.smpp_user['password'])
      read_pdu = client.send_message(
          source_addr_ton = 5,
          source_addr_npi = 1,
          source_addr = settings.phone_number.encode('utf-8'),
          dest_addr_ton = 1,
          dest_addr_npi = 1,
          destination_addr = phone.encode('utf-8'),
          short_message = text.encode('utf-8'),
          data_coding = encoding_flag,
          esm_class = msg_type_flag,
          registered_delivery = True
      )
      msg_id = read_pdu.message_id
      status = read_pdu.status
      if status == 0 and msg_id:
        sent = True
      else:
        raise Exception('sms not sent. status = %d'%status)
    except Exception as e:
      print e
      traceback.print_exc(file=sys.stdout)
      if attempt < 4:
        print 'SMS is not sent. Requeuing it.'
        queue.put([order_id, phone, code, attempt + 1])
      else:
        print 'Number of attempts is exceeded. Marking as "NO MORE TRIES"'
        sms_sent(order_id, 3)
        continue

    if sent:
      sms_sent(order_id) # status = 2 - sms sent
      print ' SMS is sent'

    print
    print '-'*95
    print


def shutdown(signum, frame):
  print 'Shutting down...'
  if threading.active_count() > 1:
    exit_event.set()
  while threading.active_count() > 1:
    print '  Waiting for threads (%d remained)'%(threading.active_count() - 1)
    sleep(1)
  if not sms_queue.empty():
    print """
-----------------------------------------------------------------------------------------------
    ATTENTION!!! SMS queue is not empty! Don't forget to change SMS status in base manually
-----------------------------------------------------------------------------------------------

Found these values in queue:

"""
    while not sms_queue.empty():
      print sms_queue.get()
      sms_queue.task_done()
  print
  print '-'*95
  print '\nStopped'
  sys.exit(0)

if __name__ == '__main__':
  signal.signal(signal.SIGTERM, shutdown)
  signal.signal(signal.SIGINT, shutdown)
  print 'Started'
  for i in range(4):
    name = '-'.join(('SMSer-Thread',str(i)))
    print 'Starting %s...'%name
    thread = threading.Thread(name=name, target=send_sms, args=(name, sms_queue))
    thread.setDaemon(True)
    thread.start()
  print '-'*95
  print
  sleep(1)
  while True:
      items = get_phones_to_sms()
      for item in items:
        sms = list(item) + [ 0 ]
        print sms
        sms_queue.put(sms)
        sms_sent(item[0], status=1)  # 1 - sms scheduled to send
      sleep(3)
