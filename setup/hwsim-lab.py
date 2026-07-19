#!/usr/bin/env python3

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

LAB_DIR = Path("/tmp/hwsim-lab")
HOSTAPD_CONF = LAB_DIR / "hostapd.conf"
WPA_CONF = LAB_DIR / "open.conf"
HOSTAPD_LOG = LAB_DIR / "hostapd.log"
DNSMASQ_LOG = LAB_DIR / "dnsmasq.log"
WPA_LOG = LAB_DIR / "wpa_supplicant.log"

AP_IFACE = "wlan0"
CLIENT_IFACE = "wlan1"
SSID = "HWSIM-AP"
AP_IP = "192.168.50.1/24"
DHCP_RANGE = "192.168.50.10,192.168.50.100,12h"


def run(cmd, check=True):
    print(f"[cmd] {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, text=True)


def output(cmd):
    return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)


def require_root():
    if os.geteuid() != 0:
        print("[!] Please run with sudo:")
        print("    sudo python3 setup/hwsim-lab.py start")
        sys.exit(1)


def write_configs():
    LAB_DIR.mkdir(parents=True, exist_ok=True)

    HOSTAPD_CONF.write_text(f"""interface={AP_IFACE}
driver=nl80211

ssid={SSID}

hw_mode=g
channel=6

auth_algs=1
ignore_broadcast_ssid=0
""")

    WPA_CONF.write_text(f"""network={{
    ssid="{SSID}"
    key_mgmt=NONE
}}
""")


def pkill(name):
    subprocess.run(["pkill", "-f", name], check=False)


def stop():
    print("[*] Stopping hwsim lab processes...")
    pkill("wpa_supplicant.*wlan1")
    pkill("dnsmasq.*wlan0")
    pkill("hostapd.*/tmp/hwsim-lab/hostapd.conf")

    subprocess.run(["dhclient", "-r", CLIENT_IFACE], check=False)
    subprocess.run(["ip", "addr", "flush", "dev", CLIENT_IFACE], check=False)
    subprocess.run(["ip", "addr", "flush", "dev", AP_IFACE], check=False)

    print("[*] Removing mac80211_hwsim module...")
    subprocess.run(["modprobe", "-r", "mac80211_hwsim"], check=False)

    print("[✓] Stopped.")


def start():
    require_root()
    write_configs()

    print("[*] Cleaning previous lab state...")
    stop()

    print("[*] Loading mac80211_hwsim with 4 radios...")
    run(["modprobe", "mac80211_hwsim", "radios=4"])

    time.sleep(1)

    print("[*] Current wireless interfaces:")
    print(output(["iw", "dev"]))

    print("[*] Starting hostapd on wlan0...")
    hostapd_log = open(HOSTAPD_LOG, "w")
    subprocess.Popen(
        ["hostapd", str(HOSTAPD_CONF)],
        stdout=hostapd_log,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )

    time.sleep(2)

    print("[*] Assigning AP IP...")
    subprocess.run(["ip", "addr", "add", AP_IP, "dev", AP_IFACE], check=False)

    print("[*] Starting dnsmasq DHCP server...")
    dnsmasq_log = open(DNSMASQ_LOG, "w")
    subprocess.Popen(
        [
            "dnsmasq",
            f"--interface={AP_IFACE}",
            "--bind-interfaces",
            f"--dhcp-range={DHCP_RANGE}",
            "--no-daemon",
        ],
        stdout=dnsmasq_log,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )

    time.sleep(1)

    print("[*] Bringing client interface up...")
    run(["ip", "link", "set", CLIENT_IFACE, "up"])

    print("[*] Starting wpa_supplicant on wlan1...")
    wpa_log = open(WPA_LOG, "w")
    subprocess.Popen(
        ["wpa_supplicant", "-i", CLIENT_IFACE, "-c", str(WPA_CONF)],
        stdout=wpa_log,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )

    time.sleep(4)

    print("[*] Requesting DHCP lease on wlan1...")
    dhclient = subprocess.run(["dhclient", "-v", CLIENT_IFACE], text=True)

    print("[*] Final AP interface:")
    subprocess.run(["ip", "addr", "show", AP_IFACE], check=False)

    print("[*] Final client interface:")
    subprocess.run(["ip", "addr", "show", CLIENT_IFACE], check=False)

    print("[*] Client wireless link:")
    subprocess.run(["iw", "dev", CLIENT_IFACE, "link"], check=False)

    print("[✓] hwsim lab started.")
    print(f"[i] Logs written to: {LAB_DIR}")
    print(f"    hostapd:        {HOSTAPD_LOG}")
    print(f"    dnsmasq:        {DNSMASQ_LOG}")
    print(f"    wpa_supplicant: {WPA_LOG}")


def status():
    print("[*] Wireless interfaces:")
    subprocess.run(["iw", "dev"], check=False)

    print("\n[*] AP IP:")
    subprocess.run(["ip", "addr", "show", AP_IFACE], check=False)

    print("\n[*] Client IP:")
    subprocess.run(["ip", "addr", "show", CLIENT_IFACE], check=False)

    print("\n[*] Client link:")
    subprocess.run(["iw", "dev", CLIENT_IFACE, "link"], check=False)

    print("\n[*] Relevant processes:")
    subprocess.run(["pgrep", "-a", "hostapd|dnsmasq|wpa_supplicant"], check=False)


def main():
    parser = argparse.ArgumentParser(description="Start/stop Week 2 hwsim wireless lab")
    parser.add_argument("action", choices=["start", "stop", "status"])
    args = parser.parse_args()

    if args.action == "start":
        start()
    elif args.action == "stop":
        require_root()
        stop()
    elif args.action == "status":
        status()


if __name__ == "__main__":
    main()
