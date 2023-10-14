import os
import datetime as dt
import board
import RPi.GPIO as GPIO
import Adafruit_DHT
import adafruit_ens160
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import io
import numpy as np
import requests
import json
import base64
from flask import Flask, render_template#, send_file
from apscheduler.schedulers.background import BackgroundScheduler

# Sample Rate
sec_between_log_entries = 30

#%% AM2302
# Set up the GPIO pin for the sensor
GPIO.setmode(GPIO.BCM)
DHT_PIN = 4

# Initialize the sensor
sensor = Adafruit_DHT.AM2302;

#%% ENS160
i2c = board.I2C()
ens = adafruit_ens160.ENS160(i2c)

#%% Functions
# Create pickle file if it doesn't exist
file_path = "aq_data.pkl"
if not os.path.exists(file_path):
    df = pd.DataFrame(columns=['aqi', 'tvoc', 'eco2','temp','hum'])
    df.to_pickle(file_path)

# Read the temperature and humidity from the sensor
def read_temp_humidity():
    humidity, temperature = Adafruit_DHT.read_retry(sensor, DHT_PIN)

    if humidity is not None and temperature is not None:
	# Convert C to F
        temperature = round((temperature*9/5)+32,1)
        return temperature, round(humidity,1)
    else:
        return None, None

def read_air_quality(temperature, humidity):
    if temperature is not None or humidity is not None:
        # for best sensor calibration
        ens.temperature_compensation = temperature
        # Same for ambient relative humidity
        ens.humidity_compensation = humidity
    else:
        ens.temperature_compensation = 23
        ens.humidity_compensation = humidity = 55
        
    aqi  =   int(ens.AQI)
    tvoc = float(ens.TVOC)
    eco2 = float(ens.eCO2)

    if aqi is not None and tvoc is not None and eco2 is not None:
        return aqi, tvoc, eco2
    else:
        return None, None, None

def create_data_frame():
    # Read sensors
    temperature, humidity = read_temp_humidity()
    # Set the temperature compensation variable to the ambient temp

    aqi, tvoc, eco2 = read_air_quality(temperature, humidity )

    # Get current time
    current_time = dt.datetime.now()
	
    # Create new dataframe
    new_df = pd.DataFrame(index=[current_time], data={"aqi":aqi, "tvoc":tvoc, "eco2":eco2, "temp":temperature, "hum":humidity})
    return new_df

def sensor_update():
    # Read pickle file
    df = pd.read_pickle(file_path)

    # append data
    df = pd.concat([df, create_data_frame()])
	
    # Drop oldest value if greater than
    if df.shape[0]>1000:
        df = df.drop(df.index[0])
		
    # Store data to a pickle
    df.to_pickle(file_path)

def get_outside_temp():	    
    # pip install requests
    # Sign Up for an OpenWeatherMap API Key:    
    # Go to the OpenWeatherMap website.
    # Sign up for a free account.
    # Once registered, you can generate an API key.
    # Replace with your OpenWeatherMap API key
    api_key = 'YOUR_API_KEY'
    
    # Replace with the city and country code of the location you want to get the weather for
    city = 'South Bel Air'
    country_code = 'US'
    
    # Make the API request
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city},{country_code}&appid={api_key}&units=metric'
    response = requests.get(url)
    
    if response.status_code == 200:
        data = json.loads(response.text)
        temperature = data['main']['temp']
        return temperature
    else:
        print('Error fetching data from OpenWeatherMap API')
        return np.nan

def make_plot(df):    	   
    # Create subplots
    fig, axs = plt.subplots(5, 1, figsize=(8, 16), sharex=True)  
    # AQI
    axs[0].plot(df.index.values, df.aqi.values,  linestyle='-', marker='', color='r')
    # TVOC
    axs[1].plot(df.index.values, df.tvoc.values, linestyle='-', marker='', color='g')
    axs[1].axhline(y = 400,  color = 'g', linestyle = '-') 
    axs[1].axhline(y = 2200, color = 'y', linestyle = '-') 
    axs[1].axhline(y = 3000, color = 'r', linestyle = '-') 
    # EC02
    axs[2].plot(df.index.values, df.eco2.values, linestyle='-', marker='', color='b')
    axs[2].axhline(y = 400,  color = 'g', linestyle = '-') 
    axs[2].axhline(y = 600,  color = 'b', linestyle = '-') 
    axs[2].axhline(y = 800,  color = 'm', linestyle = '-') 
    axs[2].axhline(y = 1000, color = 'y', linestyle = '-') 
    axs[2].axhline(y = 1500, color = 'r', linestyle = '-') 
    # Temp
    axs[3].plot(df.index.values, df.temp.values, linestyle='-', marker='', color='m')
    # Humidity
    axs[4].plot(df.index.values, df.hum.values,  linestyle='-', marker='', color='y')
    
    # Hide xticks
    for ax in axs:
        ax.set_xticks([])
        ax.grid()
    
    # y labels
    axs[0].set_ylabel("AQI")
    axs[1].set_ylabel("TVOC, ppb")
    axs[2].set_ylabel("ECO2, ppm")
    axs[3].set_ylabel("Temperature, F")
    axs[4].set_ylabel("Humidity, %")
    
    # Y limits
    axs[0].set_yticks(np.arange(0, 6, 1))
    axs[2].set_ylim([300,1600])
    axs[3].set_ylim([30,100])
    axs[4].set_ylim([0,100])
    
    # Format the x-axis datetime ticks
    date_format = mdates.DateFormatter('%Y-%m-%d %H:%M')  # Customize the date format as needed
    axs[4].xaxis.set_major_formatter(date_format)
    axs[4].xaxis.set_major_locator(mdates.MinuteLocator(interval=30))  # Specify tick interval
    
    # Add labels and a title
    axs[4].set_xlabel("Date Time")
    plt.xticks(rotation=90)  # Adjust the rotation angle as needed  
    
    # Adjust subplot spacing
    plt.tight_layout()
     
    # Save the plot to a BytesIO object
    img_stream = io.BytesIO()
    plt.savefig(img_stream, format='png')
    img_stream.seek(0)
    plt.close()
    
    # Encode the plot image as base64
    img_base64 = base64.b64encode(img_stream.read()).decode('utf-8')
    
    return img_base64

print("Creating interval timer. This step takes almost 2 minutes on the Raspberry Pi...")
#create timer that is called every n seconds, without accumulating delays as when using sleep
scheduler = BackgroundScheduler()
scheduler.add_job(sensor_update, 'interval', seconds=sec_between_log_entries, max_instances=1, replace_existing=True)
scheduler.start()
print("Started interval timer which will be called the first time in {0} seconds.".format(sec_between_log_entries))

#%%	app
# Flask web framework
app = Flask(__name__)

# Route to the main page
@app.route("/")
def index():
	# Read pickle file
    df = pd.read_pickle(file_path)
	
	# Make plot
    plot_image = make_plot(df)
    
    # Format time
    formatted_time = df.index[-1].strftime("%Y-%m-%d %H:%M:%S")	
    
    # Temperature classification
    temp = df.temp.iloc[-1]
    if temp<60:
        temp_quality = 'Very Low'
    elif temp>=60 and temp<68:
        temp_quality = 'Low'
    elif temp>=68 and temp<=76:
        temp_quality = 'Good'
    elif temp>=76 and temp<80:
        temp_quality = 'High'
    elif temp>=76 and temp<80:
        temp_quality = 'Very High'
        
    # Humidity classification
    humidity = df.hum.iloc[-1]
    outside_temp = 40
    # outside_temp = get_outside_temp()
    if outside_temp>=40:
        recommended_humidity = 45
    elif outside_temp>=30:
        recommended_humidity = 40
    elif outside_temp>=20:
        recommended_humidity = 35
    elif outside_temp>=10:
        recommended_humidity = 30
    elif outside_temp>=0:
        recommended_humidity = 25
    elif outside_temp>=-10:
        recommended_humidity = 20
    elif outside_temp>=-20:
        recommended_humidity = 15
       
    humidity_dif = humidity - recommended_humidity
    if abs(humidity_dif)>3:
        if humidity_dif>3:
            hum_quality = 'Ok'
        else:
            hum_quality = 'Ok'
    elif abs(humidity_dif)>5:
        if humidity_dif>5:
            hum_quality = 'High'
        else:
            hum_quality = 'Low'
    elif abs(humidity_dif)>10:
        if humidity_dif>10:
            hum_quality = 'Very High'
        else:
            hum_quality = 'Very Low'
        
    # AQI classification
    aqi_class_dict = {1:'Excellent',2:'Good',3:'Moderate',4:'Poor',5:'Unhealthy'}
    aqi_class = aqi_class_dict[df.aqi.iloc[-1]]
    
    # TVOC classification
    tvoc = df.tvoc.iloc[-1]
    if tvoc<400:
        tvoc_quality = 'Normal'
    elif tvoc>=400 and tvoc<2200:
        tvoc_quality = 'Iidentify the sources of VOCs and eliminate them'
    elif tvoc>=2200 and tvoc<3000:
        tvoc_quality = 'Take immediate action to improve air quality by increasing ventilation and removing products that emit gasses'
    
    # eco2 classification  
    eco2 = df.eco2.iloc[-1]
    if eco2>=400 and eco2<600:
        eco2_quality = 'Excellent'
    elif eco2>=600 and eco2<800:
        eco2_quality = 'Good'
    elif eco2>=800 and eco2<1000:
        eco2_quality = 'Fair'
    elif eco2>=1000 and eco2<15000:
        eco2_quality = 'Poor'
    elif eco2>=15000:
        eco2_quality = 'Bad'
        
	# Pass the values to the template
    return render_template("index.html", 
                           time=formatted_time,
						   temperature=temp, 
                           temp_quality=temp_quality,
						   humidity=humidity, 
                           hum_quality=hum_quality,
						   aqi=df.aqi.iloc[-1],
                           aqi_type=aqi_class,
						   tvoc=tvoc, 
                           tvoc_quality=tvoc_quality,
						   eco2=eco2,
                           eco2_type=eco2_quality,
						   plot_image=plot_image)


    
#%% Main
if __name__ == "__main__":
    try:
        app.run(host='192.168.0.110', port=9999, debug=True, use_reloader=False)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

