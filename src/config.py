import json


class Config(object):
    filename: str
    config: dict
    # FLAC or MP3 format
    _default_codec: str = "flac"
    _default_ffmpeg_path: str = "/opt/homebrew/bin/ffmpeg"

    def __init__(self, filename='config.json'):
        self.filename = filename

    def load(self) -> bool:
        """Load a JSON file and return the configuration"""

        with open(self.filename) as json_file:
            self.config = json.load(json_file)
            return self.validate()

    def validate(self) -> bool:
        """Validate the mandatory configuration elements"""
        return True

    def ffmpeg_path(self) -> str:
        """Get the path to the ffmpeg"""
        return self.config['ffmpeg'] if 'ffmpeg' in self.config else Config._default_ffmpeg_path

    def codec(self) -> str:
        """Get the codec for Icecast"""
        return self.config['codec'].lower() if 'codec' in self.config else Config._default_codec

    def mqtt_config(self) -> dict:
        """Return the MQTT configuration"""
        return self.config['mqtt']

    def icecast_config(self) -> dict:
        """Return the Icecast configuration"""
        return self.config['icecast']

    def hdhomerun_config(self) -> dict:
        """Return the HDHomeRun configuration"""
        return self.config['hdhomerun']

    def radio_stations_config(self) -> dict:
        """Return the radio stations configuration"""
        return self.config['stations']

    def owntone_pipe(self) -> str:
        """Return the path to the owntone pipe"""
        return self.config['owntone_pipe']