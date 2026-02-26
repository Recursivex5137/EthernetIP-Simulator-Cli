"""Provides tag data to EthernetIP server"""

from typing import Dict, Any
import logging
from ..models.data_types import DataType


class TagProvider:
    """Provides tag data to EthernetIP server"""

    def __init__(self, tag_service, udt_service=None):
        self.tag_service = tag_service
        self.udt_service = udt_service
        self.logger = logging.getLogger(__name__)

    def get_all_tags_for_server(self) -> Dict[str, Any]:
        """Convert internal tags to cpppo server format"""
        tags = self.tag_service.get_all_tags()
        server_tags = {}

        for tag in tags:
            try:
                # Convert our Tag model to cpppo's expected format
                # cpppo expects: {tag_name: {'type': cip_code, 'data': value}}
                server_tags[tag.name] = self._tag_to_cpppo_format(tag)
                self.logger.debug("Added tag %s to server", tag.name)
            except Exception as e:
                self.logger.error(f"Error converting tag {tag.name}: {e}")

        self.logger.info(f"Provided {len(server_tags)} tags to server")
        return server_tags

    def _tag_to_cpppo_format(self, tag) -> dict:
        """Convert Tag object to cpppo format"""
        cpppo_tag = {
            'type': tag.data_type.cip_code,
            'data': tag.value,
            'writable': True,
            'udt_type_id': tag.udt_type_id,
        }

        # UDT tags: compute flat SINT size from UDT definition
        if tag.data_type == DataType.UDT and self.udt_service and tag.udt_type_id:
            udt_def = self.udt_service.get_udt_by_id(tag.udt_type_id)
            if udt_def:
                instance_size = udt_def.size_bytes
                if tag.is_array and isinstance(tag.value, list):
                    cpppo_tag['flat_sint_size'] = instance_size * len(tag.value)
                else:
                    cpppo_tag['flat_sint_size'] = instance_size
                cpppo_tag['elements'] = cpppo_tag['flat_sint_size']
            return cpppo_tag

        # Handle arrays
        if tag.is_array:
            cpppo_tag['elements'] = len(tag.value) if isinstance(tag.value, list) else 0

        return cpppo_tag

    def update_tag_from_server(self, tag_name: str, new_value):
        """Called when external client writes to a tag"""
        try:
            success = self.tag_service.update_tag_value(tag_name, new_value)
            if success:
                self.logger.debug("Tag %s updated from external client", tag_name)
            else:
                self.logger.warning(f"Failed to update tag {tag_name}")
            return success
        except Exception as e:
            self.logger.error(f"Error updating tag {tag_name}: {e}")
            return False

    def get_tag_value(self, tag_name: str) -> Any:
        """Get current value of a tag"""
        tag = self.tag_service.get_tag_by_name(tag_name)
        if tag:
            return tag.value
        return None
