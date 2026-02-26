"""Database repository for server configuration operations"""

from typing import Optional
from .db_manager import DBManager


class ConfigRepository:
    """Database operations for server configuration"""

    def __init__(self, db_manager: DBManager,
                 default_address: str = '0.0.0.0',
                 default_port: int = 44818):
        self.db = db_manager
        self.default_address = default_address
        self.default_port = default_port

    def get_config(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve configuration value by key"""
        with self.db.get_cursor() as cursor:
            cursor.execute('SELECT value FROM server_config WHERE key = ?', (key,))
            row = cursor.fetchone()
        return row['value'] if row else default

    def set_config(self, key: str, value: str) -> None:
        """Set configuration value (insert or update)"""
        with self.db.get_cursor() as cursor:
            cursor.execute('''
                INSERT INTO server_config (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            ''', (key, value))

    def get_server_address(self) -> str:
        """Get server IP address from configuration"""
        return self.get_config('server_address', self.default_address)

    def get_server_port(self) -> int:
        """Get server port from configuration"""
        port_str = self.get_config('server_port', str(self.default_port))
        try:
            return int(port_str)
        except (ValueError, TypeError):
            return self.default_port

    def set_server_address(self, address: str) -> None:
        """Set server IP address in configuration"""
        self.set_config('server_address', address)

    def set_server_port(self, port: int) -> None:
        """Set server port in configuration"""
        self.set_config('server_port', str(port))
