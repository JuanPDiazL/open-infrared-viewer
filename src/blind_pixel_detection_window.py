import os
import traceback
import sys
import cv2

from PyQt5.uic import loadUiType
from PyQt5.QtWidgets import (
    QMainWindow,
    QDialog,
    QPushButton,
    QLabel,
    QCheckBox,
    QComboBox,
    QSlider,
    QDoubleSpinBox,
    QGroupBox,
    QDialogButtonBox,
    QStatusBar,
)
from PyQt5.QtGui import (
    QPixmap,
    QImage,
)
from PyQt5.QtCore import (
    Qt,
)
import numpy as np

from src.Calibrator import Calibrator
from src.utils import matlike_to_pixmap

FORM_CLASS, _ = loadUiType(os.path.join(
    os.path.dirname(__file__), '../ui/blind_pixel_detection_window.ui'))

class BlindPixelDetectionWindow(QDialog, FORM_CLASS):
    captureFrameButton: QPushButton
    buttonBox: QDialogButtonBox
    toleranceLabel: QLabel
    blindPixelToleranceSlider: QSlider

    frameCanvas1: QLabel
    frameCanvas2: QLabel
    maskCanvas: QLabel
    
    def __init__(self, parent=None):
        super(BlindPixelDetectionWindow, self).__init__(parent)
        self.setupUi(self)
        self.calibrator: Calibrator = None
        self.blind_pixel_mask = None

        self.blindPixelToleranceSlider.valueChanged.connect(self.blind_pixel_tolerance_changed)

    def set_calibrator(self, calibrator: Calibrator):
        self.calibrator = calibrator
        self.captureFrameButton.clicked.connect(self.capture_frame_event)
        self.blindPixelToleranceSlider.setValue(int(self.calibrator.blind_pixel_detection_tolerance * 1000))

    def capture_frame_event(self):
        self.calibrator.blind_pixel_detection()
        if len(self.calibrator.blind_pixel_detection_frames) == 1:
            frame1 = cv2.cvtColor(cv2.normalize(
                self.calibrator.blind_pixel_detection_frames[0], 
                None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U),
                cv2.COLOR_GRAY2BGR)
            pixmap1 = matlike_to_pixmap(frame1)
            pixmap1 = pixmap1.scaled(self.frameCanvas1.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
            self.frameCanvas1.setPixmap(pixmap1)
        if len(self.calibrator.blind_pixel_detection_frames) == 2:
            frame2 = cv2.cvtColor(cv2.normalize(
                self.calibrator.blind_pixel_detection_frames[1], 
                None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U),
                cv2.COLOR_GRAY2BGR)
            pixmap2 = matlike_to_pixmap(frame2)
            pixmap2 = pixmap2.scaled(self.frameCanvas1.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
            self.frameCanvas2.setPixmap(pixmap2)

            mask_frame = cv2.cvtColor(cv2.normalize(
                self.calibrator.blind_pixel_mask, 
                None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U),
                cv2.COLOR_GRAY2BGR)
            diff_pixmap = matlike_to_pixmap(mask_frame)
            diff_pixmap = diff_pixmap.scaled(self.maskCanvas.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
            self.maskCanvas.setPixmap(diff_pixmap)

    def blind_pixel_tolerance_changed(self, value: int) -> None:
        tolerance = value / 1000.0
        self.calibrator.set_blind_pixel_detection_tolerance(tolerance)
        self.toleranceLabel.setText(f"Tolerance: {tolerance/10:.1f}")

        diff_frame = cv2.cvtColor(cv2.normalize(
            self.calibrator.frame_difference, 
            None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U),
            cv2.COLOR_GRAY2BGR)
        
        # Colorize to red
        blind_pixel_mask = np.zeros_like(diff_frame)
        blind_pixel_mask[:, :, 2] = self.calibrator.blind_pixel_mask
        mask_frame = blind_pixel_mask
        
        diff_pixmap = matlike_to_pixmap(mask_frame)
        diff_pixmap = diff_pixmap.scaled(self.maskCanvas.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        self.maskCanvas.setPixmap(diff_pixmap)
        
    def acceptEvent(self, event):
        print("saveEvent")
        self.calibrator.blind_pixel_mask = self.blind_pixel_mask
        self.acceptEvent(event)

    def cancelEvent(self, event):
        print("cancelEvent")
        self.reject()