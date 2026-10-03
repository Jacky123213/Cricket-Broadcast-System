"""Keep Windows awake during the server lifespan; no persistent power-plan edits."""
import ctypes
import logging
import sys

log = logging.getLogger('uvicorn.error')
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


class SleepGuard:
    def __init__(self):
        self.status = 'Not started'
        self._set_state = None

    def start(self):
        if sys.platform != 'win32':
            self.status = 'Automatic sleep prevention is Windows-only'
            return
        try:
            fn = ctypes.WinDLL('kernel32', use_last_error=True).SetThreadExecutionState
            fn.argtypes = [ctypes.c_uint32]
            fn.restype = ctypes.c_uint32
            if not fn(ES_CONTINUOUS | ES_SYSTEM_REQUIRED):
                raise OSError('Windows rejected the keep-awake request')
            self._set_state = fn
            self.status = 'Automatic Windows sleep prevented while server runs'
            log.info(self.status)
        except (OSError, AttributeError) as exc:
            self.status = f'Sleep prevention unavailable: {exc}'
            log.warning(self.status)

    def stop(self):
        # Must run on the same thread as start (the ASGI lifespan thread).
        if self._set_state:
            if not self._set_state(ES_CONTINUOUS):
                log.warning('Could not release Windows keep-awake request')
            self._set_state = None
        self.status = 'Stopped'
