# RpiWebAirQuality
WebAirQuality
A raspberypi python script for sampling temperature, humidity, AQI, ECO2 and TVOC. It also runs a webserver to display these values and coresponding graphs to a webpage.

**Hardware:**

- Raspbery Pi
- ENS160 Air quaility sensor
- AM2302 Temperature and Humidity sensor

**Software:**

- Python 3 or greater

**Dependancies:**

- pandas
- matplotlib
- Adafruit_DHT
- adafruit_ens160
- flask
- apscheduler

**Usage:**

_python WebAirQuality.py_

Access the webpage a the raspberrypi's ip address followed by the port. Example: 192.168.1.10:9999

Default port is 9999
