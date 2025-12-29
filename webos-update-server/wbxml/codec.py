"""
WBXML Encoder/Decoder for SyncML 1.2

WBXML (WAP Binary XML) is a compact binary representation of XML.
Used by OMA DM for efficient over-the-air transmission.
"""
import io
import xml.etree.ElementTree as ET
from typing import Optional, Tuple, Dict, Any
from .tokens import (
    SWITCH_PAGE, END, STR_I, STR_T, OPAQUE, LITERAL,
    TAG_HAS_CONTENT, TAG_HAS_ATTRS,
    SYNCML_1_2_PUBLIC_ID,
    CODE_PAGES, CODE_PAGES_REV,
    SYNCML_TAGS, SYNCML_TAGS_REV,
    METINF_TAGS, METINF_TAGS_REV,
)


class WBXMLDecoder:
    """Decode WBXML binary data to XML ElementTree"""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.string_table: bytes = b""
        self.current_page = 0

    def read_byte(self) -> int:
        """Read a single byte"""
        if self.pos >= len(self.data):
            raise ValueError(f"Unexpected end of data at position {self.pos}")
        b = self.data[self.pos]
        self.pos += 1
        return b

    def read_mb_uint32(self) -> int:
        """Read a multi-byte encoded uint32 (variable length)"""
        result = 0
        while True:
            b = self.read_byte()
            result = (result << 7) | (b & 0x7F)
            if not (b & 0x80):
                break
        return result

    def read_string(self) -> str:
        """Read null-terminated inline string"""
        start = self.pos
        while self.data[self.pos] != 0:
            self.pos += 1
        s = self.data[start:self.pos].decode('utf-8')
        self.pos += 1  # skip null terminator
        return s

    def read_opaque(self) -> bytes:
        """Read opaque data (length-prefixed binary)"""
        length = self.read_mb_uint32()
        data = self.data[self.pos:self.pos + length]
        self.pos += length
        return data

    def get_string_from_table(self, offset: int) -> str:
        """Get string from string table at given offset"""
        end = self.string_table.find(b'\x00', offset)
        if end == -1:
            end = len(self.string_table)
        return self.string_table[offset:end].decode('utf-8')

    def get_tag_name(self, token: int) -> str:
        """Get tag name for token in current code page"""
        tag_token = token & 0x3F  # Remove content/attr flags
        tags = CODE_PAGES.get(self.current_page, SYNCML_TAGS)
        return tags.get(tag_token, f"Unknown_0x{tag_token:02X}")

    def decode(self) -> ET.Element:
        """Decode WBXML to ElementTree"""
        # Read header
        version = self.read_byte()  # WBXML version (e.g., 0x03 for 1.3)
        public_id = self.read_mb_uint32()  # Public identifier

        # Handle public ID that might be in string table
        if public_id == 0:
            public_id_index = self.read_mb_uint32()

        charset = self.read_mb_uint32()  # Character set (106 = UTF-8)

        # String table
        str_table_len = self.read_mb_uint32()
        if str_table_len > 0:
            self.string_table = self.data[self.pos:self.pos + str_table_len]
            self.pos += str_table_len

        # Parse body
        root = self.parse_element()
        return root

    def parse_element(self) -> Optional[ET.Element]:
        """Parse a single element"""
        token = self.read_byte()

        # Handle switch page
        while token == SWITCH_PAGE:
            self.current_page = self.read_byte()
            token = self.read_byte()

        if token == END:
            return None

        has_content = bool(token & TAG_HAS_CONTENT)
        has_attrs = bool(token & TAG_HAS_ATTRS)

        # Get tag name
        if token & 0x3F == 0x04:  # LITERAL
            tag_index = self.read_mb_uint32()
            tag_name = self.get_string_from_table(tag_index)
        else:
            tag_name = self.get_tag_name(token)

        elem = ET.Element(tag_name)

        # Parse attributes (if any)
        if has_attrs:
            self.parse_attributes(elem)

        # Parse content (if any)
        if has_content:
            self.parse_content(elem)

        return elem

    def parse_attributes(self, elem: ET.Element):
        """Parse element attributes"""
        # Simplified - full implementation would handle attribute tokens
        while True:
            token = self.read_byte()
            if token == END:
                break
            # Handle attribute tokens...
            # For now, skip unknown attributes

    def parse_content(self, elem: ET.Element):
        """Parse element content (text and child elements)"""
        text_parts = []

        while True:
            token = self.read_byte()

            if token == END:
                break
            elif token == SWITCH_PAGE:
                self.current_page = self.read_byte()
            elif token == STR_I:
                # Inline string
                text_parts.append(self.read_string())
            elif token == STR_T:
                # String table reference
                offset = self.read_mb_uint32()
                text_parts.append(self.get_string_from_table(offset))
            elif token == OPAQUE:
                # Opaque data - store as base64 or raw
                data = self.read_opaque()
                try:
                    text_parts.append(data.decode('utf-8'))
                except UnicodeDecodeError:
                    import base64
                    text_parts.append(base64.b64encode(data).decode('ascii'))
            else:
                # It's a tag - push back and parse as child element
                self.pos -= 1
                child = self.parse_element()
                if child is not None:
                    elem.append(child)

        if text_parts:
            elem.text = ''.join(text_parts)


class WBXMLEncoder:
    """Encode XML ElementTree to WBXML binary"""

    def __init__(self):
        self.output = io.BytesIO()
        self.string_table = io.BytesIO()
        self.string_table_index: Dict[str, int] = {}
        self.current_page = 0

    def write_byte(self, b: int):
        """Write a single byte"""
        self.output.write(bytes([b]))

    def write_mb_uint32(self, value: int):
        """Write multi-byte encoded uint32"""
        if value == 0:
            self.write_byte(0)
            return

        bytes_list = []
        while value > 0:
            bytes_list.insert(0, value & 0x7F)
            value >>= 7

        for i, b in enumerate(bytes_list):
            if i < len(bytes_list) - 1:
                b |= 0x80
            self.write_byte(b)

    def write_string(self, s: str):
        """Write inline string (STR_I)"""
        self.write_byte(STR_I)
        self.output.write(s.encode('utf-8'))
        self.write_byte(0)  # null terminator

    def write_opaque(self, data: bytes):
        """Write opaque data"""
        self.write_byte(OPAQUE)
        self.write_mb_uint32(len(data))
        self.output.write(data)

    def add_to_string_table(self, s: str) -> int:
        """Add string to string table and return offset"""
        if s in self.string_table_index:
            return self.string_table_index[s]

        offset = self.string_table.tell()
        self.string_table_index[s] = offset
        self.string_table.write(s.encode('utf-8'))
        self.string_table.write(b'\x00')
        return offset

    def get_tag_token(self, tag_name: str, page: int) -> Optional[int]:
        """Get token for tag name in given code page"""
        tags_rev = CODE_PAGES_REV.get(page, SYNCML_TAGS_REV)
        return tags_rev.get(tag_name)

    def switch_page(self, page: int):
        """Switch to a different code page"""
        if page != self.current_page:
            self.write_byte(SWITCH_PAGE)
            self.write_byte(page)
            self.current_page = page

    def encode(self, root: ET.Element) -> bytes:
        """Encode ElementTree to WBXML"""
        # Build string table first (for literal tags)
        self.build_string_table(root)

        # Header will be written later
        body_start = self.output.tell()

        # Encode body
        self.encode_element(root)

        # Build final output with header
        body = self.output.getvalue()
        string_table = self.string_table.getvalue()

        final = io.BytesIO()

        # WBXML Version 1.3
        final.write(bytes([0x03]))

        # Public ID - SyncML 1.2
        self.write_mb_uint32_to(final, SYNCML_1_2_PUBLIC_ID)

        # Charset - UTF-8 (106)
        self.write_mb_uint32_to(final, 106)

        # String table length and content
        self.write_mb_uint32_to(final, len(string_table))
        final.write(string_table)

        # Body
        final.write(body)

        return final.getvalue()

    def write_mb_uint32_to(self, stream: io.BytesIO, value: int):
        """Write multi-byte uint32 to specific stream"""
        if value == 0:
            stream.write(bytes([0]))
            return

        bytes_list = []
        while value > 0:
            bytes_list.insert(0, value & 0x7F)
            value >>= 7

        for i, b in enumerate(bytes_list):
            if i < len(bytes_list) - 1:
                b |= 0x80
            stream.write(bytes([b]))

    def build_string_table(self, elem: ET.Element):
        """Pre-scan elements to build string table for unknown tags"""
        tag_name = elem.tag
        # Check if tag needs to be in string table
        if self.get_tag_token(tag_name, 0) is None and self.get_tag_token(tag_name, 1) is None:
            self.add_to_string_table(tag_name)

        for child in elem:
            self.build_string_table(child)

    def encode_element(self, elem: ET.Element):
        """Encode a single element"""
        tag_name = elem.tag

        # Determine code page and token
        token = self.get_tag_token(tag_name, 0)
        page = 0

        if token is None:
            token = self.get_tag_token(tag_name, 1)
            page = 1

        if token is None:
            # Use LITERAL with string table
            self.switch_page(0)
            has_content = bool(elem.text or len(elem) > 0)
            literal_token = LITERAL
            if has_content:
                literal_token |= TAG_HAS_CONTENT
            self.write_byte(literal_token)
            offset = self.string_table_index.get(tag_name, 0)
            self.write_mb_uint32(offset)
        else:
            self.switch_page(page)
            has_content = bool(elem.text or len(elem) > 0)
            if has_content:
                token |= TAG_HAS_CONTENT
            self.write_byte(token)

        # Encode content
        if elem.text or len(elem) > 0:
            if elem.text:
                self.write_string(elem.text)

            for child in elem:
                self.encode_element(child)
                if child.tail:
                    self.write_string(child.tail)

            self.write_byte(END)


def decode_wbxml(data: bytes) -> ET.Element:
    """Convenience function to decode WBXML to ElementTree"""
    decoder = WBXMLDecoder(data)
    return decoder.decode()


def encode_wbxml(root: ET.Element) -> bytes:
    """Convenience function to encode ElementTree to WBXML"""
    encoder = WBXMLEncoder()
    return encoder.encode(root)


def wbxml_to_xml_string(data: bytes) -> str:
    """Convert WBXML to XML string"""
    root = decode_wbxml(data)
    return ET.tostring(root, encoding='unicode')


def xml_string_to_wbxml(xml_str: str) -> bytes:
    """Convert XML string to WBXML"""
    root = ET.fromstring(xml_str)
    return encode_wbxml(root)
