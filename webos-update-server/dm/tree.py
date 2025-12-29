"""
OMA DM Tree Operations

Manages the server-side device management tree for webOS devices.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
import config


@dataclass
class DMNode:
    """A node in the DM tree"""
    name: str
    value: Optional[str] = None
    children: Dict[str, 'DMNode'] = field(default_factory=dict)
    acl: str = "Get=*&Replace=*"  # Access control list
    format: str = "chr"  # chr, int, bool, bin, node, null
    type_: str = "text/plain"

    def is_leaf(self) -> bool:
        """Check if this is a leaf node (has value, no children)"""
        return len(self.children) == 0

    def get_child(self, name: str) -> Optional['DMNode']:
        """Get child node by name"""
        return self.children.get(name)

    def add_child(self, node: 'DMNode') -> 'DMNode':
        """Add a child node"""
        self.children[node.name] = node
        return node

    def to_dict(self) -> dict:
        """Convert to dictionary representation"""
        if self.is_leaf():
            return {"value": self.value, "format": self.format}
        return {
            name: child.to_dict()
            for name, child in self.children.items()
        }


class DMTree:
    """
    Device Management Tree

    Represents the server's view of device state and configuration.
    Standard paths for webOS:
    - ./DevInfo/        Device information (read-only from device)
    - ./Software/       Software/update management
    - ./Download/       Download management
    """

    def __init__(self):
        self.root = DMNode(name=".")
        self._init_standard_tree()

    def _init_standard_tree(self):
        """Initialize standard DM tree structure"""
        # DevInfo - device information (populated from device)
        devinfo = DMNode(name="DevInfo")
        devinfo.add_child(DMNode(name="DevId", value=""))
        devinfo.add_child(DMNode(name="Man", value=""))
        devinfo.add_child(DMNode(name="Mod", value=""))
        devinfo.add_child(DMNode(name="DmV", value=""))
        devinfo.add_child(DMNode(name="Lang", value=""))
        devinfo.add_child(DMNode(name="FwV", value=""))
        devinfo.add_child(DMNode(name="SwV", value=""))
        devinfo.add_child(DMNode(name="HwV", value=""))
        self.root.add_child(devinfo)

        # Software - update management
        software = DMNode(name="Software")
        software.add_child(DMNode(name="Build", value=""))
        software.add_child(DMNode(name="Carrier", value=""))

        # Package info for updates
        package = DMNode(name="Package")
        package.add_child(DMNode(name="PkgName", value=""))
        package.add_child(DMNode(name="PkgVersion", value=""))
        package.add_child(DMNode(name="PkgURL", value=""))
        package.add_child(DMNode(name="PkgSize", value=""))
        package.add_child(DMNode(name="PkgDesc", value=""))
        package.add_child(DMNode(name="PkgInstallNotify", value=""))
        software.add_child(package)

        # Download operations
        operations = DMNode(name="Operations")
        operations.add_child(DMNode(name="Download", value=""))
        operations.add_child(DMNode(name="DownloadAndInstall", value=""))
        operations.add_child(DMNode(name="Install", value=""))
        software.add_child(operations)

        self.root.add_child(software)

        # Download management
        download = DMNode(name="Download")
        download.add_child(DMNode(name="Status", value=""))
        download.add_child(DMNode(name="Progress", value=""))
        self.root.add_child(download)

    def get(self, path: str) -> Optional[str]:
        """
        Get value at path.

        Path format: ./DevInfo/Mod or DevInfo/Mod
        """
        node = self._get_node(path)
        if node:
            return node.value
        return None

    def set(self, path: str, value: str) -> bool:
        """
        Set value at path.

        Creates intermediate nodes if necessary.
        """
        parts = self._parse_path(path)
        if not parts:
            return False

        current = self.root
        for i, part in enumerate(parts[:-1]):
            child = current.get_child(part)
            if child is None:
                # Create intermediate node
                child = DMNode(name=part)
                current.add_child(child)
            current = child

        # Set or create leaf node
        leaf_name = parts[-1]
        leaf = current.get_child(leaf_name)
        if leaf is None:
            leaf = DMNode(name=leaf_name, value=value)
            current.add_child(leaf)
        else:
            leaf.value = value
        return True

    def delete(self, path: str) -> bool:
        """Delete node at path"""
        parts = self._parse_path(path)
        if not parts:
            return False

        current = self.root
        for part in parts[:-1]:
            child = current.get_child(part)
            if child is None:
                return False
            current = child

        leaf_name = parts[-1]
        if leaf_name in current.children:
            del current.children[leaf_name]
            return True
        return False

    def exists(self, path: str) -> bool:
        """Check if path exists"""
        return self._get_node(path) is not None

    def list_children(self, path: str) -> List[str]:
        """List child node names at path"""
        node = self._get_node(path)
        if node:
            return list(node.children.keys())
        return []

    def _get_node(self, path: str) -> Optional[DMNode]:
        """Get node at path"""
        parts = self._parse_path(path)
        if not parts:
            return self.root

        current = self.root
        for part in parts:
            child = current.get_child(part)
            if child is None:
                return None
            current = child
        return current

    def _parse_path(self, path: str) -> List[str]:
        """Parse path string to list of parts"""
        # Remove leading ./ or /
        path = path.strip()
        if path.startswith('./'):
            path = path[2:]
        elif path.startswith('.'):
            path = path[1:]
        if path.startswith('/'):
            path = path[1:]

        if not path:
            return []

        return [p for p in path.split('/') if p]

    def get_devinfo_paths(self) -> List[str]:
        """Get standard DevInfo paths to query from device"""
        return [
            "./DevInfo/DevId",
            "./DevInfo/Man",
            "./DevInfo/Mod",
            "./DevInfo/DmV",
            "./DevInfo/Lang",
            "./DevInfo/FwV",
            "./DevInfo/SwV",
            "./DevInfo/HwV",
        ]

    def get_software_paths(self) -> List[str]:
        """Get software-related paths to query"""
        return [
            "./Software/Build",
            "./Software/Carrier",
        ]
