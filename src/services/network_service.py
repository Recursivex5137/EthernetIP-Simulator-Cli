"""Network interface detection and validation service"""

import socket
import logging
import time
from typing import List, Dict, Tuple, Optional


class NetworkService:
    """Service for detecting and validating network interfaces"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._interfaces_cache = None
        self._cache_time = 0.0
        self._cache_ttl = 30.0

    def get_available_interfaces(self) -> List[Dict[str, str]]:
        """
        Get list of available network interfaces with their IP addresses.
        Includes Ethernet, WiFi, VPN, and other network adapters.

        Returns:
            List of dicts with keys: 'ip', 'name', 'is_loopback'
            Always includes '0.0.0.0' as first entry
        """
        now = time.monotonic()
        if self._interfaces_cache is not None and (now - self._cache_time) < self._cache_ttl:
            return list(self._interfaces_cache)

        interfaces = []

        # Always add "bind to all interfaces" option first
        interfaces.append({
            'ip': '0.0.0.0',
            'name': 'All Interfaces (Recommended)',
            'is_loopback': False
        })

        try:
            # Get hostname
            hostname = socket.gethostname()

            # Get all IP addresses for this host
            # This returns (hostname, aliaslist, ipaddrlist)
            _, _, ip_list = socket.gethostbyname_ex(hostname)

            # Also try getaddrinfo to get more complete list
            try:
                addr_info = socket.getaddrinfo(hostname, None, socket.AF_INET)
                for info in addr_info:
                    ip = info[4][0]
                    if ip not in ip_list:
                        ip_list.append(ip)
            except Exception:
                pass

            # Remove duplicates while preserving order
            seen = set()
            unique_ips = []
            for ip in ip_list:
                if ip not in seen:
                    seen.add(ip)
                    unique_ips.append(ip)

            for ip in unique_ips:
                # Skip link-local addresses (169.254.x.x) initially
                if ip.startswith('169.254.'):
                    continue

                # Determine if loopback
                is_loopback = ip.startswith('127.')

                # Try to get a descriptive name for the interface
                interface_name = self._get_interface_name(ip, is_loopback)

                interfaces.append({
                    'ip': ip,
                    'name': interface_name,
                    'is_loopback': is_loopback
                })

            # Also explicitly add localhost if not already present
            if not any(iface['ip'] == '127.0.0.1' for iface in interfaces):
                interfaces.append({
                    'ip': '127.0.0.1',
                    'name': 'Loopback (localhost)',
                    'is_loopback': True
                })

            # If we only have 0.0.0.0 and localhost, add link-local as fallback
            if len(interfaces) <= 2:
                for ip in unique_ips:
                    if ip.startswith('169.254.') and not any(iface['ip'] == ip for iface in interfaces):
                        interfaces.append({
                            'ip': ip,
                            'name': 'Link-Local (Auto-configured)',
                            'is_loopback': False
                        })

        except Exception as e:
            self.logger.error(f"Error detecting network interfaces: {e}")

        self._interfaces_cache = interfaces
        self._cache_time = time.monotonic()
        return interfaces

    def _get_interface_name(self, ip: str, is_loopback: bool) -> str:
        """
        Get a descriptive name for an interface based on its IP.
        Attempts to identify WiFi, Ethernet, VPN, etc.

        Args:
            ip: IP address string
            is_loopback: Whether this is a loopback interface

        Returns:
            Descriptive name string
        """
        if is_loopback:
            return "Loopback (localhost)"

        # Try to categorize by IP range
        if ip.startswith('192.168.'):
            # Common WiFi and home network range
            return "WiFi / Ethernet (192.168.x.x)"
        elif ip.startswith('10.'):
            # Common corporate/VPN network range
            return "Corporate / VPN Network (10.x.x.x)"
        elif ip.startswith('172.'):
            # 172.16.0.0 - 172.31.255.255 is private
            try:
                second_octet = int(ip.split('.')[1])
                if 16 <= second_octet <= 31:
                    return "Private Network (172.16-31.x.x)"
                else:
                    return "Network Adapter"
            except (ValueError, IndexError):
                return "Network Adapter"
        elif ip.startswith('169.254.'):
            return "Auto-configured (No DHCP)"
        else:
            # Public IP or other
            return "Network Adapter (Public IP)"

    def validate_ip_available(self, ip: str) -> Tuple[bool, str]:
        """
        Validate that an IP address is available on a local network interface.

        Args:
            ip: IP address to validate

        Returns:
            Tuple of (is_valid, error_message)
            - (True, "") if IP is valid
            - (False, "error message") if IP is not available
        """
        # 0.0.0.0 is always valid (binds to all interfaces)
        if ip == '0.0.0.0':
            return (True, "")

        # Get all available IPs
        interfaces = self.get_available_interfaces()
        available_ips = [iface['ip'] for iface in interfaces]

        if ip in available_ips:
            return (True, "")
        else:
            return (False, f"IP address {ip} is not available on any network interface")

    def get_primary_interface(self) -> Optional[str]:
        """
        Get the primary (recommended) network interface IP.

        Returns:
            IP address of the primary interface, or '0.0.0.0' if none found
            Priority: First non-loopback, non-link-local IPv4 interface
        """
        interfaces = self.get_available_interfaces()

        # Filter out 0.0.0.0 and loopback
        candidates = [
            iface for iface in interfaces
            if iface['ip'] != '0.0.0.0' and not iface['is_loopback']
        ]

        # Prefer private network addresses over link-local
        for iface in candidates:
            ip = iface['ip']
            if not ip.startswith('169.254.'):
                return ip

        # Fall back to link-local if that's all we have
        if candidates:
            return candidates[0]['ip']

        # Last resort: bind to all interfaces
        return '0.0.0.0'
