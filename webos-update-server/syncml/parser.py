"""
SyncML Message Parser

Parses SyncML messages (XML or WBXML) into structured Python objects.
"""
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from wbxml import WBXMLDecoder


@dataclass
class SyncMLHeader:
    """SyncML message header"""
    ver_dtd: str = "1.2"
    ver_proto: str = "DM/1.2"
    session_id: str = ""
    msg_id: str = ""
    target: str = ""
    source: str = ""
    cred_type: Optional[str] = None
    cred_data: Optional[str] = None
    cred_format: Optional[str] = None
    meta: Dict[str, str] = field(default_factory=dict)


@dataclass
class SyncMLItem:
    """SyncML item (data container)"""
    target: Optional[str] = None
    source: Optional[str] = None
    data: Optional[str] = None
    meta: Dict[str, str] = field(default_factory=dict)


@dataclass
class SyncMLCommand:
    """SyncML command (Alert, Get, Replace, etc.)"""
    name: str = ""
    cmd_id: str = ""
    msg_ref: Optional[str] = None
    cmd_ref: Optional[str] = None
    cmd: Optional[str] = None  # For Status commands
    target_ref: Optional[str] = None
    source_ref: Optional[str] = None
    data: Optional[str] = None
    items: List[SyncMLItem] = field(default_factory=list)
    meta: Dict[str, str] = field(default_factory=dict)
    no_resp: bool = False


@dataclass
class SyncMLMessage:
    """Complete SyncML message"""
    header: SyncMLHeader = field(default_factory=SyncMLHeader)
    commands: List[SyncMLCommand] = field(default_factory=list)
    is_final: bool = False

    def get_alerts(self) -> List[SyncMLCommand]:
        """Get all Alert commands"""
        return [c for c in self.commands if c.name == 'Alert']

    def get_statuses(self) -> List[SyncMLCommand]:
        """Get all Status commands"""
        return [c for c in self.commands if c.name == 'Status']

    def get_results(self) -> List[SyncMLCommand]:
        """Get all Results commands"""
        return [c for c in self.commands if c.name == 'Results']

    def get_command(self, name: str) -> Optional[SyncMLCommand]:
        """Get first command by name"""
        for c in self.commands:
            if c.name == name:
                return c
        return None


class SyncMLParser:
    """Parse SyncML messages from XML or WBXML"""

    def __init__(self):
        pass

    def parse(self, data: bytes, content_type: str = "") -> SyncMLMessage:
        """Parse SyncML message from bytes"""
        # Detect format
        if content_type.endswith('wbxml') or (data and data[0] in (0x02, 0x03)):
            # WBXML format
            root = self._decode_wbxml(data)
        else:
            # XML format
            root = ET.fromstring(data)

        return self._parse_syncml(root)

    def parse_xml(self, xml_str: str) -> SyncMLMessage:
        """Parse SyncML from XML string"""
        root = ET.fromstring(xml_str)
        return self._parse_syncml(root)

    def _decode_wbxml(self, data: bytes) -> ET.Element:
        """Decode WBXML to ElementTree"""
        decoder = WBXMLDecoder(data)
        return decoder.decode()

    def _parse_syncml(self, root: ET.Element) -> SyncMLMessage:
        """Parse SyncML ElementTree to message object"""
        msg = SyncMLMessage()

        # Find SyncHdr
        sync_hdr = root.find('.//SyncHdr')
        if sync_hdr is None:
            sync_hdr = root.find('SyncHdr')

        if sync_hdr is not None:
            msg.header = self._parse_header(sync_hdr)

        # Find SyncBody
        sync_body = root.find('.//SyncBody')
        if sync_body is None:
            sync_body = root.find('SyncBody')

        if sync_body is not None:
            msg.commands = self._parse_body(sync_body)
            # Check for Final
            msg.is_final = sync_body.find('Final') is not None

        return msg

    def _parse_header(self, hdr: ET.Element) -> SyncMLHeader:
        """Parse SyncHdr element"""
        header = SyncMLHeader()

        header.ver_dtd = self._get_text(hdr, 'VerDTD', '1.2')
        header.ver_proto = self._get_text(hdr, 'VerProto', 'DM/1.2')
        header.session_id = self._get_text(hdr, 'SessionID', '')
        header.msg_id = self._get_text(hdr, 'MsgID', '')

        # Target
        target = hdr.find('Target')
        if target is not None:
            header.target = self._get_text(target, 'LocURI', '')

        # Source
        source = hdr.find('Source')
        if source is not None:
            header.source = self._get_text(source, 'LocURI', '')

        # Credentials
        cred = hdr.find('Cred')
        if cred is not None:
            meta = cred.find('Meta')
            if meta is not None:
                header.cred_type = self._get_text(meta, 'Type', '')
                header.cred_format = self._get_text(meta, 'Format', '')
            header.cred_data = self._get_text(cred, 'Data', '')

        # Meta
        meta = hdr.find('Meta')
        if meta is not None:
            header.meta = self._parse_meta(meta)

        return header

    def _parse_body(self, body: ET.Element) -> List[SyncMLCommand]:
        """Parse SyncBody element"""
        commands = []

        for child in body:
            if child.tag == 'Final':
                continue

            cmd = self._parse_command(child)
            if cmd:
                commands.append(cmd)

        return commands

    def _parse_command(self, elem: ET.Element) -> Optional[SyncMLCommand]:
        """Parse a single command element"""
        cmd = SyncMLCommand()
        cmd.name = elem.tag
        cmd.cmd_id = self._get_text(elem, 'CmdID', '')

        # Status-specific fields
        cmd.msg_ref = self._get_text(elem, 'MsgRef')
        cmd.cmd_ref = self._get_text(elem, 'CmdRef')
        cmd.cmd = self._get_text(elem, 'Cmd')
        cmd.target_ref = self._get_text(elem, 'TargetRef')
        cmd.source_ref = self._get_text(elem, 'SourceRef')
        cmd.data = self._get_text(elem, 'Data')

        # NoResp flag
        cmd.no_resp = elem.find('NoResp') is not None

        # Items
        for item_elem in elem.findall('Item'):
            item = self._parse_item(item_elem)
            cmd.items.append(item)

        # Meta
        meta = elem.find('Meta')
        if meta is not None:
            cmd.meta = self._parse_meta(meta)

        return cmd

    def _parse_item(self, elem: ET.Element) -> SyncMLItem:
        """Parse Item element"""
        item = SyncMLItem()

        target = elem.find('Target')
        if target is not None:
            item.target = self._get_text(target, 'LocURI', '')

        source = elem.find('Source')
        if source is not None:
            item.source = self._get_text(source, 'LocURI', '')

        item.data = self._get_text(elem, 'Data')

        meta = elem.find('Meta')
        if meta is not None:
            item.meta = self._parse_meta(meta)

        return item

    def _parse_meta(self, meta: ET.Element) -> Dict[str, str]:
        """Parse Meta element to dictionary"""
        result = {}
        for child in meta:
            if child.text:
                result[child.tag] = child.text
        return result

    def _get_text(self, elem: ET.Element, tag: str, default: Optional[str] = None) -> Optional[str]:
        """Get text content of child element"""
        child = elem.find(tag)
        if child is not None and child.text:
            return child.text
        return default
