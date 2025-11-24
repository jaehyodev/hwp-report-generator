"""Template file management utility.

Handles HWPX file upload, extraction, placeholder extraction, and validation.
"""

import os
import re
import shutil
import hashlib
from pathlib import Path
from typing import Set, List
from zipfile import ZipFile, BadZipFile

# 프로젝트 홈 디렉토리 계산 (backend/app/utils/templates_manager.py -> project_home)
PROJECT_HOME = Path(__file__).parent.parent.parent.parent


class TemplatesManager:
    """Manages template file operations (upload, extraction, placeholder extraction)."""

    def __init__(self):
        """Initialize TemplatesManager with directory paths."""
        self.templates_dir = PROJECT_HOME / "backend" / "templates"
        self.temp_dir = PROJECT_HOME / "backend" / "temp"

        # Create directories if they don't exist
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def validate_hwpx(self, file_content: bytes) -> bool:
        """Validates HWPX file using magic byte (ZIP signature).

        HWPX is a ZIP archive format, so we check for ZIP file signature.

        Args:
            file_content: File content as bytes

        Returns:
            True if valid HWPX (ZIP) file, False otherwise

        Examples:
            >>> with open("template.hwpx", "rb") as f:
            ...     content = f.read()
            >>> manager = TemplatesManager()
            >>> is_valid = manager.validate_hwpx(content)
            >>> print(is_valid)
            True
        """
        # ZIP file signature: PK\x03\x04
        return len(file_content) >= 4 and file_content[:4] == b'PK\x03\x04'

    def extract_hwpx(self, file_path: str) -> str:
        """Extracts HWPX file to temporary directory.

        Args:
            file_path: Path to HWPX file

        Returns:
            Path to extracted directory

        Raises:
            BadZipFile: If file is corrupted or not a valid ZIP
            FileNotFoundError: If file doesn't exist

        Examples:
            >>> manager = TemplatesManager()
            >>> work_dir = manager.extract_hwpx("temp/upload.hwpx")
            >>> print(os.path.exists(work_dir))
            True
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            # Create unique working directory
            work_dir = self.temp_dir / f"extract_{hash(file_path) % 10**8}"
            work_dir.mkdir(parents=True, exist_ok=True)

            # Extract ZIP
            with ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(work_dir)

            return str(work_dir)
        except BadZipFile as e:
            raise BadZipFile(f"Invalid HWPX file: {str(e)}")

    def extract_placeholders(self, work_dir: str) -> List[str]:
        """Extracts placeholders from section*.xml files in Contents directory.

        Searches for pattern {{KEY}} where KEY contains uppercase letters and underscores.
        Filters to only process files that start with "section" in Contents directory.
        Preserves duplicates to allow duplicate detection.

        Args:
            work_dir: Extracted HWPX directory path

        Returns:
            List of placeholders with duplicates preserved (e.g., ["{{TITLE}}", "{{SUMMARY}}", "{{BACKGROUND}}", "{{BACKGROUND}}"])

        Raises:
            FileNotFoundError: If Contents directory doesn't exist

        Examples:
            >>> manager = TemplatesManager()
            >>> work_dir = manager.extract_hwpx("temp/upload.hwpx")
            >>> placeholders = manager.extract_placeholders(work_dir)
            >>> print(placeholders)
            ['{{TITLE}}', '{{SUMMARY}}', '{{BACKGROUND}}', '{{BACKGROUND}}']
        """
        contents_dir = Path(work_dir) / "Contents"

        if not contents_dir.exists():
            raise FileNotFoundError(f"Contents directory not found in {work_dir}")

        placeholders = []
        # Pattern to match {{UPPERCASE_KEY}}
        pattern = r'\{\{([A-Z_]+)\}\}'

        # Process only files that start with "section"
        for xml_file in sorted(contents_dir.glob("section*.xml")):
            try:
                with open(xml_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    matches = re.findall(pattern, content)
                    for match in matches:
                        placeholders.append(f"{{{{{match}}}}}")
            except Exception as e:
                # Log but continue processing other files
                print(f"Warning: Failed to read {xml_file}: {e}")
                continue

        return placeholders

    def has_duplicate_placeholders(self, placeholder_keys: List[str]) -> bool:
        """Checks if there are duplicate placeholders while preserving order.

        Args:
            placeholder_keys: List of placeholder keys

        Returns:
            True if duplicates exist, False otherwise

        Examples:
            >>> manager = TemplatesManager()
            >>> placeholders = ["{{TITLE}}", "{{SUMMARY}}", "{{TITLE}}"]
            >>> has_dup = manager.has_duplicate_placeholders(placeholders)
            >>> print(has_dup)
            True
        """
        seen = set()
        for key in placeholder_keys:
            if key in seen:
                return True
            seen.add(key)
        return False

    def get_duplicate_placeholders(self, placeholder_keys: List[str]) -> List[str]:
        """Gets list of duplicate placeholder keys.

        Args:
            placeholder_keys: List of placeholder keys

        Returns:
            List of duplicate keys (e.g., ["{{TITLE}}"])

        Examples:
            >>> manager = TemplatesManager()
            >>> placeholders = ["{{TITLE}}", "{{SUMMARY}}", "{{TITLE}}", "{{SUMMARY}}"]
            >>> duplicates = manager.get_duplicate_placeholders(placeholders)
            >>> print(duplicates)
            ['{{TITLE}}', '{{SUMMARY}}']
        """
        seen = set()
        duplicates: List[str] = []

        for key in placeholder_keys:
            if key in seen and key not in duplicates:
                # Preserve the order in which duplicates are first detected
                duplicates.append(key)
            else:
                seen.add(key)

        return duplicates

    def save_template_file(self, temp_file_path: str, user_id: int, template_id: int) -> str:
        """Moves temporary template file to final storage location.

        Structure: backend/templates/user_{user_id}/template_{template_id}/

        Args:
            temp_file_path: Path to temporary file
            user_id: User ID
            template_id: Template ID

        Returns:
            Final file path

        Raises:
            FileNotFoundError: If temp file doesn't exist
            FileExistsError: If destination exists

        Examples:
            >>> manager = TemplatesManager()
            >>> final_path = manager.save_template_file(
            ...     "backend/temp/upload.hwpx",
            ...     user_id=1,
            ...     template_id=5
            ... )
            >>> print(final_path)
            backend/templates/user_1/template_5/template.hwpx
        """
        if not os.path.exists(temp_file_path):
            raise FileNotFoundError(f"Temp file not found: {temp_file_path}")

        # Create target directory
        target_dir = self.templates_dir / f"user_{user_id}" / f"template_{template_id}"
        target_dir.mkdir(parents=True, exist_ok=True)

        # Move file
        filename = Path(temp_file_path).name
        final_path = target_dir / filename

        shutil.move(temp_file_path, str(final_path))

        return str(final_path)

    def cleanup_temp_files(self, work_dir: str):
        """Cleans up temporary files and directories.

        Args:
            work_dir: Temporary directory path to clean up

        Examples:
            >>> manager = TemplatesManager()
            >>> manager.cleanup_temp_files("backend/temp/extract_12345")
        """
        if os.path.exists(work_dir):
            try:
                shutil.rmtree(work_dir)
            except Exception as e:
                print(f"Warning: Failed to clean up {work_dir}: {e}")

    @staticmethod
    def calculate_sha256(file_path: str) -> str:
        """Calculates SHA256 hash of file for integrity checking.

        Args:
            file_path: Path to file

        Returns:
            SHA256 hash as hex string

        Raises:
            FileNotFoundError: If file doesn't exist

        Examples:
            >>> manager = TemplatesManager()
            >>> hash_value = manager.calculate_sha256("template.hwpx")
            >>> print(hash_value)
            abc123def456...
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        return sha256_hash.hexdigest()
