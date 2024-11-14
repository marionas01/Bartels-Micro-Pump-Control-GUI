#   Imports:
import sys
import glob
import time
import serial

import nidaqmx
import nidaqmx.system
import nidaqmx.system.device
import nidaqmx.system._collections.device_collection
from nidaqmx.constants import AcquisitionType, LoggingMode, LoggingOperation, READ_ALL_AVAILABLE


def get_ni_system_devices_str() -> list:
    system = nidaqmx.system.System.local()
    result: list = [str(device) for device in system.devices]
    if len(result) == 0:
        return ["no NI System detected"]
    else:
        return result


def get_ni_system_channels():
    system = nidaqmx.system.System.local()
    channels = system.global_channels
    print(system)
    print(channels)
    for device in system.devices:
        print(device)
        print(system.devices)
        print(type(system.devices))
    return


def get_ni_system_signal(device: str, physical_chanel: str):
    with nidaqmx.Task() as task:
        task.ai_channels.add_ai_voltage_chan(f"{device}/{physical_chanel}")
        task.timing.cfg_samp_clk_timing(1000.0, sample_mode=AcquisitionType.CONTINUOUS, samps_per_chan=10)
        task.in_stream.configure_logging("TestData.tdms", LoggingMode.LOG_AND_READ,
                                         operation=LoggingOperation.CREATE_OR_REPLACE)
        data = task.read(READ_ALL_AVAILABLE)
    return data
