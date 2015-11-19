from service.amqp import Publisher, Consumer
from settings import sms_send_settings as send_settings, sms_status_settings as status_settings, sms_status_consumers_number as number
from billing import sms_sent
#from multiprocessing import Process
from threading import Thread
import time
import json
import logging

def on_message(message):
    [ order_id, state ] = json.loads(message.body)
    sms_sent(order_id, state)
    message.ack()

def process():
    logging.info('Creating consumer...')
    while True:
        try:
            sc = Consumer(status_settings)
            sc.on_message = on_message
            logging.info('Starting consumer...')
            sc.start()
        except KeyboardInterrupt:
            logging.warning('Control-C detected. Stopping StatusConsumer')
            break
        except Exception as e:
<<<<<<< HEAD
            logging.error('SMS status queue consumer trouble: %s'%str(e))
        time.sleep(10)
        logging.info('SMS status queue consumer restarting')

#sms_status_consumers = [ Process(name='StatusComsumer-%d'%x, target=process) for x in range(number) ]
=======
            logging.error('Consumer error: %s'%e)
            continue
        time.sleep(10)
        logging.info('SMS status queue consumer restarting')

>>>>>>> e5417d8422e39120f1f1202ab9dec63bb5a85ff1
sms_status_consumers = [ Thread(name='StatusComsumer-%d'%x, target=process) for x in range(number) ]

def start_consume(consumers):
    for c in consumers:
        c.setDaemon(True)
        c.start()
