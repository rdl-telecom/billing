#!bin/python

#import logging
#log_filename = 'smser.log'

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

logging.basicConfig(
                    filename=settings.logs_dir + '/smser.log',
                    level=logging.INFO,
                    format='%(asctime)s %(name)-20s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    filemode='aw'
            )
logger = logging.getLogger('smser')

NOT_SENT=0
SENDING=1
SENT=2
FAILED=3

STATUS = [ 'NOT SENT', 'SENDING', 'SENT', 'FAILED' ]

#############################
def masked(code):
    code_len = len(code)
    if not code or code_len <= 5:
        result = '*' * code_len
    else:
        result = ('*'*(code_len - 4)).join((code[:2], code[-2:]))
    return result

def on_new_message(message):
    logger = logging.getLogger('smser.on_message')
    [ oid, phone, code ] = json.loads(message.body)
    logger.debug('Received message. OrderID: {0}, Phone: {1}, Code: {2}'.format(oid, phone, masked(code)))
    logger.debug('Creating message status AMQP publisher')
    publisher = Publisher(settings.sms_status_settings)
    text = settings.sms_text%code
    encoding_flag = 0
    msg_type_flag = 0
    attempt = 0
    sent = False
    logger.debug('Publishing SENDING message status for OrderID: {}'.format(oid))
    publisher.publish([oid, SENDING])
    state = FAILED
    sms_var=0
    while not sent:
        logger.info('Sending SMS to {}'.format(phone))
        try:
            if attempt > 5:
                sms_var += 1
                if sms_var >= len(settings.smpp_hosts):
                    break
                else:
                    attempt = 0
            sleep_dur = attempt*5
            logger.debug('Sleeping {} seconds...'.format(sleep_dur))
            sleep(sleep_dur)
            logger.debug('SMPP gate {0} ({1}:{2}). Attempt: {3}'.format(
                        sms_var + 1,
                        settings.smpp_hosts[sms_var]['host'], settings.smpp_hosts[sms_var]['port'],
                        attempt+1
                    ))
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
                logger.info('SMS to {} was sent'.format(phone))
                sent = True
            else:
                logger.info('SMPP gate returned status {0} for SMS to {1}'.format(status, phone))
        except Exception as e:
            logger.error('Error occured while sending SMS to {0}: {1}'.format(phone, e))
            logger.debug(traceback.format_exc())
        attempt += 1
    if sent:
        state = SENT
    logger.debug('Acknowleging mesaage. OrderID: {0}, Phone: {1}, Code: {2}'.format(oid, phone, masked(code)))
    message.ack()
    logger.debug('Publishing {0} message status for OrderID: {1}'.format(STATUS[state], oid))
    if oid > 0:
        publisher.publish([oid, state])

def consumer():
    while True:
        consumer = Consumer(settings.sms_send_settings)
        try:
            consumer.on_message = on_new_message
            consumer.start()
        except KeyboardInterrupt:
            logger.info('Control-C detected. Stopping SMS consumer')
            break
        except Exception as e:
            logger.error('SMSer exception: {}'.format(e))
            logger.debug('Restarting consumer')

if __name__ == '__main__':
  logger.info('SMSer started')
  consumers = [ threading.Thread(name='SMSConsumer-%d'%x, target=consumer) for x in range(settings.sms_senders) ]
  for consumer in consumers:
    logger.info('Starting consumer {}'.format(consumer.name))
#    consumer.setDaemon(True)
    consumer.start()

  from sms_processor import start_consume, sms_status_consumers
  start_consume(sms_status_consumers)

  for consumer in consumers + sms_status_consumers:
    consumer.join()
