# -*- coding: utf-8 -*-
"""
Created on Tue Dec 19 21:24:38 2023

@author: Tim
"""

import requests
import json
import pprint
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

##url = 'https://api.weather.gov/points/39.4858,-76.3076'
url = 'https://api.weather.gov/gridpoints/LWX/118,101/forecast/hourly'

response = requests.get(url)

data = json.loads(response.text)
pprint.pprint(data)

forcast = {}
for p in data['properties']['periods']:
    date_string = p['startTime']
    
    # Convert string to datetime object
    date_time_obj = datetime.fromisoformat(date_string[:-6])  # Remove the timezone offset for parsing
    
    # Extract timezone offset
    timezone_offset = date_string[-6:]
    offset_hours = int(timezone_offset[:3])
    offset_minutes = int(timezone_offset[4:])
    
    # Create a timezone object with the extracted offset
    timezone = timedelta(hours=offset_hours, minutes=offset_minutes)
    
    # Apply the timezone offset to the datetime object
    date_time_obj_with_tz = date_time_obj - timezone

    outdoor_temp = p['temperature']
    
    outdoor_hum = p['relativeHumidity']['value']
    
    forcast[date_time_obj] = {'outdoor_temp':outdoor_temp, 'outdoor_hum':outdoor_hum}
    
df = pd.DataFrame(forcast).T

# Find closest time to now
dx = df.index - datetime.now()

closest_value = df.iloc[np.argmin(abs(dx))]