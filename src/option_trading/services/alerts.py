from abc import ABC, abstractmethod

class baseAlerts(ABC):
    """enforces the same class methods 
    used for logging module 
    on all alerts services"""
    @abstractmethod
    def info(self, message:str):
        pass
    @abstractmethod
    def error(self, message:str):
        pass
    @abstractmethod
    def warning(self, message:str):
        pass
    
class alertsManager(baseAlerts):
    """dispatches messages to all NOTIFICATION services
    
    Currently implemented services include:
    - telegram
    - logger
    """
    def __init__(self, services: list):
        self.services = services
    
    def info(self, message):
        for services in self.services:
            services.info(message)
    
    def error(self, message):
        for services in self.services:
            services.error(message)
    
    def warning(self, message):
        for services in self.services:
            services.warning(message)