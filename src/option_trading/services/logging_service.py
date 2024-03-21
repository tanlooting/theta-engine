import logging
from logging.handlers import SysLogHandler

def loggerService(host:str, port):
    
    """Set up logger
    Add PAPERTRAIL_HOST and PAPERTRAIL_PORT in .env file
    """
    _logger = logging.getLogger("trading_system")
    _logger.setLevel(logging.INFO)

    sysloghandler = SysLogHandler(
        address=(
            host,
            int(port),
        )
    )
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    sysloghandler.setFormatter(formatter)

    _logger.addHandler(sysloghandler)

    return _logger
    