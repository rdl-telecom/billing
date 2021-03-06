from service.amqp import Publisher, Consumer
from settings import sms_send_settings as send_settings, sms_status_settings as status_settings, sms_status_consumers_number as number
from billing import sms_sent
#from multiprocessing import Process
from threading import Thread
import time
import json
import logging

logger = logging.getLogger(__name__)

def on_message(message):
    [ order_id, state ] = json.loads(message.body)
    sms_sent(order_id, state)
    message.ack()

def process():
    while True:
        try:
            sc = Consumer(status_settings)
            sc.on_message = on_message
            logging.info('Starting consumer')
            sc.start()
        except KeyboardInterrupt:
            logger.warning('Control-C detected. Stopping StatusConsumer')
            break
        except Exception as e:
            logger.error('Consumer error: %s'%e)
            continue
        time.sleep(10)
        logger.info('SMS status queue consumer restarting')

sms_status_consumers = [ Thread(name='StatusComsumer-%d'%x, target=process) for x in range(number) ]

def start_consume(consumers):
    for c in consumers:
        logger.debug('Creating consumer {}'.format(c.name))
#        c.daemon = True
        c.start()
