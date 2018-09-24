""" Redis based simple queue acting as middleware """

import redis
import datetime
import time
import sys
import cPickle
import hashlib
import uuid

class RedisQueue(object):
    """A simple redis based FIFO queue. Pushes are non-blocking but pops are blocking """

    def __init__(self):
        self._red = redis.Redis()
        # Current queue id
        self.qid = uuid.uuid4().hex
        # This queue is used to communicate with crawlers
        self.cid_name = "crawler"
        # This queue is used to communicate with the file path listeners (downloaders)
        self.lid_name = "listener" 
        
    def cpush(self, element):
        """Push an element to the tail of the crawler queue""" 

        push_element = self._red.lpush(self.cid_name, element)

    def cpop(self, timeout=5):
        """Pop an element from the head of the crawler queue"""

        # Blocking rpop
        popped_element = self._red.brpop(self.cid_name, timeout)
        return popped_element

    def lpush(self, element):
        """Push an element to the tail of the listener queue""" 

        push_element = self._red.lpush(self.lid_name, element)

    def lpop(self, timeout=5):
        """Pop an element from the head of the listener queue"""

        # Blocking rpop
        popped_element = self._red.brpop(self.lid_name, timeout)
        return popped_element   

    def get_timestamp(self):
        """ Return current timestamp """

        # INTERNAL FUNCTION
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


