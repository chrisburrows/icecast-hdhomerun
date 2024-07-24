from pathlib import Path

ffmpeg_codec: dict[str, list[str]] = dict()


def _find_ffmpeg() -> str:
    for p in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"]:
        file = Path(p)
        if file.is_file():
            return p
    return None


class FFmpeg:

    def __init__(self, path: str = None):
        if path is None:
            self._ffmpeg = _find_ffmpeg()
        else:
            self._ffmpeg = path

    def preamble(self) -> [str]:
        return [
            '{ffmpeg}'.format(ffmpeg=self._ffmpeg),
            '-hide_banner',
            '-loglevel', 'panic',
            '-nostats',
            '-fflags', 'nobuffer',
        ]

    def url_input(self, source_url: str) -> [str]:
        return [
            '-analyzeduration', '1000000',
            '-i', '{source}'.format(source=source_url),
            '-vn',
            '-map', '0:a:0',
            '-ar', '48000',
            '-ac', '2'
        ]

    def pipe_input(self) -> [str]:
        return [
            '-i', '-'
            '-vn'
            '-map', '0:a:0',
            '-ar', '48000',
            '-ac', '2'
        ]

    def hifiberry_input(self) -> [str]:
        return [
            "-f", "alsa",
            "-c:a", "pcm_s32le",
            "-r", "48000",
            "-use_wallclock_as_timestamps", "1",
            "-i", "dsnoop:CARD=sndrpihifiberry,DEV=0"
        ]

    def icecast_output(self, name: str, description: str, icecast: str) -> [str]:
        return [
            '-ice_name', '{name}'.format(name=name),
            '-ice_description', '{description}'.format(description=description),
            'icecast://{icecast}'.format(icecast=icecast)
        ]

    def pipe_output(self) -> [str]:
        return [
            '-'
        ]

    def codec(self, codec: str) -> [str]:
        if codec.lower() == "flac":
            return [
                '-c:a', 'flac',
                '-b:a', '192k',
                '-compression_level', '10',
                '-f', 'ogg',
                '-content_type', 'application/ogg'
            ]

        if codec.lower() == "mp3":
            return [
                '-c:a', 'libmp3lame',
                '-qscale:a', '3',
                '-f', 'mp3',
                '-content_type', 'audio/mpeg'
            ]

        if codec.lower() == "aac":
            return [
                '-c:a', 'aac',
                '-b:a', '192k',
                '-f', 'adts',
                '-content_type', 'audio/aac'
            ]
