#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

#import logging
#log_filename = 'smser.log'
#logging.basicConfig(filename=log_filename,level=logging.DEBUG)

import traceback

import signal
import Queue
import smpplib
import threading
# from pprint import pprint
import settings
from time import sleep
import datetime
from billing import get_phones_to_sms, sms_sent

def timer_echo():
    print ' --- ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

#############################

threads_counter = 0
tc_lock = threading.Lock()

sms_queue = Queue.Queue()

timer = threading.Timer(1800, timer_echo)

#############################
def send_sms(phone, code, order_id):
  global threads_counter
  global tc_lock
  tc_updated = False
  while not tc_updated:
    tc_lock.acquire()
    try:
      threads_counter += 1
      tc_updated = True
    finally:
      tc_lock.release()
  text = (settings.sms_text%(code))
  sent = False
  sms_var = 0
  counter = 0
  print ' --- ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '  sms to ' + phone + ' with text "' + text + '"'

  while not sent:
    try:
      encoding_flag = 0
      msg_type_flag = 0
      client = smpplib.client.Client(settings.smpp_hosts[sms_var]['host'], settings.smpp_hosts[sms_var]['port'])
      client.connect()
      client.bind_transmitter(system_id=settings.smpp_user['username'], password=settings.smpp_user['password'])
      read_pdu = client.send_message(
        source_addr_ton = 5,
        source_addr_npi = 1,
        source_addr = settings.phone_number,
        dest_addr_ton = 1,
        dest_addr_npi = 1,
        destination_addr = phone,
        short_message = text,
        data_coding = encoding_flag,
        esm_class = msg_type_flag,
        registered_delivery = True
      )
      msg_id = read_pdu.message_id
      status = read_pdu.status
      if status == 0 and msg_id:
        sent = True
      sent = True
    except Exception as e:
      print e
      break
      if counter > 0: 
        break
      if sms_var:
        counter += 1
        sms_var = 0
      else:
        sms_var = 1
      sleep(15*(counter+1))
      pass
  if sent:
    sms_sent(order_id) # status = 2 - sms sent
    print ' --- sms sent'
  else:
    print ' --- sms NOT sent'
  tc_updated = False
  while not tc_updated:
    tc_lock.acquire()
    try:
      threads_counter -= 1
      tc_updated = True
    finally:
      tc_lock.release()

def shutdown(signum, frame):
  print 'Shutting down...'
  while threads_counter:
    print '  Waiting for threads (%d remained)'%threads_counter
    sleep(1)
  print 'Stopped'
  timer.cancel()
  sys.exit(0)

if __name__ == '__main__':
  signal.signal(signal.SIGTERM, shutdown)
  signal.signal(signal.SIGINT, shutdown)
  timer_echo()
  print 'Started'
  timer.start()
  while True:
      items = get_phones_to_sms()
      for item in items:
        sms_queue.put(item)
        sms_sent(item[0], status=1)  # 1 - sms scheduled to send
      if not sms_queue.empty() and threads_counter <= 4:
        [ order_id, phone, code ] = sms_queue.get()
        tread = threading.Thread(target=send_sms, args=(phone, code, order_id))
        tread.daemon = True
        tread.start()
      sleep(3)
