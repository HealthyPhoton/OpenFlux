# OpenFlux, an open-source online EC flux calculation software
OpenFlux is an online flux calculation software developed by HealthyPhoton Technology. It includes a data collection module and a flux calculation module. The software can collect high-frequency data from site observation devices in real time and calculate flux based on specified time intervals
## Features
- Monitoring Program
	- Real-time monitoring of high-frequency data from multiple instruments
	- Store raw data locally at half-hour intervals
	- Flux Calculation Program

- Secondary coordinate transformation
	- Turbulence stability assessment
	- Time lag calculation
	- Raw flux calculation
## Installation
- python3.x
	- threading
	- pyserial
	- pandas
	- numpy
	- logging

If using a Raspberry Pi, additional packages need to be installed.
- RPi
- pigpio
## License
This project is licensed under the Apache License，as found in the LICENSE file.