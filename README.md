# Stream HDHomeRun Radio Stations to Icecast

Server to allow radio services pulled from an HDHomeRun server to be pushed to an Icecast server 
controlled by MQTT.

The server pulls a list of available radio stations from the HDHomeRun and creates a Select sensor in
Home Assistant. MQTT switches and sensors are used to control the selection of a radio station 
that is then pushed to an Icecast server.

A single stream (radio station) is supported at any one time.

Can be dockerised for ease of deployment.

