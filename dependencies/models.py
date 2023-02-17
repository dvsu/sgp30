from typing import List, Optional
from dataclasses import dataclass


@dataclass
class SensorInfo:
    maker: str
    model: Optional[str]
    serial: Optional[str]
    version: Optional[str]


@dataclass
class Measurement:
    name: str
    unit: str
    value: float


@dataclass
class SensorData:
    measurements: List[Measurement]


@dataclass
class Sensor(SensorInfo, SensorData):
    timestamp: str
