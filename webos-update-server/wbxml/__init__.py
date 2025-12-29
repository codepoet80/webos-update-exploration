"""
WBXML (WAP Binary XML) codec for SyncML/OMA DM
"""
from .codec import WBXMLDecoder, WBXMLEncoder
from .tokens import SYNCML_TAGS, METINF_TAGS, DEVINF_TAGS

__all__ = ['WBXMLDecoder', 'WBXMLEncoder', 'SYNCML_TAGS', 'METINF_TAGS', 'DEVINF_TAGS']
