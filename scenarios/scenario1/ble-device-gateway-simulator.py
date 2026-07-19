#!/usr/bin/env python3
"""
BLE Device + Gateway Simulator

Creates both a BLE peripheral (device broadcasting data) and a BLE central (gateway receiving data)
on a virtual Bluetooth interface. Both run together to simulate a complete BLE conversation.

Requires: python3-dbus, python3-gi, bluez

Usage:
    python3 ble-device-gateway-simulator.py --device-name "Heart Rate Monitor" --data "HR:72,SpO2:98"
    python3 ble-device-gateway-simulator.py --config scenario.json
"""

import argparse
import json
import sys
import time
import threading
import subprocess
from pathlib import Path

try:
    from dbus import DBusException
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    import gi
    gi.require_version('GLib', '2.0')
    from gi.repository import GLib, GObject
except ImportError as e:
    print(f"Error: Required packages not installed. Install with:")
    print("  sudo apt-get install python3-dbus python3-gi gir1.2-glib-2.0 bluez")
    print(f"  Missing: {e}")
    sys.exit(1)

# BlueZ D-Bus interfaces
BLUEZ_SERVICE = "org.bluez"
ADAPTER_INTERFACE = "org.bluez.Adapter1"
DEVICE_INTERFACE = "org.bluez.Device1"
GATT_MANAGER_INTERFACE = "org.bluez.GattManager1"
GATT_SERVICE_INTERFACE = "org.bluez.GattService1"
GATT_CHAR_INTERFACE = "org.bluez.GattCharacteristic1"
GATT_DESC_INTERFACE = "org.bluez.GattDescriptor1"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"
DBUS_OM_IFACE = "org.freedesktop.DBus.ObjectManager"


class BLEPeripheral:
    """Simulate a BLE peripheral device (wearable, sensor, etc.)"""
    
    def __init__(self, device_name, service_uuid, data, adapter='hci0'):
        self.device_name = device_name
        self.service_uuid = service_uuid
        self.data = data  # dict of key:value pairs to broadcast
        self.adapter = adapter
        self.bus = None
        self.adapter_path = None
        self.running = False
        
    def setup(self):
        """Connect to DBus and find adapter"""
        try:
            self.bus = dbus.SystemBus()
            
            # Get adapter path
            manager = dbus.Interface(
                self.bus.get_object(BLUEZ_SERVICE, "/"),
                DBUS_OM_IFACE
            )
            
            for path, interfaces in manager.GetManagedObjects().items():
                if ADAPTER_INTERFACE in interfaces:
                    if self.adapter in path:
                        self.adapter_path = path
                        break
            
            if not self.adapter_path:
                print(f"✗ Adapter {self.adapter} not found")
                return False
            
            # Power on adapter
            adapter = dbus.Interface(
                self.bus.get_object(BLUEZ_SERVICE, self.adapter_path),
                ADAPTER_INTERFACE
            )
            adapter.Set(ADAPTER_INTERFACE, "Powered", dbus.Boolean(True))
            adapter.Set(ADAPTER_INTERFACE, "Discoverable", dbus.Boolean(True))
            
            print(f"✓ Adapter {self.adapter} ready")
            return True
            
        except Exception as e:
            print(f"✗ Setup error: {e}")
            return False
    
    def advertise(self):
        """Start advertising the device"""
        try:
            adapter = dbus.Interface(
                self.bus.get_object(BLUEZ_SERVICE, self.adapter_path),
                ADAPTER_INTERFACE
            )
            
            # Set alias (friendly name)
            adapter.Set(ADAPTER_INTERFACE, "Alias", self.device_name)
            
            print(f"✓ Advertising as '{self.device_name}' on {self.adapter}")
            self.running = True
            return True
            
        except Exception as e:
            print(f"✗ Advertisement error: {e}")
            return False
    
    def broadcast_data(self):
        """Continuously broadcast data"""
        while self.running:
            print(f"\n[{time.strftime('%H:%M:%S')}] Device broadcasting:")
            for key, value in self.data.items():
                print(f"  {key}: {value}")
            time.sleep(5)


class BLEGateway:
    """Simulate a BLE central/gateway that receives device data"""
    
    def __init__(self, adapter='hci0'):
        self.adapter = adapter
        self.bus = None
        self.adapter_path = None
        self.discovered_devices = {}
        self.running = False
    
    def setup(self):
        """Connect to DBus and find adapter"""
        try:
            self.bus = dbus.SystemBus()
            
            # Get adapter path
            manager = dbus.Interface(
                self.bus.get_object(BLUEZ_SERVICE, "/"),
                DBUS_OM_IFACE
            )
            
            for path, interfaces in manager.GetManagedObjects().items():
                if ADAPTER_INTERFACE in interfaces:
                    if self.adapter in path:
                        self.adapter_path = path
                        break
            
            if not self.adapter_path:
                print(f"✗ Adapter {self.adapter} not found for gateway")
                return False
            
            # Power on adapter
            adapter = dbus.Interface(
                self.bus.get_object(BLUEZ_SERVICE, self.adapter_path),
                ADAPTER_INTERFACE
            )
            adapter.Set(ADAPTER_INTERFACE, "Powered", dbus.Boolean(True))
            
            print(f"✓ Gateway using adapter {self.adapter}")
            return True
            
        except Exception as e:
            print(f"✗ Gateway setup error: {e}")
            return False
    
    def scan_devices(self):
        """Scan for BLE devices"""
        try:
            # Start discovery
            adapter = dbus.Interface(
                self.bus.get_object(BLUEZ_SERVICE, self.adapter_path),
                ADAPTER_INTERFACE
            )
            adapter.StartDiscovery()
            print(f"✓ Gateway scanning for BLE devices...")
            
            self.running = True
            return True
            
        except Exception as e:
            print(f"✗ Scan error: {e}")
            return False
    
    def monitor_devices(self):
        """Monitor discovered devices"""
        while self.running:
            try:
                manager = dbus.Interface(
                    self.bus.get_object(BLUEZ_SERVICE, "/"),
                    DBUS_OM_IFACE
                )
                
                devices_found = []
                for path, interfaces in manager.GetManagedObjects().items():
                    if DEVICE_INTERFACE in interfaces:
                        device = interfaces[DEVICE_INTERFACE]
                        if device.get('Connected'):
                            name = device.get('Name', 'Unknown')
                            address = device.get('Address', 'N/A')
                            rssi = device.get('RSSI', 0)
                            devices_found.append((name, address, rssi))
                
                if devices_found and devices_found != self.discovered_devices:
                    print(f"\n[{time.strftime('%H:%M:%S')}] Gateway received from device:")
                    for name, address, rssi in devices_found:
                        print(f"  Device: {name} ({address}) - Signal: {rssi} dBm")
                    self.discovered_devices = devices_found
                
                time.sleep(5)
                
            except Exception as e:
                print(f"⚠ Monitor error (continuing): {e}")
                time.sleep(5)


class BLESimulator:
    """Orchestrate peripheral and gateway together"""
    
    def __init__(self, config):
        self.config = config
        self.device_name = config.get('device_name', 'BLE Device')
        self.service_uuid = config.get('service_uuid', '180D')
        self.data = config.get('data', {})
        self.adapter = config.get('adapter', 'hci0')
        
        # Parse data string if needed
        if isinstance(self.data, str):
            self.data = self._parse_data(self.data)
        
        self.peripheral = None
        self.gateway = None
        self.threads = []
    
    @staticmethod
    def _parse_data(data_str):
        """Parse 'key:value,key:value' format"""
        result = {}
        for item in data_str.split(','):
            if ':' in item:
                k, v = item.split(':', 1)
                result[k.strip()] = v.strip()
        return result
    
    def run(self):
        """Start both peripheral and gateway"""
        print(f"\n{'='*70}")
        print(f"BLE Device + Gateway Simulator")
        print(f"{'='*70}")
        print(f"Device Name:     {self.device_name}")
        print(f"Service UUID:    {self.service_uuid}")
        print(f"Adapter:         {self.adapter}")
        print(f"Data:            {self.data}")
        print(f"{'='*70}\n")
        
        # Create peripheral and gateway
        self.peripheral = BLEPeripheral(
            self.device_name,
            self.service_uuid,
            self.data,
            self.adapter
        )
        
        self.gateway = BLEGateway(self.adapter)
        
        # Setup both
        if not self.peripheral.setup():
            return False
        if not self.gateway.setup():
            return False
        
        # Start advertising
        if not self.peripheral.advertise():
            return False
        if not self.gateway.scan_devices():
            return False
        
        # Run both in threads
        print("✓ Starting BLE peripheral and gateway...\n")
        
        p_thread = threading.Thread(target=self.peripheral.broadcast_data, daemon=True)
        g_thread = threading.Thread(target=self.gateway.monitor_devices, daemon=True)
        
        p_thread.start()
        g_thread.start()
        
        self.threads = [p_thread, g_thread]
        
        try:
            # Keep main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n✓ Shutting down...")
            self.peripheral.running = False
            self.gateway.running = False
            
            # Stop discovery
            try:
                adapter = dbus.Interface(
                    self.bus.get_object(BLUEZ_SERVICE, self.gateway.adapter_path),
                    ADAPTER_INTERFACE
                )
                adapter.StopDiscovery()
            except:
                pass
            
            for t in self.threads:
                t.join(timeout=1)
            
            return True
    
    @property
    def bus(self):
        return self.gateway.bus


def load_config(config_file):
    """Load JSON configuration"""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"✗ Config file not found: {config_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='BLE Device + Gateway Simulator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  # Medical scenario
  python3 ble-device-gateway-simulator.py \\
    --device-name "Heart Rate Monitor" \\
    --service 180D \\
    --data "HR:72,SpO2:98,BP:120/80"

  # Sensor scenario
  python3 ble-device-gateway-simulator.py \\
    --device-name "Temperature Sensor" \\
    --service 181A \\
    --data "Temp:22.5,Humidity:65"

  # From config file
  python3 ble-device-gateway-simulator.py --config scenario.json
        """
    )
    
    parser.add_argument('--config', help='JSON config file')
    parser.add_argument('--device-name', help='BLE device name')
    parser.add_argument('--adapter', default='hci0', help='Adapter (default: hci0)')
    parser.add_argument('--service', dest='service_uuid', help='Service UUID')
    parser.add_argument('--data', help='Data (comma-separated key:value)')
    
    args = parser.parse_args()
    
    # Load or build config
    if args.config:
        config = load_config(args.config)
    else:
        config = {}
        if args.device_name:
            config['device_name'] = args.device_name
        if args.adapter:
            config['adapter'] = args.adapter
        if args.service_uuid:
            config['service_uuid'] = args.service_uuid
        if args.data:
            config['data'] = args.data
    
    if not config.get('device_name'):
        parser.print_help()
        sys.exit(1)
    
    # Run simulator
    simulator = BLESimulator(config)
    
    try:
        success = simulator.run()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()