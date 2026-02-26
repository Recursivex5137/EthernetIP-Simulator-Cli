"""EthernetIP server implementation using cpppo"""

import threading
import logging
from typing import Optional, Tuple
from ..models.data_types import DataType

# Logix-compatible STRING UDT type definition for cpppo STRUCT_typed.
# LabVIEW expects CIP type 0x02A0 (STRUCT) with structure_handle 0x0FCE.
# Format: 4-byte DINT .LEN + 82-byte SINT[82] .DATA + 2 bytes padding = 88 bytes.
LOGIX_STRING_UDT_TYPE = {
    "name": "STRING",
    "data_type": {
        "name": "STRING",
        "template": {"structure_handle": 0x0FCE, "structure_size": 88},
        "attributes": ["LEN", "DATA"],
        "internal_tags": {
            "LEN":  {"offset": 0, "data_type": "DINT", "tag_type": "atomic"},
            "DATA": {"offset": 4, "data_type": "SINT", "array": 82, "tag_type": "atomic"},
        },
    },
    "dimensions": [1],
}


class EthernetIPServer:
    """cpppo-based EthernetIP server wrapper"""

    def __init__(self, tag_provider, address='0.0.0.0', port=44818, udt_service=None):
        self.tag_provider = tag_provider
        self.address = address
        self.port = port
        self.udt_service = udt_service
        self.server_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.logger = logging.getLogger(__name__)
        self._stop_event = threading.Event()
        self._cpppo_tags = None
        self._cpppo_ready = threading.Event()
        self._tags_lock = threading.Lock()
        self._server_control = None
        self._string_tag_names: set = set()
        self._udt_tag_names: set = set()
        self._udt_flattener = None
        if udt_service:
            from .udt_flattener import UDTFlattener
            self._udt_flattener = UDTFlattener(udt_service)
        self._last_error: Optional[str] = None
        self._error_code: Optional[int] = None

    def _kill_port_holder(self):
        """Kill zombie processes holding our port (Windows only).

        After an unclean exit the previous Python process may still own
        the socket.  Use netstat to find its PID and taskkill to remove it.
        """
        import sys
        if sys.platform != 'win32':
            return

        import os
        import subprocess

        my_pid = os.getpid()
        try:
            result = subprocess.run(
                ['netstat', '-ano', '-p', 'TCP'],
                capture_output=True, text=True, timeout=5,
            )
            for line in result.stdout.splitlines():
                # Match lines like "  TCP  0.0.0.0:44818  ... LISTENING  12345"
                parts = line.split()
                if len(parts) < 5:
                    continue
                local_addr = parts[1]
                if not local_addr.endswith(f':{self.port}'):
                    continue
                try:
                    pid = int(parts[-1])
                except ValueError:
                    continue
                if pid == my_pid or pid == 0:
                    continue
                self.logger.warning("Killing zombie process PID %d holding port %d", pid, self.port)
                subprocess.run(
                    ['taskkill', '/F', '/PID', str(pid)],
                    capture_output=True, timeout=5,
                )
        except Exception as e:
            self.logger.debug("Could not check/kill port holder: %s", e)

    def _is_port_available(self) -> bool:
        """Check if the port is available for binding.

        On Windows, SO_REUSEADDR lets bind() succeed even when another
        process is actively listening, masking the real conflict.  Use a
        connect-based probe instead: if we can connect, something is
        listening and the port is NOT available.
        """
        import socket
        import sys

        if sys.platform == 'win32':
            # Connect-based check — immune to SO_REUSEADDR false positives
            try:
                probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                probe.settimeout(1)
                target = '127.0.0.1' if self.address == '0.0.0.0' else self.address
                probe.connect((target, self.port))
                probe.close()
                # Connection succeeded → something is listening
                return False
            except (ConnectionRefusedError, OSError, socket.timeout):
                # Nothing listening → port is free
                return True
        else:
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                test_socket.bind((self.address, self.port))
                test_socket.close()
                return True
            except OSError as e:
                self.logger.debug("Port %d not available: %s", self.port, e)
                return False

    def start(self):
        """Start the EthernetIP server in background thread"""
        if self.is_running:
            self.logger.warning("Server is already running")
            return

        # Clear any previous errors
        self.clear_error()

        # Proactively kill any zombie process holding our port from a prior crash
        self._kill_port_holder()

        self._stop_event.clear()
        self._cpppo_ready.clear()
        self._server_control = None
        self.is_running = True
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        self.logger.info(f"EthernetIP server started on {self.address}:{self.port}")

    def _wait_for_port_release(self, timeout=5.0):
        """Poll until the server port is free or timeout elapses."""
        import socket
        import time

        # Nudge lingering sockets with a connect probe
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            probe.settimeout(0.5)
            target = '127.0.0.1' if self.address == '0.0.0.0' else self.address
            probe.connect((target, self.port))
            probe.close()
        except (ConnectionRefusedError, OSError, socket.timeout):
            pass

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._is_port_available():
                return True
            time.sleep(0.25)

        self.logger.warning("Port %d still not available after %.1fs", self.port, timeout)
        return False

    def _force_cleanup_threads(self):
        """Force-kill hung cpppo client-handler threads so their sockets are released."""
        import ctypes

        client_threads = [t for t in threading.enumerate()
                         if t.daemon and t != threading.current_thread() and t.is_alive()
                         and t != self.server_thread]

        if not client_threads:
            return

        self.logger.warning("Force-killing %d hung client threads", len(client_threads))

        for thread in client_threads:
            try:
                # Inject SystemExit into the thread to force it to unwind
                # and release its socket resources
                ctypes.pythonapi.PyThreadState_SetAsyncExc(
                    ctypes.c_ulong(thread.ident),
                    ctypes.py_object(SystemExit),
                )
            except Exception as e:
                self.logger.debug("Could not kill thread %s: %s", thread.name, e)

        # Give threads a moment to unwind
        for thread in client_threads:
            thread.join(timeout=1.0)
            if thread.is_alive():
                self.logger.warning("Thread %s still alive after force-kill", thread.name)

    def stop(self):
        """Stop the EthernetIP server gracefully"""
        if not self.is_running:
            self.logger.warning("Server is not running")
            return

        try:
            self.logger.info("Stopping EthernetIP server...")

            # Step 1: Signal stop event (triggers KeyboardInterrupt in idle_sync)
            self._stop_event.set()

            # Step 2: Signal cpppo to shut down via its control dict (if available)
            if self._server_control is not None:
                try:
                    self._server_control['done'] = True
                    self.logger.debug("Set control['done'] = True for graceful shutdown")
                except Exception as e:
                    self.logger.warning(f"Could not set control['done']: {e}")

            # Step 3: Give server_main a moment to start its shutdown
            if self.server_thread:
                self.server_thread.join(timeout=2)

            # Step 4: Kill lingering cpppo sub-threads (e.g. UDP handler)
            # that keep server_main stuck in its join loop.  Once these are
            # dead, server_main can finish closing tcp_sock / udp_sock.
            self._force_cleanup_threads()

            # Step 5: Now wait for the server thread itself to finish
            # (it should exit quickly once sub-threads are dead).
            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join(timeout=5)
                if self.server_thread.is_alive():
                    self.logger.warning("Server thread still alive after cleanup")

            self.server_thread = None

            # Step 6: Clean up state
            self.is_running = False
            with self._tags_lock:
                self._cpppo_tags = None
            self._cpppo_ready.clear()
            self._string_tag_names.clear()
            self._udt_tag_names.clear()
            self._server_control = None

            # Step 7: Force GC to close any lingering socket objects,
            # then wait for the OS to fully release the port.
            import gc
            gc.collect()
            self._wait_for_port_release(timeout=5.0)

            self.logger.info("Server stopped successfully")

        except Exception as e:
            self.logger.error(f"Error stopping server: {e}", exc_info=True)
            # Still clean up state even if error occurred
            self.is_running = False
            self._server_control = None
            raise

    @staticmethod
    def _str_to_string_record(text, parser_instance):
        """Convert a Python str to a cpppo STRUCT_typed dotdict record for Logix STRING."""
        from cpppo.dotdict import dotdict
        if not isinstance(text, str):
            text = str(text) if text is not None else ''
        encoded = text.encode('iso-8859-1', errors='replace')[:82]
        record = dotdict(
            LEN=len(encoded),
            DATA=list(encoded) + [0] * (82 - len(encoded)),
        )
        # Pre-create nested data.input path; STRUCT_typed.produce() does
        # value.data.input = ... which GETs .data first (AttributeError if missing)
        record['data.input'] = b''
        parser_instance.produce(record)
        return record

    @staticmethod
    def _string_record_to_str(record):
        """Convert a cpppo STRUCT_typed dotdict record back to a Python str."""
        try:
            length = int(record.LEN)
            data = record.DATA
            length = max(0, min(length, 82))
            return ''.join(chr(c & 0xFF) for c in data[:length])
        except Exception:
            return ''

    def _run_server(self):
        """Internal server loop using cpppo"""
        try:
            from cpppo.server.enip.main import main as enip_main, tags as cpppo_tags_global

            tags = self.tag_provider.get_all_tags_for_server()
            self.logger.info(f"Starting cpppo server with {len(tags)} tags")

            # Build type map dynamically from DataType enum
            type_map = {}
            for dt in DataType:
                if dt != DataType.UDT:
                    type_map[dt.cip_code] = dt.type_name

            # Separate STRING and UDT tags from regular tags
            tag_args = []
            string_tags_info = {}
            udt_tags_info = {}
            for tag_name, tag_info in tags.items():
                cip_code = tag_info.get('type', 196)
                if cip_code == DataType.STRING.cip_code:
                    string_tags_info[tag_name] = tag_info
                    continue
                if cip_code == DataType.UDT.cip_code:
                    udt_tags_info[tag_name] = tag_info
                    continue
                type_name = type_map.get(cip_code, 'DINT')
                if 'elements' in tag_info and tag_info['elements'] > 1:
                    tag_args.append(f'{tag_name}={type_name}[{tag_info["elements"]}]')
                else:
                    tag_args.append(f'{tag_name}={type_name}')

            # UDT tags are registered as STRUCT_typed in idle_sync (not on command line)

            init_done = [False]

            def idle_sync():
                # Check if stop was requested - raise KeyboardInterrupt to
                # trigger cpppo's clean shutdown and release the port
                if self._stop_event.is_set():
                    raise KeyboardInterrupt()

                if not init_done[0]:
                    init_done[0] = True
                    from cpppo.server.enip import udt, device as cpppo_device
                    from cpppo.dotdict import dotdict as cpppo_dotdict

                    # Capture cpppo's server control dict so stop() can signal
                    # control['done'] = True directly for a clean socket release.
                    try:
                        from cpppo.server.enip.main import srv_ctl as _srv_ctl
                        if 'control' in _srv_ctl:
                            self._server_control = _srv_ctl['control']
                    except Exception:
                        pass

                    with self._tags_lock:
                        self._cpppo_tags = cpppo_tags_global

                        # Register STRING tags as STRUCT_typed for LabVIEW compatibility
                        if string_tags_info:
                            type_cls = lambda: udt.STRUCT_typed(
                                data_type=LOGIX_STRING_UDT_TYPE
                            )
                            string_parser = type_cls()
                            for sname, sinfo in string_tags_info.items():
                                initial_str = sinfo.get('data', '')
                                if not isinstance(initial_str, str):
                                    initial_str = str(initial_str) if initial_str is not None else ''
                                record = self._str_to_string_record(initial_str, string_parser)
                                attr = cpppo_device.Attribute(
                                    name=sname,
                                    type_cls=type_cls,
                                    default=[record],
                                )
                                tag_entry = cpppo_dotdict()
                                tag_entry.attribute = attr
                                tag_entry.path = None
                                tag_entry.error = 0x00
                                dict.__setitem__(cpppo_tags_global, sname, tag_entry)
                                self._string_tag_names.add(sname)
                                self.logger.info(f"Registered STRING tag '{sname}' as STRUCT_typed")

                        # Register UDT tags as STRUCT_typed for CIP member-level access
                        if udt_tags_info and self._udt_flattener:
                            for udt_name, udt_info in udt_tags_info.items():
                                udt_type_id = udt_info.get('udt_type_id')
                                if not udt_type_id:
                                    continue
                                udt_def = self.udt_service.get_udt_by_id(udt_type_id)
                                if not udt_def or not udt_def.members:
                                    continue
                                tag = self.tag_provider.tag_service.get_tag_by_name(udt_name)
                                if not tag:
                                    continue

                                # Determine array size
                                if tag.is_array and isinstance(tag.value, list):
                                    array_size = len(tag.value)
                                else:
                                    array_size = 1

                                # Build cpppo type definition (like LOGIX_STRING_UDT_TYPE)
                                type_def = self._udt_flattener.build_cpppo_udt_type(udt_def, array_size)
                                udt_type_cls = lambda td=type_def: udt.STRUCT_typed(data_type=td)
                                udt_parser = udt_type_cls()

                                # Create initial records from DB values
                                records = []
                                if tag.is_array and isinstance(tag.value, list):
                                    for inst in tag.value:
                                        d = inst if isinstance(inst, dict) else {}
                                        records.append(self._udt_flattener.dict_to_record(udt_def, d, udt_parser))
                                else:
                                    d = tag.value if isinstance(tag.value, dict) else {}
                                    records.append(self._udt_flattener.dict_to_record(udt_def, d, udt_parser))

                                udt_attr = cpppo_device.Attribute(
                                    name=udt_name,
                                    type_cls=udt_type_cls,
                                    default=records,
                                )
                                tag_entry = cpppo_dotdict()
                                tag_entry.attribute = udt_attr
                                tag_entry.path = None
                                tag_entry.error = 0x00
                                dict.__setitem__(cpppo_tags_global, udt_name, tag_entry)
                                self._udt_tag_names.add(udt_name)
                                self.logger.info("Registered UDT tag '%s' as STRUCT_typed (%s[%d])",
                                                 udt_name, udt_def.name, array_size)

                        # Write initial values for non-STRUCT tags
                        for our_tag in self.tag_provider.tag_service.get_all_tags():
                            if our_tag.name in self._string_tag_names:
                                continue
                            if our_tag.name in self._udt_tag_names:
                                continue
                            self._write_to_cpppo_locked(our_tag.name, our_tag.value, our_tag.is_array)

                    self._cpppo_ready.set()
                    self.logger.info("Cpppo tags initialized with DB values")

            import time as _time

            max_bind_attempts = 3
            for attempt in range(max_bind_attempts):
                try:
                    enip_main(
                        argv=tag_args + ['--address', f'{self.address}:{self.port}'],
                        idle_service=idle_sync,
                    )
                    break  # Normal exit (e.g. KeyboardInterrupt caught inside cpppo)
                except KeyboardInterrupt:
                    break
                except OSError as e:
                    is_addr_in_use = getattr(e, 'errno', None) == 10048 or getattr(e, 'winerror', None) == 10048
                    if is_addr_in_use and attempt < max_bind_attempts - 1:
                        self.logger.warning(
                            "Port %d in use (attempt %d/%d), killing holder and retrying...",
                            self.port, attempt + 1, max_bind_attempts,
                        )
                        self._kill_port_holder()
                        _time.sleep(2)
                        continue
                    self._last_error = str(e)
                    self._error_code = e.errno if hasattr(e, 'errno') else None
                    self.logger.error(f"Server binding error: {e} (errno: {self._error_code})")
                    break
                except Exception as e:
                    self._last_error = str(e)
                    self._error_code = None
                    self.logger.error(f"Server error: {e}")
                    break

        except ImportError as e:
            self.logger.error(f"cpppo not installed: {e}")
        except Exception as e:
            self.logger.error(f"Error running server: {e}", exc_info=True)
        finally:
            # Always reset state when server thread exits
            self.is_running = False
            self._cpppo_ready.clear()
            self._server_control = None

    def _write_to_cpppo_locked(self, tag_name, value, is_array=False):
        """Write to cpppo storage (caller must hold _tags_lock)."""
        if not self._cpppo_tags or tag_name not in self._cpppo_tags:
            return
        attr = self._cpppo_tags[tag_name].attribute
        try:
            if tag_name in self._string_tag_names:
                text = str(value) if value is not None else ''
                record = self._str_to_string_record(text, attr.parser)
                attr[0:1] = [record]
            elif tag_name in self._udt_tag_names and self._udt_flattener:
                # Write UDT dict(s) as STRUCT_typed records
                tag = self.tag_provider.tag_service.get_tag_by_name(tag_name)
                if tag:
                    udt_def = self._udt_flattener._get_udt_def(tag)
                    if udt_def:
                        if tag.is_array and isinstance(value, list):
                            records = []
                            for inst in value:
                                d = inst if isinstance(inst, dict) else {}
                                records.append(self._udt_flattener.dict_to_record(udt_def, d, attr.parser))
                            attr[0:len(records)] = records
                        elif isinstance(value, dict):
                            record = self._udt_flattener.dict_to_record(udt_def, value, attr.parser)
                            attr[0:1] = [record]
            elif is_array and isinstance(value, list):
                attr[0:len(value)] = value
            else:
                attr[0] = value
        except Exception as e:
            self.logger.error(f"Failed to write {tag_name} to cpppo: {e}")

    def _write_to_cpppo(self, tag_name, value, is_array=False):
        """Write a value directly to cpppo's internal tag storage (thread-safe)"""
        with self._tags_lock:
            self._write_to_cpppo_locked(tag_name, value, is_array)

    def read_tag_value(self, tag_name):
        """Read current value from cpppo's live tag storage"""
        if not self._cpppo_ready.is_set():
            return None
        with self._tags_lock:
            if not self._cpppo_tags or tag_name not in self._cpppo_tags:
                return None
            attr = self._cpppo_tags[tag_name].attribute
            try:
                if tag_name in self._string_tag_names:
                    return self._string_record_to_str(attr[0])
                if tag_name in self._udt_tag_names and self._udt_flattener:
                    tag = self.tag_provider.tag_service.get_tag_by_name(tag_name)
                    if tag:
                        udt_def = self._udt_flattener._get_udt_def(tag)
                        if udt_def:
                            if tag.is_array and isinstance(tag.value, list):
                                return [self._udt_flattener.record_to_dict(udt_def, attr[i])
                                        for i in range(len(tag.value))]
                            else:
                                return self._udt_flattener.record_to_dict(udt_def, attr[0])
                    return None
                tag = self.tag_provider.tag_service.get_tag_by_name(tag_name)
                if tag and tag.is_array:
                    return list(attr[0:len(attr)])
                return attr[0]
            except Exception as e:
                self.logger.error("Failed to read %s: %s", tag_name, e)
                return None

    def read_all_tag_values(self):
        """Read all live tag values in a single lock acquisition.

        Returns dict {tag_name: value} for all tags, or empty dict if not ready.
        Used by the UI refresh timer to avoid per-row lock acquisitions.
        """
        if not self._cpppo_ready.is_set():
            return {}
        result = {}
        # Get known tag names from tag_service (avoids iterating cpppo dotdict sub-keys)
        all_tags = self.tag_provider.tag_service.get_all_tags()
        if not self._tags_lock.acquire(timeout=0.05):
            return {}  # Lock contended — skip this cycle, UI stays responsive
        try:
            if not self._cpppo_tags:
                return {}
            for tag in all_tags:
                tag_name = tag.name
                if tag_name not in self._cpppo_tags:
                    continue
                try:
                    attr = self._cpppo_tags[tag_name].attribute
                    if tag_name in self._string_tag_names:
                        result[tag_name] = self._string_record_to_str(attr[0])
                    elif tag_name in self._udt_tag_names and self._udt_flattener:
                        udt_def = self._udt_flattener._get_udt_def(tag)
                        if udt_def:
                            if tag.is_array and isinstance(tag.value, list):
                                result[tag_name] = [self._udt_flattener.record_to_dict(udt_def, attr[i])
                                                    for i in range(len(tag.value))]
                            else:
                                result[tag_name] = self._udt_flattener.record_to_dict(udt_def, attr[0])
                    elif tag.is_array:
                        result[tag_name] = list(attr[0:len(attr)])
                    else:
                        result[tag_name] = attr[0]
                except Exception as e:
                    self.logger.error("Failed to read %s: %s", tag_name, e)
        finally:
            self._tags_lock.release()
        return result

    def write_tag_value(self, tag_name, value, is_array=False):
        """Write a value to cpppo's live tag storage"""
        if not self._cpppo_ready.is_set():
            return
        self._write_to_cpppo(tag_name, value, is_array)

    def snapshot_live_values(self):
        """Read all live values from cpppo and persist them to DB/cache.

        Must be called BEFORE stop() to preserve external writes.
        """
        if not self._cpppo_ready.is_set():
            return 0

        # Phase 1: Read all values while holding the lock
        values_to_persist = {}
        all_tags = self.tag_provider.tag_service.get_all_tags()
        with self._tags_lock:
            if not self._cpppo_tags:
                return 0
            for tag in all_tags:
                tag_name = tag.name
                if tag_name not in self._cpppo_tags:
                    continue
                try:
                    attr = self._cpppo_tags[tag_name].attribute
                    if tag_name in self._string_tag_names:
                        values_to_persist[tag_name] = self._string_record_to_str(attr[0])
                    elif tag_name in self._udt_tag_names and self._udt_flattener:
                        udt_def = self._udt_flattener._get_udt_def(tag)
                        if udt_def:
                            if tag.is_array and isinstance(tag.value, list):
                                values_to_persist[tag_name] = [
                                    self._udt_flattener.record_to_dict(udt_def, attr[i])
                                    for i in range(len(tag.value))
                                ]
                            else:
                                values_to_persist[tag_name] = self._udt_flattener.record_to_dict(udt_def, attr[0])
                    elif tag.is_array:
                        values_to_persist[tag_name] = list(attr[0:len(attr)])
                    else:
                        values_to_persist[tag_name] = attr[0]
                except Exception as e:
                    self.logger.error("Failed to snapshot %s: %s", tag_name, e)

        # Phase 2: Persist to DB/cache outside the lock
        count = 0
        for tag_name, value in values_to_persist.items():
            try:
                self.tag_provider.tag_service.update_tag_value(tag_name, value)
                count += 1
            except Exception as e:
                self.logger.error("Failed to persist %s: %s", tag_name, e)

        self.logger.info("Snapshotted %d live tag values", count)
        return count

    def get_last_error(self) -> Tuple[Optional[str], Optional[int]]:
        """
        Get the last error that occurred during server startup.

        Returns:
            Tuple of (error_message, errno_code) or (None, None) if no error
        """
        return (self._last_error, self._error_code)

    def clear_error(self):
        """Clear the last error state"""
        self._last_error = None
        self._error_code = None

    @property
    def tags_ready(self):
        return self._cpppo_ready.is_set()

    @property
    def status(self) -> str:
        return "Running" if self.is_running else "Stopped"

    def get_connection_info(self) -> dict:
        return {
            'address': self.address,
            'port': self.port,
            'status': self.status,
            'is_running': self.is_running
        }
