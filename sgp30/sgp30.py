import sys
from math import exp
from dataclasses import asdict
from time import sleep, time
from typing import Final, Optional
from traceback import print_exc
from smbus2 import SMBus
from sgp30.models import Measurement, SensorData, SensorInfo


I2C_ADDRESS: Final[int] = 0x58

REG_BASE: Final[int] = 0x00

CMD_HEAD: Final[int] = 0x20
CMD_IAQ_INIT: Final[int] = 0x03
CMD_MEASURE_IAQ: Final[int] = 0x08
CMD_GET_IAQ_BASELINE: Final[int] = 0x15
CMD_SET_IAQ_BASELINE: Final[int] = 0x1E
CMD_SET_ABS_HUMI: Final[int] = 0x61
CMD_GET_FEATURE_SET: Final[int] = 0x2F
CMD_MEASURE_RAW: Final[int] = 0x50
CMD_GET_TVOC_INCEPTIVE_BASELINE: Final[int] = 0xB3
CMD_SET_TVOC_BASELINE: Final[int] = 0x77
CMD_SOFT_RESET: Final[int] = 0x06

CMD_GET_SERIAL_ID: Final[list[int]] = [0x36, 0x82]

T_IDLE: Final[float] = 0.001  # recommended 0.05ms, but given 1ms

SENSOR_MAKER: Final[str] = "Sensirion"


class SGP30:

    def __init__(self, bus_no: int) -> None:
        self.__tracker: int = 0
        self.__bus: SMBus = None

        try:
            self.__bus = SMBus(bus_no)

        except FileNotFoundError:
            print_exc(limit=2, file=sys.stdout)
            sys.exit(1)

        self.__address = I2C_ADDRESS

        try:
            self.__bus.read_byte_data(self.__address, 0)

        except OSError:
            print_exc(limit=2, file=sys.stdout)
            self.close()
            sys.exit(1)

        self.iaq_init()

    def crc_check(self, data: list[int], checksum: int) -> bool:
        return self.crc_calc(data) == checksum

    def crc_calc(self, data: list[int]) -> int:
        crc = 0xFF
        for i in range(2):
            crc ^= data[i]
            for _ in range(8, 0, -1):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0x31
                else:
                    crc = crc << 1

        # The checksum only contains 8-bit, so the calculated value will be masked with 0xFF
        return (crc & 0x0000FF)

    def get_serial_id(self) -> str:
        self.__bus.write_i2c_block_data(self.__address, CMD_GET_SERIAL_ID[0], [CMD_GET_SERIAL_ID[1]])
        sleep(T_IDLE)
        data = self.__bus.read_i2c_block_data(self.__address, REG_BASE, 9)
        serial_id_hex = "{:06X}".format(data[0] << 40 | data[1] << 32 | data[3] <<
                                        24 | data[4] << 16 | data[6] << 8 | data[7])
        return serial_id_hex

    def get_product_version(self) -> str:
        self.__bus.write_i2c_block_data(self.__address, CMD_HEAD, [CMD_GET_FEATURE_SET])
        sleep(0.05)
        byte_data = self.__bus.read_i2c_block_data(self.__address, REG_BASE, 3)
        data = byte_data[1]
        version_major = (data & 0b11100000) >> 5
        version_minor = data & 0b00011111
        return f"{version_major}.{version_minor}"

    def get_product_type(self) -> Optional[str]:
        self.__bus.write_i2c_block_data(self.__address, CMD_HEAD, [CMD_GET_FEATURE_SET])
        sleep(0.05)
        byte_data = self.__bus.read_i2c_block_data(self.__address, REG_BASE, 3)
        data = byte_data[0]
        product_type = (data & 0b11110000) >> 4

        if product_type == 0:
            return "SGP30"
        else:
            return None

    def calculate_abs_humidity(self, temp: float, humi: float) -> list[int]:
        abs_humi = 216.7 * (((humi/100) * 6.112 * exp((17.62*temp)/(243.12+temp))) / (273.15+temp))
        abs_humi_hex = "{:04x}".format(int(abs_humi * 256))
        return [int(abs_humi_hex[:2], 16), int(abs_humi_hex[2:], 16)]

    def set_abs_humidity_compensation(self, temp: float, humi: float) -> None:
        byte_list = self.calculate_abs_humidity(temp=temp, humi=humi)
        write_bytes = [CMD_SET_ABS_HUMI] + byte_list + [self.crc_calc(byte_list)]

        self.__bus.write_i2c_block_data(self.__address, CMD_HEAD, write_bytes)
        sleep(0.05)

    def iaq_init(self) -> None:
        self.__bus.write_i2c_block_data(self.__address, CMD_HEAD, [CMD_IAQ_INIT])
        sleep(0.05)

    def get_iaq_baseline(self) -> dict:
        # TODO
        self.__bus.write_i2c_block_data(self.__address, CMD_HEAD, [CMD_GET_IAQ_BASELINE])
        sleep(0.05)
        data = self.__bus.read_i2c_block_data(self.__address, REG_BASE, 6)
        sleep(0.05)

    def soft_reset(self) -> None:
        self.__bus.write_byte(CMD_HEAD, CMD_SOFT_RESET)

    def get_sensor_info(self) -> SensorInfo:
        serial = self.get_serial_id()
        product_type = self.get_product_type()
        product_version = self.get_product_version()
        return SensorInfo(SENSOR_MAKER, product_type, serial, product_version)

    def get_measurement(self, as_dict: bool = False, temp: float = 0.0, humi: float = 0.0) -> SensorData:
        if (time() - self.__tracker < 1):
            sleep(1)

        # self.set_abs_humidity_compensation(temp=temp, humi=humi)
        self.__bus.write_i2c_block_data(self.__address, CMD_HEAD, [CMD_MEASURE_IAQ])
        sleep(1)
        data = self.__bus.read_i2c_block_data(self.__address, REG_BASE, 6)
        self.__tracker = time()

        co2 = round(data[0] << 8 | data[1], 0)
        tvoc = round(data[3] << 8 | data[4], 0)

        measured = SensorData([
            Measurement("co2", "ppm", co2),
            Measurement("tvoc", "ppb", tvoc)
        ])

        if as_dict:
            return asdict(measured)

        return measured

    def close(self) -> None:
        print(f"Closing I2C bus {self.__bus}")
        self.soft_reset()
        self.__bus.close()
