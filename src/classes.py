import sys
import glob
import time
import serial
import traceback
import numpy as np

import threading
from PyQt5.QtCore import *

import nidaqmx
import nidaqmx.system
import nidaqmx.system.device
import nidaqmx.system._collections.device_collection
from nidaqmx.constants import AcquisitionType, LoggingMode, LoggingOperation, READ_ALL_AVAILABLE
from nidaqmx.stream_readers import AnalogMultiChannelReader, AnalogSingleChannelReader


class Thread(threading.Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""
    def __init__(self, *args, **keywords):
        threading.Thread.__init__(self, *args, **keywords)
        self.killed = False

    def start(self):
        self.__run_backup = self.run
        self.run = self.__run
        threading.Thread.start(self)

    def __run(self):
        sys.settrace(self.globaltrace)
        self.__run_backup()
        self.run = self.__run_backup

    def globaltrace(self, frame, event, arg):
        if event == 'call':
            return self.localtrace
        else:
            return None

    def localtrace(self, frame, event, arg):
        if self.killed:
            if event == 'line':
                raise SystemExit()
        return self.localtrace

    def kill(self):
        self.killed = True


class MicroPumpController:

    #  Data transition format
    # Mode : Amplitude
    #   1  :    250
    # Mode: 1 = 'Ein', 0 = 'Aus'
    # Amplitude: Value between 0-250

    def __init__(self) -> None:
        self.available_ports: None | list = None
        self.update_serial_ports()
        self.active_port: None | serial.Serial = None
        self.change_port(self.available_ports[0])
        self.current_thread: None | Thread = None

    def update_serial_ports(self) -> None:
        """ Lists serial port names

            :raises EnvironmentError:
                On unsupported or unknown platforms
            :returns:
                A list of the serial ports available on the system
        """
        if sys.platform.startswith('win'):
            ports = ['COM%s' % (i + 1) for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            # this excludes your current terminal "/dev/tty"
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            raise EnvironmentError('Unsupported platform')

        result = []
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except (OSError, serial.SerialException):
                pass
        if len(result) == 0:
            result.append("no port detected")

        self.available_ports = result

    def change_port(self, selection: str) -> None:
        if selection != "no port detected" and selection != "":
            self.active_port = serial.Serial(port=str(selection), baudrate=115200)
            print(f"Current Serial Port: {self.active_port}")

    def start(self, amplitude: int | float) -> float:
        if self.active_port:
            command = f"1:" + str(amplitude) + "\n"
            self.active_port.write(command.encode())
            timestamp = time.time()
            print(f'Injection timestamp: {timestamp}')
            print("start command send:", command)

            return timestamp

    def stop(self) -> None:
        if self.active_port:
            command = "1:0\n"
            self.active_port.write(command.encode())
            print("stop command send:", command)

    def pulse(self, amplitude: int | float, injection_time: int | float, file_name: None | str = None) -> None:
        timestamp = self.start(amplitude=amplitude)
        if file_name is not None or file_name != "":
            file = open(f'{file_name}.txt', "a")
            file.write(f'Injection timestamp: {timestamp}, Amplitude: {amplitude}[V], Duration: {injection_time}[s]\n')
            file.close()
        time.sleep(injection_time)
        self.stop()

    def pulse_series(self, amplitude: int | float,
                     injection_time: int | float,
                     injection_number: int,
                     injection_interval: int | float,
                     file_name: None | str = None) -> None:
        for _ in range(0, injection_number):
            print(f"Injection {_+1} of {injection_number}:")
            self.pulse(amplitude=amplitude, injection_time=injection_time, file_name=file_name)
            print(f"Pause for {injection_interval}[sec]")
            time.sleep(injection_interval)

    def threaded_start(self, amplitude: int | float,
                       injection_time: int | float,
                       injection_number: int,
                       injection_interval: int | float,
                       file_name: None | str = None) -> None:
        if not self.current_thread:
            if injection_time == 0:
                self.current_thread = Thread(target=self.start, args=[amplitude])
                print(f"Start current thread: {self.current_thread}")
                self.current_thread.start()
            elif injection_number != 0:
                self.current_thread = Thread(target=self.pulse_series, args=[amplitude,
                                                                             injection_time,
                                                                             injection_number,
                                                                             injection_interval,
                                                                             file_name])
                print(f"Start current thread: {self.current_thread}")
                self.current_thread.start()
            else:
                self.current_thread = Thread(target=self.pulse, args=[amplitude,
                                                                      injection_time,
                                                                      file_name])
                print(f"Start current thread: {self.current_thread}")
                self.current_thread.start()

    def threaded_stop(self) -> None:
        if self.current_thread:
            self.current_thread.kill()
            print(f"Stop current thread: {self.current_thread}")
            self.current_thread = None
        self.stop()


class NIDeviceController:

    def __init__(self) -> None:
        if not sys.platform.startswith('darwin'):
            self.available_devices_str: None | list[str] = None
            self.update_ni_system_devices_str()
            self.active_device_str: None | str = None
            self.change_device_selection(self.available_devices_str[0])
            self.current_thread: None | Thread = None

    def update_ni_system_devices_str(self) -> None:
        system = nidaqmx.system.System.local()
        result: list = [str(device) for device in system.devices]
        if len(result) == 0:
            self.available_devices_str = ["no NI System detected"]
        else:
            self.available_devices_str = result

    def change_device_selection(self, selection: str) -> None:
        if selection != "no NI System detected":
            self.active_device_str = ''.join(selection.split("=")[1].split(")")[0])
            print(f"Current NI Device: {self.active_device_str}")

    def get_ni_system_signal(self, physical_chanel: str):
        if self.active_device_str:
            with nidaqmx.Task() as read_task:
                read_task.ai_channels.add_ai_voltage_chan(f"{self.active_device_str}/{physical_chanel}")
                read_task.timing.cfg_samp_clk_timing(1000.0,
                                                     sample_mode=AcquisitionType.CONTINUOUS,
                                                     samps_per_chan=10)
                reader = AnalogSingleChannelReader(read_task.in_stream)
                output = np.zeros([10])
                read_task.start()
                while True:
                    reader.read_many_sample(data=output, number_of_samples_per_channel=10)
                    output = np.around(output, 8)
                    time.sleep(0.1)

                    return output
                #[-1.4  -1.4  -1.4  -1.4  -1.4  -1.4  -1.39 -1.39 -1.39 -1.39]
                #[-1.4  -1.4  -1.4  -1.4  -1.39 -1.39 -1.39 -1.39 -1.39 -1.38]
                #[-1.38 -1.39 -1.38 -1.38 -1.38 -1.38 -1.39 -1.4  -1.4  -1.41]
                #[-1.41 -1.41 -1.4  -1.39 -1.39 -1.38 -1.38 -1.38 -1.38 -1.38]

                #read_task.in_stream.configure_logging("TestData.tdms",
                #                                 LoggingMode.LOG_AND_READ,
                #                                 operation=LoggingOperation.CREATE_OR_REPLACE)
                #data = read_task.read(READ_ALL_AVAILABLE)


class WorkerSignals(QObject):

    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # Add the callback to our kwargs
        self.kwargs['progress_callback'] = self.signals.progress

    @pyqtSlot()
    def run(self):

        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done
