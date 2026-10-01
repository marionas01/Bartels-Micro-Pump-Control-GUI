import sys
import glob
import time
import threading
import traceback

import serial
import numpy as np

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

# nidaqmx is only needed on Windows/Linux - guard the import so macOS still works
try:
    import nidaqmx
    import nidaqmx.system
    from nidaqmx.constants import AcquisitionType
    from nidaqmx.stream_readers import AnalogSingleChannelReader
    NIDAQ_AVAILABLE = True
except ImportError:
    NIDAQ_AVAILABLE = False


# ----------------------------------------------------------------------------------------------------------------------
#   Hardware controllers (no threading logic in here anymore - just talking to the hardware)
# ----------------------------------------------------------------------------------------------------------------------
class MicroPumpController:

    #  Data transition format
    # Mode : Amplitude
    #   1  :    250
    # Mode: 1 = 'Ein', 0 = 'Aus'
    # Amplitude: Value between 0-250

    def __init__(self) -> None:
        self.available_ports: None | list = None
        self.active_port: None | serial.Serial = None
        # The serial port is now written from the worker thread AND (on port change) from the GUI thread
        self._port_lock = threading.Lock()
        self.update_serial_ports()
        self.change_port(self.available_ports[0])

    def update_serial_ports(self) -> None:
        """ Lists serial port names

            :raises EnvironmentError:
                On unsupported or unknown platforms
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
            with self._port_lock:
                if self.active_port is not None and self.active_port.is_open:
                    self.active_port.close()
                self.active_port = serial.Serial(port=str(selection), baudrate=115200)
            print(f"Current Serial Port: {self.active_port}")

    def _write(self, command: str) -> None:
        with self._port_lock:
            if self.active_port:
                self.active_port.write(command.encode())

    def start(self, amplitude: int | float) -> float:
        command = f"1:{amplitude}\n"
        self._write(command)
        timestamp = time.time()
        print(f'Injection timestamp: {timestamp}')
        print("start command send:", command)
        return timestamp

    def stop(self) -> float:
        command = "1:0\n"
        self._write(command)
        timestamp = time.time()
        print("stop command send:", command)
        return timestamp


class NIDeviceController:

    def __init__(self) -> None:
        self.available_devices_str: list[str] = []
        self.active_device_str: None | str = None
        if NIDAQ_AVAILABLE:
            self.update_ni_system_devices_str()
            self.change_device_selection(self.available_devices_str[0])

    def update_ni_system_devices_str(self) -> None:
        system = nidaqmx.system.System.local()
        result: list = [str(device) for device in system.devices]
        self.available_devices_str = result if result else ["no NI System detected"]

    def change_device_selection(self, selection: str) -> None:
        if selection != "no NI System detected" and selection != "":
            self.active_device_str = ''.join(selection.split("=")[1].split(")")[0])
            print(f"Current NI Device: {self.active_device_str}")


# ----------------------------------------------------------------------------------------------------------------------
#   QThread workers
#   Pattern: worker (QObject) is moved to a QThread, communicates with the GUI ONLY via signals.
#   Stopping is cooperative: stop() sets a threading.Event which the worker checks / waits on.
# ----------------------------------------------------------------------------------------------------------------------
class PumpWorker(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    status = pyqtSignal(str)
    progress = pyqtSignal(int, int)        # (current injection, total injections)
    voltage_changed = pyqtSignal(float, float)  # (timestamp [s since epoch], voltage [V]) - for the live plot

    def __init__(self, controller: MicroPumpController,
                 amplitude: int | float,
                 injection_time: int | float,
                 injection_number: int,
                 injection_interval: int | float,
                 file_name: None | str = None) -> None:
        super().__init__()
        self.controller = controller
        self.amplitude = amplitude
        self.injection_time = injection_time
        self.injection_number = injection_number
        self.injection_interval = injection_interval
        self.file_name = file_name
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """Called DIRECTLY from the GUI thread (not via signal - the worker's event loop
        is busy inside run(), so a queued signal would never be delivered)."""
        self._stop_event.set()

    def _pump_on(self) -> float:
        timestamp = self.controller.start(amplitude=self.amplitude)
        self.voltage_changed.emit(timestamp, float(self.amplitude))
        return timestamp

    def _pump_off(self) -> None:
        timestamp = self.controller.stop()
        self.voltage_changed.emit(timestamp, 0.0)

    @pyqtSlot()
    def run(self) -> None:
        try:
            if self.injection_time == 0:
                # Continuous mode: switch on and block until Stop is pressed
                self._pump_on()
                self.status.emit("Pump running (continuous)")
                self._stop_event.wait()
            else:
                for i in range(self.injection_number):
                    if self._stop_event.is_set():
                        break
                    self.progress.emit(i + 1, self.injection_number)
                    self.status.emit(f"Injection {i + 1} of {self.injection_number}")
                    if self._pulse():
                        break                                   # stopped during the pulse
                    if i < self.injection_number - 1:           # no pause after the last injection
                        self.status.emit(f"Pause for {self.injection_interval} s")
                        if self._stop_event.wait(self.injection_interval):
                            break                               # stopped during the pause
        except Exception:
            self.error.emit(traceback.format_exc())
        finally:
            self._pump_off()                                    # pump is ALWAYS switched off
            self.status.emit("Pump stopped")
            self.finished.emit()

    def _pulse(self) -> bool:
        """One injection. Returns True if it was interrupted by stop()."""
        timestamp = self._pump_on()
        if self.file_name:                                      # was: 'is not None or != ""' -> always True
            with open(f'{self.file_name}.txt', "a") as file:
                file.write(f'Injection timestamp: {timestamp}, Amplitude: {self.amplitude}[V], '
                           f'Duration: {self.injection_time}[s]\n')
        # Event.wait() replaces time.sleep(): it returns immediately (True) when stop() is called
        interrupted = self._stop_event.wait(self.injection_time)
        self._pump_off()
        return interrupted


class NIWorker(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    data_ready = pyqtSignal(object)        # np.ndarray with the newest samples

    def __init__(self, device: str, channel: str,
                 sample_rate: float = 1000.0, samples_per_read: int = 100) -> None:
        super().__init__()
        self.device = device
        self.channel = channel
        self.sample_rate = sample_rate
        self.samples_per_read = samples_per_read
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    @pyqtSlot()
    def run(self) -> None:
        try:
            with nidaqmx.Task() as read_task:
                read_task.ai_channels.add_ai_voltage_chan(f"{self.device}/{self.channel}")
                read_task.timing.cfg_samp_clk_timing(self.sample_rate,
                                                     sample_mode=AcquisitionType.CONTINUOUS,
                                                     samps_per_chan=self.samples_per_read * 10)
                reader = AnalogSingleChannelReader(read_task.in_stream)
                read_task.start()
                while not self._stop_event.is_set():
                    # New buffer each time: the array is handed to the GUI thread by reference
                    output = np.zeros(self.samples_per_read)
                    # Blocks until samples_per_read samples are there (100 / 1000 Hz = 0.1 s),
                    # so no time.sleep() is needed (sleeping would let the DAQ buffer overflow)
                    reader.read_many_sample(data=output,
                                            number_of_samples_per_channel=self.samples_per_read,
                                            timeout=10.0)
                    self.data_ready.emit(np.around(output, 8))
        except Exception:
            self.error.emit(traceback.format_exc())
        finally:
            self.finished.emit()