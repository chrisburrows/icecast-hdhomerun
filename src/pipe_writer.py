import os
import sys
import threading
import selectors
import logging
import argparse
from collections import deque

import fcntl
import select

from process_state import ProcessState

MAX_CHUNKS = 256
CHUNK_SIZE = 1024


def _non_blocking(fd) -> None:
    """Make a file descriptor non-blocking"""

    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)


class PipeWriter:

    def __init__(self, audio_in, audio_out_filename):
        self._callback = None
        self._audio_in = audio_in
        self._audio_out_filename = audio_out_filename

        logging.debug("PipeWriter: {f} {t}".format(f=audio_in, t=type(audio_in)))

        # deque limits the number of elements to maxlen by discarding from the head
        # when elements are appended to the tail creating a fixed size buffer
        self._audio_buffers = deque(maxlen=MAX_CHUNKS)

        # condition variable to kick writer to start again when
        # audio data is available
        self._audio_available = threading.Semaphore(0)

        # exit flag
        self._done = False

        # Start reader and writer threads
        self._read_thread = threading.Thread(target=self._reader)
        self._write_thread = threading.Thread(target=self._writer)

        self._read_thread.start()
        self._write_thread.start()

    def bind(self, callback) -> None:
        """Register a callback to track state"""
        self._callback = callback

    def _do_callback(self, state: ProcessState, rc: int) -> None:
        if self._callback:
            self._callback(state, rc)

    def stop(self) -> None:
        """Stop the threads"""

        self._done = True

    def wait(self) -> None:
        """Wait for the two threads to finish"""
        self._read_thread.join()
        self._write_thread.join()
        self._do_callback(ProcessState.FINISHED, 0)

    def _writer(self):
        """
        Write data to the output pipe. Waits for data to be available, and will
        reopen the output pipe (fifo) if it is closed.
        """
        logging.info("Writer starting...")
        sel = selectors.DefaultSelector()

        while not self._done:
            try:
                logging.info("Writer opening audio pipe")
                audio_out = open(self._audio_out_filename, "wb")
                _non_blocking(audio_out)
                sel.register(audio_out, selectors.EVENT_WRITE)

                logging.info("Writer successfully opened audio pipe")

                while not self._done:
                    if self._audio_available.acquire(True, 0.1):
                        try:
                            # this could still throw an IndexError exception if the buffer deque is out of sync
                            # with the semaphore. This all works OK as long as the semaphore value is always
                            # >= buffers in the deque.
                            audio = self._audio_buffers.popleft()

                            written = 0
                            while written < len(audio):
                                events = sel.select(0.1)
                                for key, mask in events:
                                    if mask == selectors.EVENT_WRITE:
                                        written = written + audio_out.write(audio[written:])

                        except IndexError:
                            #logging.debug("Audio buffer empty... waiting for audio")
                            pass

            except IOError as e:
                logging.info("Writer IO error")

    def _reader(self):
        """
        Read data from stdin as bytes into a buffer and add the buffer to the audio buffers.
        The audio buffers are implemented using the Deque class that will limit the number of
        buffer elements to its capacity by discarding the first buffer... i.e. it drops
        the oldest data.
        """
        logging.info("Reader starting...")
        sel = selectors.DefaultSelector()
        _non_blocking(self._audio_in)
        sel.register(self._audio_in, selectors.EVENT_READ)

        while not self._done:
            events = sel.select(0.1)
            for key, mask in events:
                if mask == selectors.EVENT_READ:
                    audio = self._audio_in.read(CHUNK_SIZE)
                    self._audio_buffers.append(audio)

                    # semaphore counts available buffers and synchronises between threads
                    # if the writer isn't keeping up, and the deque is discarding things,
                    # the semaphore value could exceed the available buffers in the deque.
                    # Consumer beware!
                    self._audio_available.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="p2p", description="Pipe 2 pipe transfer audio data")
    parser.add_argument("-p", "--pipe",
                        type=str, default="INFO", dest="pipe",
                        help="Output pipe path")
    parser.add_argument("-b", "--buffer-size",
                        type=int, default=256, dest="buffer_size",
                        help="Size of buffer kBytes")
    parser.add_argument("-l", "--log-level",
                        type=str, default="INFO", dest="log_level",
                        help="Log level")

    args = parser.parse_args()

    log_level = getattr(logging, args.log_level.upper(), None)
    logging.basicConfig(filename="p2p.log", level=log_level)

    pipeWriter = PipeWriter(sys.stdin, args.pipe, args.buffer_size)
    pipeWriter.wait()
