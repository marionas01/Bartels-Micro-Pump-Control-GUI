#   Imports:
import os
import threading
import concurrent.futures

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
import pyqtgraph as pg

from src.functions import *
from src.classes import *

#   set git path reader
basedir = os.path.dirname(__file__)


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
        self.injection_number_spinbox.setRange(0, 10000)
        self.injection_number_spinbox.setValue(0)
        self.injection_number_spinbox.setDisabled(True)

        self.injection_distance_label: QLabel = QLabel("Injection Distance [s]:")
        self.injection_distance_spinbox: QDoubleSpinBox = QDoubleSpinBox()
        self.injection_distance_spinbox.setRange(0, 10000)
        self.injection_distance_spinbox.setValue(0)
        self.injection_distance_spinbox.setDisabled(True)

        self.start_button: QPushButton = QPushButton(QIcon(os.path.join(basedir, "icons", "control.png")),
                                                     '&Start',
                                                     self)
        self.start_button.clicked.connect(self.start_clicked)

        self.stop_button: QPushButton = QPushButton(QIcon(os.path.join(basedir, "icons", "control-stop-square.png")),
                                                    '&Stop',
                                                    self)
        self.stop_button.clicked.connect(self.stop_clicked)

        # NIDaq Settings
        if not sys.platform.startswith('darwin'):
            self.ni_device_button: QPushButton = QPushButton(QIcon(os.path.join(basedir, "icons", "arrow-circle-double.png")),
                                                             '&refresh NI System',
                                                             self)
            self.ni_device_button.clicked.connect(self.refresh_ni_system)
            self.ni_device_combobox: QComboBox = QComboBox()
            self.ni_device_combobox.addItems(self.ndc.available_devices_str)
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
        self.left_layout.addWidget(self.injection_distance_label, 5, 0)
        self.left_layout.addWidget(self.injection_distance_spinbox, 5, 1)
        self.left_layout.addWidget(self.start_button, 6, 0)
        self.left_layout.addWidget(self.stop_button, 6, 1)

        if not sys.platform.startswith('darwin'):
            self.left_layout.addWidget(self.ni_device_button, 8, 0)
            self.left_layout.addWidget(self.ni_device_combobox, 8, 1)
            self.left_layout.addWidget(self.ni_device_channel_lineedit, 9, 1)
            self.left_layout.addWidget(self.ni_device_start_button, 10, 0)
            self.left_layout.addWidget(self.ni_device_stop_button, 10, 1)

        # # Threading Test Buttons
        # self.test_start_button: QPushButton = QPushButton("Test Start")
        # self.test_start_button.clicked.connect(self.thread_test_start_clicked)
        # self.test_stop_button: QPushButton = QPushButton("Test Stop")
        # self.test_stop_button.clicked.connect(self.thread_test_stop_clicked)

        # # NI Test Buttons
        # self.test_start_button: QPushButton = QPushButton("Test Start")
        # self.test_start_button.clicked.connect(get_ni_system_channels)
        # self.test_stop_button: QPushButton = QPushButton("Test Stop")
        # self.test_stop_button.clicked.connect(get_ni_system_signal)

        # self.left_layout.addWidget(self.test_start_button, 10, 0)
        # self.left_layout.addWidget(self.test_stop_button, 10, 1)

        self.left_widget.setLayout(self.left_layout)

        # #   Right Layout:
        self.right_layout: QGridLayout = QGridLayout()
        self.right_widget: QWidget = QWidget()

        self.scope_pump: pg.plot = pg.plot(title="Pump Output")
        self.scope_pump.setBackground('w')

        self.scope_ai: pg.plot = pg.plot(title="NI Input")
        self.scope_ai.setBackground('w')

        self.right_layout.addWidget(self.scope_pump, 0, 0)
        self.right_layout.addWidget(self.scope_ai, 1, 0)
        self.right_widget.setLayout(self.right_layout)

        #   Main Layout:
        self.main_widget: QWidget = QWidget()
        self.main_layout: QHBoxLayout = QHBoxLayout()
        self.main_layout.addWidget(self.left_widget, stretch=1)
        # self.main_layout.addWidget(self.right_widget, stretch=3)

        self.main_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.main_widget)

    #   Methods:
    # Widgets
    def toggle_q_spin_boxes(self):
        if self.injection_time_spinbox.value()==0.0:
            self.injection_number_spinbox.setDisabled(True)
            self.injection_distance_spinbox.setDisabled(True)
        else:
            self.injection_number_spinbox.setEnabled(True)
            self.injection_distance_spinbox.setEnabled(True)

    # MicroPump
    def set_window_size(self):
        self.setGeometry(0, 0, 250, 350)
        # self.setMaximumSize(200, 250)

    def refresh_ports(self):
        [self.port_combobox.removeItem(i) for i in list(range(len(self.mpc.available_ports)))]
        self.mpc.update_serial_ports()
        self.port_combobox.addItems(self.mpc.available_ports)
        self.port_combobox.setCurrentText(self.mpc.available_ports[0])

    def change_port(self):
        val = self.port_combobox.currentText()
        if val != "no port detected" and val != "":
            self.mpc.change_port(val)

    def start_clicked(self):
        self.mpc.threaded_start(amplitude=self.voltage_spinbox.value(),
                                injection_time=self.injection_time_spinbox.value(),
                                injection_number=self.injection_number_spinbox.value(),
                                injection_distance=self.injection_distance_spinbox.value(),
                                file_name=self.txt_file_lineedit.text())

    def stop_clicked(self):
        self.mpc.threaded_stop()

    # NIDevice
    def refresh_ni_system(self):
        [self.ni_device_combobox.removeItem(i) for i in list(range(len(self.ndc.available_devices_str)))]
        self.ndc.update_ni_system_devices_str()
        self.ni_device_combobox.addItems(self.ndc.available_devices_str)
        self.ni_device_combobox.setCurrentText(self.ndc.available_devices_str[0])

    def change_device(self):
        val = self.ni_device_combobox.currentText()
        if val != "no NI System detected" and val != "":
            self.ndc.change_device_selection(val)

    def start_ni(self):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(self.ndc.get_ni_system_signal,
                                     self.ni_device_channel_lineedit.text())
            data = future.result()
            print(data)
            #self.scope_ai.plot(data)

    def stop_ni(self):
        return


#   create Application obj
if __name__ == "__main__":
    app = QApplication(sys.argv)
    #   Constructor GUI
    gui = MainWindow()
    #   execute Application
    gui.show()
    sys.exit(app.exec_())
