from dataclasses import dataclass
import cv2
from matplotlib import pyplot as plt
import numpy as np
import usb.core
import usb.util
from PyQt5.QtGui import (
    QPixmap,
    QImage,
)
from PyQt5.QtCore import (
    Qt,
    QObject,
    pyqtSignal,
)

NONE_SHUTTER_TYPE = "No Shutter"
MONO_STABLE_SHUTTER_TYPE = "Mono Stable Shutter"
BI_STABLE_SHUTTER_TYPE = "Bi Stable Shutter"

NONE_SHUTTER_TRIGGER = "No Shutter Trigger"
IN_DEVICE_SHUTTER_TRIGGER = "In Device Shutter Trigger"
MANUAL_SHUTTER_TRIGGER = "Manual Shutter Trigger"
TEMPERATURE_SHUTTER_TRIGGER = "Temperature Shutter Trigger"
TIME_INTERVAL_SHUTTER_TRIGGER = "Time Interval Shutter Trigger"

COLORMAPS = {"COLORMAP_GRAY": None}
COLORMAPS = {**COLORMAPS, **dict([(name, getattr(cv2, name)) for name in dir(cv2) if name.startswith('COLORMAP')])}

def get_endpoint(device_interface, ep_addr):
    return usb.util.find_descriptor(
        device_interface,
        custom_match = lambda e: \
            e.bEndpointAddress == ep_addr)

def bytes_to_int(data):
    return int.from_bytes(data, byteorder='little')

@dataclass
class GeneralSettings:
    ffc_mode = TEMPERATURE_SHUTTER_TRIGGER
    post_capture_ffc = False
    freeze_on_ffc = False
    manual_span = False
    slider_range = [0, 2 * 2**15]
    span_range = [0, 2 * 2**15]
    color_palette = 0
    invert_colors = False
    rotation = 0
    flip = 0

    show_other_palettes = False

@dataclass
class FrameProperties:
     min_value = 0
     max_value = 0
     
class Signal(QObject):
    """A PyQt signal wrapper that provides a simple interface for emitting and 
    connecting signals."""
    signal = pyqtSignal(str)

    def connect(self, slot):
        self.signal.connect(slot)

    def emit(self, message=""):
        self.signal.emit(message)
    
    def disconnect(self, slot=None):
        self.signal.disconnect(slot)

def matlike_to_pixmap(frame: np.ndarray) -> QPixmap:
        height, width, channels = frame.shape
        bytesPerLine = width * channels
        image = QImage(frame.data, width, height, bytesPerLine, QImage.Format.Format_BGR888)
        pixmap = QPixmap.fromImage(image)
        return pixmap


def show_image(array):
    plt.imshow(array, cmap='gray')
    plt.colorbar()
    plt.title('Image')
    plt.show()