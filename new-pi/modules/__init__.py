"""
Waste detection system modules package.
"""
from .camera_module import CameraModule
from .detection_module import DetectionModule
from .gps_module import GPSModule
from .gas_sensor_module import GasSensorModule
from .communication import CommunicationModule
from .web_server import WebServer

__all__ = [
    'CameraModule',
    'DetectionModule',
    'GPSModule',
    'GasSensorModule',
    'CommunicationModule',
    'WebServer'
] 