#!/bin/bash
# Dependencies installation script for WebAirQuality v2.0
set -e

echo "=============================================="
echo "Installing dependencies for WebAirQuality v2.0"
echo "=============================================="

# Update package lists
sudo apt-get update

# Install system dependencies for GPIO and I2C if not already present
sudo apt-get install -y python3-pip python3-setuptools python3-requests python3-flask

# Install Python packages
pip3 install flask apscheduler requests adafruit-circuitpython-ens160 Adafruit_DHT

echo ""
echo "Dependencies installation complete!"
echo "Make sure I2C interface is enabled: sudo raspi-config -> Interfacing Options -> I2C"
echo "To run the dashboard: python3 WebAirQuality.py"
