# ---------------------------------------------------------------------------
# Open Asset Import Library (HealthyPhoton Technology)
# ---------------------------------------------------------------------------

# Copyright (c) 2006-2024, HealthyPhoton Technology

# All rights reserved.

# Redistribution and use of this software in source and binary forms,
# with or without modification, are permitted provided that the following
# conditions are met:

# * Redistributions of source code must retain the above
#   copyright notice, this list of conditions and the
#   following disclaimer.

# * Redistributions in binary form must reproduce the above
#   copyright notice, this list of conditions and the
#   following disclaimer in the documentation and/or other
#   materials provided with the distribution.

# * Neither the name of the HealthyPhoton Technology, nor the names of its
#   contributors may be used to endorse or promote products
#   derived from this software without specific prior
#   written permission of the HealthyPhoton Technology .

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# ---------------------------------------------------------------------------
 
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import logging
import re




# 常量设置
SAMPLING_FREQUENCY = 10  # Sample frequence unit:Hz
LAG_TIME = timedelta(seconds=1)  # Lag time unit:s
BASE_DIR = r'.' # path
raw_data_dir = os.path.join(BASE_DIR, "RawData")  # RawData folder name
ec_flux_dir = os.path.join(BASE_DIR, "EC_FLUX")  # Result folder name
# air_density = 1.225  # 空气密度, kg/m^3（常见的标准值）

# Creating a Logger
logging.basicConfig(filename='data_calculation.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Make sure the EC_FLUX folder exists
if not os.path.exists(ec_flux_dir):
    os.makedirs(ec_flux_dir)
#
# # 确保 RawData 文件夹存在
# if not os.path.exists(raw_data_dir):
#     os.makedirs(raw_data_dir)

print(f"Raw Data path: {raw_data_dir}")
print(f"EC FLUX path: {ec_flux_dir}")


# 二次坐标转化
def rotate_coordinates(u, v, w):
    '''
    rotation raw sonic wind speed
    :param u: unit：m/s
    :param v:unit：m/s
    :param w:unit：m/s
    :return: rotated wind speed
    '''
    u_mean = np.mean(u)
    v_mean = np.mean(v)
    theta_z = np.arctan2(v_mean, u_mean)
    u_rot_z = u * np.cos(theta_z) + v * np.sin(theta_z)
    v_rot_z = -u * np.sin(theta_z) + v * np.cos(theta_z)
    w_mean = np.mean(w)
    theta_y = np.arctan2(w_mean,np.nanmean(u_rot_z))
    u2 = u_rot_z * np.cos(theta_y) + w * np.sin(theta_y)
    w2 = -u_rot_z * np.sin(theta_y) + w * np.cos(theta_y)
    v2 = v_rot_z
    return u2, v2, w2


def extract_lagged_data_and_calculate_cov(lag, data, sampling_frequency):
    """
    Extracts the aligned data according to the given time lag and returns the covariance of w_prime and c_prime for the first 5 minutes after alignment

    :param lag: time lag
    :param data:
    :param sampling_frequency:
    :return:
    """
    if lag < 0:
        aligned_w_prime = data['w_prime'][:lag]
        aligned_c_prime = data['c_prime'][-lag:]
    elif lag > 0:
        aligned_w_prime = data['w_prime'][lag:]
        aligned_c_prime = data['c_prime'][:-lag]
    else:
        aligned_w_prime = data['w_prime']
        aligned_c_prime = data['c_prime']

    five_minutes_data_w = aligned_w_prime[:int(5 * 60 * sampling_frequency)]
    five_minutes_data_c = aligned_c_prime[:int(5 * 60 * sampling_frequency)]

    return np.cov(five_minutes_data_w, five_minutes_data_c)[0, 1]


def calculate_turbulent_steady_state(cross_cov_results, w_prime, c_prime, sampling_frequency):
    """
    Calculation of turbulence stability
    :param cross_cov_results:
    :param w_prime:
    :param c_prime:
    :param sampling_frequency:
    :return:
    """
    max_index = np.argmax(cross_cov_results)
    max_lag = max_index - len(cross_cov_results) // 2  # 确定最大值对应的lag

    # 提取经过lag对齐后的原始数据的前5分钟数据，并计算协方差
    previous_flux_mean = extract_lagged_data_and_calculate_cov(max_lag, {'w_prime': w_prime, 'c_prime': c_prime},
                                                               sampling_frequency)
    raw_flux = cross_cov_results[max_index]

    # 计算turbulent_steady_state
    turbulent_steady_state = abs(previous_flux_mean - raw_flux) / abs(raw_flux)
    if turbulent_steady_state <= 0.3:
        turbulent_steady_state = 0
    elif 0.3 < turbulent_steady_state <= 1.0:
        turbulent_steady_state = 1
    else:
        turbulent_steady_state = 2

    return previous_flux_mean, turbulent_steady_state
def calculate_friction_velocity(u_prime, w_prime):
    """
    Calculation of friction wind speed u*
    :param u_prime: unit：m/s
    :param w_prime: unit：m/s
    :return:
    """
    cov_uw = np.mean(u_prime * w_prime)
    u_star = np.sqrt(-cov_uw)
    return u_star


def save_cross_covariance_results(time_data, cross_cov_results, output_path):
    """
    Save the covariance results to a txt file
    :param time_data:
    :param cross_cov_results:
    :param output_path:
    :return:
    """
    headers = [f"{round((i - len(cross_cov_results) // 2) * 0.1, 1)}s" for i in range(len(cross_cov_results))]
    headers.insert(0, "time")  # 在开头插入 "time"
    cross_cov_results.insert(0, time_data)
    cross_cov_results = np.reshape(cross_cov_results ,[1,-1])
    df = pd.DataFrame(cross_cov_results,   columns=headers)
    if not os.path.exists(output_path):
        df.to_csv(output_path, sep='\t', index=True, header=True, mode='w')
    else:
        df.to_csv(output_path, sep='\t', index=True, header=False, mode='a')


def run_data_calculation(filename="flag_file.txt",extra_data_path=""):
    """
    main function，calculation EC flux each half hour
    :param filename:
    :return:
    """
    logging.info("Starting data calculation module.")
    print("Starting data calculation module.")

    # Verify that the original data file exists
    flag_file_path = os.path.join(BASE_DIR,"OpenFLux_data",filename)
    # flag_file_path = os.path.join("./", "OpenFLux数据保存", filename)

    if not os.path.exists(flag_file_path):
        print(f"Flag bit file does not exist, end of program {flag_file_path}")
        return


    if True:

        # ==========================================================================================
        # Read raw data
        # ==========================================================================================
        data = pd.read_csv(flag_file_path, delimiter=',')
        data.dropna(inplace=True)
        data.iloc[:, 1:] = data.iloc[:, 1:].apply(pd.to_numeric, errors='coerce').fillna(0)
        logging.info(f"data length is {len(data)}")

        if extra_data_path:
            extra_data = pd.read_csv(extra_data_path, delimiter=',')
            openflux_rawdata_data =pd.concat([data,extra_data])
        else:
            openflux_rawdata_data = data
        openflux_rawdata_data['real_time_concentration']=openflux_rawdata_data['real_time_concentration']  /16
        # ==========================================================================================
        # Process data
        # ==========================================================================================
        # Initialise the filtered_data
        filtered_data = openflux_rawdata_data.copy()
        filtered_data['u2_axis_speed'] = None
        filtered_data['v2_axis_speed'] = None
        filtered_data['w2_axis_speed'] = None
        # Rotation wind direction
        u2, v2, w2 = rotate_coordinates(filtered_data['u_axis_speed'], filtered_data['v_axis_speed'], filtered_data['w_axis_speed'])
        filtered_data[ 'u2_axis_speed'] = u2
        filtered_data[ 'v2_axis_speed'] = v2
        filtered_data[ 'w2_axis_speed'] = w2



        # Calculate variable detrends use average value
        u_prime = filtered_data['u2_axis_speed'].values - np.nanmean(filtered_data['u2_axis_speed'].values)
        v_prime = filtered_data['v2_axis_speed'].values - np.nanmean(filtered_data['v2_axis_speed'].values)
        w_prime = filtered_data['w2_axis_speed'].values- np.nanmean(filtered_data['w2_axis_speed'].values)
        c_prime = filtered_data['real_time_concentration'].values - np.nanmean(filtered_data['real_time_concentration'].values)

        # Time lag and calculate raw flux

        cross_cov_results = []
        for lag in range(-SAMPLING_FREQUENCY, SAMPLING_FREQUENCY + 1):
            if lag < 0:

                cov = np.cov(w_prime[:lag],c_prime[-lag:])
            elif lag > 0:

                cov = np.cov(w_prime[lag:], c_prime[:-lag])
            else:

                cov = np.cov(w_prime , c_prime )
            cross_cov_results.append(cov[0,1]* 16e-3)

        #  Get the maximum value as raw flux
        index = np.argmax(abs(np.array(cross_cov_results)))
        raw_flux =cross_cov_results[index]

        # Calculate u*

        friction_velocity = (np.cov(u_prime,w_prime)[0,1]**2+np.cov(v_prime,w_prime)[0,1]**2)**0.25

        # Calculate average value
        concentration_mean = np.mean(filtered_data['real_time_concentration'].values)
        u2_mean = np.mean(filtered_data['u2_axis_speed'].values)
        v2_mean = np.mean(filtered_data['v2_axis_speed'].values)
        w2_mean = np.mean(filtered_data['w2_axis_speed'].values)

        #  Turbulent steady state
        previous_flux_mean, turbulent_steady_state = calculate_turbulent_steady_state(cross_cov_results, w_prime,
                                                                                      c_prime, SAMPLING_FREQUENCY)



        # Record the final result in a new CSV file
        result_file_path = os.path.join(ec_flux_dir, 'EC_FLUX.csv')
        result_data = pd.DataFrame({
            'TIMESTAMP': [filtered_data['TIMESTAMP'].iloc[0]],
            'flux': [raw_flux], # mg/(m^2 s) for CH4
            'friction_velocity': [friction_velocity],
            'concentration_mean': [concentration_mean],
            'u2_mean': [u2_mean],
            'v2_mean': [v2_mean],
            'w2_mean': [w2_mean],
            'turbulent_steady_state': [turbulent_steady_state]
        })

        if not os.path.exists(result_file_path):
            result_data.to_csv(result_file_path, index=False, mode='w', header=True)
        else:
            result_data.to_csv(result_file_path, index=False, mode='a', header=False)

        # Save the cross-covariance results to cross_covariance_results.txt
        output_file_path = os.path.join(ec_flux_dir, 'cross_covariance_results.txt')
        save_cross_covariance_results(filtered_data['TIMESTAMP'].iloc[0], cross_cov_results, output_file_path)

        logging.info("Data calculation completed and results saved.")
    else:
        print("No matching files found in RawData folder")

if __name__ == "__main__":

    print("Data_Calculation_Module.py")

