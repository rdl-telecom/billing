#!bin/python

#import logging
#log_filename = 'smser.log'
#logging.basicConfig(filename=log_filename,level=logging.DEBUG)

import sys
import traceback
import signal
import smpplib
import threading
import settings
from time import sleep
import datetime
import random
from service.amqp import Publisher, Consumer
import logging
import json

logger = logging.getLogger('smser')

NOT_SENT=0
SENDING=1
SENT=2
FAILED=3

#############################

exit_event = threading.Event()

#############################
def on_new_message(message):
    [ oid, phone, code ] = json.loads(message.body)
    publisher = Publisher(settings.sms_status_settings)
    text = settings.sms_text%code
    encoding_flag = 0
    msg_type_flag = 0
    attempt = 0
    sent = False
    print datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ' > ' + ': sms to ' + phone + ' with code "' + code + '". attempt #' + str(attempt+1)
    publisher.publish([oid, SENDING])
    state = FAILED
    sms_var=0
    while not sent:
        try:
            if attempt > 5:
                sms_var += 1
                if sms_var >= len(settings.smpp_hosts):
                    break
                else:
                    attempt = 0
            sleep(attempt*5)
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
        except Exception as e:
            print 'Error occured while sending message'
            traceback.print_exc(file=sys.stdout)
        attempt += 1
    if sent:
        state = SENT
    message.ack()
    publisher.publish([oid, state])

def consumer():
    while True:
        try:
            consumer = Consumer(settings.sms_send_settings)
            consumer.on_message = on_new_message
            consumer.start()
        except KeyboardInterrupt:
            print 'Control-C detected. Stopping SMS consumer'
            break
        except Exception as e:
            print 'SMSer exception: %s'%str(e)
            print 'Restarting consumer'

if __name__ == '__main__':
  print 'Started'
  consumers = [ threading.Thread(name='SMSConsumer-%d'%x, target=consumer) for x in range(settings.sms_senders) ]
  for consumer in consumers:
    print 'Starting %s...'%consumer.name
    consumer.setDaemon(True)
    consumer.start()
  print '-'*95
  print

  from sms_processor import start_consume, sms_status_consumers
  start_consume(sms_status_consumers)

  for consumer in consumers + sms_status_consumers:
    consumer.join()
