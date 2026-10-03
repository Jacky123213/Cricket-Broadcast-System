"""Windows GATT peripheral. Hardware integration must be tested on Windows."""
import asyncio
import sys
from uuid import UUID
from .scoreboard_protocol import SERVICE_UUID, WRITE_UUID


async def run_receiver(state, stop):
    if sys.platform != 'win32':
        state.set_status('Bluetooth requires Windows. Manual overlay is available.')
        return
    provider = None
    characteristic = None
    write_token = status_token = None
    pending = set()
    try:
        from winrt.windows.devices.bluetooth import BluetoothAdapter, BluetoothError
        from winrt.windows.devices.bluetooth.genericattributeprofile import (
            GattServiceProvider, GattLocalCharacteristicParameters,
            GattCharacteristicProperties, GattProtectionLevel,
            GattServiceProviderAdvertisingParameters, GattWriteOption)
        from winrt.windows.storage.streams import DataReader
        adapter = await BluetoothAdapter.get_default_async()
        if adapter is None or not adapter.is_peripheral_role_supported:
            raise RuntimeError('The default adapter cannot act as a BLE peripheral')
        result = await GattServiceProvider.create_async(UUID(SERVICE_UUID))
        if result.error != BluetoothError.SUCCESS:
            raise RuntimeError('Creating scoreboard service failed: ' + str(result.error))
        provider = result.service_provider
        params = GattLocalCharacteristicParameters()
        params.characteristic_properties = (GattCharacteristicProperties.WRITE |
                                             GattCharacteristicProperties.WRITE_WITHOUT_RESPONSE)
        params.write_protection_level = GattProtectionLevel.PLAIN
        params.user_description = 'Backyard Scoreboard score input'
        result = await provider.service.create_characteristic_async(UUID(WRITE_UUID), params)
        if result.error != BluetoothError.SUCCESS:
            raise RuntimeError('Creating score characteristic failed: ' + str(result.error))
        characteristic = result.characteristic
        loop = asyncio.get_running_loop()

        async def handle_write(args, deferral):
            request = None
            try:
                request = await args.get_request_async()
                if request is None: return
                if request.offset != 0:
                    if request.option == GattWriteOption.WRITE_WITH_RESPONSE:
                        request.respond_with_protocol_error(0x07)
                    state.set_status('Received unsupported offset write; reconnect using Generic')
                    return
                reader = DataReader.from_buffer(request.value)
                raw = bytearray(reader.unconsumed_buffer_length)
                reader.read_bytes(raw)
                reader.close()
                if request.option == GattWriteOption.WRITE_WITH_RESPONSE:
                    request.respond()
                state.receive(bytes(raw))
            except Exception as exc:
                state.set_status('Bluetooth write error: ' + str(exc))
            finally:
                deferral.complete()

        def schedule(args, deferral):
            task = asyncio.create_task(handle_write(args, deferral))
            pending.add(task)
            task.add_done_callback(pending.discard)

        def on_write(sender, args):
            # WinRT callbacks may arrive on a different thread. Take the deferral
            # before returning, then marshal work onto our asyncio loop.
            deferral = args.get_deferral()
            try: loop.call_soon_threadsafe(schedule, args, deferral)
            except RuntimeError: deferral.complete()

        def on_status(sender, args):
            state.set_status('Bluetooth advertising: ' + args.status.name +
                             ('; error ' + str(args.error) if args.error != BluetoothError.SUCCESS else ''))

        write_token = characteristic.add_write_requested(on_write)
        status_token = provider.add_advertisement_status_changed(on_status)
        advertising = GattServiceProviderAdvertisingParameters()
        advertising.is_discoverable = True
        advertising.is_connectable = True
        state.set_status('Starting Bluetooth scoreboard advertising…')
        provider.start_advertising_with_parameters(advertising)
        while not stop.is_set(): await asyncio.sleep(.25)
    except Exception as exc:
        state.set_status('Bluetooth unavailable: ' + str(exc) + '. See README; manual overlay remains available.')
    finally:
        if provider:
            provider.stop_advertising()
            if status_token is not None: provider.remove_advertisement_status_changed(status_token)
        if characteristic and write_token is not None:
            characteristic.remove_write_requested(write_token)
        if pending:
            for task in pending: task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)


def start_receiver(state, stop):
    if sys.platform == 'win32':
        try:
            from winrt.runtime import init_apartment, uninit_apartment, ApartmentType
            init_apartment(ApartmentType.MULTI_THREADED)
        except Exception as exc:
            state.set_status('Bluetooth runtime could not start: ' + str(exc)); return
        try: asyncio.run(run_receiver(state, stop))
        finally: uninit_apartment()
    else:
        asyncio.run(run_receiver(state, stop))
