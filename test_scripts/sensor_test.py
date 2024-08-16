import time
import board
import adafruit_ens160
import Adafruit_DHT

i2c = board.I2C()  # uses board.SCL and board.SDA

ens = adafruit_ens160.ENS160(i2c)

hum, temp = Adafruit_DHT.read_retry(Adafruit_DHT.AM2302, 4) #(Sensor, Pin)

# Set the temperature compensation variable to the ambient temp
# for best sensor calibration
ens.temperature_compensation = temp
# Same for ambient relative humidity
ens.humidity_compensation = hum

while True:
	print("AQI (1-5):", ens.AQI)
	print("TVOC (ppb):", ens.TVOC)
	print("eCO2 (ppm):", ens.eCO2)

	hum, temp = Adafruit_DHT.read_retry(Adafruit_DHT.AM2302, 4) #(Sensor, Pin)
	print("Temp C:", temp)
	print("Hum %:", hum)
	print()

	# new data shows up every second or so
	time.sleep(5)
