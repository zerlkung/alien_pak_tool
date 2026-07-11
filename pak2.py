"""
PAK2 format parser for Alien: Isolation PAK archives.
Matches the original CathodeLib implementation exactly.

Format (from CathodeLib PAK2.cs):
    Header (16 bytes):
        magic:          "PAK2" (4 bytes)
        rel_offset:     uint32 - (offset table position - 16)
        num_files:      uint32 - number of entries
        alignment:      uint32 - byte alignment (always 4)

    Name table (rel_offset + 16 - 16 = rel_offset bytes from offset 16):
        Null-terminated filenames, concatenated.

    Offset table (num_files * 4 bytes starting at rel_offset + 16):
        uint32 LE end-positions. File i data ends at offset_table[i].
        Synthetic offset_table[-1] = offset_table_start + num_files * 4
        = start of data section.

    File data:
        After the offset table, file content is laid out sequentially
        with alignment padding between files.
        File i content: from align_up(prev_end, alignment) to offset_table[i]
        where prev_end = offset_table[i-1] for i>0, or data_section for i=0.
"""

import struct
import os
from dataclasses import dataclass
from typing import List, Optional


def align_up(pos: int, alignment: int) -> int:
    """Round position up to next alignment boundary."""
    if pos % alignment == 0:
        return pos
    return pos + (alignment - pos % alignment)


@dataclass
class PAK2Entry:
    """A single file entry within a PAK2 archive.

    All data is stored CLEAN — alignment padding between files
    is handled by the PAK2 container, not the entries.
    """
    filename: str
    offset: int       # byte offset within the PAK (after alignment)
    size: int         # content size in bytes (no padding)
    _data: Optional[bytes] = None

    @property
    def data(self) -> bytes:
        """Clean file content (no alignment padding)."""
        return self._data

    @data.setter
    def data(self, value: bytes):
        self._data = value
        self.size = len(value)

    @property
    def ext(self) -> str:
        _, ext = os.path.splitext(self.filename)
        return ext.upper()


class PAK2:
    """Read/write PAK2 archives matching CathodeLib format."""

    MAGIC = b"PAK2"
    HEADER_SIZE = 16
    DEFAULT_ALIGNMENT = 4

    def __init__(self, path: str = None):
        self.path: str = path
        self.num_files: int = 0
        self.alignment: int = self.DEFAULT_ALIGNMENT
        self.entries: List[PAK2Entry] = []
        # Internal: offset table (end positions, exclusive)
        self._offsets: List[int] = []

        if path and os.path.exists(path):
            self.load(path)

    # ── read ──────────────────────────────────────────────

    def load(self, path: str):
        """Read a PAK2 file from disk."""
        self.path = path
        with open(path, "rb") as f:
            data = f.read()
        self._parse(data)

    def _parse(self, data: bytes):
        """Parse PAK2 binary data (matches CathodeLib LoadInternal)."""
        if len(data) < self.HEADER_SIZE:
            raise ValueError("File too small for PAK2 header")

        magic, rel_offset, self.num_files, self.alignment = struct.unpack_from(
            "<4sIII", data, 0
        )
        if magic != self.MAGIC:
            raise ValueError(f"Not a PAK2 file (magic={magic!r})")

        offset_table_start = rel_offset + self.HEADER_SIZE

        # Read filename table (from byte 16 to offset_table_start)
        name_blob = data[self.HEADER_SIZE:offset_table_start]
        filenames = [s.decode("latin-1") for s in name_blob.split(b"\x00") if s]

        if len(filenames) != self.num_files:
            raise ValueError(
                f"Filename count mismatch: found {len(filenames)}, "
                f"header says {self.num_files}"
            )

        # Read offset table
        self._offsets = []
        for i in range(self.num_files):
            off = struct.unpack_from("<I", data, offset_table_start + i * 4)[0]
            self._offsets.append(off)

        # Data section: right after offset table
        data_section = offset_table_start + self.num_files * 4

        # Read file contents with alignment (matches CathodeLib)
        self.entries = []
        prev_end = data_section
        for i, filename in enumerate(filenames):
            # Align to alignment boundary (CathodeLib: Utilities.Align(reader, alignment))
            content_start = align_up(prev_end, self.alignment)
            content_end = self._offsets[i]
            content_size = content_end - content_start

            entry_data = data[content_start:content_end]
            self.entries.append(PAK2Entry(
                filename=filename,
                offset=content_start,
                size=content_size,
                _data=entry_data,
            ))
            prev_end = content_end

    # ── write ──────────────────────────────────────────────

    def save(self, path: str = None):
        """Write PAK2 archive (matches CathodeLib SaveInternal)."""
        if path is None:
            path = self.path
        if path is None:
            raise ValueError("No output path specified")

        # Build name table (null-terminated)
        name_parts = [e.filename.encode("latin-1") + b"\x00" for e in self.entries]
        name_blob = b"".join(name_parts)

        offset_table_pos = self.HEADER_SIZE + len(name_blob)
        data_section = offset_table_pos + len(self.entries) * 4
        rel_offset = offset_table_pos - self.HEADER_SIZE  # = len(name_blob)

        # Header: magic + rel_offset + num_files + alignment
        header = struct.pack(
            "<4sIII",
            self.MAGIC,
            rel_offset,
            len(self.entries),
            self.alignment,
        )

        # Build offset table and data blob with alignment
        offsets = []
        data_parts = []
        prev_end = data_section

        for entry in self.entries:
            # Align writer
            aligned_pos = align_up(prev_end, self.alignment)
            if aligned_pos > prev_end:
                data_parts.append(b"\x00" * (aligned_pos - prev_end))
            data_parts.append(entry.data if entry.data else b"")
            prev_end = aligned_pos + (len(entry.data) if entry.data else 0)
            offsets.append(prev_end)

        # Final alignment padding
        final_aligned = align_up(prev_end, self.alignment)
        if final_aligned > prev_end:
            data_parts.append(b"\x00" * (final_aligned - prev_end))

        offset_blob = b"".join(struct.pack("<I", off) for off in offsets)
        data_blob = b"".join(data_parts)

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "wb") as f:
            f.write(header)
            f.write(name_blob)
            f.write(offset_blob)
            f.write(data_blob)

    # ── helpers ────────────────────────────────────────────

    def get(self, filename: str) -> Optional[PAK2Entry]:
        """Find an entry by exact filename."""
        for e in self.entries:
            if e.filename == filename:
                return e
        return None

    def add(self, filename: str, data: bytes):
        """Append a new file entry (no padding in data)."""
        self.entries.append(PAK2Entry(
            filename=filename, offset=0, size=len(data), _data=data,
        ))

    def remove(self, filename: str) -> bool:
        """Remove an entry. Returns True if found."""
        for i, e in enumerate(self.entries):
            if e.filename == filename:
                self.entries.pop(i)
                return True
        return False

    def replace(self, filename: str, data: bytes) -> bool:
        """Replace an entry's data. No padding — raw content only."""
        entry = self.get(filename)
        if entry:
            entry.data = data
            return True
        return False

    def extract(self, filename: str, output_path: str):
        """Extract a single file (clean, no alignment bytes)."""
        entry = self.get(filename)
        if entry is None:
            raise FileNotFoundError(f"File not in archive: {filename}")
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(entry.data)

    def extract_all(self, output_dir: str):
        """Extract all files to a directory."""
        for entry in self.entries:
            out_path = os.path.join(output_dir, entry.filename.lstrip("/"))
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(entry.data)

    def __repr__(self):
        total = sum(e.size for e in self.entries)
        return f"PAK2({self.path!r}, {len(self.entries)} files, {total:,} bytes, align={self.alignment})"

    def __len__(self):
        return len(self.entries)
