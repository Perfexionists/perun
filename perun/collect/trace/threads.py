"""Module containing various thread related features such as timeout or periodic timers."""

import sys
from threading import Thread, Event

from perun.collect.trace.watchdog import WATCH_DOG


class NonBlockingTee(Thread):
    """The NonBlockingTee imitates the 'tee' utility and routes the stream output to
    a terminal and file.

    However, the interactivity of the output (i.e. if the terminal output as well as the file
    updates are real-time) depends heavily on the use of buffers in the application that is
    generating the output.

    :ivar _stream: stream object that is being read
    :ivar file: the name of the file to store the stream output to
    """

    def __init__(self, stream, file):
        """Construct the NonBlockingTee object

        :param stream: stream object that can be read
        :param file: the name of the file to store the stream output to
        """
        super().__init__()
        self._stream = stream
        self._file = file
        # Start the thread immediately
        self.start()

    def run(self):
        """The thread loop which blocks until new output from the stream is available."""
        WATCH_DOG.debug(f"NonBlockingTee thread starting, output stored in '{self._file}'")
        with open(self._file, "wb") as tee_file:
            try:
                # Wait for a next line from the stream
                for line in self._stream:
                    if line:
                        sys.stdout.buffer.write(line)
                        tee_file.write(line)
                    else:
                        # No more output lines
                        break
            except ValueError:
                # The stream was closed, stop the thread
                pass
            finally:
                # Flush all the buffers before terminating the thread
                sys.stdout.buffer.flush()
                tee_file.flush()
                WATCH_DOG.debug("NonBlockingTee thread terminating")


class PeriodicThread(Thread):
    """The PeriodicThread allows to periodically perform given action as long as the timer
    is not disabled. This is used to e.g. inform the user about the progress of time-intensive
    operations.

    The thread is intended to be used as a context manager.

    :ivar _stop_event: the threading.Event object used to interrupt the sleeping thread
    :ivar _timer: the interval of the periodical action
    :ivar _callback: the action to perform periodically
    :ivar callback_args: the arguments of the action function
    """

    def __init__(self, timer, callback, callback_args):
        """Creates the PeriodicThread object

        :param timer: the interval of the periodical action
        :param callback: the action to perform periodically
        :param callback_args: the arguments of the action function
        """
        super().__init__()
        self._stop_event = Event()
        self._timer = timer
        self._callback = callback
        self._callback_args = callback_args

    def run(self):
        """The thread loop that waits for a stop event to happen. After each _timer amount
        of time, the waiting is interrupted and the action is invoked.
        """
        WATCH_DOG.debug(f"PeriodicThread starting, action will be performed every {self._timer}s")
        # Repeat the wait as long as the stop event is not set
        while not self._stop_event.is_set():
            # Wait the _timer seconds or until the stop event is set
            if self._stop_event.wait(self._timer):
                # The sleep was interrupted by the stop_event, terminated the thread
                break
            # The sleep was interrupted by a wait timeout, perform the action
            self._callback(*self._callback_args)
        WATCH_DOG.debug("PeriodicThread stop_event detected, terminating the thread")

    def __enter__(self):
        """The context manager entry sentinel, starts the thread loop.

        :return: the thread object
        """
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """The context manager exit sentinel, sets the stop_event flag so that the thread loop
        terminates.

        :param exc_type: the type of the exception
        :param exc_val: the value of the exception
        :param exc_tb: the exception traceback
        """
        self._stop_event.set()


class TimeoutThread(Thread):
    """The TimeoutThread starts a timer that waits for a specified amount of time, after which
    a flag that indicates the reached timeout is set.

    The thread is intended to be used as a context manager.

    :ivar timeout_event: the threading.Event that represents the timer
    :ivar _timer: the time to wait until a timeout is reached
    """

    def __init__(self, timer):
        """Creates the TimeoutThread object

        :param timer: the time to wait until a timeout is reached
        """
        super().__init__()
        self.timeout_event = Event()
        self._timer = timer

    def run(self):
        """The thread loop that waits for the timeout to be reached."""
        WATCH_DOG.debug(f"TimeoutThread started, waiting for {self._timer}s")
        if self.timeout_event.wait(self._timer):
            WATCH_DOG.debug("TimeoutThread interrupted before reaching the timeout")
            return
        # Set the event so that the main thread can check, that the timeout has been reached
        self.timeout_event.set()
        WATCH_DOG.debug("Timeout reached")

    def reached(self):
        """Checks if the timeout has already been reached.

        :return: true if the timeout has been reached
        """
        return self.timeout_event.is_set()

    def __enter__(self):
        """The context manager entry sentinel, starts the thread loop.

        :return: the thread object
        """
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """The context manager exit sentinel, stops the timer if it is still running.

        :param exc_type: the type of the exception
        :param exc_val: the value of the exception
        :param exc_tb: the exception traceback
        """
        # The event might be already set, if the timer went off
        # Or it might not, if the main thread has been interrupted by a signal etc.
        if not self.timeout_event.is_set():
            self.timeout_event.set()
