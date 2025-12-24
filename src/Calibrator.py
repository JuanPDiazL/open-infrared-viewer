import cv2
import numpy as np

from src.drivers.base import BaseDriver
from src.utils import GeneralSettings

class Calibrator():
    def __init__(self):
        self.current_device: BaseDriver | None = None
        self.settings: GeneralSettings | None = None

        self.blind_pixel_detection_frames: list[np.ndarray] = []
        self.frame_difference: np.ndarray | None = None

        self.blind_pixel_detection_tolerance = 0.05

        self.blind_pixel_mask = np.zeros((120, 160), dtype=np.uint8)
        self.blind_pixel_mask[12, 72] = 1
        self.blind_pixel_mask[51:53, 124:127] = 1
        self.blind_pixel_mask[59:62, 80] = 1


    def assign_device(self, device: BaseDriver):
        self.current_device = device

    def blind_pixel_detection(self):
        if len(self.blind_pixel_detection_frames) < 2:
            self.blind_pixel_detection_frames.append(self.current_device.frame_buffer - self.current_device.ffc_frame)

        if len(self.blind_pixel_detection_frames) == 2:
            self.frame_difference = np.abs(self.blind_pixel_detection_frames[1] - self.blind_pixel_detection_frames[0])

            self.frame_min_value = self.frame_difference.min()
            self.frame_max_value = self.frame_difference.max()

            self.normalized_difference = (self.frame_difference - self.frame_min_value) / (self.frame_max_value - self.frame_min_value)

            self.blind_pixel_mask = self.normalized_difference < self.blind_pixel_detection_tolerance
            self.blind_pixel_mask = self.blind_pixel_mask.astype(np.uint8) * 255

    def set_blind_pixel_detection_tolerance(self, tolerance: float):
        self.blind_pixel_detection_tolerance = tolerance
        self.blind_pixel_mask = self.normalized_difference < self.blind_pixel_detection_tolerance
        self.blind_pixel_mask = self.blind_pixel_mask.astype(np.uint8) * 255

    def clear_blind_pixel_detection_frames(self):
        self.blind_pixel_detection_frames.clear()