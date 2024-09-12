# ===========================================================================================
# Copyright (c)  2024 HealthyPhoton Technology. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root for details.
# ===========================================================================================
import datetime
import threading
import serial
import os
import time
import Data_Calculation_Module

data_dic = {}
data_lock = threading.Lock()  # Lock of data_dic
stop_event = threading.Event()  # Events that control thread stopping
# =======================================================================
# Initialise the serial port
# =======================================================================
ser_wind = 0
ser_ht8x00 = 0
class softuart(threading.Thread):
    global data_dic

    """soft uart(ttl) based on pigpio wiht Rx & Tx GPIO need to be set"""

    def __init__(self, uart_name, rxPin, txPin, baud=9600, timeout=5):
        threading.Thread.__init__(self)
        self._uart_name = uart_name
        self._rxPin = rxPin
        self._txPin = txPin
        self._baud = baud  # according to https://www.raspberrypi.org/forums/viewtopic.php?p=694626, bard>19200 is not reliable
        self._timeout = timeout
        # PIGPIO
        self._pi = pigpio.pi()
        if not self._pi.connected:
            os.system('sudo pigpiod')
            self._pi = pigpio.pi()
        self._pi.set_mode(self._rxPin, pigpio.INPUT)
        self._pi.set_mode(self._txPin, pigpio.OUTPUT)

    def run(self):
        self.flushInput()
        send_cnt = 0
        while True:
            buf = self.read()  # Block and receive data until one frame of data is received

            if self._uart_name == "ser_ht8x00":
                process_ht8x00_data(buf)
            elif self._uart_name == "ser_wind":
                process_wind_data(buf)

    def flushInput(self):
        # fatal exceptions off (so that closing an unopened gpio doesn't error)
        pigpio.exceptions = False
        self._pi.bb_serial_read_close(self._rxPin)
        pigpio.exceptions = True
        # open a gpio to bit bang read, 1 byte each time.
        self._pi.bb_serial_read_open(self._rxPin, self._baud, 8)

    def read(self):


        count = 0
        text = []
        lt = 0
        while lt == 0:

            time.sleep(0.01)
            (count, data) = self._pi.bb_serial_read(self._rxPin)
            if count:
                text += list(data)
                lt += count
                break

        while True:
            # time.sleep(0.02)  # enough time to ensure more data
            time.sleep(0.01)  # enough time to ensure more data
            (count, data) = self._pi.bb_serial_read(self._rxPin)
            if count:
                text += list(data)
                lt += count
            else:
                break
        return bytes(text)


def get_ht8x00_data():
    """
    Obtain HT8x00 data
    :return:
    """
    global data_dic
    try:
        buffer = b''
        while not stop_event.is_set():
            byte = ser_ht8x00.read(1)
            if byte:
                buffer += byte
                if byte == b'\r':
                    process_ht8x00_data(buffer)
                    buffer = b''
                    return data_dic["HT8x00"]
    except Exception as e:
        print(f"An exception occurred while processing HT8x00 data.: {e}")

def get_wind_data():
    """
    Obtain anemometer data
    :return:
    """
    global data_dic
    try:
        buffer = b''
        while not stop_event.is_set():
            byte = ser_wind.read(1)
            if byte == b'\x02':
                buffer = byte
                continue

            buffer += byte

            if byte == b'\x03':
                process_wind_data(buffer)
                buffer = ""
                return data_dic['wind']
    except serial.SerialException as e:
        print(f"Serial port read error: {e}")
    except Exception as e:
        print(f"An exception occurred while retrieving anemometer data: {e}")
    return None

def process_ht8x00_data(data):
    """
    Process the received frame of HT8X00 data
    :param data:
    :return:
    """
    global data_dic
    try:
        data_str = data.decode('utf-8').strip()
        # print("A frame of data received is", data_str)
        parts = data_str.split(',')
        if len(parts) >= 19 :
            nh3_data = float(parts[2].strip())
            ambient_temperature = float(parts[7].strip())
            transmittance = float(parts[9].strip())
            with data_lock:
                data_dic["HT8x00"] = {
                    "real_time_concentration": nh3_data,
                    "ambient_temperature": ambient_temperature,
                    "transmittance": transmittance
                }
    except Exception as e:
        print(f"Error while processing ht8x00 frame data: {e}")



def process_wind_data(data):
    """
    Process the received frame of anemometer data
    :param data:
    :return:
    """
    global data_dic
    try:
        data_str = data[1:-1].decode('utf-8').strip()

        parts = data_str.split(',')
        if len(parts) >= 8 :
            u_axis_speed = float(parts[1].strip())
            v_axis_speed = float(parts[2].strip())
            w_axis_speed = float(parts[3].strip())
            sonic_temp = float(parts[6].strip())
            with data_lock:
                data_dic["wind"] = {
                    "u_axis_speed": u_axis_speed,
                    "v_axis_speed": v_axis_speed,
                    "w_axis_speed": w_axis_speed,
                    "sonic_temp": sonic_temp
                }
        else:
            print("The data format is incorrect or required fields are missing")
            return None
    except Exception as e:
        print(f"An error occurred while processing ultrasonic anemometer data: {e}")
        return None

def read_data():
    """Data reading thread function, the main thread is responsible for this task"""
    while not stop_event.is_set():
        get_ht8x00_data()
        get_wind_data()
        time.sleep(0.01)

def write_data():
    """
    Write Thread
    :return:
    """

    global last_file_time, current_file
    last_timestamp = None  # Used to store the previous timestamp
    while not stop_event.is_set():
        # Reduce cpu usage
        time.sleep(0.01)
        # Get milliseconds
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-4]
        current_centisecond = now.strftime("%f")[:1]
        # Creating a Merge Data Dictionary
        if last_timestamp is None or current_centisecond != last_timestamp:
            with data_lock:

                combined_data = {
                    "time": timestamp,
                    "real_time_concentration": data_dic.get("HT8x00", {}).get("real_time_concentration", None),
                    "ambient_temperature": data_dic.get("HT8x00", {}).get("ambient_temperature", None),
                    "transmittance": data_dic.get("HT8x00", {}).get("transmittance", None),
                    "u_axis_speed": data_dic.get("wind", {}).get("u_axis_speed", None),
                    "v_axis_speed": data_dic.get("wind", {}).get("v_axis_speed", None),
                    "w_axis_speed": data_dic.get("wind", {}).get("w_axis_speed", None),
                    "sonic_temp": data_dic.get("wind", {}).get("sonic_temp", None)
                }
            # Save data to local
            save_data_to_local(combined_data)

            # Update last_timestamp
            last_timestamp = current_centisecond


def sanitize_data(data):
    """

    :param data:
    :return:
    """
    for key in data:
        if isinstance(data[key], str):
            data[key] = data[key].replace('\n', '').replace('\r', '')
    return data

def save_data_to_local(data):
    """
    Save data to local
    :param data:
    :return:
    """
    global last_file_time, current_file,output_filename
    data = sanitize_data(data)
    # try:
    #     print((datetime.datetime.now() - last_file_time).total_seconds() )
    # except:
    #     pass
    # time_inserval =(datetime.datetime.now() - last_file_time).total_seconds()
    if last_file_time is None :
        last_file_time = datetime.datetime.now()
        output_filename = f"{last_file_time.strftime('%Y%m%d_%H%M')}.txt"
        current_file = os.path.join(file_path, output_filename)

    # elif (datetime.datetime.now().minute ==0 or datetime.datetime.now().minute ==30 ):
    elif (datetime.datetime.now().minute%30==0):
        if output_filename !=f"{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt":

            cal_flux = threading.Thread(target=Data_Calculation_Module.run_data_calculation, args=(output_filename,))
            cal_flux.start()
            last_file_time = datetime.datetime.now()
            output_filename = f"{last_file_time.strftime('%Y%m%d_%H%M')}.txt"
            current_file = os.path.join(file_path, output_filename)

    file_exists = os.path.isfile(current_file)

    with open(current_file, 'a', encoding='utf-8') as file:
        if not file_exists:
            header_line = "TIMESTAMP,real_time_concentration,ambient_temperature,transmittance,u_axis_speed,v_axis_speed,w_axis_speed,sonic_temp\n"
            file.write(header_line)
        data_line = f"{data['time']},{data['real_time_concentration']},{data['ambient_temperature']},{data['transmittance']},{data['u_axis_speed']},{data['v_axis_speed']},{data['w_axis_speed']},{data['sonic_temp']}\n"
        file.write(data_line)
        # print("Write data successfully")
        file.flush()


if __name__ == "__main__":

    # =======================================================================
    # Created folder
    # =======================================================================

    file_path = './OpenFLux_data'
    if not os.path.exists(file_path):
        os.makedirs(file_path)

    last_file_time = None
    current_file = None

    # =======================================================================
    # Created folder
    # =======================================================================
    sys = "Windows" # Raspberry ; Windows ;
    try:
        print(f"The program running system is {sys}")
        if sys == "Windows":
            # Start the data reading thread
            read_thread = threading.Thread(target=read_data)
            read_thread.start()
        elif sys == "Raspberry":
            # Start the data reading thread
            import RPi.GPIO as GPIO
            import pigpio
            ser_ht8x00 = softuart('ser_ht8x00', 19, 26, 38400)
            ser_ht8x00.start()
            ser_wind = softuart('ser_wind', 25, 8, 38400)
            ser_wind.start()

            print("Serial port initialisation complete, connecting...")
        while not data_dic:
            time.sleep(0.1)

        # Start the data saving thread
        write_thread = threading.Thread(target=write_data)
        write_thread.start()

        # The main thread waits for the child thread to finish
        read_thread.join()
        write_thread.join()
    except KeyboardInterrupt:
        print("An interrupt signal was captured and is stopping...")
        stop_event.set()
        read_thread.join()  # Wait for the read thread to stop
        write_thread.join()  # Wait for the write thread to stop
        print("The programme has been safely exited.")