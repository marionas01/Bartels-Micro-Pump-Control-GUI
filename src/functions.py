#   Imports:
import sys
import glob
import time
import serial

#  Data transition format
# Mode : Amplitude
#   1  :    250
# Mode: 1 = 'Ein', 0 = 'Aus'
# Amplitude: Value between 0-250


def serial_ports():
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

    return result


def port_changed(new_port_str: str) -> serial.Serial:
    if new_port_str != "no port detected" and new_port_str != "":
        return serial.Serial(port=str(new_port_str), baudrate=115200)


def start(serial_port: serial.Serial, amplitude: int | float) -> None:
    command = f"1:"+str(amplitude)+"\n"
    serial_port.write(command.encode())
    print("start command send:", command)


def stop(serial_port: serial.Serial) -> None:
    command = "1:0\n"
    serial_port.write(command.encode())
    print("stop command send:", command)


def pulse(serial_port: serial.Serial, amplitude: int | float, injection_time: int | float) -> None:
    start(serial_port=serial_port, amplitude=amplitude)
    time.sleep(injection_time)
    stop(serial_port=serial_port)


def pulse_series(serial_port: serial.Serial, amplitude: int | float, injection_time: int | float, injection_number: int,
                 injection_distance: int | float) -> None:
    for i in range(0, injection_number):
        pulse(serial_port=serial_port, amplitude=amplitude, injection_time=injection_time)
        time.sleep(injection_distance)


def test_start(arg: bool):
    while arg is True:
        print("Thread 1 started: going to sleep for 10 sec")
        time.sleep(1)
        print("Thread 1 completed:")


def test_stop(arg: bool):
    return
