import time
import cv2
import numpy as np

from src.drivers.base import BaseDriver
from src.Calibrator import Calibrator
from src.utils import (
    GeneralSettings,
    FrameProperties,
)

NULL_FRAME = np.zeros((480, 640, 3))

class Compositor():
    def __init__(self):
        self.test = True
        self.current_device = None
        self.calibrator: Calibrator = None
        self.last_frame = NULL_FRAME
        self.last_frame_properties = FrameProperties()
        self.settings = GeneralSettings()

        self.recording = False
        self.recording_resolution = (640, 480)
        self.recording_scale = 1

        self.fourcc = cv2.VideoWriter.fourcc(*'XVID')
        self.video_writer = None

    def assign_device(self, device: BaseDriver):
        if self.current_device is not None:
            self.current_device.close()
        self.current_device = device

    def read(self):
        if self.current_device is None:
            return NULL_FRAME
        
        # Frame Readout
        ir_raw_frame = self.current_device.frame_buffer
        ffc_pause = self.current_device.performing_ffc and self.settings.freeze_on_ffc
        if ir_raw_frame is None or ffc_pause: 
            return self.last_frame
        ffc_raw_frame = self.current_device.ffc_frame

        # Correction
        ffc_corrected_frame = ir_raw_frame - ffc_raw_frame + np.mean(ffc_raw_frame)

        if self.calibrator.blind_pixel_mask is not None:
            ffc_corrected_frame = cv2.inpaint(ffc_corrected_frame, self.calibrator.blind_pixel_mask.astype(np.uint8), 3, cv2.INPAINT_TELEA)

        # Span Adjustment
        if self.settings.manual_span:
            frame_min_value, frame_max_value = self.settings.span_range
        else:
            frame_min_value = ffc_corrected_frame.min()
            frame_max_value = ffc_corrected_frame.max()
        ffc_corrected_frame = np.clip(ffc_corrected_frame, frame_min_value, frame_max_value)
        normalized_frame = cv2.normalize(ffc_corrected_frame, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)

        # Transform
        transformed_frame = np.rot90(normalized_frame, 4 - self.settings.rotation)
        if self.settings.flip == 1:
            transformed_frame = np.flip(transformed_frame, 0)
        elif self.settings.flip == 2:
            transformed_frame = np.flip(transformed_frame, 1)
        elif self.settings.flip == 3:
            transformed_frame = np.flip(transformed_frame, (0,1))

        # Colorize
        color_frame = transformed_frame
        if self.settings.invert_colors:
            color_frame = np.invert(color_frame)
        color_frame = cv2.cvtColor(color_frame, cv2.COLOR_GRAY2BGR)
        if self.settings.color_palette is not None:
            color_frame = cv2.applyColorMap(color_frame, self.settings.color_palette)

        self.last_frame = color_frame
        if self.recording:
            record_frame = cv2.resize(color_frame, None, fx=self.recording_scale, fy=self.recording_scale, interpolation=cv2.INTER_CUBIC)
            self.video_writer.write(record_frame)
            
        self.last_frame_properties.min_value = frame_min_value
        self.last_frame_properties.max_value = frame_max_value
        return color_frame
    
    def get_palette_ruler(self):
        gradient = np.arange(256, dtype=np.uint8).reshape(1, 256)
        if self.settings.invert_colors: 
            gradient = np.flip(gradient)
        color_ruler = cv2.cvtColor(gradient, cv2.COLOR_GRAY2BGR)
        if self.settings.color_palette is not None:
            color_ruler = cv2.applyColorMap(gradient, self.settings.color_palette)
        return color_ruler
    
    def capture_frame(self):
        if self.current_device is None:
            return
        if self.settings.post_capture_ffc:
            self.current_device.ffc_frame_ready.connect(self.post_capture)
            self.current_device.set_ffc_frame(True)
            
        cv2.imwrite('frame.png', self.last_frame)

    def post_capture(self):
        print('ffc frame ready')
        self.current_device.ffc_frame_ready.disconnect(self.post_capture)
        
    def start_recording(self):
        if self.recording: return
        self.recording = True
        height, width, channels = self.last_frame.shape
        self.video_writer = cv2.VideoWriter(
            'output.avi', 
            self.fourcc, 
            self.current_device.framerate, 
            (width * self.recording_scale, height * self.recording_scale), 
            )

    def stop_recording(self):
        if not self.recording: return
        self.recording = False
        self.video_writer.release()