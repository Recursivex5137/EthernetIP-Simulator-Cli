"""Service for managing server configuration with validation"""

import re
from typing import Tuple
from ..database.config_repository import ConfigRepository


class ConfigService:
    """Business logic for server configuration management"""

    # IP validation pattern: xxx.xxx.xxx.xxx
    IP_PATTERN = re.compile(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$')

    # Port validation range (avoid privileged ports)
    MIN_PORT = 1024
    MAX_PORT = 65535

    def __init__(self, config_repository: ConfigRepository):
        self.repository = config_repository
        self._cached_address: str | None = None
        self._cached_port: int | None = None

    def get_server_address(self) -> str:
        """Get configured server IP address"""
        if self._cached_address is None:
            self._cached_address = self.repository.get_server_address()
        return self._cached_address

    def get_server_port(self) -> int:
        """Get configured server port"""
        if self._cached_port is None:
            self._cached_port = self.repository.get_server_port()
        return self._cached_port

    def set_server_config(self, address: str, port: int) -> Tuple[bool, str]:
        """
        Set server configuration with validation.

        Returns:
            Tuple of (success: bool, error_message: str)
        """
        # Validate IP address
        ip_valid, ip_error = self.validate_ip(address)
        if not ip_valid:
            return False, ip_error

        # Validate port
        port_valid, port_error = self.validate_port(port)
        if not port_valid:
            return False, port_error

        # Save configuration
        try:
            self.repository.set_server_address(address)
            self.repository.set_server_port(port)
            self._cached_address = address
            self._cached_port = port
            return True, "Configuration saved successfully"
        except Exception as e:
            return False, f"Failed to save configuration: {str(e)}"

    def validate_ip(self, ip: str) -> Tuple[bool, str]:
        """
        Validate IP address format and range.

        Returns:
            Tuple of (is_valid: bool, error_message: str)
        """
        if not ip or not ip.strip():
            return False, "IP address cannot be empty"

        ip = ip.strip()

        # Check format
        match = self.IP_PATTERN.match(ip)
        if not match:
            return False, "Invalid IP format. Use xxx.xxx.xxx.xxx (e.g., 192.168.1.100)"

        # Check each octet is in valid range (0-255)
        try:
            octets = [int(octet) for octet in match.groups()]
            for octet in octets:
                if octet < 0 or octet > 255:
                    return False, "Each IP octet must be between 0 and 255"
        except ValueError:
            return False, "Invalid IP address format"

        return True, ""

    def validate_port(self, port: int) -> Tuple[bool, str]:
        """
        Validate port number range.

        Returns:
            Tuple of (is_valid: bool, error_message: str)
        """
        try:
            port_num = int(port)

            if port_num < self.MIN_PORT:
                return False, f"Port must be at least {self.MIN_PORT} (avoiding privileged ports)"

            if port_num > self.MAX_PORT:
                return False, f"Port must be {self.MAX_PORT} or less"

            return True, ""

        except (ValueError, TypeError):
            return False, "Port must be a valid number"
