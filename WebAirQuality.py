# -*- coding: utf-8 -*-
"""
Created on Tue Dec 19 21:24:38 2023

@author: Tim Mallen

Script for measure the air quality from multiple sensosrs on a raspberry pi and
host a web site with values and charts of the sensor values. 
"""

import os
import datetime as dt
from datetime import datetime, timedelta
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

    
#%% AM2302
# Set up the GPIO pin for the sensor
GPIO.setmode(GPIO.BCM)
DHT_PIN = 4

# Initialize the sensor
sensor = Adafruit_DHT.AM2302;

#%% ENS160
i2c = board.I2C()
ens = adafruit_ens160.ENS160(i2c)

# Set the temperature compensation variable to the ambient temp
# for best sensor calibration
ens.temperature_compensation = 23
# Same for ambient relative humidity
ens.humidity_compensation = 55

#%% Create blank image for img_base64
# Save the plot to a BytesIO object
plt.plot()
img_stream = io.BytesIO()
plt.savefig(img_stream, format='png')
img_stream.seek(0)
plt.close()

# Encode the plot image as base64
img_base64 = base64.b64encode(img_stream.read()).decode('utf-8')

#%% Predefine global forcast dataframe
forcast_df = pd.DataFrame({})

#%% Functions
def read_temp_humidity():
    # Read the temperature and humidity from the sensor
    humidity, temperature = Adafruit_DHT.read_retry(sensor, DHT_PIN)

    if humidity is not None and temperature is not None:
	# Convert C to F
        temperature = round((temperature*9/5)+32,1)
        return temperature, round(humidity,1)
    else:
        return None, None
    

def read_air_quality():
    aqi  = int(ens.AQI)
    tvoc = float(ens.TVOC)
    eco2 = float(ens.eCO2)

    if aqi is not None and tvoc is not None and eco2 is not None:
        return aqi, tvoc, eco2
    else:
        return None, None, None
    

def create_data_frame():
    # Read sensors
    temperature, humidity = read_temp_humidity()
    aqi, tvoc, eco2 = read_air_quality()

    # Get current time
    current_time = dt.datetime.now()
    
    # Get getoutside temp
    outside_temp, outdoor_hum = get_outside_temp()
	
    # Create new dataframe
    new_df = pd.DataFrame(index=[current_time], data={"aqi":aqi, "tvoc":tvoc, "eco2":eco2, "temp":temperature, "hum":humidity, "out_temp":outside_temp, "out_hum":outdoor_hum})
    
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
    

def get_forcast():
    global forcast_df
    
    ## https://weather-gov.github.io/api/general-faqs
    ## Use this to find your location:
    ## url = 'https://api.weather.gov/points/39.4858,-76.3076'
    
    # Get hour forcast from the National Weather Service API 
    url = 'https://api.weather.gov/gridpoints/LWX/118,101/forecast/hourly'
    try:
        response = requests.get(url)
    
        if response.status_code == 200:
            data = json.loads(response.text)
            
            forcast = {}
            for p in data['properties']['periods']:
                date_string = p['startTime']
                
                # Convert string to datetime object
                date_time_obj = datetime.fromisoformat(date_string[:-6])  # Remove the timezone offset for parsing
                
        #        # Extract timezone offset
        #        timezone_offset = date_string[-6:]
        #        offset_hours = int(timezone_offset[:3])
        #        offset_minutes = int(timezone_offset[4:])
        #        
        #        # Create a timezone object with the extracted offset
        #        timezone = timedelta(hours=offset_hours, minutes=offset_minutes)
        #        
        #        # Apply the timezone offset to the datetime object
        #        date_time_obj_with_tz = date_time_obj - timezone
            
                # Get temperature
                outdoor_temp = p['temperature']
                
                # Get Humidity
                outdoor_hum = p['relativeHumidity']['value']
                
                # Add temp and humidity to a list of dictionaries
                forcast[date_time_obj] = {'outdoor_temp':outdoor_temp, 'outdoor_hum':outdoor_hum}
            
            # create and transpose a pandad data frame of the hour forcast
            forcast_df = pd.DataFrame(forcast).T
        else:
            print('Error fetching data from api.weather.gov')
    except:
        print('Error with response')
    
def get_outside_temp(): 
    global forcast_df
    
    # Find closet time
    try:
        closest_value = forcast_df.iloc[np.argmin(abs(forcast_df.index - datetime.now()))]   
    
        # Return Outdoor temperature of the nearest forcast hour
        return closest_value['outdoor_temp'], closest_value['outdoor_hum']
    except:
        print("Error reading outdoor temp and humidity")
        return 0, 0
        

def make_plot():
    global img_base64
    
    # Read in data frame of air quality data
    df = pd.read_pickle(file_path)
    	   
    # Create subplots
    fig, axs = plt.subplots(5, 1, figsize=(8, 16), sharex=True)  
    
    # AQI
    axs[0].plot(df.index.values, df.aqi.values,  linestyle='-', marker='', color='r')   
    
    # TVOC
    axs[1].plot(df.index.values, df.tvoc.values, linestyle='-', marker='', color='g')
    # TVOC Boundary Lines
    axs[1].axhline(y = 400,  color = 'g', linestyle = '-') 
    axs[1].axhline(y = 2200, color = 'y', linestyle = '-') 
    axs[1].axhline(y = 3000, color = 'r', linestyle = '-') 
    # TVOC Boundary Labels
    axs[1].text(df.index[0],  400, 'Normal',  color = 'g') 
    axs[1].text(df.index[0],  2200, 'Bad',     color = 'y') 
    axs[1].text(df.index[0],  3000, 'Serious', color = 'r') 
    
    # EC02
    axs[2].plot(df.index.values, df.eco2.values, linestyle='-', marker='', color='b')
    # ECO2 Boundary Lines
    axs[2].axhline(y = 400,  color = 'g', linestyle = '-') 
    axs[2].axhline(y = 600,  color = 'b', linestyle = '-') 
    axs[2].axhline(y = 800,  color = 'm', linestyle = '-') 
    axs[2].axhline(y = 1000, color = 'y', linestyle = '-') 
    axs[2].axhline(y = 1500, color = 'r', linestyle = '-') 
    # ECO2 Boundary Labels
    axs[2].text(df.index[0],  400, 'Excellent', color = 'g') 
    axs[2].text(df.index[0],  600, 'Good',      color = 'b') 
    axs[2].text(df.index[0],  800, 'Fair',      color = 'm') 
    axs[2].text(df.index[0], 1000, 'Poor',      color = 'y') 
    axs[2].text(df.index[0], 1500, 'Bad',       color = 'r') 
    
    # Temperature
    axs[3].plot(df.index.values, df.temp.values, linestyle='-', marker='', color='m')
    
    # Outside Temperature
    axs[4].plot(df.index.values, df.out_temp.values, linestyle='--', marker='', color='m')
    
    # Humidity
    axs[4].plot(df.index.values, df.hum.values,  linestyle='-', marker='', color='b')
    axs[4].plot(df.index.values, df.out_hum.values,  linestyle='--', marker='', color='b')
    
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
    
    # y limits
    axs[0].set_yticks(np.arange(0, 6, 1))
    axs[0].set_yticklabels([' ','Excellent','Good','Moderate','Poor','Unhealthy'])
    axs[2].set_ylim([300,1600])
    axs[3].set_ylim([40,90])
    axs[4].set_ylim([0,100])
    
    # Format the x-axis datetime ticks
    date_format = mdates.DateFormatter('%H:%M')  # Customize the date format as needed
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


#%%	app
# Flask web framework
app = Flask(__name__)

# Route to the main page
@app.route("/")
def index():
	# Read pickle file
    df = pd.read_pickle(file_path)
    
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
    outside_temp = df.out_temp.iloc[-1]
    
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
    else:
        recommended_humidity = 0
        
    humidity_dif = np.round(humidity - recommended_humidity)
    
    if humidity_dif>0:
        hum_quality = 'High, ' + str(humidity_dif)
    else:
        hum_quality = 'Low, ' + str(humidity_dif)
            
    if abs(humidity_dif)>=10:
        hum_quality = 'Very ' + hum_quality
    elif abs(humidity_dif)>=5:
        hum_quality = hum_quality
    elif abs(humidity_dif)<5:
        hum_quality = 'Ok'
    else:
        hum_quality = 'NA'   
        
    # AQI classification
    aqi_class_dict = {1:'Excellent',2:'Good',3:'Moderate',4:'Poor',5:'Unhealthy'}
    try:
        aqi_class = aqi_class_dict[df.aqi.iloc[-1]]
    except:
        aqi_class = "Error"
    
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
                            time = formatted_time,
                            temperature = temp, 
                            temp_quality = temp_quality,
                            humidity = humidity, 
                            hum_quality = hum_quality,
                            aqi = df.aqi.iloc[-1],
                            aqi_type = aqi_class,
                            tvoc = tvoc, 
                            tvoc_quality = tvoc_quality,
                            eco2 = eco2,
                            eco2_type = eco2_quality,
                            plot_image = img_base64)

    
#%% Main
if __name__ == "__main__":    
    # Create pickle file if it doesn't exist
    file_path = "aq_data.pkl"
    if not os.path.exists(file_path):
        df = pd.DataFrame(columns=['aqi', 'tvoc', 'eco2','temp','hum','out_temp','out_hum'])
        df.to_pickle(file_path)
    
    # Call forcast for the first time    
    get_forcast()
    
    # Sample Rate
    sec_between_log_entries = 30
    
    # Create timer that is called every n seconds, without accumulating delays as when using sleep
    print("Creating interval timer. This step takes almost 2 minutes on the Raspberry Pi...")   
    scheduler = BackgroundScheduler()
    scheduler.add_job(sensor_update, 'interval', seconds=sec_between_log_entries, max_instances=1, replace_existing=True)
    scheduler.add_job(make_plot,     'interval', seconds=60, max_instances=1, replace_existing=True)
    scheduler.add_job(get_forcast,   'interval', days=1, max_instances=1, replace_existing=True)
    scheduler.start()
    print("Started interval timer which will be called the first time in {0} seconds.".format(sec_between_log_entries))

    # Start webserver
    try:
        app.run(host='192.168.0.110', port=9999, debug=True, use_reloader=False)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

