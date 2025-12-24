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

SHUTTER_TYPE_NONE = 0 # "No Shutter"
SHUTTER_TYPE_MONO_STABLE = 1 # "Mono Stable Shutter"
SHUTTER_TYPE_BI_STABLE = 2 # "Bi Stable Shutter"

SHUTTER_TYPES = dict([(name, value) for name, value in locals().items() if name.startswith('SHUTTER_TYPE')])

SHUTTER_TRIGGER_NONE = 0 # "No Shutter Trigger"
SHUTTER_TRIGGER_MANUAL = 2 # "Manual Shutter Trigger"
SHUTTER_TRIGGER_TEMPERATURE = 3 # "Temperature Shutter Trigger"
SHUTTER_TRIGGER_TIME_INTERVAL = 4 # "Time Interval Shutter Trigger"

SHUTTER_TRIGGERS = dict([(name, value) for name, value in locals().items() if name.startswith('SHUTTER_TRIGGER')])

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
    ffc_mode = SHUTTER_TRIGGER_TEMPERATURE
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
        if len(frame.shape) == 2:
            height, width = frame.shape
            channels = 1
            pixel_format = QImage.Format.Format_Grayscale16
        else:
            height, width, channels = frame.shape
            pixel_format = QImage.Format.Format_BGR888
        bytesPerLine = width * channels
        image = QImage(frame.data, width, height, bytesPerLine, pixel_format)
        pixmap = QPixmap.fromImage(image)
        return pixmap


def show_image(array):
    plt.imshow(array, cmap='gray')
    plt.colorbar()
    plt.title('Image')
    plt.show()