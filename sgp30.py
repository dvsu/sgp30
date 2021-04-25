from time import sleep
from math import exp
from smbus2 import SMBus


REG_BASE = 0x00

CMD_HEAD = 0x20
CMD_IAQ_INIT = 0x03
CMD_MEASURE_IAQ = 0x08
CMD_GET_IAQ_BASELINE = 0x15
CMD_SET_IAQ_BASELINE = 0x1E
CMD_SET_ABS_HUMI = 0x61
CMD_GET_FEATURE_SET = 0x2F
CMD_MEASURE_RAW = 0x50
CMD_GET_TVOC_INCEPTIVE_BASELINE = 0xB3
CMD_SET_TVOC_BASELINE = 0x77
CMD_SOFT_RESET = 0x06

CMD_GET_SERIAL_ID = [0x36, 0x82]


class SGP30:

    def __init__(self, bus_obj:SMBus):
        self.__bus = bus_obj
        self.__address = 0x58
        self.iaq_init()
    
    def crc_check(self, data:list, checksum:int) -> bool:
        return self.crc_calc(data) == checksum
    
    def crc_calc(self, data:list) -> int:
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
        self.__bus.write_i2c_block_data(self.__address, CMD_GET_SERIAL_ID[0],[CMD_GET_SERIAL_ID[1]])
        sleep(0.05)
        data = self.__bus.read_i2c_block_data(self.__address, REG_BASE, 9)
        serial_id_hex = "{:06X}".format(data[0] << 40 | data[1] << 32 | data[3] << 24 | data[4] << 16 | data[6] << 8 | data[7])
        sleep(0.05)
        return serial_id_hex

    def abs_humidity_calculation(self, temp:float, humi:float) -> list:
        abs_humi = 216.7 * (((humi/100) * 6.112 * exp((17.62*temp)/(243.12+temp))) / (273.15+temp))
        abs_humi_hex = "{:04x}".format(int(abs_humi * 256))
        return [int(abs_humi_hex[:2], 16), int(abs_humi_hex[2:], 16)]

    def set_abs_humidity_compensation(self, temp:float, humi:float) -> None:
        byte_list = self.abs_humidity_calculation(temp=temp, humi=humi)
        write_bytes = [CMD_SET_ABS_HUMI] + byte_list + [self.crc_calc(byte_list)]

        self.__bus.write_i2c_block_data(self.__address, CMD_HEAD, write_bytes)
        sleep(0.05)

    def iaq_init(self) -> None:
        self.__bus.write_i2c_block_data(self.__address, CMD_HEAD,[CMD_IAQ_INIT])
        sleep(0.05)

    def get_iaq_baseline(self) -> dict:
        self.__bus.write_i2c_block_data(self.__address, CMD_HEAD,[CMD_GET_IAQ_BASELINE])
        sleep(0.05)
        data = self.__bus.read_i2c_block_data(self.__address, REG_BASE, 6)
        sleep(0.05)

    def soft_reset(self) -> None:
        self.__bus.write_byte(CMD_HEAD, CMD_SOFT_RESET)

    def get_measurement(self, temp:float=0.0, humi:float=0.0) -> dict:
        sleep(0.05)
        self.set_abs_humidity_compensation(temp=temp, humi=humi)
        self.__bus.write_i2c_block_data(self.__address, CMD_HEAD,[CMD_MEASURE_IAQ])
        sleep(0.05)
        data = self.__bus.read_i2c_block_data(self.__address, REG_BASE,6)
        sleep(0.05)

        co2 = round(data[0] << 8 | data[1], 0)
        tvoc  = round(data[3] << 8 | data[4], 0)
            
        return {
            "co2": co2,
            "co2_unit": "ppm",
            "tvoc": tvoc,
            "tvoc_unit": "ppb"
        }       


# uncomment for test

# import sys
# from datetime import datetime


# bus = SMBus(1)
# sen = SGP30(bus_obj=bus)


# while True:

#     try:
#         print(datetime.now(), sen.get_measurement())
#         sleep(3)

#     except KeyboardInterrupt:
#         sys.exit(1)
