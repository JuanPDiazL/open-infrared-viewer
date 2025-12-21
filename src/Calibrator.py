import cv2
import numpy as np

from src.drivers.base import BaseDriver

class Calibrator():
    def __init__(self):
        self.blind_pixel_detection_frames: list[np.ndarray] = []


    def assign_device(self, device: BaseDriver):
        self.current_device = device

    def blind_pixel_detection(self, frame: np.ndarray):
        if len(self.blind_pixel_detection_frames) < 2:
            self.blind_pixel_detection_frames.append(frame)
            return
        
        frame_1, frame_2 = self.blind_pixel_detection_frames
        self.frame_difference = frame_2 - frame_1
        self.frame_min_value = self.frame_difference.min()
        self.frame_max_value = self.frame_difference.max()


    def clear_blind_pixel_detection_frames(self):
        self.blind_pixel_detection_frames.clear()