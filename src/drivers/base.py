from abc import ABC, abstractmethod
from numpy import ndarray
from src.utils import Signal

class BaseDriver(ABC):
    @abstractmethod
    def __init__(self):
        self.driver_name = "Base Driver"
        self.device = None
        self.device_info = None
        self.frame_width = None
        self.frame_height = None
        self.framerate = None
        self.frame_buffer: ndarray = None
        self.frame_info = None
        self.ffc_frame: ndarray = None
        self.performing_ffc = False
        self.frame_ready = Signal()
        self.ffc_frame_ready = Signal()

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def read(self):
        pass
