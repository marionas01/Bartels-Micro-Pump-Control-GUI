#   Imports:
import os
import sys

import time

import numpy as np
from PyQt5.QtCore import QThread, QTimer
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
import pyqtgraph as pg

from src.functions import *
from test.classes import *

#   set git path reader
basedir = os.path.dirname(__file__)

PLOT_HISTORY = 2000         # number of NI samples shown in the scope
PUMP_PLOT_WINDOW = 60.0     # seconds of pump history visible while the pump runs
PUMP_PLOT_REFRESH_MS = 50   # redraw interval of the pump plot (20 fps)


#   MainWindow Class
class MainWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()

        #   MainWindow settings:
        self.setWindowIcon(QIcon(os.path.join(basedir, "icons", "equalizer.png")))  # Icon for application
        self.setWindowTitle("BMPC")
        self.set_window_size()
        qt_rectangle = self.frameGeometry()
        center_point = QDesktopWidget().availableGeometry().center()
        qt_rectangle.moveCenter(center_point)
        self.move(qt_rectangle.topLeft())

        #   Controller Constructor:
        self.mpc = MicroPumpController()
        if not sys.platform.startswith('darwin'):
            self.ndc = NIDeviceController()

        #   Thread / worker references (must be kept, otherwise they get garbage collected)
        self.pump_thread: None | QThread = None
        self.pump_worker: None | PumpWorker = None
        self.ni_thread: None | QThread = None
        self.ni_worker: None | NIWorker = None
        self.ni_data: np.ndarray = np.zeros(0)

        #   Pump plot data: (timestamp, voltage) points of a step curve
        self.pump_t: list[float] = []
        self.pump_v: list[float] = []
        self.pump_level: float = 0.0            # voltage the pump is currently set to
        self.pump_plot_timer = QTimer(self)     # moves the curve's end along with the clock
        self.pump_plot_timer.setInterval(PUMP_PLOT_REFRESH_MS)
        self.pump_plot_timer.timeout.connect(self.redraw_pump_plot)

        #   Layouts:
        # Left Layout:
        self.left_widget: QWidget = QWidget()
        self.left_layout: QGridLayout = QGridLayout()

        # General Settings
        self.port_button: QPushButton = QPushButton(QIcon(os.path.join(basedir, "icons", "arrow-circle-double.png")),
                                                    '&refresh Ports',
                                                    self)
        self.port_button.clicked.connect(self.refresh_ports)
        self.port_combobox: QComboBox = QComboBox()
        self.port_combobox.addItems(self.mpc.available_ports)
        self.port_combobox.setCurrentText(self.mpc.available_ports[0])
        self.port_combobox.currentTextChanged.connect(self.change_port)

        self.txt_file_label: QLabel = QLabel("Timestamp file name:")
        self.txt_file_lineedit: QLineEdit = QLineEdit()
        self.txt_file_lineedit.setPlaceholderText("enter file name")
        self.txt_file_lineedit.textChanged.connect(self.update_button)

        self.voltage_label: QLabel = QLabel("Pump Voltage [V]:")
        self.voltage_spinbox: QDoubleSpinBox = QDoubleSpinBox()
        self.voltage_spinbox.setRange(0, 250)
        self.voltage_spinbox.setValue(0)

        # Impulse Settings
        self.injection_time_label: QLabel = QLabel("Injection Time [s]:")
        self.injection_time_spinbox: QDoubleSpinBox = QDoubleSpinBox()
        self.injection_time_spinbox.setRange(0, 10000)
        self.injection_time_spinbox.setValue(0)
        self.injection_time_spinbox.valueChanged.connect(self.toggle_q_spin_boxes)

        self.injection_number_label: QLabel = QLabel("Number of Injections:")
        self.injection_number_spinbox: QSpinBox = QSpinBox()
        self.injection_number_spinbox.setRange(1, 10000)
        self.injection_number_spinbox.setValue(1)
        self.injection_number_spinbox.setDisabled(True)

        self.injection_interval_label: QLabel = QLabel("Injection Interval [s]:")
        self.injection_interval_spinbox: QDoubleSpinBox = QDoubleSpinBox()
        self.injection_interval_spinbox.setRange(0, 10000)
        self.injection_interval_spinbox.setValue(0)
        self.injection_interval_spinbox.setDisabled(True)

        self.start_button: QPushButton = QPushButton(QIcon(os.path.join(basedir, "icons", "control.png")),
                                                     '&Start',
                                                     self)
        self.start_button.clicked.connect(self.start_clicked)
        self.start_button.setEnabled(False)

        self.stop_button: QPushButton = QPushButton(QIcon(os.path.join(basedir, "icons", "control-stop-square.png")),
                                                    '&Stop',
                                                    self)
        self.stop_button.clicked.connect(self.stop_clicked)
        self.stop_button.setEnabled(False)

        self.h_line1: QFrame = QFrame()
        self.h_line1.setFrameShape(QFrame.HLine)
        self.h_line1.setLineWidth(1)

        self.h_line2: QFrame = QFrame()
        self.h_line2.setFrameShape(QFrame.HLine)
        self.h_line2.setLineWidth(1)

        # NIDaq Settings
        if not sys.platform.startswith('darwin'):
            self.ni_device_button: QPushButton = QPushButton(QIcon(os.path.join(basedir, "icons", "arrow-circle-double.png")),
                                                             '&refresh NI System',
                                                             self)
            self.ni_device_button.clicked.connect(self.refresh_ni_system)
            self.ni_device_combobox: QComboBox = QComboBox()
            self.ni_device_combobox.addItems(self.ndc.available_devices_str)
            if self.ndc.available_devices_str:
                self.ni_device_combobox.setCurrentText(self.ndc.available_devices_str[0])
            self.ni_device_combobox.currentTextChanged.connect(self.change_device)

            self.ni_device_channel_lineedit: QLineEdit = QLineEdit()
            self.ni_device_channel_lineedit.setPlaceholderText("Enter Channel Name:")

            self.ni_device_start_button: QPushButton = QPushButton(QIcon(os.path.join(basedir,
                                                                                      "icons", "control.png")),
                                                                   '&Start',
                                                                   self)
            self.ni_device_start_button.clicked.connect(self.start_ni)
            self.ni_device_stop_button: QPushButton = QPushButton(QIcon(os.path.join(basedir,
                                                                                     "icons", "control-stop-square.png")),
                                                                  '&Stop',
                                                                  self)
            self.ni_device_stop_button.clicked.connect(self.stop_ni)
            self.ni_device_stop_button.setEnabled(False)

        #   Layout:
        self.left_layout.addWidget(self.port_button, 0, 0)
        self.left_layout.addWidget(self.port_combobox, 0, 1)
        self.left_layout.addWidget(self.txt_file_label, 1, 0)
        self.left_layout.addWidget(self.txt_file_lineedit, 1, 1)
        self.left_layout.addWidget(self.voltage_label, 2, 0)
        self.left_layout.addWidget(self.voltage_spinbox, 2, 1)
        self.left_layout.addWidget(self.injection_time_label, 3, 0)
        self.left_layout.addWidget(self.injection_time_spinbox, 3, 1)
        self.left_layout.addWidget(self.injection_number_label, 4, 0)
        self.left_layout.addWidget(self.injection_number_spinbox, 4, 1)
        self.left_layout.addWidget(self.injection_interval_label, 5, 0)
        self.left_layout.addWidget(self.injection_interval_spinbox, 5, 1)
        self.left_layout.addWidget(self.start_button, 6, 0)
        self.left_layout.addWidget(self.stop_button, 6, 1)

        if not sys.platform.startswith('darwin'):
            self.left_layout.addWidget(self.h_line1, 7, 0)
            self.left_layout.addWidget(self.h_line2, 7, 1)
            self.left_layout.addWidget(self.ni_device_button, 8, 0)
            self.left_layout.addWidget(self.ni_device_combobox, 8, 1)
            self.left_layout.addWidget(self.ni_device_channel_lineedit, 9, 1)
            self.left_layout.addWidget(self.ni_device_start_button, 10, 0)
            self.left_layout.addWidget(self.ni_device_stop_button, 10, 1)

        self.left_widget.setLayout(self.left_layout)

        #   Right Layout:
        self.right_layout: QGridLayout = QGridLayout()
        self.right_widget: QWidget = QWidget()

        # pg.PlotWidget instead of pg.plot(): pg.plot() opens its own top-level window
        # DateAxisItem shows the x values (time.time() timestamps) as clock time
        self.scope_pump: pg.PlotWidget = pg.PlotWidget(title="Pump Output",
                                                       axisItems={'bottom': pg.DateAxisItem()})
        self.scope_pump.setBackground('w')
        self.scope_pump.setLabel('left', "Voltage", units='V')
        self.scope_pump.setLabel('bottom', "Time")
        self.scope_pump.showGrid(x=True, y=True, alpha=0.3)
        self.pump_curve = self.scope_pump.plot(pen=pg.mkPen('r', width=2))

        self.scope_ai: pg.PlotWidget = pg.PlotWidget(title="NI Input")
        self.scope_ai.setBackground('w')
        self.ai_curve = self.scope_ai.plot(pen='b')     # one curve, updated with setData()

        self.right_layout.addWidget(self.scope_pump, 0, 0)
        self.right_layout.addWidget(self.scope_ai, 1, 0)
        self.right_widget.setLayout(self.right_layout)

        #   Main Layout:
        self.main_widget: QWidget = QWidget()
        self.main_layout: QHBoxLayout = QHBoxLayout()
        self.main_layout.addWidget(self.left_widget, stretch=1)
        self.main_layout.addWidget(self.right_widget, stretch=3)

        self.main_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.main_widget)

        self.statusBar()

    #   Methods:
    # Threading helper
    def _run_in_thread(self, worker: QObject) -> QThread:
        """Moves a worker into a new QThread, wires up the clean-up and starts it."""
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)            # stop the thread's event loop
        worker.finished.connect(worker.deleteLater)     # free the worker
        thread.finished.connect(thread.deleteLater)     # free the thread
        worker.error.connect(self.show_error)
        thread.start()
        return thread

    def show_error(self, message: str):
        QMessageBox.critical(self, "Error", message)

    # Widgets
    def update_button(self, text):
        self.start_button.setEnabled(bool(text.strip()) and self.pump_thread is None)

    def toggle_q_spin_boxes(self):
        if self.injection_time_spinbox.value() == 0.0:
            self.injection_number_spinbox.setDisabled(True)
            self.injection_interval_spinbox.setDisabled(True)
        else:
            self.injection_number_spinbox.setEnabled(True)
            self.injection_interval_spinbox.setEnabled(True)

    # MicroPump
    def set_window_size(self):
        self.setGeometry(0, 0, 700, 350)

    def refresh_ports(self):
        self.port_combobox.blockSignals(True)
        self.port_combobox.clear()          # removeItem(i) in a loop skipped every 2nd item
        self.mpc.update_serial_ports()
        self.port_combobox.addItems(self.mpc.available_ports)
        self.port_combobox.blockSignals(False)
        self.port_combobox.setCurrentText(self.mpc.available_ports[0])
        self.change_port()

    def change_port(self):
        val = self.port_combobox.currentText()
        if val != "no port detected" and val != "":
            self.mpc.change_port(val)

    def start_clicked(self):
        if self.pump_thread is not None:
            return
        self.pump_worker = PumpWorker(controller=self.mpc,
                                      amplitude=self.voltage_spinbox.value(),
                                      injection_time=self.injection_time_spinbox.value(),
                                      injection_number=self.injection_number_spinbox.value(),
                                      injection_interval=self.injection_interval_spinbox.value(),
                                      file_name=self.txt_file_lineedit.text())
        self.pump_worker.status.connect(self.statusBar().showMessage)
        self.pump_worker.voltage_changed.connect(self.on_pump_voltage_changed)
        self.pump_thread = self._run_in_thread(self.pump_worker)
        self.pump_thread.finished.connect(self.pump_finished)
        self.pump_plot_timer.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.port_button.setEnabled(False)          # don't change the port while the pump runs
        self.port_combobox.setEnabled(False)

    def stop_clicked(self):
        if self.pump_worker is not None:
            self.pump_worker.stop()                 # direct call - just sets a threading.Event
        self.stop_button.setEnabled(False)          # buttons are re-enabled in pump_finished()

    def pump_finished(self):
        """Runs in the GUI thread when the pump thread has ended (stopped OR series completed)."""
        self.pump_thread = None
        self.pump_worker = None
        self.pump_plot_timer.stop()
        self.redraw_pump_plot(live=False)           # final draw, curve ends at the last stop command
        self.stop_button.setEnabled(False)
        self.start_button.setEnabled(bool(self.txt_file_lineedit.text().strip()))
        self.port_button.setEnabled(True)
        self.port_combobox.setEnabled(True)

    # Pump plot
    def on_pump_voltage_changed(self, timestamp: float, voltage: float):
        """Slot - runs in the GUI thread for every start/stop command the worker sends.
        Two points per change (old level, new level) at the same time give a square wave."""
        self.pump_t.append(timestamp)           # hold the previous level up to this moment
        self.pump_v.append(self.pump_level)
        self.pump_t.append(timestamp)           # jump to the new level
        self.pump_v.append(voltage)
        self.pump_level = voltage
        self.redraw_pump_plot()

    def redraw_pump_plot(self, live: bool = True):
        if not self.pump_t:
            return
        t = list(self.pump_t)
        v = list(self.pump_v)
        if live:
            now = time.time()
            t.append(now)                       # extend the current level up to "now"
            v.append(self.pump_level)
            self.scope_pump.setXRange(max(t[0], now - PUMP_PLOT_WINDOW), now, padding=0.02)
        self.pump_curve.setData(t, v)

    # NIDevice
    def refresh_ni_system(self):
        self.ni_device_combobox.blockSignals(True)
        self.ni_device_combobox.clear()
        self.ndc.update_ni_system_devices_str()
        self.ni_device_combobox.addItems(self.ndc.available_devices_str)
        self.ni_device_combobox.blockSignals(False)
        self.ni_device_combobox.setCurrentText(self.ndc.available_devices_str[0])
        self.change_device()

    def change_device(self):
        val = self.ni_device_combobox.currentText()
        if val != "no NI System detected" and val != "":
            self.ndc.change_device_selection(val)

    def start_ni(self):
        if self.ni_thread is not None or not self.ndc.active_device_str:
            return
        self.ni_data = np.zeros(0)
        self.ni_worker = NIWorker(device=self.ndc.active_device_str,
                                  channel=self.ni_device_channel_lineedit.text())
        self.ni_worker.data_ready.connect(self.update_ni_plot)
        self.ni_thread = self._run_in_thread(self.ni_worker)
        self.ni_thread.finished.connect(self.ni_finished)

        self.ni_device_start_button.setEnabled(False)
        self.ni_device_stop_button.setEnabled(True)

    def stop_ni(self):
        if self.ni_worker is not None:
            self.ni_worker.stop()
        self.ni_device_stop_button.setEnabled(False)

    def update_ni_plot(self, data: np.ndarray):
        """Slot - runs in the GUI thread, receives the samples from NIWorker.data_ready."""
        self.ni_data = np.concatenate((self.ni_data, data))[-PLOT_HISTORY:]
        self.ai_curve.setData(self.ni_data)

    def ni_finished(self):
        self.ni_thread = None
        self.ni_worker = None
        self.ni_device_start_button.setEnabled(True)
        self.ni_device_stop_button.setEnabled(False)

    # Shutdown
    def closeEvent(self, event):
        """Stop all running workers and wait for their threads before the window closes."""
        for worker, thread in ((self.pump_worker, self.pump_thread), (self.ni_worker, self.ni_thread)):
            if worker is not None:
                worker.stop()
            if thread is not None:
                thread.quit()
                thread.wait(3000)
        super().closeEvent(event)


#   create Application obj
if __name__ == "__main__":
    app = QApplication(sys.argv)
    #   Constructor GUI
    gui = MainWindow()
    #   execute Application
    gui.show()
    sys.exit(app.exec_())