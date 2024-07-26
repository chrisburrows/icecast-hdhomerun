import logging
import subprocess
import threading
import time
import sys
import traceback
import atexit
from queue import Queue
from typing import Callable

from process_state import ProcessState

logger = logging.getLogger(__name__)


class ProcessRunner:

    def __init__(self, callback: Callable, pipe_stdin: bool = False, pipe_stdout: bool = False) -> None:
        logger.info("Starting ProcessRunner")
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

    def start(self, command: list[str], restart: bool = False, stdin: bool = False, stdout: bool = False, stderr: bool = False):
        """Pass the command to run"""
        logger.debug("Queuing command: {cmd} with restart {restart}"
                           .format(cmd=command, restart=restart))
        self._queue.put((command, restart, stdin, stdout, stderr))

    def _manage(self):
        """Wait for the command to run from the client"""
        logger.info("Waiting for command to run")
        while True:
            try:
                (command, restart, stdin, stdout, stderr) = self._queue.get()
                self._queue.task_done()
                logger.debug("Command: " + " ".join(command))
                if self.is_running():
                    logger.debug("Stopping old command")
                    self.stop()
                    self._watcher.join(timeout=2)
                self._watcher = threading.Thread(target=self._start, args=[command, restart, stdin, stdout, stderr])
                self._watcher.start()

            except Exception as e:
                logger.debug(str(e))
                traceback.print_exc(file=sys.stdout)

    def _start(self, command: list[str], restart: bool, stdin: bool, stdout: bool, stderr: bool):
        """Start the required process running"""

        logger.debug("Starting process: {cmd} restart: {restart} stdin: {stdin} stdout: {stdout} stderr: {stderr}".format(cmd=command, restart=restart, stdin=stdin, stdout=stdout, stderr=stderr))
        if command is None:
            raise Exception("No command specified")

        while True:
            self._process = subprocess.Popen(command,
                                             stdin=subprocess.PIPE if stdin else None,
                                             stdout=subprocess.PIPE if stdout else None,
                                             stderr=subprocess.PIPE if stderr else None,
                                             shell=False,
                                             pipesize=4096,
                                             start_new_session=True)
            if self._callback is not None:
                self._callback(ProcessState.STARTED, 0)

            logger.debug("Waiting for process to finish")
            self._process.wait()
            logger.debug("Process has exited with status {rc}".format(rc=self._process.returncode))

            if self._callback is not None:
                self._callback(ProcessState.STOPPED, self._process.returncode)

            if not restart or self._process.returncode < 0:
                break

    def is_running(self):
        return self._process is not None and self._process.returncode is None

    def stop(self):
        """Stop the subprocess"""

        logger.debug("Stopping process")
        if self._process is not None and self._process.returncode is None:
            logger.debug("  - Terminating process")
            self._process.terminate()
            for i in range(0, 50):
                if self._process.returncode is not None:
                    break
                time.sleep(0.1)

            if self._process.returncode is None:
                logger.debug("  - Killing process")
                self._process.kill()
                for i in range(0, 50):
                    if self._process.returncode is not None:
                        break
                    time.sleep(0.1)
                if self._process.returncode is None:
                    return False
        return True

    def wait(self):
        """Wait for the process to complete"""
        if self._process is not None and self._process.returncode is None:
            logger.debug("Waiting for process")
            self._process.wait()

    def get_stdin(self):
        """Get the STDIN pipe for the command - to send it data"""
        return self._process.stdin if self._process is not None else None

    def get_stdout(self):
        """Get the STDIN pipe for the command - to read data"""
        return self._process.stdout if self._process is not None else None

    def get_stderr(self):
        """Get the STDERR pipe for the command - to read data"""
        return self._process.stderr if self._process is not None else None

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    _process = ProcessRunner()
    _process.start(["/bin/sleep", "60"])

    time.sleep(15)
    _process.stop()
