#   Imports:
import os

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from pyqtgraph import *

from src.functions import *
from src.classes import *

#   set git path reader
basedir = os.path.dirname(__file__)


#   MainWindow Class
class MainWindow(QMainWindow):

    def __init__(self, available_ports) -> None:
        super().__init__()

        #   MainWindow settings:
        self.setWindowIcon(QIcon(os.path.join(basedir, "icons", "equalizer.png")))  # Icon for application
        self.setWindowTitle("BMPC")
        self.set_window_size()
        qt_rectangle = self.frameGeometry()
        center_point = QDesktopWidget().availableGeometry().center()
        qt_rectangle.moveCenter(center_point)
        self.move(qt_rectangle.topLeft())

        #   Ports:
        self.ports: list = available_ports
        if "no port detected" not in self.ports:
            self.port: serial.Serial | None = serial.Serial(port=str(self.ports[0]), baudrate=115200)
        else:
            self.port: serial.Serial | None = None

        #   Threads:
        self.current_thread: threading.Thread | None = None

        #   Layouts:
        # Left Layout:
        self.left_widget: QWidget = QWidget()
        self.left_layout: QGridLayout = QGridLayout()

        # General Setting
        self.port_button: QPushButton = QPushButton(QIcon(os.path.join(basedir, "icons", "arrow-circle-double.png")),
                                                    '&refresh Ports',
                                                    self)
        self.port_button.clicked.connect(self.refresh_ports)
        self.port_combobox: QComboBox = QComboBox()
        self.port_combobox.addItems(self.ports)
        self.port_combobox.setCurrentText(self.ports[0])
        self.port_combobox.currentTextChanged.connect(self.change_port)

        self.voltage_label: QLabel = QLabel("Pump Voltage [Volt]:")
        self.voltage_spinbox: QDoubleSpinBox = QDoubleSpinBox()
        self.voltage_spinbox.setRange(0, 250)
        self.voltage_spinbox.setValue(0)

        # Impulse Settings
        self.injection_time_label: QLabel = QLabel("Injection Time [sec]:")
        self.injection_time_spinbox: QDoubleSpinBox = QDoubleSpinBox()
        self.injection_time_spinbox.setRange(0, 10000)
        self.injection_time_spinbox.setValue(0)

        self.injection_number_label: QLabel = QLabel("Number of Injections:")
        self.injection_number_spinbox: QSpinBox = QSpinBox()
        self.injection_number_spinbox.setRange(0, 10000)
        self.injection_number_spinbox.setValue(0)

        self.injection_distance_label: QLabel = QLabel("Injection Distance [sec]:")
        self.injection_distance_spinbox: QDoubleSpinBox = QDoubleSpinBox()
        self.injection_distance_spinbox.setRange(0, 10000)
        self.injection_distance_spinbox.setValue(0)

        self.start_button: QPushButton = QPushButton(QIcon(os.path.join(basedir, "icons", "control.png")),
                                                     '&Start',
                                                     self)
        self.start_button.clicked.connect(self.start_clicked)

        self.stop_button: QPushButton = QPushButton(QIcon(os.path.join(basedir, "icons", "control-stop-square.png")),
                                                    '&Stop',
                                                    self)
        self.stop_button.clicked.connect(self.stop_clicked)

        self.left_layout.addWidget(self.port_button, 0, 0)
        self.left_layout.addWidget(self.port_combobox, 0, 1)
        self.left_layout.addWidget(self.voltage_label, 1, 0)
        self.left_layout.addWidget(self.voltage_spinbox, 1, 1)
        self.left_layout.addWidget(self.injection_time_label, 2, 0)
        self.left_layout.addWidget(self.injection_time_spinbox, 2, 1)
        self.left_layout.addWidget(self.injection_number_label, 3, 0)
        self.left_layout.addWidget(self.injection_number_spinbox, 3, 1)
        self.left_layout.addWidget(self.injection_distance_label, 4, 0)
        self.left_layout.addWidget(self.injection_distance_spinbox, 4, 1)
        self.left_layout.addWidget(self.start_button, 5, 0)
        self.left_layout.addWidget(self.stop_button, 5, 1)

        # # Threading Test Buttons
        # self.test_start_button: QPushButton = QPushButton("Test Start")
        # self.test_start_button.clicked.connect(self.thread_test_start_clicked)
        # self.test_stop_button: QPushButton = QPushButton("Test Stop")
        # self.test_stop_button.clicked.connect(self.thread_test_stop_clicked)
        #
        # self.left_layout.addWidget(self.test_start_button, 7, 0)
        # self.left_layout.addWidget(self.test_stop_button, 7, 1)

        # # NI Test Buttons
        self.test_start_button: QPushButton = QPushButton("Test Start")
        self.test_start_button.clicked.connect(get_ni_system_channels)
        self.test_stop_button: QPushButton = QPushButton("Test Stop")
        self.test_stop_button.clicked.connect(get_ni_system_signal)
        #
        self.left_layout.addWidget(self.test_start_button, 7, 0)
        self.left_layout.addWidget(self.test_stop_button, 7, 1)

        self.left_widget.setLayout(self.left_layout)

        # #   Right Layout:
        self.right_layout: QGridLayout = QGridLayout()
        self.right_widget: QWidget = QWidget()

        self.scope_ai: PlotWidget = PlotWidget()
        self.scope_ai.setBackground('w')

        self.scope_pump: PlotWidget = PlotWidget()
        self.scope_pump.setBackground('w')

        self.right_layout.addWidget(self.scope_ai, 0, 0)
        self.right_layout.addWidget(self.scope_pump, 1, 0)
        self.right_widget.setLayout(self.right_layout)

        #   Main Layout:
        self.main_widget: QWidget = QWidget()
        self.main_layout: QHBoxLayout = QHBoxLayout()
        self.main_layout.addWidget(self.left_widget, stretch=1)
        self.main_layout.addWidget(self.right_widget, stretch=3)

        self.main_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.main_widget)

    #   Methods:
    def set_window_size(self):
        self.setGeometry(0, 0, 600, 300)
        # self.setMaximumSize(200, 250)

    def refresh_ports(self):
        self.ports = serial_ports()
        [self.port_combobox.removeItem(i) for i in list(range(len(self.ports)))]
        self.port_combobox.addItems(self.ports)
        self.port_combobox.setCurrentText(self.ports[0])

    def change_port(self):
        val = self.port_combobox.currentText()
        if val != "no port detected" and val != "":
            self.port = port_changed(self.port_combobox.currentText())

    def start_clicked(self):
        if self.port:
            if self.current_thread:
                print(f"Stop current thread: {self.current_thread}")
                self.current_thread.kill()
            if self.injection_time_spinbox.value() == 0:
                self.current_thread = Thread(target=start(self.port, self.voltage_spinbox.value()),
                                             args=[self.port, self.voltage_spinbox.value()])
            else:
                if self.injection_distance_spinbox.value() != 0 and self.injection_number_spinbox.value() != 0:
                    self.current_thread = Thread(target=pulse_series,
                                                 args=[self.port,
                                                       self.voltage_spinbox.value(),
                                                       self.injection_time_spinbox.value(),
                                                       self.injection_number_spinbox.value(),
                                                       self.injection_distance_spinbox.value()])

                else:
                    self.current_thread = Thread(target=pulse,
                                                 args=[self.port,
                                                       self.voltage_spinbox.value(),
                                                       self.injection_time_spinbox.value()])

    def stop_clicked(self):
        if self.port:
            if self.current_thread:
                print(f"Stop current thread: {self.current_thread}")
                self.current_thread.kill()
                self.current_thread = None
            stop(self.port)

    def thread_test_start_clicked(self):
        self.current_thread = Thread(target=test_start, args=[True])
        self.current_thread.start()

    def thread_test_stop_clicked(self):
        if self.current_thread:
            print(f"Stop current thread: {self.current_thread}")
            self.current_thread.kill()
            self.current_thread = None


#   create Application obj
if __name__ == "__main__":
    app = QApplication(sys.argv)
    #   Constructor GUI
    gui = MainWindow(serial_ports())
    #   execute Application
    gui.show()
    sys.exit(app.exec_())
