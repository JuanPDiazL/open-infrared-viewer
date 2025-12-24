import os
import traceback
import sys
import cv2

from PyQt5.uic import loadUiType
from PyQt5.QtWidgets import (
    QMainWindow,
    QPushButton,
    QLabel,
    QCheckBox,
    QComboBox,
    QSlider,
    QDoubleSpinBox,
    QGroupBox,
    QStatusBar,
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import (
    Qt,
)

from src.blind_pixel_detection_window import BlindPixelDetectionWindow
from src.Compositor import Compositor
from src.Calibrator import Calibrator
from src.drivers.MAG160Core import Mag160Core
from src.utils import (
    GeneralSettings,
    COLORMAPS,
    SHUTTER_TRIGGERS,
    matlike_to_pixmap,
)

FORM_CLASS, _ = loadUiType(os.path.join(
    os.path.dirname(__file__), '../ui/main_window.ui'))

class MainWindow(QMainWindow, FORM_CLASS):
    canvasLabel: QLabel

    captureButton: QPushButton
    recordButton: QPushButton

    triggerFfcButton: QPushButton
    freezeViewportCheckBox: QCheckBox
    ffcModeComboBox: QComboBox

    manualSpanGroupBox: QGroupBox
    sliderRangeMinimumDoubleSpinBox: QDoubleSpinBox
    sliderRangeMaximumDoubleSpinBox: QDoubleSpinBox
    spanStartSlider: QSlider
    spanStartDoubleSpinBox: QDoubleSpinBox
    spanEndSlider: QSlider
    spanEndDoubleSpinBox: QDoubleSpinBox

    colorPaletteComboBox: QComboBox
    invertPaletteCheckBox: QCheckBox
    paletteRulerLabel: QLabel
    transformGroupBox: QGroupBox
    rotateComboBox: QComboBox
    flipComboBox: QComboBox

    blindPixelDetectionButton: QPushButton

    statusbar: QStatusBar

    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)

        self.blind_pixel_detection_window = BlindPixelDetectionWindow(self)

        self.settings = GeneralSettings()

        self.selected_camera = Mag160Core()
        self.selected_camera.connect()

        self.calibrator = Calibrator()
        self.calibrator.settings = self.settings
        self.calibrator.current_device = self.selected_camera
        self.blind_pixel_detection_window.set_calibrator(self.calibrator)

        self.compositor = Compositor()
        self.compositor.settings = self.settings
        self.compositor.assign_device(self.selected_camera)
        self.compositor.calibrator = self.calibrator

        blank_canvas = QPixmap(640, 480)
        blank_canvas.fill(Qt.black)
        self.canvasLabel.setPixmap(blank_canvas)

        self.freezeViewportCheckBox.stateChanged.connect(self.set_settings_from_form)
        self.manualSpanGroupBox.toggled.connect(self.set_settings_from_form)
        self.sliderRangeMinimumDoubleSpinBox.valueChanged.connect(self.span_range_event)
        self.sliderRangeMaximumDoubleSpinBox.valueChanged.connect(self.span_range_event)
        self.spanStartDoubleSpinBox.valueChanged.connect(self.span_spinbox_event)
        self.spanEndDoubleSpinBox.valueChanged.connect(self.span_spinbox_event)
        self.spanStartSlider.valueChanged.connect(self.span_slider_event)
        self.spanEndSlider.valueChanged.connect(self.span_slider_event)
        self.colorPaletteComboBox.currentIndexChanged.connect(self.set_settings_from_form)
        self.invertPaletteCheckBox.stateChanged.connect(self.set_settings_from_form)
        self.rotateComboBox.currentIndexChanged.connect(self.set_settings_from_form)
        self.flipComboBox.currentIndexChanged.connect(self.set_settings_from_form)

        self.captureButton.clicked.connect(self.compositor.capture_frame)
        self.recordButton.clicked.connect(self.record_button_event)
        self.triggerFfcButton.clicked.connect(lambda: self.selected_camera.set_ffc_frame(True))
        self.selected_camera.frame_ready.connect(self.update_frame)

        self.blindPixelDetectionButton.clicked.connect(self.blind_pixel_detection_window.show)

        self.update_fields()

    def update_frame(self):
        frame = self.compositor.read()
        pixmap = matlike_to_pixmap(frame)
        pixmap = pixmap.scaled(self.canvasLabel.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        self.canvasLabel.setPixmap(pixmap)

        if not self.settings.manual_span:
            self.spanStartSlider.setValue(int(self.compositor.last_frame_properties.min_value*10))
            self.spanStartDoubleSpinBox.setValue(self.compositor.last_frame_properties.min_value)
            self.spanEndSlider.setValue(int(self.compositor.last_frame_properties.max_value*10))
            self.spanEndDoubleSpinBox.setValue(self.compositor.last_frame_properties.max_value)

    def update_palette_ruler(self):
        frame = self.compositor.get_palette_ruler()
        pixmap = matlike_to_pixmap(frame)
        pixmap = pixmap.scaled(self.paletteRulerLabel.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
        self.paletteRulerLabel.setPixmap(pixmap)

    def update_fields(self):
        self.colorPaletteComboBox.clear()
        self.colorPaletteComboBox.addItems(COLORMAPS.keys())
        
        self.sliderRangeMinimumDoubleSpinBox.setValue(self.settings.slider_range[0])
        self.sliderRangeMaximumDoubleSpinBox.setValue(self.settings.slider_range[1])
        self.spanStartSlider.setMinimum(int(self.settings.slider_range[0])*10)
        self.spanStartSlider.setMaximum(int(self.settings.slider_range[1])*10)
        self.spanEndSlider.setMinimum(int(self.settings.slider_range[0])*10)
        self.spanEndSlider.setMaximum(int(self.settings.slider_range[1])*10)

        self.spanStartSlider.setValue(int(self.settings.span_range[0]*10))
        self.spanEndSlider.setValue(int(self.settings.span_range[1]*10))

    def set_settings_from_form(self):
        self.settings.freeze_on_ffc = self.freezeViewportCheckBox.isChecked()
        self.settings.ffc_mode = self.ffcModeComboBox.currentText()

        self.settings.manual_span = self.manualSpanGroupBox.isChecked()
        self.settings.span_range[0] = self.spanStartDoubleSpinBox.value()
        self.settings.span_range[1] = self.spanEndDoubleSpinBox.value()
        # self.settings.slider_range[0] = self.sliderRangeMinimumDoubleSpinBox.value()
        # self.settings.slider_range[1] = self.sliderRangeMaximumDoubleSpinBox.value()
        
        self.settings.color_palette = COLORMAPS[self.colorPaletteComboBox.currentText()]
        self.settings.invert_colors = self.invertPaletteCheckBox.isChecked()
        self.settings.rotation = self.rotateComboBox.currentIndex()
        self.settings.flip = self.flipComboBox.currentIndex()

        self.update_palette_ruler()

    def span_slider_event(self):
        span_start = self.spanStartSlider.value()/10
        span_end = self.spanEndSlider.value()/10
        self.spanStartDoubleSpinBox.setValue(span_start)
        self.spanEndDoubleSpinBox.setValue(span_end)
        self.set_settings_from_form()

    def span_spinbox_event(self):
        self.spanStartSlider.setValue(int(self.spanStartDoubleSpinBox.value()*10))
        self.spanEndSlider.setValue(int(self.spanEndDoubleSpinBox.value()*10))
        self.set_settings_from_form()

    def span_range_event(self):
        self.spanStartSlider.setMinimum(int(self.sliderRangeMinimumDoubleSpinBox.value())*10)
        self.spanStartSlider.setMaximum(int(self.sliderRangeMaximumDoubleSpinBox.value())*10)
        self.spanEndSlider.setMinimum(int(self.sliderRangeMinimumDoubleSpinBox.value())*10)
        self.spanEndSlider.setMaximum(int(self.sliderRangeMaximumDoubleSpinBox.value())*10)
        self.set_settings_from_form()

    def record_button_event(self):
        if self.compositor.recording:
            self.compositor.stop_recording()
            self.recordButton.setText("Start Recording")
            self.transformGroupBox.setEnabled(True)
        else:
            self.compositor.start_recording()
            self.recordButton.setText("Stop Recording")
            self.transformGroupBox.setEnabled(False)

    def closeEvent(self, event):
        # self.selected_camera.close()
        ...