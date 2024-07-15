FROM python:3.11-slim

RUN apt update
RUN apt-get install -y ffmpeg
RUN apt-get clean
RUN apt-get autoclean

RUN mkdir -p /radio/src /radio/etc

COPY src/* /radio/src
COPY requirements.txt /radio

RUN pip install --upgrade pip
RUN pip install -r /radio/requirements.txt

WORKDIR /radio/src
CMD python radio.py --config /radio/etc/config.json
