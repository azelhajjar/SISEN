#!/bin/bash
# alfa-driver.sh
# Installs RTL8812AU driver for Alfa AWUS036ACH on Kali Linux
# Author: Dr Ayman El Hajjar

set -euo pipefail

echo "[i] Installing RTL8812AU driver for Alfa adapter..."

sudo apt update
sudo apt install -y dkms git build-essential libelf-dev "linux-headers-$(uname -r)"

if [ ! -d "/opt/rtl8812au" ]; then
  echo "[i] Cloning driver source..."
  sudo git clone https://github.com/aircrack-ng/rtl8812au.git /opt/rtl8812au
fi

cd /opt/rtl8812au

if ! dkms status | grep -q "8812au/5.6.4.2"; then
  echo "[i] Adding driver to DKMS..."
  sudo dkms add .
fi

echo "[i] Building and installing driver..."
sudo dkms build 8812au/5.6.4.2
sudo dkms install 8812au/5.6.4.2

echo "[✓] RTL8812AU driver installed successfully."

echo "[i] Loading module..."
sudo modprobe 8812au
