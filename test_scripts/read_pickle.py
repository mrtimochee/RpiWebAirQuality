# -*- coding: utf-8 -*-
"""
Created on Tue Dec 19 21:24:38 2023

@author: Tim Mallen

 Reads data from the pickle file into a panda dataframe and prints out the last 20 rows.
"""

import pandas

# Read pickle file into a panda data frame
df = pandas.read_pickle("aq_data.pkl")

# Print out last 20 rows of pickle file
print(df[-20:-1])
