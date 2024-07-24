import logging
import subprocess
import threading
import time
import sys
import traceback
import atexit
from queue import Queue
from typing import Callable

from src.process_state import ProcessState


class ProcessRunner:
    _logger = logging.getLogger(__name__)

    def __init__(self, callback: Callable, pipe_stdin: bool = False, pipe_stdout: bool = False) -> None:
        self._logger.info("Starting ProcessRunner")
        self._callback = callback
        self._pipe_stdin = pipe_stdin
        self._pipe_stdout = pipe_stdout
        self._queue: Queue = Queue()
        self._manager: threading.Thread = None
        self._watcher: threading.Thread = None
        self._process: subprocess.Popen = None
        self._manager = threading.Thread(target=self._manage)
        self._manager.daemon = True
        self._manager.start()
        atexit.register(self.stop)

    def start(self, command: list[str], restart: bool = False):
        """Pass the command to run"""
        self._logger.debug("Queuing command: {cmd} with restart {restart}"
                           .format(cmd=command, restart=restart))
        self._queue.put((command, restart))

    def _manage(self):
        """Wait for the command to run from the client"""
        self._logger.info("Waiting for command to run")
        while True:
            try:
                (command, restart) = self._queue.get()
                self._queue.task_done()
                self._logger.debug("Command: " + " ".join(command))
                if self.is_running():
                    self._logger.debug("Stopping old command")
                    self.stop()
                    self._watcher.join(timeout=2)
                self._watcher = threading.Thread(target=self._start, args=[command, restart])
                self._watcher.start()

            except Exception as e:
                self._logger.debug(str(e))
                traceback.print_exc(file=sys.stdout)

    def _start(self, command: list[str], restart: bool = False):
        """Start the required process running"""

        self._logger.debug("Starting process")
        if command is None:
            raise Exception("No command specified")

        while True:
            self._process = subprocess.Popen(command,
                                             stdin=None,
                                             stdout=None,
                                             stderr=None,
                                             shell=False,
                                             start_new_session=True)
            if self._callback is not None:
                self._callback(ProcessState.STARTED, 0)

            self._process.wait()

            if self._callback is not None:
                self._callback(ProcessState.STOPPED, self._process.returncode)

            if not restart or self._process.returncode < 0:
                break

    def is_running(self):
        return self._process is not None and self._process.returncode is None

    def stop(self):
        """Stop the subprocess"""

        self._logger.debug("Stopping process")
        if self._process is not None and self._process.returncode is None:
            self._logger.debug("  - Terminating process")
            self._process.terminate()
            for i in range(0, 25):
                if self._process.returncode is not None:
                    break
                time.sleep(0.1)

            if self._process.returncode is None:
                self._logger.debug("  - Killing process")
                self._process.kill()
                for i in range(0, 25):
                    if self._process.returncode is not None:
                        break
                if self._process.returncode is None:
                    return False
        return True

    def wait(self):
        """Wait for the process to complete"""
        if self._process is not None and self._process.returncode is None:
            self._logger.debug("Waiting for process")
            self._process.wait()

    def get_stdin(self):
        """Get the STDIN pipe for the command - to send it data"""
        return self._process.stdin if self._process is not None else None

    def get_stdout(self):
        """Get the STDIN pipe for the command - to send it data"""
        return self._process.stdout if self._process is not None else None


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    _process = ProcessRunner()
    _process.start(["/bin/sleep", "60"])

    time.sleep(15)
    _process.stop()
