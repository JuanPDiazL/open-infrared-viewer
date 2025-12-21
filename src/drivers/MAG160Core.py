import datetime
import json
import struct
from time import sleep
import time
import numpy as np
import usb.core
import usb.util
from PyQt5.QtCore import (
    Qt,
    QTimer,
)
from PyQt5.QtTest import QTest

from src.drivers.base import BaseDriver
from src.utils import (
    bytes_to_int,
    get_endpoint
)

COMMAND_CODES = {
    "GetParameter1"     : 0x6BB6B66B,
    "GetParameter2"     : 0x6BB6B66C,
    "SetParameter1"     : 0x6BB6B66D,
    "SetParameter2"     : 0x6BB6B66E,
    "GetCaliInfo"       : 0x6BB6B66F,
    "GetCaliFile"       : 0x6BB6B670,
    "SendCaliFile"      : 0x6BB6B671,
    "SetShutterState"   : 0x6BB6B672,
    "StartTransferImg"  : 0x6BB6B673,
    "StopTransferImg"   : 0x6BB6B674,
    "GetLifeTime"       : 0x6BB6B675,
    "PowerSave"         : 0x6BB6B677,
    "SetFrameRate"      : 0x6BB6B679,
}
RESPONSE_CODES = {
    "SendParameter1"    : 0x5BB5B55B,
    "SendParameter2"    : 0x5BB5B55C,
    "SendCaliFile"      : 0x5BB5B55D,
    "SendCaliInfo"      : 0x5BB5B55E,
    "CmdHandledAck"     : 0x5BB5B55F,
    "CaliHandledAck"    : 0x5BB5B560,
    "SendLifeTime"      : 0x5BB5B561,
}
ENDPOINT_ADDRESSES = {
    "command_out"       : 0x03,
    "calibration_out"   : 0x05,
    "image_in"          : 0x81,
    "command_in"        : 0x82,
    "calibration_in"    : 0x84,
}
VID = 0x833c
PID = 0x0001
DEVICE_CODE = 0x03
IMG_START_CODE = 0x1BB1B11B
IMG_END_CODE = 0x1BB1B11C
CMD_TIMEOUT = 800


class Mag160Core(BaseDriver):
    def __init__(self):
        super().__init__()
        self.driver_name = "MAG-160 Core"

    def connect(self):
        self.device = usb.core.find(idVendor=VID, idProduct=PID)
        if self.device is None:
            raise ValueError("Device not found")
        
        # Set the device configuration
        self.device.set_configuration()
        device_configuration = self.device.get_active_configuration()
        device_interface = device_configuration[(0,0)]
        usb.util.claim_interface(self.device, 0)

        # set the endpoints
        self.cmdout_endpoint = get_endpoint(device_interface, ENDPOINT_ADDRESSES["command_out"])
        self.cmdin_endpoint = get_endpoint(device_interface, ENDPOINT_ADDRESSES["command_in"])
        self.calibration_in_endpoint = get_endpoint(device_interface, ENDPOINT_ADDRESSES["calibration_in"])
        self.caliout_endpoint = get_endpoint(device_interface, ENDPOINT_ADDRESSES["calibration_out"])
        self.imgin_endpoint = get_endpoint(device_interface, ENDPOINT_ADDRESSES["image_in"])

        self.device_info = self.get_parameters()
        self.frame_width = self.device_info["fpa_width"]
        self.frame_height = self.device_info["fpa_height"]
        self.frame_dims = self.frame_width, self.frame_height
        self.framerate = self.device_info["fps"]
        self.frame_packet_size = (self.frame_width*self.frame_height*2) + 1024

        self.ffc_frame = np.zeros((self.frame_height, self.frame_width), dtype=np.uint16)
        self.last_ffc_time = 0
        self.last_ffc_temp = 0

        self.get_calibration_info()
        self.send_command(COMMAND_CODES["StartTransferImg"], 2000)

        # start asynchronous frame read
        self.read_timer = QTimer()
        self.read_timer.timeout.connect(self.read)
        self.read_timer.start(1000//self.framerate)

        self.ffc_timer = QTimer()
        self.ffc_timer.timeout.connect(self.set_ffc_frame)
        self.ffc_timer.start(1000//self.framerate)

        return self.device
    
    def read(self):
        self.frame_buffer, self.frame_info = self.get_image_data()
        self.frame_ready.emit()
        # print(f'n: {self.frame_info["frame_index"]:010d}, Cam temp: {self.frame_info["cam_temp_celsius"]:.1f}, FPA temp: {self.frame_info["fpa_temp_celsius"]:.1f}', end='\r')
    
    def set_ffc_frame(self, force=False):
        ffc_temp_diff = self.frame_info["fpa_temp_celsius"] - self.last_ffc_temp
        if force or ffc_temp_diff > 0.3 or ffc_temp_diff < -0.3:
            self.performing_ffc = True
            self.set_shutter(1)
            QTest.qWait(410)
            self.ffc_frame = self.frame_buffer.copy()
            self.last_ffc_temp = self.frame_info["fpa_temp_celsius"]
            self.last_ffc_timestamp = time.time()
            self.ffc_frame_ready.emit()
            self.set_shutter(0)
            QTest.qWait(140)
            self.performing_ffc = False
        
    
    def close(self):
        self.read_timer.stop()
        self.ffc_timer.stop()
        self.send_command(COMMAND_CODES["StopTransferImg"], 2000, None)
        usb.util.release_interface(self.device, 0)
    
    def send_command(self, command_data, timeout=CMD_TIMEOUT, read_delay_ms=0):
        command_bytes = bytearray()
        if not isinstance(command_data, list):
            command_bytes = command_data.to_bytes(4, 'little')
        else:
            for data in (command_data):
                command_bytes.extend(((data)).to_bytes(4, 'little'))
        # pprint_bytes(command_bytes)
        bytes_sent = self.device.write(self.cmdout_endpoint.bEndpointAddress, command_bytes, timeout)
        if read_delay_ms is not None:
            sleep(read_delay_ms / 1000)
            response = self.device.read(self.cmdin_endpoint.bEndpointAddress, 64, timeout)
            return response
    
    def get_parameters(self):
        # print(f'get parameters')
        params1 = self.send_command(COMMAND_CODES["GetParameter1"])
        parameters = {
            # "command_code": bytes_to_int(params1[0:4]),
            "serial_number": bytes_to_int(params1[4:8]),
            "hardware_version": bytes_to_int(params1[8:11]), # 3 bytes
            "device_type": params1[11], # byte.
            "firmware_version": bytes_to_int(params1[12:16]),
            "fpa_serial_number": bytes_to_int(params1[16:20]),
            "fpa_width": bytes_to_int(params1[20:24]),
            "fpa_height": bytes_to_int(params1[24:28]),
            "fps": bytes_to_int(params1[28:32]),
            "reserved_1": bytes_to_int(params1[32:36]),
            "fpa_gain": bytes_to_int(params1[36:40]), 
            "fpa_flip": bytes_to_int(params1[40:44]),
            "inter_frame": bytes_to_int(params1[44:48]),
            "inter_line": bytes_to_int(params1[48:52]),
            "gfid": bytes_to_int(params1[52:56]),
            "gsk": bytes_to_int(params1[56:60]),
        }

        params2 = self.send_command(COMMAND_CODES["GetParameter2"])
        parameters = {
            **parameters,
            # "command_code": bytes_to_int(params2[0:4]),
            "base_line_acc": bytes_to_int(params2[4:8]),
            "denoise_level": bytes_to_int(params2[8:12]),
            "reserved_2": bytes_to_int(params2[12:16]),
            "reserved_3": bytes_to_int(params2[16:18]),  # Short
            "fpa_temp_fix": bytes_to_int(params2[18:20]),  # Short
            "shutter_close_speed": bytes_to_int(params2[20:24]),
            "shutter_open_speed": bytes_to_int(params2[24:28]),
            "ffc_trigger_frame": bytes_to_int(params2[28:32]),
            "ffc_trigger_temperature": bytes_to_int(params2[32:36]),
            "enlarge_range": bytes_to_int(params2[36:40]),
            "laser_pos": bytes_to_int(params2[40:44]),
            "at_zero_error_point": bytes_to_int(params2[44:48]),
            "at_error_slope": struct.unpack('f', params2[48:52])[0],  # Float
            "reserved_4": bytes_to_int(params2[52:56]),
            "reserved_5": bytes_to_int(params2[56:60]),
        }
        # print(f"Camera parameters: {json.dumps(parameters, indent=4)}")
        return parameters
    
    def get_calibration_info(self, save_file=False):
        # print(f'get calibration info')
        cali_info = self.send_command(COMMAND_CODES["GetCaliInfo"])
        calibration_info = {
            "command": bytes_to_int(cali_info[0:4]),
            "size": bytes_to_int(cali_info[4:8]),
            "reserved_1": bytes_to_int(cali_info[8:12]),
            "date": datetime.datetime.fromtimestamp(bytes_to_int(cali_info[12:20])).isoformat(), 
        }
        if 65536 > calibration_info["size"] > 104857600:
            raise ValueError("Calibration file size is invalid")
        
        if save_file:
            self.send_command(COMMAND_CODES["GetCaliFile"])
            cali_data = bytearray()
            remain = cali_info["size"]
            while remain > 0:
                cali_data_block = self.device.read(self.calibration_in_endpoint.bEndpointAddress, 
                                                   min(remain, 16384), 
                                                   CMD_TIMEOUT)
                cali_data+=cali_data_block
                remain -= 16384
            with open(f"calibration_data.dat", "wb") as f:
                f.write(cali_data)

    def get_image_data(self):
        header_block = self.device.read(self.imgin_endpoint.bEndpointAddress, self.frame_packet_size, 200)
        content_block = self.device.read(self.imgin_endpoint.bEndpointAddress, self.frame_packet_size, 200)
        img_block = content_block[0:-28]
        tail_block = content_block[-28:]
        # header_info = {
        #     "code": bytes_to_int(header_block[0:4]),
        #     "frame_index": bytes_to_int(header_block[4:8]),
        #     "reserved": [bytes_to_int(header_block[8:12]), 
        #                     bytes_to_int(header_block[12:16]),
        #                     bytes_to_int(header_block[16:20]),
        #                     bytes_to_int(header_block[20:24])],
        #     "send_bytes": bytes_to_int(header_block[24:28]),
        # }
        frame_info = {
            "code": bytes_to_int(tail_block[0:4]),
            "frame_index": bytes_to_int(tail_block[4:8]),
            "fpa_temp": bytes_to_int(tail_block[8:12]),
            "int_drop": bytes_to_int(tail_block[12:16]),
            # "reserved": [bytes_to_int(tail_block[16:20]), 
            #                 bytes_to_int(tail_block[20:24]),
            #                 bytes_to_int(tail_block[24:28])],
        }
        cam_temp = frame_info["fpa_temp"] - 500
        fixed_fpa_temp = frame_info["fpa_temp"] + self.device_info["fpa_temp_fix"]
        fixed_cam_temp = cam_temp + self.device_info["fpa_temp_fix"]
        other_info = {
            "cam_temp_celsius": fixed_cam_temp / 1000,
            "fpa_temp_celsius": fixed_fpa_temp / 1000,
        }
        all_info = {
            **frame_info,
            **other_info,
        }
        image_array = np.frombuffer(img_block, dtype=np.uint16).reshape((self.frame_height, self.frame_width)).astype(np.float32)
        return image_array, all_info
    

    def set_shutter(self, state):
        state = not state
        command_data = [
            COMMAND_CODES["SetShutterState"],
            state
        ]
        return self.send_command(command_data)