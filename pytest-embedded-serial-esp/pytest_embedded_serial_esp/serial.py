import contextlib
import functools
import logging
from enum import Enum
from typing import Dict, Optional

import esptool
import serial as pyserial
from esptool import CHIP_DEFS, FatalError, detect_chip
from pytest_embedded.log import MessageQueue
from pytest_embedded_serial.dut import Serial


class EsptoolVersion(Enum):
    V3 = 3
    V4 = 4


class EspSerial(Serial):
    """
    Serial class for ports connected to espressif products
    """

    ESPTOOL_DEFAULT_BAUDRATE = 921600

    try:
        # esptool>=4.0
        from esptool import __version__
        from esptool.loader import ESPLoader
        from esptool.targets import CHIP_LIST

        ESPTOOL_VERSION = EsptoolVersion.V4
        ESPTOOL_CHIPS = CHIP_LIST
        _ESPTOOL_RAW_VERSION = __version__
    except (AttributeError, ModuleNotFoundError):
        # esptool<4.0
        from esptool import SUPPORTED_CHIPS, ESPLoader, __version__

        ESPTOOL_VERSION = EsptoolVersion.V3
        ESPTOOL_CHIPS = SUPPORTED_CHIPS
        _ESPTOOL_RAW_VERSION = __version__

    def __init__(
        self,
        msg_queue: MessageQueue,
        target: Optional[str] = None,
        beta_target: Optional[str] = None,
        port: Optional[str] = None,
        baud: int = Serial.DEFAULT_BAUDRATE,
        esptool_baud: int = ESPTOOL_DEFAULT_BAUDRATE,
        skip_autoflash: bool = False,
        erase_all: bool = False,
        port_target_cache: Dict[str, str] = None,
        **kwargs,
    ) -> None:
        self._port_target_cache: Dict[str, str] = port_target_cache if port_target_cache is not None else {}

        esptool_target = beta_target or target
        if port is None:
            available_ports = esptool.get_port_list()
            ports = list(set(available_ports) - set(self.occupied_ports.keys()))

            # sort to make /dev/ttyS* ports before /dev/ttyUSB* ports
            # esptool will reverse the list
            ports.sort()

            # prioritize the cache recorded target port
            if esptool_target:
                for _port, _target in self._port_target_cache.items():
                    if _target == esptool_target and _port in ports:
                        ports.sort(key=lambda x: x == _port)
                        logging.debug('hit port-target cache: %s - %s', _port, _target)

            logging.debug(f'Detecting ports from {", ".join(ports)}')
        else:
            ports = [port]

        # normal loader
        if esptool_target not in (['auto'] + self.ESPTOOL_CHIPS):
            raise ValueError(
                f'esptool version {self._ESPTOOL_RAW_VERSION} not support target {esptool_target}\n'
                f'Supported targets: {self.ESPTOOL_CHIPS}'
            )

        with contextlib.redirect_stdout(msg_queue):
            esp: esptool.ESPLoader = esptool.get_default_connected_device(
                ports,
                port=port,
                connect_attempts=3,
                initial_baud=baud,
                chip=esptool_target,
            )
        if not esp:
            raise ValueError('Couldn\'t auto detect chip. Please manually specify with "--port"')
        # ensure port is closed. The redirect instance would be opened later
        esp._port.close()

        self.esp = None
        self.stub = None

        target = esp.CHIP_NAME.lower().replace('-', '')
        logging.info(f'Target: %s, Port: %s', target, esp.serial_port)

        self.target = target

        self.skip_autoflash = skip_autoflash
        self.erase_all = erase_all
        self.esptool_baud = esptool_baud
        super().__init__(msg_queue, esp.serial_port, baud, **kwargs)

    def _post_init(self):
        logging.debug('set port-target cache: %s - %s', self.port, self.target)
        self._port_target_cache[self.port] = self.target
        super()._post_init()

    def use_esptool(func):
        """
        1. close the redirect serial process if exists
        2. close the serial connection
        3. use esptool to connect to the serial port and call `run_stub()`
        4. call to the decorated function, could use `self.stub` inside the function as the stubbed loader
        5. call `hard_reset()`
        5. create the redirect serial process again

        Warning:
            the real `pyserial` object must be created inside `self._forward_io`,
                The `pyserial` object can't be pickled when using multiprocessing.Process
        """

        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            with self.disable_redirect_serial():
                _s = pyserial.serial_for_url(self.port, **self.port_config)
                settings = _s.get_settings()
                try:
                    with contextlib.redirect_stdout(self._q):
                        self.esp = esptool.detect_chip(_s, self.baud)
                        self.esp.connect('hard_reset')
                        self.stub = self.esp.run_stub()

                        ret = func(self, *args, **kwargs)
                finally:
                    self.stub.hard_reset()

                    _s.apply_settings(settings)
                    _s.close()

            return ret

        return wrapper

    def _start(self):
        self.hard_reset()

    @use_esptool
    def hard_reset(self):
        """Hard reset your espressif device"""
        pass
