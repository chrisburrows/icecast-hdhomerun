import threading
import requests
import time
import logging

UPDATE_INTERVAL = 30


class Icecast(object):
    _logger = logging.getLogger(__name__)

    def __init__(self, config: dict):
        self.server = config["server"]
        self.status_url = config["scheme"] + "://" + config["server"] + "/status-json.xsl"
        self.username = config["username"]
        self.password = config["password"]
        self.mount_point = config["mount"]
        self.streams: dict = dict()
        self.bindings: dict = dict()
        self.last_update: int = 0
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def _save(self, s):
        count: int = s["listeners"]
        path: str = s["listenurl"].lower()
        self.streams[path] = count
        if path in self.bindings:
            for callback in self.bindings[path]:
                callback(path, count)

    def update(self):
        """Pull latest channel lineup from the tuner"""
        self._logger.debug("Fetching latest state from " + self.status_url)

        r = requests.get(self.status_url)
        if r.status_code == 200:
            stats = r.json()["icestats"]
            if "source" in stats:
                # very annoying JSON serialisation where "source" may be absent,
                # a single object or an array
                if isinstance(stats["source"], list):
                    for s in stats["source"]:
                        self._save(s)
                elif isinstance(stats["source"], object):
                    self._save(stats["source"])
            self.last_update = time.time()

    def get_listener_count(self, url: str):
        """Lookup channel URL in listener data"""

        if self.streams is None:
            return None

        if url.lower() in self.streams:
            return self.streams[url.lower()]

        return None

    def bind(self, url: str, callback: callable):
        if url not in self.bindings:
            self.bindings[url.lower()] = list()

        self.bindings[url.lower()].append(callback)

    def get_icecast_publish_url(self) -> str:
        """Get Icecast URL with login details but with no protocol / scheme"""
        return '{user}:{password}@{server}/{mount}'.format(
            user=self.username, password=self.password, server=self.server, mount=self.mount_point)

    def get_icecast_listen_url(self) -> str:
        """Get Icecast listen URL"""
        return 'http://{server}/{mount}'.format(
           server=self.server, mount=self.mount_point)

    def run(self):
        while True:
            try:
                self.update()
                time.sleep(UPDATE_INTERVAL)
            except IOError:
                self._logger.error("Error accessing ICECAST API to check listener count")
                time.sleep(UPDATE_INTERVAL)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    icecast = Icecast({"server": "http://streamer.home:8000",
                       "username": "source", "password": "w1bbl3!",
                       "mount": "radio"})
    icecast.update()
    print(icecast.get_listener_count("http://streamer.home:8000/radio"))
