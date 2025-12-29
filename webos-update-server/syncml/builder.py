"""
SyncML Message Builder

Builds SyncML response messages for OMA Device Management.
"""
import xml.etree.ElementTree as ET
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from wbxml import WBXMLEncoder
import config


@dataclass
class StatusBuilder:
    """Build Status command"""
    cmd_id: str
    msg_ref: str
    cmd_ref: str
    cmd: str
    data: int  # Status code
    target_ref: Optional[str] = None
    source_ref: Optional[str] = None
    items: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ItemBuilder:
    """Build Item element"""
    target: Optional[str] = None
    source: Optional[str] = None
    data: Optional[str] = None
    meta: Dict[str, str] = field(default_factory=dict)


class SyncMLBuilder:
    """Build SyncML messages"""

    def __init__(self, server_id: str = None):
        self.server_id = server_id or config.SERVER_ID
        self.cmd_id_counter = 0

    def next_cmd_id(self) -> str:
        """Get next command ID"""
        self.cmd_id_counter += 1
        return str(self.cmd_id_counter)

    def reset_cmd_id(self):
        """Reset command ID counter"""
        self.cmd_id_counter = 0

    def build_response(
        self,
        session_id: str,
        msg_id: str,
        target: str,
        source: str = None,
        statuses: List[StatusBuilder] = None,
        commands: List[ET.Element] = None,
        is_final: bool = True
    ) -> ET.Element:
        """Build a complete SyncML response message"""
        self.reset_cmd_id()

        # Root element
        syncml = ET.Element('SyncML')
        syncml.set('xmlns', 'SYNCML:SYNCML1.2')

        # SyncHdr
        sync_hdr = self._build_header(session_id, msg_id, target, source)
        syncml.append(sync_hdr)

        # SyncBody
        sync_body = ET.SubElement(syncml, 'SyncBody')

        # Add statuses
        if statuses:
            for status in statuses:
                sync_body.append(self._build_status(status))

        # Add commands
        if commands:
            for cmd in commands:
                sync_body.append(cmd)

        # Final marker
        if is_final:
            ET.SubElement(sync_body, 'Final')

        return syncml

    def _build_header(
        self,
        session_id: str,
        msg_id: str,
        target: str,
        source: str = None
    ) -> ET.Element:
        """Build SyncHdr element"""
        hdr = ET.Element('SyncHdr')

        ET.SubElement(hdr, 'VerDTD').text = '1.2'
        ET.SubElement(hdr, 'VerProto').text = 'DM/1.2'
        ET.SubElement(hdr, 'SessionID').text = session_id
        ET.SubElement(hdr, 'MsgID').text = msg_id

        # Target (device)
        target_elem = ET.SubElement(hdr, 'Target')
        ET.SubElement(target_elem, 'LocURI').text = target

        # Source (server)
        source_elem = ET.SubElement(hdr, 'Source')
        ET.SubElement(source_elem, 'LocURI').text = source or self.server_id

        return hdr

    def _build_status(self, status: StatusBuilder) -> ET.Element:
        """Build Status element"""
        elem = ET.Element('Status')

        ET.SubElement(elem, 'CmdID').text = self.next_cmd_id()
        ET.SubElement(elem, 'MsgRef').text = status.msg_ref
        ET.SubElement(elem, 'CmdRef').text = status.cmd_ref
        ET.SubElement(elem, 'Cmd').text = status.cmd
        ET.SubElement(elem, 'Data').text = str(status.data)

        if status.target_ref:
            ET.SubElement(elem, 'TargetRef').text = status.target_ref
        if status.source_ref:
            ET.SubElement(elem, 'SourceRef').text = status.source_ref

        for item_data in status.items:
            item = ET.SubElement(elem, 'Item')
            if 'target' in item_data:
                t = ET.SubElement(item, 'Target')
                ET.SubElement(t, 'LocURI').text = item_data['target']
            if 'data' in item_data:
                ET.SubElement(item, 'Data').text = item_data['data']

        return elem

    def build_status(
        self,
        msg_ref: str,
        cmd_ref: str,
        cmd: str,
        status_code: int,
        target_ref: str = None,
        source_ref: str = None
    ) -> ET.Element:
        """Build a Status element"""
        elem = ET.Element('Status')

        ET.SubElement(elem, 'CmdID').text = self.next_cmd_id()
        ET.SubElement(elem, 'MsgRef').text = msg_ref
        ET.SubElement(elem, 'CmdRef').text = cmd_ref
        ET.SubElement(elem, 'Cmd').text = cmd
        ET.SubElement(elem, 'Data').text = str(status_code)

        if target_ref:
            ET.SubElement(elem, 'TargetRef').text = target_ref
        if source_ref:
            ET.SubElement(elem, 'SourceRef').text = source_ref

        return elem

    def build_get(self, targets: List[str]) -> ET.Element:
        """Build Get command"""
        elem = ET.Element('Get')
        ET.SubElement(elem, 'CmdID').text = self.next_cmd_id()

        for target in targets:
            item = ET.SubElement(elem, 'Item')
            target_elem = ET.SubElement(item, 'Target')
            ET.SubElement(target_elem, 'LocURI').text = target

        return elem

    def build_replace(self, items: List[ItemBuilder]) -> ET.Element:
        """Build Replace command"""
        elem = ET.Element('Replace')
        ET.SubElement(elem, 'CmdID').text = self.next_cmd_id()

        for item_data in items:
            item = ET.SubElement(elem, 'Item')

            if item_data.target:
                target = ET.SubElement(item, 'Target')
                ET.SubElement(target, 'LocURI').text = item_data.target

            if item_data.source:
                source = ET.SubElement(item, 'Source')
                ET.SubElement(source, 'LocURI').text = item_data.source

            if item_data.meta:
                meta = ET.SubElement(item, 'Meta')
                for key, value in item_data.meta.items():
                    ET.SubElement(meta, key).text = value

            if item_data.data is not None:
                ET.SubElement(item, 'Data').text = item_data.data

        return elem

    def build_add(self, items: List[ItemBuilder]) -> ET.Element:
        """Build Add command"""
        elem = ET.Element('Add')
        ET.SubElement(elem, 'CmdID').text = self.next_cmd_id()

        for item_data in items:
            item = ET.SubElement(elem, 'Item')

            if item_data.target:
                target = ET.SubElement(item, 'Target')
                ET.SubElement(target, 'LocURI').text = item_data.target

            if item_data.meta:
                meta = ET.SubElement(item, 'Meta')
                for key, value in item_data.meta.items():
                    ET.SubElement(meta, key).text = value

            if item_data.data is not None:
                ET.SubElement(item, 'Data').text = item_data.data

        return elem

    def build_exec(self, target: str, data: str = None) -> ET.Element:
        """Build Exec command"""
        elem = ET.Element('Exec')
        ET.SubElement(elem, 'CmdID').text = self.next_cmd_id()

        item = ET.SubElement(elem, 'Item')
        target_elem = ET.SubElement(item, 'Target')
        ET.SubElement(target_elem, 'LocURI').text = target

        if data:
            ET.SubElement(item, 'Data').text = data

        return elem

    def build_alert(self, alert_code: int, items: List[ItemBuilder] = None) -> ET.Element:
        """Build Alert command"""
        elem = ET.Element('Alert')
        ET.SubElement(elem, 'CmdID').text = self.next_cmd_id()
        ET.SubElement(elem, 'Data').text = str(alert_code)

        if items:
            for item_data in items:
                item = ET.SubElement(elem, 'Item')
                if item_data.target:
                    target = ET.SubElement(item, 'Target')
                    ET.SubElement(target, 'LocURI').text = item_data.target
                if item_data.source:
                    source = ET.SubElement(item, 'Source')
                    ET.SubElement(source, 'LocURI').text = item_data.source
                if item_data.data:
                    ET.SubElement(item, 'Data').text = item_data.data

        return elem

    def build_results(self, msg_ref: str, cmd_ref: str, items: List[ItemBuilder]) -> ET.Element:
        """Build Results command"""
        elem = ET.Element('Results')
        ET.SubElement(elem, 'CmdID').text = self.next_cmd_id()
        ET.SubElement(elem, 'MsgRef').text = msg_ref
        ET.SubElement(elem, 'CmdRef').text = cmd_ref

        for item_data in items:
            item = ET.SubElement(elem, 'Item')

            if item_data.source:
                source = ET.SubElement(item, 'Source')
                ET.SubElement(source, 'LocURI').text = item_data.source

            if item_data.meta:
                meta = ET.SubElement(item, 'Meta')
                for key, value in item_data.meta.items():
                    ET.SubElement(meta, key).text = value

            if item_data.data is not None:
                ET.SubElement(item, 'Data').text = item_data.data

        return elem

    def to_xml_string(self, root: ET.Element) -> str:
        """Convert ElementTree to XML string"""
        return ET.tostring(root, encoding='unicode', xml_declaration=True)

    def to_wbxml(self, root: ET.Element) -> bytes:
        """Convert ElementTree to WBXML"""
        encoder = WBXMLEncoder()
        return encoder.encode(root)
