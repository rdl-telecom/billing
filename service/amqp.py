import rabbitpy
import logging
import threading

log_format = ('%(asctime) -25s %(name) -20s %(levelname) -8s %(funcName)s (line %(lineno)d) : %(message)s')
logger = logging.getLogger(__name__)

class AMQPAgent(object):
    def __init__(self, settings):
        self._url = settings['url']
        self._exchange_name = settings.get('exchange', 'default')
        self._exchange_type = settings.get('type', 'direct')
        self._durable = settings.get('durable', False)
        self._auto_delete = settings.get('auto_delete', False)
        self._queue_name = settings.get('queue', 'default')
        self._routing_key = settings.get('routing_key', None)
        self._content_type = settings.get('content_type', 'application/json')

        self._connection = None
        self._exchange = None
        self._queue = None

        self.prepare()

    def __del__(self):
        try:
            self._queue.unbind(self._exchange, self._routing_key)
        except:
            pass
        try:
            self._channel.close()
        except:
            pass
        try:
            self._connection.close()
        except:
            pass

    def prepare(self):
        self.connect()
        self.create_channel()
        self.create_exchange()
        self.declare_queue()

    def connect(self):
        self._connection = rabbitpy.Connection(self._url)

    def create_channel(self):
        self._channel = self._connection.channel()

    def create_exchange(self):
        self._exchange = rabbitpy.Exchange(
                                self._channel,
                                self._exchange_name,
                                exchange_type = self._exchange_type,
                                durable = self._durable,
                                auto_delete = self._auto_delete)

    def declare_queue(self):
        self._queue = rabbitpy.Queue(self._channel, self._queue_name)
        self._queue.declare()
        self._queue.bind(self._exchange, self._routing_key)


class Consumer(AMQPAgent):
    def __init__(self, settings):
        super(Consumer, self).__init__(settings)

    def __del__(self):
        try:
            self._queue.stop_consuming()
        except:
            pass
        super(Consumer, self).__del__()
        
    def on_message(self, message):
        import time
        message.pprint(True)
        message.ack()

    def start(self):
        for message in self._queue:
            self.on_message(message)


class Publisher(AMQPAgent):
    _lock = threading.Lock()

    def __init__(self, settings):
        super(Publisher, self).__init__(settings)
        self._channel.enable_publisher_confirms()
        self._app_id = settings.get('app_id', __name__)

    def message_handler(self, message):
        if message.publish(self._exchange_name, self._routing_key):
            logger.info('Message was successfully added to queue')
        else:
            logger.error('Error occured while message was queued')

    def publish(self, body, properties=None):
        if not properties:
            properties = {
                'content_type' : self._content_type
            }
        properties['app_id'] = self._app_id
        message = rabbitpy.Message(self._channel, body, properties=properties)
        thread = threading.Thread(target=self.message_handler, name=str(body)[:32], args=(message,))
        with Publisher._lock:
            thread.start()
        thread.join()
