

def hifi_berry() -> [str]:
    return [
        "arecord",
        "-D", "dsnoop:CARD=sndrpihifiberry,DEV=0",
        "-r", "48000",
        "-c", "2",
        "-f", "S32_LE"
    ]

