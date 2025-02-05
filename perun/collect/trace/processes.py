"""A module with multiprocessing wrappers and classes."""

import queue
from multiprocessing import Queue, Event

from perun.collect.trace.values import QUEUE_TIMEOUT


class SafeQueue:
    """A wrapper over the multiprocessing Queue. The wrapper implements
    blocking read / write operations, end-of-input signalling and cleanup
    procedures.

    Note: The wrapper expects a one-directional usage (i.e., no duplex)

    :ivar _eoi_event: event used to signal that no more input will be written
    :ivar _queue: a multiprocessing queue
    :ivar _is_closed: a flag indicating whether the queue has already been closed
    """

    def __init__(self, maxsize=-1):
        """
        :param maxsize: the queue capacity
        """
        self._eoi_event = Event()
        self._queue = Queue(maxsize)
        self._is_closed = False

    def end_of_input(self):
        """Signal to the consumer(s) that no more data will be written by the producer."""
        if not self._eoi_event.is_set():
            self._eoi_event.set()

    def close_reader(self):
        """Remove all remaining elements from the queue."""
        while self.read() is not None:
            continue

    def close_writer(self):
        """Close the producer's end of queue."""
        # Multiple close() calls are not allowed
        if not self._is_closed:
            self.end_of_input()
            self._queue.close()
            self._queue.join_thread()
            self._is_closed = True

    def write(self, data):
        """Send data through the queue.

        :param data: the data to send
        """
        while True:
            # Attempt to send the data, repeat if queue is currently full
            try:
                self._queue.put(data, block=True, timeout=QUEUE_TIMEOUT)
                break
            except queue.Full:
                continue

    def read(self, timeout=QUEUE_TIMEOUT, retries=1):
        """Read data from the queue.

        :return: the obtained data.
        """
        retry = 0
        while True:
            # Attempt to get data from the queue
            try:
                return self._queue.get(block=True, timeout=timeout)
            except queue.Empty:
                # If EOI event has been signalled, attempt the 'get' operation once more
                # since there are generally some delays before the written data are accessible
                # to the consumer, although the EOI might had already been set.
                if self._eoi_event.is_set():
                    if retry < retries:
                        retry += 1
                        continue
                    # If no data are available even after a retry, assume the queue to be empty
                    return None
                continue

    # TODO: temporary hack, maybe sent/recv object counting would be better?
    def read_large(self):
        """Read large data from the queue (i.e., Profile object)

        :return: the obtained data.
        """
        # We know that a profile has been sent through a queue, however, it might take a while
        # until it is accessible
        for _ in range(20):
            profile = self.read(QUEUE_TIMEOUT * 5, 10)
            if profile is not None:
                return profile
        return None
