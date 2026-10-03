import asyncio
import enum
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
from server.scoreboard_state import State
from server.bluetooth_receiver import run_receiver

class ReceiverTests(unittest.IsolatedAsyncioTestCase):
    async def test_advertise_receive_respond_and_cleanup(self):
        stop=threading.Event();calls=[]
        class Error(enum.IntEnum): SUCCESS=0
        class Props(enum.IntFlag): WRITE=8;WRITE_WITHOUT_RESPONSE=4
        class Option(enum.IntEnum): WRITE_WITH_RESPONSE=0
        class Protection: PLAIN=0
        class Params: pass
        class Request:
            offset=0;option=0;value=b'BTS95/4'
            def respond(self):calls.append('respond')
        class Deferral:
            def complete(self):calls.append('complete');stop.set()
        class Args:
            def get_deferral(self):calls.append('defer');return Deferral()
            async def get_request_async(self):return Request()
        class Characteristic:
            def add_write_requested(self,callback):self.callback=callback;return 1
            def remove_write_requested(self,t):calls.append('unsubscribe')
        characteristic=Characteristic()
        class Service:
            async def create_characteristic_async(self,uuid,params):
                self.uuid=uuid
                self.params=params
                return types.SimpleNamespace(error=Error.SUCCESS,characteristic=characteristic)
        class Provider:
            service=Service()
            def add_advertisement_status_changed(self,callback):return 2
            def remove_advertisement_status_changed(self,t):pass
            def start_advertising_with_parameters(self,p):
                assert p.is_connectable and p.is_discoverable
                calls.append('advertise');characteristic.callback(None,Args())
            def stop_advertising(self):calls.append('stop')
        provider=Provider()
        class ProviderFactory:
            @staticmethod
            async def create_async(uuid):return types.SimpleNamespace(error=Error.SUCCESS,service_provider=provider)
        class Adapter:
            @staticmethod
            async def get_default_async():return types.SimpleNamespace(is_peripheral_role_supported=True)
        class Reader:
            unconsumed_buffer_length=7
            @classmethod
            def from_buffer(cls,raw):obj=cls();obj.raw=raw;return obj
            def read_bytes(self,buf):buf[:]=self.raw
            def close(self):pass
        bt=types.ModuleType('winrt.windows.devices.bluetooth');bt.BluetoothAdapter=Adapter;bt.BluetoothError=Error
        gatt=types.ModuleType('winrt.windows.devices.bluetooth.genericattributeprofile')
        for key,value in dict(GattServiceProvider=ProviderFactory,GattLocalCharacteristicParameters=Params,GattCharacteristicProperties=Props,GattProtectionLevel=Protection,GattServiceProviderAdvertisingParameters=Params,GattWriteOption=Option).items():setattr(gatt,key,value)
        streams=types.ModuleType('winrt.windows.storage.streams');streams.DataReader=Reader
        modules={bt.__name__:bt,gatt.__name__:gatt,streams.__name__:streams}
        with tempfile.TemporaryDirectory() as temp,patch.dict(sys.modules,modules),patch('server.bluetooth_receiver.sys.platform','win32'):
            state=State(temp)
            await asyncio.wait_for(run_receiver(state,stop),2)
            self.assertEqual(state.snapshot()['score']['runs'],'95')
            self.assertEqual(calls,['advertise','defer','respond','complete','stop','unsubscribe'])

if __name__=='__main__':unittest.main()
