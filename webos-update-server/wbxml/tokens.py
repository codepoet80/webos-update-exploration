"""
WBXML Token Tables for SyncML 1.2 and OMA DM

Based on:
- OMA-TS-SyncML_RepPro-V1_2 (SyncML Representation Protocol)
- OMA-TS-DM_Protocol-V1_2 (OMA Device Management Protocol)
"""

# WBXML Global Tokens
SWITCH_PAGE = 0x00
END = 0x01
ENTITY = 0x02
STR_I = 0x03  # Inline string
LITERAL = 0x04
EXT_I_0 = 0x40
EXT_I_1 = 0x41
EXT_I_2 = 0x42
PI = 0x43
LITERAL_C = 0x44
EXT_T_0 = 0x80
EXT_T_1 = 0x81
EXT_T_2 = 0x82
STR_T = 0x83  # String table reference
LITERAL_A = 0x84
EXT_0 = 0xC0
EXT_1 = 0xC1
EXT_2 = 0xC2
OPAQUE = 0xC3
LITERAL_AC = 0xC4

# Tag token flags
TAG_HAS_CONTENT = 0x40
TAG_HAS_ATTRS = 0x80

# SyncML 1.2 Public ID
SYNCML_1_2_PUBLIC_ID = 0x1201  # -//SYNCML//DTD SyncML 1.2//EN

# SyncML Tag Tokens (Code Page 0x00)
SYNCML_TAGS = {
    # Tag code -> Tag name
    0x05: 'Add',
    0x06: 'Alert',
    0x07: 'Archive',
    0x08: 'Atomic',
    0x09: 'Chal',
    0x0A: 'Cmd',
    0x0B: 'CmdID',
    0x0C: 'CmdRef',
    0x0D: 'Copy',
    0x0E: 'Cred',
    0x0F: 'Data',
    0x10: 'Delete',
    0x11: 'Exec',
    0x12: 'Final',
    0x13: 'Get',
    0x14: 'Item',
    0x15: 'Lang',
    0x16: 'LocName',
    0x17: 'LocURI',
    0x18: 'Map',
    0x19: 'MapItem',
    0x1A: 'Meta',
    0x1B: 'MsgID',
    0x1C: 'MsgRef',
    0x1D: 'NoResp',
    0x1E: 'NoResults',
    0x1F: 'Put',
    0x20: 'Replace',
    0x21: 'RespURI',
    0x22: 'Results',
    0x23: 'Search',
    0x24: 'Sequence',
    0x25: 'SessionID',
    0x26: 'SftDel',
    0x27: 'Source',
    0x28: 'SourceRef',
    0x29: 'Status',
    0x2A: 'Sync',
    0x2B: 'SyncBody',
    0x2C: 'SyncHdr',
    0x2D: 'SyncML',
    0x2E: 'Target',
    0x2F: 'TargetRef',
    0x30: 'Reserved',  # Reserved for future use
    0x31: 'VerDTD',
    0x32: 'VerProto',
    0x33: 'NumberOfChanges',
    0x34: 'MoreData',
    0x35: 'Field',
    0x36: 'Filter',
    0x37: 'Record',
    0x38: 'FilterType',
    0x39: 'SourceParent',
    0x3A: 'TargetParent',
    0x3B: 'Move',
    0x3C: 'Correlator',
}

# Reverse mapping for encoding
SYNCML_TAGS_REV = {v: k for k, v in SYNCML_TAGS.items()}

# MetInf Tag Tokens (Code Page 0x01)
METINF_TAGS = {
    0x05: 'Anchor',
    0x06: 'EMI',
    0x07: 'Format',
    0x08: 'FreeID',
    0x09: 'FreeMem',
    0x0A: 'Last',
    0x0B: 'Mark',
    0x0C: 'MaxMsgSize',
    0x0D: 'Mem',
    0x0E: 'MetInf',
    0x0F: 'Next',
    0x10: 'NextNonce',
    0x11: 'SharedMem',
    0x12: 'Size',
    0x13: 'Type',
    0x14: 'Version',
    0x15: 'MaxObjSize',
    0x16: 'FieldLevel',
}

METINF_TAGS_REV = {v: k for k, v in METINF_TAGS.items()}

# DevInf Tag Tokens (Code Page 0x00 for DevInf document)
DEVINF_TAGS = {
    0x05: 'CTCap',
    0x06: 'CTType',
    0x07: 'DataStore',
    0x08: 'DataType',
    0x09: 'DevID',
    0x0A: 'DevInf',
    0x0B: 'DevTyp',
    0x0C: 'DisplayName',
    0x0D: 'DSMem',
    0x0E: 'Ext',
    0x0F: 'FwV',
    0x10: 'HwV',
    0x11: 'Man',
    0x12: 'MaxGUIDSize',
    0x13: 'MaxID',
    0x14: 'MaxMem',
    0x15: 'Mod',
    0x16: 'OEM',
    0x17: 'ParamName',
    0x18: 'PropName',
    0x19: 'Rx',
    0x1A: 'Rx-Pref',
    0x1B: 'SharedMem',
    0x1C: 'Size',
    0x1D: 'SourceRef',
    0x1E: 'SwV',
    0x1F: 'SyncCap',
    0x20: 'SyncType',
    0x21: 'Tx',
    0x22: 'Tx-Pref',
    0x23: 'ValEnum',
    0x24: 'VerCT',
    0x25: 'VerDTD',
    0x26: 'XNam',
    0x27: 'XVal',
    0x28: 'UTC',
    0x29: 'SupportNumberOfChanges',
    0x2A: 'SupportLargeObjs',
    0x2B: 'Property',
    0x2C: 'PropParam',
    0x2D: 'MaxOccur',
    0x2E: 'NoTruncate',
    0x2F: 'Filter-Rx',
    0x30: 'FilterCap',
    0x31: 'FilterKeyword',
    0x32: 'FieldLevel',
    0x33: 'SupportHierarchicalSync',
}

DEVINF_TAGS_REV = {v: k for k, v in DEVINF_TAGS.items()}

# DM DDF Tag Tokens (Code Page 0x00 for DM DDF)
DMDDF_TAGS = {
    0x05: 'AccessType',
    0x06: 'ACL',
    0x07: 'Add',
    0x08: 'b64',
    0x09: 'bin',
    0x0A: 'bool',
    0x0B: 'chr',
    0x0C: 'CaseSense',
    0x0D: 'CIS',
    0x0E: 'Copy',
    0x0F: 'CS',
    0x10: 'date',
    0x11: 'DDFName',
    0x12: 'DDFVersion',
    0x13: 'Delete',
    0x14: 'Description',
    0x15: 'DFFormat',
    0x16: 'DFProperties',
    0x17: 'DFTitle',
    0x18: 'DFType',
    0x19: 'Dynamic',
    0x1A: 'Exec',
    0x1B: 'float',
    0x1C: 'Format',
    0x1D: 'Get',
    0x1E: 'int',
    0x1F: 'Man',
    0x20: 'MgmtTree',
    0x21: 'MIME',
    0x22: 'Mod',
    0x23: 'Name',
    0x24: 'Node',
    0x25: 'node',
    0x26: 'NodeName',
    0x27: 'null',
    0x28: 'Occurrence',
    0x29: 'One',
    0x2A: 'OneOrMore',
    0x2B: 'OneOrN',
    0x2C: 'Path',
    0x2D: 'Permanent',
    0x2E: 'Replace',
    0x2F: 'RTProperties',
    0x30: 'Scope',
    0x31: 'Size',
    0x32: 'time',
    0x33: 'Title',
    0x34: 'TStamp',
    0x35: 'Type',
    0x36: 'Value',
    0x37: 'VerDTD',
    0x38: 'VerNo',
    0x39: 'xml',
    0x3A: 'ZeroOrMore',
    0x3B: 'ZeroOrN',
    0x3C: 'ZeroOrOne',
}

# Code page mapping
CODE_PAGES = {
    0x00: SYNCML_TAGS,
    0x01: METINF_TAGS,
}

CODE_PAGES_REV = {
    0x00: SYNCML_TAGS_REV,
    0x01: METINF_TAGS_REV,
}
