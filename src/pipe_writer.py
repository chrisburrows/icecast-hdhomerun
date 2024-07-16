import sys
import threading
import logging
import argparse
from collections import deque

MAX_CHUNKS = 256
CHUNK_SIZE = 1024


class PipeWriter():

    def __init__(self, audio_in, audio_out):
        self._audio_in = audio_in
        self._audio_out = audio_out

        # deque limits the number of elements to maxlen by discarding from the head
        # when elements are appended to the tail creating a fixed size buffer
        self._audio_buffers = deque(maxlen=MAX_CHUNKS)

        # condition variable to kick writer to start again when
        # audio data is available
        self._audio_available = threading.Condition()

        # Start reader and writer threads
        self._read_thread = threading.Thread(target=self._reader)
        self._write_thread = threading.Thread(target=self._writer)

    def _writer(self):
        """
        Write data to the output pipe. Waits for data to be available, and will
        reopen the output pipe (fifo) if it is closed.
        """
        logging.info("Writer starting...")
        while True:
            try:
                logging.info("Writer opening audio pipe")
                logging.info("Writer successfully opened audio pipe")

                while True:
                    try:
                        audio = audio_buffers.popleft()
                        self._audio_out.write(audio)
                    except IndexError:
                        logging.debug("Audio buffer empty... waiting for audio")
                        with(self.audio_available):
                            self.audio_available.wait(timeout=0.02)

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
        while True:
            audio = sys.stdin.buffer.read(CHUNK_SIZE)
            audio_buffers.append(audio)
            buffer_is_empty = len(audio_buffers) == 0

            if buffer_is_empty or len(audio_buffers) == 1:
                logging.debug("Audio buffer was empty... notifying writer")
                with(self.audio_available):
                    self.audio_available.notify()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="p2p", description="Pipe 2 pipe transfer audio data")
    parser.add_argument("-b", "--buffer-size",
                        type=int, default=256, dest="buffer_size",
                        help="Size of buffer kBytes")
    parser.add_argument("-l", "--log-level",
                        type=str, default="INFO", dest="log_level",
                        help="Log level")

    args = parser.parse_args()
    audio_buffers = deque(maxlen=args.buffer_size)

    log_level = getattr(logging, args.log_level.upper(), None)
    logging.basicConfig(filename="p2p.log", level=log_level)

    # Start reader and writer threads
    read_thread = threading.Thread(target=reader)
    write_thread = threading.Thread(target=writer)

    read_thread.start()
    write_thread.start()

