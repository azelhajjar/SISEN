#!/bin/bash
# setup-scenario-host.sh
#
# Host machine setup for the Automated Critical Infrastructure Scenario Generator.
#
# This script is SEPARATE from setup-kali-base.sh which serves the existing
# wireless labs repository. Do not merge them — they serve different purposes
# and run on different environments.
#
# This script installs and configures:
#   - KVM/QEMU and libvirt        (VM hypervisor layer)
#   - Vagrant + vagrant-libvirt   (VM provisioning)
#   - mac80211_hwsim              (virtual wireless interfaces)
#   - Python 3 + project libs     (orchestrator and traffic generation)
#   - hostapd + dnsmasq           (AP layer — disabled at startup)
#   - Supporting network tools    (iw, tcpdump, wireshark, etc.)
#
# Requirements:
#   - Ubuntu 22.04 LTS or later (bare metal — NOT inside a VM)
#   - KVM virtualisation enabled in BIOS (Intel VT-x or AMD-V)
#   - One physical wireless adaptor connected
#
# Usage:
#   sudo bash setup-scenario-host.sh
#
# After running this script, log out and back in before continuing.
# This is required for group membership changes (libvirt, kvm) to take effect.

set -euo pipefail

# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────

require_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "[!] Please run as root (use: sudo $0)"
    exit 1
  fi
}

print_section() {
  echo ""
  echo "════════════════════════════════════════════════════════"
  echo "  $1"
  echo "════════════════════════════════════════════════════════"
}

check_not_vm() {
  print_section "Checking Hardware Environment"
  if systemd-detect-virt --quiet 2>/dev/null; then
    echo "[!] This script must run on bare metal, not inside a VM."
    echo "    Virtualisation detected: $(systemd-detect-virt)"
    echo "    mac80211_hwsim and wireless interface passthrough require bare metal."
    exit 1
  fi
  echo "[✓] Running on bare metal."
}

check_kvm_support() {
  print_section "Checking KVM Support"
  if ! grep -qE '(vmx|svm)' /proc/cpuinfo; then
    echo "[!] KVM virtualisation not detected in CPU flags."
    echo "    Please enable Intel VT-x or AMD-V in your BIOS/UEFI and reboot."
    exit 1
  fi
  echo "[✓] KVM virtualisation supported by CPU."
}

check_wireless_adaptor() {
  print_section "Checking Physical Wireless Adaptor"
  if ! iw dev 2>/dev/null | grep -q Interface; then
    echo "[!] No wireless interface detected."
    echo "    Please connect a physical wireless adaptor before continuing."
    echo "    The AP (hostapd) requires a real wireless interface."
    exit 1
  fi
  WIRELESS_IFACE=$(iw dev | awk '/Interface/{print $2}' | head -n1)
  echo "[✓] Wireless interface detected: $WIRELESS_IFACE"
  echo "[i] This interface will be used for the AP (hostapd)."
  echo "[i] Set ap.interface: $WIRELESS_IFACE in your scenario config.yaml"
}

# ─────────────────────────────────────────
# Package Installation
# ─────────────────────────────────────────

install_base_tools() {
  print_section "Installing Base Network Tools"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends \
    hostapd \
    dnsmasq \
    iproute2 \
    iptables \
    iw \
    rfkill \
    net-tools \
    tcpdump \
    wireshark \
    ca-certificates \
    curl \
    wget \
    gnupg \
    lsb-release \
    software-properties-common
  echo "[✓] Base network tools installed."
}

install_kvm_libvirt() {
  print_section "Installing KVM, QEMU, and libvirt"
  apt-get install -y \
    qemu-kvm \
    libvirt-daemon-system \
    libvirt-clients \
    bridge-utils \
    virtinst \
    cpu-checker
  echo "[✓] KVM/QEMU and libvirt installed."

  # Verify KVM device is accessible
  if [ ! -e /dev/kvm ]; then
    echo "[!] /dev/kvm not found after installing KVM."
    echo "    Check that virtualisation is enabled in BIOS and reboot if needed."
    exit 1
  fi
  echo "[✓] /dev/kvm is accessible."
}

add_user_to_groups() {
  print_section "Adding User to Required Groups"

  # Determine the real user (not root, even when running via sudo)
  REAL_USER="${SUDO_USER:-$USER}"

  if [ "$REAL_USER" = "root" ]; then
    echo "[!] Could not determine non-root user to add to groups."
    echo "    Please manually run:"
    echo "      sudo usermod -aG libvirt,kvm \$USER"
    return
  fi

  usermod -aG libvirt "$REAL_USER"
  usermod -aG kvm "$REAL_USER"
  echo "[✓] Added $REAL_USER to libvirt and kvm groups."
  echo "[i] You must log out and back in for group changes to take effect."
}

install_vagrant() {
  print_section "Installing Vagrant"

  if command -v vagrant &>/dev/null; then
    echo "[i] Vagrant already installed: $(vagrant --version)"
  else
    # Add HashiCorp GPG key and repository
    wget -O /tmp/hashicorp.gpg https://apt.releases.hashicorp.com/gpg
    gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg /tmp/hashicorp.gpg
    rm /tmp/hashicorp.gpg

    echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
https://apt.releases.hashicorp.com $(lsb_release -cs) main" \
      | tee /etc/apt/sources.list.d/hashicorp.list

    apt-get update
    apt-get install -y vagrant
    echo "[✓] Vagrant installed: $(vagrant --version)"
  fi

  # Install vagrant-libvirt plugin
  print_section "Installing vagrant-libvirt Plugin"
  apt-get install -y \
    libvirt-dev \
    ruby-dev \
    build-essential \
    libxml2-dev \
    zlib1g-dev

  REAL_USER="${SUDO_USER:-$USER}"
  if [ "$REAL_USER" != "root" ]; then
    sudo -u "$REAL_USER" vagrant plugin install vagrant-libvirt \
      || echo "[!] vagrant-libvirt install failed. Run manually: vagrant plugin install vagrant-libvirt"
  else
    vagrant plugin install vagrant-libvirt \
      || echo "[!] vagrant-libvirt install failed. Run manually after logging in as your user."
  fi
  echo "[✓] vagrant-libvirt plugin installed."
}

install_mac80211_hwsim() {
  print_section "Verifying mac80211_hwsim"

  # Install extra kernel modules if needed
  KERNEL_VERSION=$(uname -r)
  if ! modinfo mac80211_hwsim &>/dev/null; then
    echo "[i] mac80211_hwsim not found in current kernel modules."
    echo "[i] Installing linux-modules-extra for kernel $KERNEL_VERSION ..."
    apt-get install -y "linux-modules-extra-$KERNEL_VERSION"
  fi

  # Test load
  if modprobe mac80211_hwsim radios=2 2>/dev/null; then
    echo "[✓] mac80211_hwsim loaded successfully."
    # Unload after test
    rmmod mac80211_hwsim
    echo "[✓] mac80211_hwsim unloaded after test."
  else
    echo "[!] mac80211_hwsim failed to load."
    echo "    You may need to reboot and rerun this script."
    echo "    Or check: dmesg | grep hwsim"
  fi

  # Ensure module is available at boot (not auto-loaded — orchestrator loads it)
  echo "[i] mac80211_hwsim will be loaded by the orchestrator at scenario start."
  echo "[i] It will NOT be auto-loaded at boot — this is intentional."
}

install_python_dependencies() {
  print_section "Installing Python Dependencies"

  apt-get install -y \
    python3 \
    python3-pip \
    python3-venv

  # Install project Python libraries system-wide
  pip3 install --break-system-packages \
    pymodbus \
    pyyaml \
    paho-mqtt

  echo "[✓] Python and project libraries installed."
  echo "[i] Libraries installed: pymodbus, pyyaml, paho-mqtt"
}

# ─────────────────────────────────────────
# Service Configuration
# ─────────────────────────────────────────

disable_conflicting_services() {
  print_section "Disabling Auto-Start Services"

  # hostapd and dnsmasq are managed by AP scripts, not systemd
  systemctl disable hostapd 2>/dev/null || true
  systemctl disable dnsmasq 2>/dev/null || true
  systemctl stop hostapd 2>/dev/null || true
  systemctl stop dnsmasq 2>/dev/null || true

  # NetworkManager can interfere with hostapd — disable management of wireless iface
  if systemctl is-active --quiet NetworkManager; then
    echo "[i] NetworkManager is running."
    echo "[i] If NetworkManager interferes with the AP, add the wireless interface"
    echo "    to /etc/NetworkManager/conf.d/unmanaged.conf:"
    echo "      [keyfile]"
    echo "      unmanaged-devices=interface-name:wlan0"
  fi

  echo "[✓] hostapd and dnsmasq disabled from auto-start."
}

enable_libvirt_service() {
  print_section "Enabling libvirt Service"
  systemctl enable libvirtd
  systemctl start libvirtd
  echo "[✓] libvirtd enabled and started."
}

# ─────────────────────────────────────────
# Verification
# ─────────────────────────────────────────

verify_installation() {
  print_section "Verifying Installation"

  PASS=true

  check_tool() {
    if command -v "$1" &>/dev/null; then
      echo "[✓] $1 found: $(command -v $1)"
    else
      echo "[✗] $1 NOT found"
      PASS=false
    fi
  }

  check_tool python3
  check_tool vagrant
  check_tool virsh
  check_tool qemu-system-x86_64
  check_tool hostapd
  check_tool dnsmasq
  check_tool iw
  check_tool tcpdump
  check_tool wireshark

  # Check Python libraries
  for lib in pymodbus yaml paho; do
    if python3 -c "import $lib" 2>/dev/null; then
      echo "[✓] Python library available: $lib"
    else
      echo "[✗] Python library NOT found: $lib"
      PASS=false
    fi
  done

  # Check libvirt service
  if systemctl is-active --quiet libvirtd; then
    echo "[✓] libvirtd is running"
  else
    echo "[✗] libvirtd is NOT running"
    PASS=false
  fi

  # Check /dev/kvm
  if [ -e /dev/kvm ]; then
    echo "[✓] /dev/kvm exists"
  else
    echo "[✗] /dev/kvm NOT found"
    PASS=false
  fi

  # Check mac80211_hwsim
  if modinfo mac80211_hwsim &>/dev/null; then
    echo "[✓] mac80211_hwsim kernel module available"
  else
    echo "[✗] mac80211_hwsim NOT available"
    PASS=false
  fi

  echo ""
  if [ "$PASS" = true ]; then
    echo "[✓] All checks passed."
  else
    echo "[!] One or more checks failed. Review output above."
  fi
}

# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────

main() {
  require_root
  check_not_vm
  check_kvm_support
  check_wireless_adaptor

  install_base_tools
  install_kvm_libvirt
  add_user_to_groups
  install_vagrant
  install_mac80211_hwsim
  install_python_dependencies
  disable_conflicting_services
  enable_libvirt_service
  verify_installation

  print_section "Setup Complete"
  echo ""
  echo "  Next steps:"
  echo ""
  echo "  1. Log out and back in (required for libvirt/kvm group membership)"
  echo "  2. Verify Vagrant works:    vagrant --version"
  echo "  3. Verify libvirt works:    virsh list --all"
  echo "  4. Note your wireless interface name and set it in config.yaml (ap.interface)"
  echo "  5. Run SISEN:              python3 launch_sisen.py"
  echo ""
  echo "  Wireless interface detected during setup: $WIRELESS_IFACE"
  echo ""
  echo "[i] If you see a 'Relogin or restart required' message, log out or reboot before continuing."
}

main "$@"
