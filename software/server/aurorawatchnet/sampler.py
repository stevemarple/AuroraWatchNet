'''Class to implement sampling. 

Only one sample() function call will run at once'''

import logging
import threading

logger = logging.getLogger(__name__)

class Sampler(object):
    def __init__(self, func):
        self.lock = threading.Lock()
        self.func = func
        self.paused = False

    def sample(self):
        logger.debug('Acquiring lock')
        if self.lock.acquire(False):
            try:
                logger.debug('Acquired lock')
                self.func()
            finally:
                logging.debug('Released lock')
                self.lock.release()
        else:
            logger.debug('Could not acquire lock')

    def pause(self):
        if not self.paused:
            self.lock.acquire() # Blocks
            self.paused = True
            logger.debug('Paused')
            return
        else:
            logger.debug('Already paused')

    def resume(self):
        if self.paused:
            self.lock.release()
            logger.debug('Resumed')
        else:
            logger.debug('Not paused')
