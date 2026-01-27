# -*- coding: utf-8 -*-
"""
Created on Tue Dec 19 21:24:38 2023

@author: Tim Mallen

Script for measure the air quality from multiple sensosrs on a raspberry pi and
host a web site with values and charts of the sensor values. 
"""

#%% Import modules
import os
import re
import datetime as dt
from datetime import datetime, timedelta
import board
import RPi.GPIO as GPIO
import Adafruit_DHT
import adafruit_ens160
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import requests
import json
from apscheduler.schedulers.background import BackgroundScheduler
import socket
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading

    
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

#%% Predefine global forcast dataframe
forcast_df = pd.DataFrame({})

#%% Functions
def get_wlan0_ip():
    result = os.popen('ifconfig wlan0').read()
    match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)', result)
    if match:
        return match.group(1)
    return None

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
    new_df = pd.DataFrame(index=[current_time], data={"aqi":aqi, 
													  "tvoc":tvoc, 
													  "eco2":eco2, 
													  "temp":temperature, 
													  "hum":humidity, 
													  "out_temp":outside_temp, 
													  "out_hum":outdoor_hum})
    
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
        print("Error reading outdoor temperature and humidity")
        return 0, 0
        
    
def get_color_segments(x, y, thresholds, colors=['green', 'yellow', 'red', 'black']):
    """Generate color-coded segments for Plotly based on thresholds"""
    # Create color index
    ci = np.zeros((len(y)))
    for t in thresholds:
        ci = ci + (y > t) * 1
    
    # Find color change indices
    cchie = np.where(np.diff(ci) != 0)[0]
    cchis = np.concatenate((np.array([0]), cchie + 1))
    cchie = np.concatenate((cchie, np.array([len(y)])))
    
    segments = []
    for i in range(len(cchis)):
        segments.append({
            'x': x[cchis[i]:cchie[i]],
            'y': y[cchis[i]:cchie[i]],
            'color': colors[int(ci[cchis[i]])]
        })
    return segments

def air_quality_context(df):   
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
        hum_quality = 'Ok'
    elif abs(humidity_dif)>5:
        if humidity_dif>0:
            hum_quality = 'High'
        else:
            hum_quality = 'Low'
    elif abs(humidity_dif)>10:
        if humidity_dif>0:
            hum_quality = 'Very High'
        else:
            hum_quality = 'Very Low'
    else:
        hum_quality = 'NA'
    
        
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

    return {
        'time': formatted_time, 
        'temperature': temp,
        'temp_quality': temp_quality,
        'humidity': humidity,
        'hum_quality': hum_quality,
        'aqi': df.aqi.iloc[-1],
        'aqi_type': aqi_class,
        'tvoc': tvoc,
        'tvoc_quality': tvoc_quality,
        'eco2': eco2,
        'eco2_type': eco2_quality
    }


def make_plot():
    # Read in data frame of air quality data
    df = pd.read_pickle(file_path)
    
    current_air_quality = air_quality_context(df) 

    # Create subplots with 5 rows
    fig = make_subplots(
        rows=5, cols=1,
        shared_xaxes=True,
        subplot_titles=("AQI", "TVOC (ppb)", "eCO2 (ppm)", "Indoor Temperature (F)", "Humidity (%) & Outside Temp"),
        vertical_spacing=0.08
    )
    
    # AQI - Row 1
    fig.add_trace(
        go.Scatter(x=df.index, y=df.aqi.values, mode='lines', name='AQI', 
                   line=dict(color='red', width=2)),
        row=1, col=1
    )
    fig.update_yaxes(range=[0, 5], dtick=1, row=1, col=1)

    # TVOC - Row 2 with color-coded segments
    tvoc_segments = get_color_segments(df.index.values, df.tvoc.values, 
                                       [400, 2200, 3000], 
                                       colors=['green', 'yellow', 'red', 'black'])
    for segment in tvoc_segments:
        fig.add_trace(
            go.Scatter(x=segment['x'], y=segment['y'], mode='lines', 
                       line=dict(color=segment['color'], width=2),
                       showlegend=False),
            row=2, col=1
        )

    fig.update_yaxes(showticklabels=False, row=2, col=1)

    # Add threshold lines for TVOC
    for y_val, label, color in [(400, 'Normal', 'green'), (2200, 'Bad', 'yellow'), (3000, 'Serious', 'red')]:
        fig.add_hline(y=y_val, line_dash="dash", line_color=color, annotation_text=label,
                      annotation_position="left", row=2, col=1)
    fig.update_yaxes(row=2, col=1)
    
    # eCO2 - Row 3 with color-coded segments
    eco2_segments = get_color_segments(df.index.values, df.eco2.values, 
                                       [400, 600, 800, 1000, 1500], 
                                       colors=['green', 'blue', 'magenta', 'yellow', 'red', 'black'])
    for segment in eco2_segments:
        fig.add_trace(
            go.Scatter(x=segment['x'], y=segment['y'], mode='lines', 
                       line=dict(color=segment['color'], width=2),
                       showlegend=False),
            row=3, col=1
        )
        
    fig.update_yaxes(showticklabels=False, row=3, col=1)

    # Add threshold lines for eCO2
    for y_val, label, color in [(400, 'Excellent', 'green'), (600, 'Good', 'blue'), 
                                 (800, 'Fair', 'magenta'), (1000, 'Poor', 'yellow'), 
                                 (1500, 'Bad', 'red')]:
        fig.add_hline(y=y_val, line_dash="dash", line_color=color, annotation_text=label,
                      annotation_position="left", row=3, col=1)
    fig.update_yaxes(range=[300, 1600], row=3, col=1)
    
    # Temperature - Row 4
    fig.add_trace(
        go.Scatter(x=df.index, y=df.temp.values, mode='lines', name='Indoor Temp',
                   line=dict(color='magenta', width=2)),
        row=4, col=1
    )
    fig.update_yaxes(range=[40, 90], row=4, col=1)
    
    # Humidity and Outside Temp - Row 5
    fig.add_trace(
        go.Scatter(x=df.index, y=df.out_temp.values, mode='lines', name='Outside Temp',
                   line=dict(color='magenta', width=2, dash='dash')),
        row=5, col=1
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df.hum.values, mode='lines', name='Indoor Humidity',
                   line=dict(color='blue', width=2)),
        row=5, col=1
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df.out_hum.values, mode='lines', name='Outside Humidity',
                   line=dict(color='blue', width=2, dash='dash')),
        row=5, col=1
    )
    fig.update_yaxes(range=[0, 100], row=5, col=1)
    fig.update_xaxes(title_text="Date Time", row=5, col=1)
    
    # Update layout with dark theme
    fig.update_layout(
        title_text=f"""<b>Air Quality Monitoring Dashboard</b><br>
        Current Time: {current_air_quality['time']}<br>
        Temperature: {current_air_quality['temperature']}°F ({current_air_quality['temp_quality']})<br>
        Humidity: {current_air_quality['humidity']}% ({current_air_quality['hum_quality']})<br>
        AQI: {current_air_quality['aqi']} ({current_air_quality['aqi_type']})<br>
        TVOC: {current_air_quality['tvoc']} ppb ({current_air_quality['tvoc_quality']})<br>
        eCO2: {current_air_quality['eco2']} ppm ({current_air_quality['eco2_type']})""",
        title_x=0.5,
        height=1200,
        width=1000,
        margin=dict(t=350, b=0),
        showlegend=False,
        hovermode='x unified',
        font=dict(size=12, color='white'),
        plot_bgcolor='black',
        paper_bgcolor='black',
        title_font_color='white',
        xaxis_title_font_color='white',
        yaxis_title_font_color='white',
        legend_title_font_color='white'
    )
    
    # Update all x and y axes to have white text
    fig.update_xaxes(title_font_color='white', tickfont_color='white', showgrid=True, gridcolor='#333333')
    fig.update_yaxes(title_font_color='white', tickfont_color='white', showgrid=True, gridcolor='#333333')
    
    # Save as HTML file
    fig.write_html('index.html')
    
    # Add black background to HTML page
    with open('index.html', 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Inject CSS to make body background black
    css_injection = '<style>body { background-color: #000000; margin: 0; padding: 0; }</style>'
    html_content = html_content.replace('<head>', '<head>' + css_injection)
    
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(html_content)


#%% Web Server
def start_http_server(port=9999):
    """Start a simple HTTP server to serve the dashboard."""
    class MyHTTPRequestHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=".", **kwargs)
        
        def log_message(self, format, *args):
            # Suppress logging or customize as needed
            print(f"[HTTP] {format % args}")
    
    server = HTTPServer((get_wlan0_ip() or "0.0.0.0", port), MyHTTPRequestHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"HTTP server started on http://{get_wlan0_ip() or 'localhost'}:{port}/index.html")
    return server

    
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
    sec_between_log_entries = 60 # Don't set below 60 or it will freeze up
    
    # Create timer that is called every n seconds, without accumulating delays as when using sleep
    print("Creating interval timer. This step takes almost 2 minutes on the Raspberry Pi...")   
    scheduler = BackgroundScheduler()
    scheduler.add_job(sensor_update, 'interval', seconds=sec_between_log_entries, max_instances=1, replace_existing=True)
    scheduler.add_job(make_plot,     'interval', seconds=60, max_instances=1, replace_existing=True)
    scheduler.add_job(get_forcast,   'interval', days=1, max_instances=1, replace_existing=True)
    scheduler.start()
    print("Started interval timer which will be called the first time in {0} seconds.".format(sec_between_log_entries))

    # Start HTTP server
    try:
        server = start_http_server(9999)
        # Keep the program running
        while True:
            pass
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

