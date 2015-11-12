from service.amqp import Publisher, Consumer
from settings import sms_send_settings as send_settings, sms_status_settings as status_settings
from billing import sms_sent
from threading import Thread
import json

class StatusConsumer(Consumer):
    def __init__(self):
        super(StatusConsumer, self).__init__(status_settings)

    def on_message(self, message):
        [ order_id, state ] = json.loads(message.body)
        sms_sent(order_id, state)
        message.ack()

def process():
    while True:
        try:
            sc = StatusConsumer()
            sc.start()
        except KeyboardInterrupt:
            print 'Control-C detected. Stopping StatusConsumer'
            break
        except Exception as e:
            print 'SMS status queue consumer trouble: %e'%str(e)
        print 'SMS status queue consumer restarting'

sms_status_consumers = [ Thread(name='StatusComsumer-%d'%x, target=process) for x in range(4) ]

def start_consume():
    for c in sms_status_consumers:
        c.start()
