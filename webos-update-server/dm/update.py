"""
Update Manager

Handles update availability logic and package management for webOS devices.
"""
import os
import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from pathlib import Path
import config


@dataclass
class UpdatePackage:
    """Represents an update package"""
    name: str
    version: str
    filename: str
    size: int = 0
    md5: str = ""
    description: str = ""
    min_version: str = ""  # Minimum device version required
    target_build: str = ""  # Target build number
    install_notify_url: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "filename": self.filename,
            "size": self.size,
            "md5": self.md5,
            "description": self.description,
            "min_version": self.min_version,
            "target_build": self.target_build,
        }


class UpdateManager:
    """
    Manages update packages and determines update availability.

    Reads packages from the packages/ directory and serves them
    to devices based on their current build version.
    """

    def __init__(self, packages_dir: str = None):
        self.packages_dir = Path(packages_dir or config.PACKAGES_DIR)
        self.packages: Dict[str, UpdatePackage] = {}
        self.manifest_path = self.packages_dir / "manifest.json"
        self._load_manifest()

    def _load_manifest(self):
        """Load package manifest from disk"""
        if not self.manifest_path.exists():
            # Create empty manifest
            self._save_manifest()
            return

        try:
            with open(self.manifest_path, 'r') as f:
                data = json.load(f)
                for pkg_data in data.get('packages', []):
                    pkg = UpdatePackage(
                        name=pkg_data.get('name', ''),
                        version=pkg_data.get('version', ''),
                        filename=pkg_data.get('filename', ''),
                        size=pkg_data.get('size', 0),
                        md5=pkg_data.get('md5', ''),
                        description=pkg_data.get('description', ''),
                        min_version=pkg_data.get('min_version', ''),
                        target_build=pkg_data.get('target_build', ''),
                        install_notify_url=pkg_data.get('install_notify_url', ''),
                    )
                    self.packages[pkg.name] = pkg
        except Exception as e:
            print(f"Error loading manifest: {e}")

    def _save_manifest(self):
        """Save package manifest to disk"""
        self.packages_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "packages": [pkg.to_dict() for pkg in self.packages.values()]
        }
        with open(self.manifest_path, 'w') as f:
            json.dump(data, f, indent=2)

    def scan_packages(self):
        """Scan packages directory and update manifest"""
        if not self.packages_dir.exists():
            self.packages_dir.mkdir(parents=True, exist_ok=True)
            return

        for filepath in self.packages_dir.glob("*.ipk"):
            if filepath.name not in [p.filename for p in self.packages.values()]:
                # New package found
                pkg = self._create_package_entry(filepath)
                if pkg:
                    self.packages[pkg.name] = pkg

        # Also scan for delta packages
        for filepath in self.packages_dir.glob("*.dipk"):
            if filepath.name not in [p.filename for p in self.packages.values()]:
                pkg = self._create_package_entry(filepath)
                if pkg:
                    self.packages[pkg.name] = pkg

        self._save_manifest()

    def _create_package_entry(self, filepath: Path) -> Optional[UpdatePackage]:
        """Create package entry from file"""
        try:
            # Calculate MD5
            md5 = hashlib.md5()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    md5.update(chunk)

            size = filepath.stat().st_size
            name = filepath.stem  # filename without extension

            return UpdatePackage(
                name=name,
                version="1.0.0",  # Default, should be updated manually
                filename=filepath.name,
                size=size,
                md5=md5.hexdigest(),
                description=f"Update package: {name}",
            )
        except Exception as e:
            print(f"Error creating package entry for {filepath}: {e}")
            return None

    def add_package(
        self,
        name: str,
        version: str,
        filepath: str,
        description: str = "",
        min_version: str = "",
        target_build: str = ""
    ) -> Optional[UpdatePackage]:
        """Add or update a package in the manifest"""
        path = Path(filepath)
        if not path.exists():
            return None

        # Copy to packages directory if not already there
        dest_path = self.packages_dir / path.name
        if path != dest_path:
            import shutil
            shutil.copy(path, dest_path)
            path = dest_path

        # Calculate checksum
        md5 = hashlib.md5()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5.update(chunk)

        pkg = UpdatePackage(
            name=name,
            version=version,
            filename=path.name,
            size=path.stat().st_size,
            md5=md5.hexdigest(),
            description=description,
            min_version=min_version,
            target_build=target_build,
        )

        self.packages[name] = pkg
        self._save_manifest()
        return pkg

    def remove_package(self, name: str) -> bool:
        """Remove a package from manifest"""
        if name in self.packages:
            del self.packages[name]
            self._save_manifest()
            return True
        return False

    def get_package(self, name: str) -> Optional[UpdatePackage]:
        """Get package by name"""
        return self.packages.get(name)

    def get_package_path(self, filename: str) -> Optional[Path]:
        """Get full path to package file"""
        path = self.packages_dir / filename
        if path.exists():
            return path
        return None

    def check_update_available(
        self,
        device_build: str,
        device_model: str = "",
        device_carrier: str = ""
    ) -> Optional[UpdatePackage]:
        """
        Check if an update is available for the device.

        Args:
            device_build: Current build string (e.g., "Nova-3.0.5-64")
            device_model: Device model (e.g., "Topaz")
            device_carrier: Carrier code (e.g., "ROW")

        Returns:
            UpdatePackage if update available, None otherwise
        """
        if not self.packages:
            return None

        # Parse device build version
        device_version = self._parse_build_version(device_build)

        # Find applicable updates
        candidates = []
        for pkg in self.packages.values():
            # Check minimum version requirement
            if pkg.min_version:
                min_ver = self._parse_build_version(pkg.min_version)
                if device_version < min_ver:
                    continue

            # Check target build is newer
            if pkg.target_build:
                target_ver = self._parse_build_version(pkg.target_build)
                if device_version >= target_ver:
                    continue  # Already at or past this version

            candidates.append(pkg)

        if not candidates:
            return None

        # Return the newest applicable update
        candidates.sort(
            key=lambda p: self._parse_build_version(p.target_build or p.version),
            reverse=True
        )
        return candidates[0]

    def _parse_build_version(self, build: str) -> tuple:
        """
        Parse build string to comparable tuple.

        Examples:
            "Nova-3.0.5-64" -> (3, 0, 5, 64)
            "3.0.5" -> (3, 0, 5, 0)
        """
        import re

        # Extract version numbers
        numbers = re.findall(r'\d+', build)
        if not numbers:
            return (0, 0, 0, 0)

        # Pad to 4 components
        while len(numbers) < 4:
            numbers.append('0')

        return tuple(int(n) for n in numbers[:4])

    def get_package_url(self, package: UpdatePackage, base_url: str = None) -> str:
        """Get download URL for package"""
        if base_url is None:
            base_url = config.SERVER_URL
        return f"{base_url}/packages/{package.filename}"

    def list_packages(self) -> List[UpdatePackage]:
        """List all available packages"""
        return list(self.packages.values())

    def get_manifest(self) -> dict:
        """Get full manifest as dictionary"""
        return {
            "packages": [pkg.to_dict() for pkg in self.packages.values()],
            "count": len(self.packages),
        }
