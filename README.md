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

**Setup:**

Install dependancies:
- _pip3 install pandas_
- _pip3 install board_
- _pip3 install Adafruit_DHT_
- _pip3 install adafruit-circuitpython-ens160_
- _pip3 install flask_
- _pip3 install apscheduler_

Enable I2C interface
 - _sudo raspi-config_ > Interface > enable I2C
 - Set IP address to a static IP address on you router
 - Change IP address at the end of the WebAirQuality.py file

**Test Scripts:**

 - forcast_test.py
 - sensor_test.py
 - read_pickle.py
   
**Usage:**

_python WebAirQuality.py_

Access the webpage a the raspberrypi's ip address followed by the port. Example: _192.168.1.10:9999_ or _raspberypi.local:9999_

Default port is: 9999

**Trouble Shooting**

If "error: externally-managed-environment..." when installing pip use the following command:
_sudo mv /usr/lib/python3.11/EXTERNALLY-MANAGED /usr/lib/python3.11/EXTERNALLY-MANAGED.old_


There are sometimes issues reported on Raspberry Pi setups when installing using pip3 install (or pip install). These will typically mention:

libf77blas.so.3: cannot open shared object file: No such file or directory
The solution will be to either:

	_sudo apt-get install libatlas-base-dev_
	to install the missing libraries expected by the self-compiled NumPy (ATLAS is a possible provider of linear algebra).

Alternatively use the NumPy provided by Raspbian. In which case run:

	_pip3 uninstall numpy_  # remove previously installed version
	_apt install python3-numpy_

https://numpy.org/devdocs/user/troubleshooting-importerror.html