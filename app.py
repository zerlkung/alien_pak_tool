#!/usr/bin/env python
"""
Deepor PAK Editor — Material Design PAK2 file editor for Alien: Isolation.
Supports PC UI.PAK, ANIMATION.PAK, and PS5 UI_PS5.PAK.

Built with CustomTkinter (Material Design GUI) + pure-Python PAK2 parser.
"""

import os
import sys
import io
import struct
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from pak2 import PAK2, PAK2Entry

# ── Constants ─────────────────────────────────────────────

APP_TITLE = "Deepor PAK Editor"
APP_VERSION = "1.0.0"
WINDOW_SIZE = "1280x800"

# Material Design colors
ACCENT = "#6200EE"
ACCENT_LIGHT = "#BB86FC"
SURFACE = "#1E1E1E"
SURFACE_VARIANT = "#2D2D2D"
BACKGROUND = "#121212"
ON_SURFACE = "#E0E0E0"
ERROR = "#CF6679"
SUCCESS = "#03DAC6"

# File type icons
FILE_ICONS = {
    ".GFX": "🎬",
    ".DDS": "🖼️",
    ".PNG": "🖼️",
    ".TGA": "🖼️",
    ".SWF": "🎬",
    ".TXT": "📄",
}
DEFAULT_ICON = "📄"
FOLDER_ICON = "📁"


# ── Helpers ───────────────────────────────────────────────

def get_file_icon(filename: str) -> str:
    _, ext = os.path.splitext(filename.upper())
    # check both single and double extensions (e.g., .PNG.DDS)
    for double in [".PNG.DDS", ".TGA.DDS", ".DXT1.DDS", ".DXT5.DDS"]:
        if filename.upper().endswith(double):
            return "🖼️"
    return FILE_ICONS.get(ext, DEFAULT_ICON)


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / 1024 / 1024:.2f} MB"


def try_decode_dds(data: bytes):
    """Try to decode a DDS texture to a PIL Image. Returns None on failure."""
    try:
        from PIL import Image
    except ImportError:
        return None

    if len(data) < 148:
        return None
    if data[:4] != b"DDS ":
        return None

    # Parse DDS header
    height = struct.unpack_from("<I", data, 12)[0]
    width = struct.unpack_from("<I", data, 16)[0]
    fourcc = data[84:88]

    # DX10 extension header
    if fourcc == b"DX10":
        dxgi_format = struct.unpack_from("<I", data, 128)[0]
        pixel_data_offset = 148
    else:
        dxgi_format = None
        pixel_data_offset = 128

    # Only attempt simple uncompressed formats
    if dxgi_format is None:
        # DXT1: try rough decode
        if fourcc == b"DXT1":
            try:
                # basic BC1 decode — block decompression
                return _decode_bc1(data, width, height, pixel_data_offset)
            except Exception:
                return None
        return None

    # DX10 uncompressed or simple formats
    # DXGI_FORMAT_R8G8B8A8_UNORM = 28, B8G8R8A8_UNORM = 87
    if dxgi_format in (28, 87):
        try:
            raw = data[pixel_data_offset:pixel_data_offset + width * height * 4]
            if len(raw) < width * height * 4:
                return None
            if dxgi_format == 87:  # BGRA → RGBA
                raw = bytearray(raw)
                for i in range(0, len(raw), 4):
                    raw[i], raw[i + 2] = raw[i + 2], raw[i]
                raw = bytes(raw)
            return Image.frombytes("RGBA", (width, height), raw, "raw")
        except Exception:
            return None

    # R8_UNORM = 61
    if dxgi_format == 61:
        try:
            raw = data[pixel_data_offset:pixel_data_offset + width * height]
            return Image.frombytes("L", (width, height), raw, "raw")
        except Exception:
            return None

    return None


def _decode_bc1(data: bytes, width: int, height: int, offset: int):
    """Minimal BC1/DXT1 decoder. Returns PIL Image or None."""
    from PIL import Image
    blocks_x = (width + 3) // 4
    blocks_y = (height + 3) // 4
    pixels = bytearray(width * height * 4)

    for by in range(blocks_y):
        for bx in range(blocks_x):
            block_off = offset + (by * blocks_x + bx) * 8
            if block_off + 8 > len(data):
                break
            c0, c1 = struct.unpack_from("<HH", data, block_off)
            color0 = _rgb565_to_rgba(c0)
            color1 = _rgb565_to_rgba(c1)
            table = struct.unpack_from("<I", data, block_off + 4)[0]

            colors = [
                (*color0, 255),
                (*color1, 255),
                _lerp2_3(color0, color1) + (255,),
                _lerp1_3(color0, color1) + (255,),
            ] if c0 > c1 else [
                (*color0, 255),
                (*color1, 255),
                _lerp_half(color0, color1) + (255,),
                (0, 0, 0, 0),
            ]

            for py in range(4):
                for px in range(4):
                    idx = (table >> ((py * 4 + px) * 2)) & 3
                    pixel_x = bx * 4 + px
                    pixel_y = by * 4 + py
                    if pixel_x < width and pixel_y < height:
                        off = (pixel_y * width + pixel_x) * 4
                        c = colors[idx]
                        pixels[off:off+4] = bytes(c)
    return Image.frombytes("RGBA", (width, height), bytes(pixels))


def _rgb565_to_rgba(c: int) -> tuple:
    r = ((c >> 11) & 0x1F) * 255 // 31
    g = ((c >> 5) & 0x3F) * 255 // 63
    b = (c & 0x1F) * 255 // 31
    return (r, g, b)


def _lerp2_3(a, b):
    return tuple((2 * a[i] + b[i]) // 3 for i in range(3))


def _lerp1_3(a, b):
    return tuple((a[i] + 2 * b[i]) // 3 for i in range(3))


def _lerp_half(a, b):
    return tuple((a[i] + b[i]) // 2 for i in range(3))


# ── Main App ──────────────────────────────────────────────

class PAKEditor(ctk.CTk):
    """Main PAK Editor application window."""

    def __init__(self):
        super().__init__()

        self.pak: Optional[PAK2] = None
        self.pak_path: Optional[str] = None
        self.modified = False
        self._current_preview = None

        self._setup_window()
        self._build_ui()

    # ── Window setup ──────────────────────────────────

    def _setup_window(self):
        self.title(APP_TITLE)
        self.geometry(WINDOW_SIZE)
        self.minsize(900, 600)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Center window
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = 1280, 800
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI construction ───────────────────────────────

    def _build_ui(self):
        # Menu bar
        self._build_menu()

        # Main layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)  # toolbar
        self.grid_rowconfigure(1, weight=1)  # content
        self.grid_rowconfigure(2, weight=0)  # status bar

        self._build_toolbar()
        self._build_content()
        self._build_statusbar()

    def _build_menu(self):
        menubar = tk.Menu(self, bg=SURFACE, fg=ON_SURFACE, activebackground=ACCENT)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open PAK...", command=self._open_pak, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self._save_pak, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self._save_pak_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Import File...", command=self._import_file)
        edit_menu.add_command(label="Replace Selected...", command=self._replace_file)
        edit_menu.add_command(label="Delete Selected", command=self._delete_file)
        edit_menu.add_separator()
        edit_menu.add_command(label="Extract Selected...", command=self._extract_file)
        edit_menu.add_command(label="Extract All...", command=self._extract_all)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)

        menubar.add_cascade(label="File", menu=file_menu)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)
        self._file_menu = file_menu

        # Keyboard shortcuts
        self.bind_all("<Control-o>", lambda e: self._open_pak())
        self.bind_all("<Control-s>", lambda e: self._save_pak())

    def _build_toolbar(self):
        toolbar = ctk.CTkFrame(self, height=48, fg_color=SURFACE_VARIANT)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=0, pady=0)
        toolbar.grid_propagate(False)

        # Left: action buttons
        btn_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_frame.pack(side="left", padx=8, pady=6)

        self.btn_open = ctk.CTkButton(
            btn_frame, text="📂 Open PAK", width=100, command=self._open_pak,
            fg_color=ACCENT, hover_color=ACCENT_LIGHT,
        )
        self.btn_open.pack(side="left", padx=2)

        self.btn_extract = ctk.CTkButton(
            btn_frame, text="📤 Extract", width=90, command=self._extract_file,
            state="disabled",
        )
        self.btn_extract.pack(side="left", padx=2)

        self.btn_replace = ctk.CTkButton(
            btn_frame, text="🔄 Replace", width=90, command=self._replace_file,
            state="disabled",
        )
        self.btn_replace.pack(side="left", padx=2)

        self.btn_import = ctk.CTkButton(
            btn_frame, text="➕ Import", width=90, command=self._import_file,
            state="disabled",
        )
        self.btn_import.pack(side="left", padx=2)

        self.btn_delete = ctk.CTkButton(
            btn_frame, text="🗑️ Delete", width=90, command=self._delete_file,
            state="disabled", fg_color=ERROR,
        )
        self.btn_delete.pack(side="left", padx=2)

        # Right: save + extract all
        btn_frame_r = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_frame_r.pack(side="right", padx=8, pady=6)

        self.btn_export_all = ctk.CTkButton(
            btn_frame_r, text="📦 Extract All", width=110, command=self._extract_all,
            state="disabled",
        )
        self.btn_export_all.pack(side="right", padx=2)

        self.btn_save = ctk.CTkButton(
            btn_frame_r, text="💾 Save", width=80, command=self._save_pak,
            state="disabled", fg_color=SUCCESS, hover_color="#029985",
        )
        self.btn_save.pack(side="right", padx=2)

    def _build_content(self):
        # Paned window: tree | preview
        paned = tk.PanedWindow(self, bg=BACKGROUND, sashwidth=3, orient=tk.HORIZONTAL)
        paned.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)

        # ── Left: file tree ──
        tree_frame = ctk.CTkFrame(paned, fg_color=SURFACE)
        paned.add(tree_frame, width=350, minsize=200)

        # Search bar
        search_frame = ctk.CTkFrame(tree_frame, fg_color="transparent")
        search_frame.pack(fill="x", padx=6, pady=(6, 2))

        ctk.CTkLabel(search_frame, text="🔍", width=20).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._filter_tree())
        self.search_entry = ctk.CTkEntry(
            search_frame, placeholder_text="Filter files...", textvariable=self.search_var,
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # Tree
        tree_container = ctk.CTkFrame(tree_frame, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=2, pady=2)

        # Use ttk.Treeview inside CTk for hierarchical display
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=SURFACE,
            foreground=ON_SURFACE,
            fieldbackground=SURFACE,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background=SURFACE_VARIANT,
            foreground=ON_SURFACE,
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "#FFFFFF")])

        self.tree = ttk.Treeview(
            tree_container, show="tree", selectmode="browse", style="Treeview",
        )
        self.tree.pack(side="left", fill="both", expand=True)

        tree_scroll = ctk.CTkScrollbar(tree_container, command=self.tree.yview)
        tree_scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=tree_scroll.set)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # ── Right: preview ──
        preview_frame = ctk.CTkFrame(paned, fg_color=SURFACE)
        paned.add(preview_frame, width=700, minsize=400)

        # Placeholder
        self.preview_placeholder = ctk.CTkLabel(
            preview_frame,
            text="📂 Open a PAK file to begin\n\n"
                 "Supported formats:\n"
                 "• UI.PAK / UI_PS5.PAK\n"
                 "• ANIMATION.PAK\n"
                 "• COMMANDS.PAK",
            font=("Segoe UI", 14),
            text_color="#888888",
            justify="center",
        )
        self.preview_placeholder.pack(expand=True, fill="both")

        # File info bar
        self.preview_info_frame = ctk.CTkFrame(preview_frame, fg_color=SURFACE_VARIANT, height=40)

        self.preview_name_label = ctk.CTkLabel(
            self.preview_info_frame, text="", font=("Segoe UI", 11),
        )
        self.preview_name_label.pack(side="left", padx=10)

        self.preview_size_label = ctk.CTkLabel(
            self.preview_info_frame, text="", font=("Segoe UI", 11), text_color="#888888",
        )
        self.preview_size_label.pack(side="right", padx=10)

        # Image preview label (will be packed when showing an image)
        self.preview_image_label = ctk.CTkLabel(preview_frame, text="")

        # Hex preview text
        self.preview_text = ctk.CTkTextbox(
            preview_frame, font=("Consolas", 11), wrap="none", fg_color=SURFACE_VARIANT,
        )

        self._preview_frame = preview_frame

    def _build_statusbar(self):
        self.statusbar = ctk.CTkFrame(self, height=28, fg_color=SURFACE_VARIANT)
        self.statusbar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=0, pady=0)
        self.statusbar.grid_propagate(False)

        self.status_label = ctk.CTkLabel(
            self.statusbar, text="Ready — Open a PAK file to begin",
            font=("Segoe UI", 9), text_color="#888888",
        )
        self.status_label.pack(side="left", padx=10, pady=2)

        self.status_count = ctk.CTkLabel(
            self.statusbar, text="", font=("Segoe UI", 9), text_color="#888888",
        )
        self.status_count.pack(side="right", padx=10, pady=2)

    # ── Actions ───────────────────────────────────────

    def _open_pak(self):
        if self.modified:
            if not messagebox.askyesno("Unsaved Changes", "Discard unsaved changes?"):
                return

        path = filedialog.askopenfilename(
            title="Open PAK File",
            filetypes=[
                ("PAK files", "*.PAK *.pak"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        try:
            self.pak = PAK2(path)
            self.pak_path = path
            self.modified = False
            self._populate_tree()
            self._update_title()
            self._enable_actions(True)
            self._clear_preview()
            self.status_label.configure(text=f"Loaded: {os.path.basename(path)} — {len(self.pak)} files")
            self.status_count.configure(text=format_size(sum(e.size for e in self.pak.entries)))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open PAK:\n{e}")

    def _save_pak(self):
        if not self.pak:
            return
        try:
            self.pak.save(self.pak_path)
            self.modified = False
            self._update_title()
            self.status_label.configure(text=f"Saved: {os.path.basename(self.pak_path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save:\n{e}")

    def _save_pak_as(self):
        if not self.pak:
            return
        path = filedialog.asksaveasfilename(
            title="Save PAK As...",
            defaultextension=".PAK",
            filetypes=[("PAK files", "*.PAK"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.pak.save(path)
            self.pak_path = path
            self.modified = False
            self._update_title()
            self.status_label.configure(text=f"Saved: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save:\n{e}")

    def _extract_file(self):
        sel = self._get_selected_entry()
        if sel is None:
            return
        filename = sel.filename
        safe_name = filename.replace("/", "_").replace("\\", "_")
        path = filedialog.asksaveasfilename(
            title=f"Extract: {filename}",
            initialfile=safe_name,
            filetypes=[("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.pak.extract(filename, path)
            self.status_label.configure(text=f"Extracted: {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Extract failed:\n{e}")

    def _extract_all(self):
        if not self.pak:
            return
        folder = filedialog.askdirectory(title="Select output folder")
        if not folder:
            return
        try:
            self.pak.extract_all(folder)
            self.status_label.configure(text=f"All {len(self.pak)} files extracted to {folder}")
            messagebox.showinfo("Done", f"Extracted {len(self.pak)} files.")
        except Exception as e:
            messagebox.showerror("Error", f"Extract all failed:\n{e}")

    def _replace_file(self):
        sel = self._get_selected_entry()
        if sel is None:
            return
        path = filedialog.askopenfilename(
            title=f"Replace: {sel.filename}",
            filetypes=[("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "rb") as f:
                data = f.read()
            self.pak.replace(sel.filename, data)
            self.modified = True
            self._update_title()
            self._update_preview(sel.filename)
            self.status_label.configure(text=f"Replaced: {sel.filename} ({format_size(len(data))})")
        except Exception as e:
            messagebox.showerror("Error", f"Replace failed:\n{e}")

    def _import_file(self):
        if not self.pak:
            return
        path = filedialog.askopenfilename(
            title="Import file into PAK",
            filetypes=[("All files", "*.*")],
        )
        if not path:
            return

        # Ask for the internal path/name
        dialog = ctk.CTkInputDialog(
            title="Import File",
            text="Enter internal path/name for the file\n(e.g. DATA/UI/MYFILE.GFX):",
        )
        internal_name = dialog.get_input()
        if not internal_name:
            return

        try:
            with open(path, "rb") as f:
                data = f.read()
            self.pak.add(internal_name, data)
            self.modified = True
            self._populate_tree()
            self._update_title()
            self.status_label.configure(text=f"Imported: {internal_name} ({format_size(len(data))})")
        except Exception as e:
            messagebox.showerror("Error", f"Import failed:\n{e}")

    def _delete_file(self):
        sel = self._get_selected_entry()
        if sel is None:
            return
        if not messagebox.askyesno(
            "Confirm Delete",
            f"Delete '{sel.filename}'?\nThis cannot be undone until you reload the PAK.",
        ):
            return
        self.pak.remove(sel.filename)
        self.modified = True
        self._populate_tree()
        self._clear_preview()
        self._update_title()
        self.status_label.configure(text=f"Deleted: {sel.filename}")

    # ── Tree ──────────────────────────────────────────

    def _populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        if not self.pak:
            return

        # Build folder hierarchy
        folders: dict = {}
        for entry in self.pak.entries:
            parts = entry.filename.replace("\\", "/").split("/")
            path_so_far = ""
            for i, part in enumerate(parts):
                parent = path_so_far
                path_so_far = (path_so_far + "/" + part) if path_so_far else part
                if path_so_far not in folders:
                    is_leaf = (i == len(parts) - 1)
                    folders[path_so_far] = {
                        "name": part,
                        "parent": parent,
                        "full_path": path_so_far,
                        "is_file": is_leaf,
                        "entry": entry if is_leaf else None,
                    }

        # Insert nodes
        node_ids = {"": ""}  # root
        # Sort: folders first, then files
        sorted_keys = sorted(
            folders.keys(),
            key=lambda k: (not folders[k]["is_file"], folders[k]["name"].lower()),
        )

        for key in sorted_keys:
            info = folders[key]
            parent_key = info["parent"]
            parent_id = node_ids.get(parent_key, "")

            icon = get_file_icon(info["name"]) if info["is_file"] else FOLDER_ICON
            display = f"{icon} {info['name']}"
            size_suffix = ""
            if info["is_file"] and info["entry"]:
                size_suffix = f"  ({format_size(info['entry'].size)})"

            iid = self.tree.insert(
                parent_id, "end",
                text=display + size_suffix,
                values=(key,),
                open=False,
            )
            node_ids[key] = iid

        self.status_count.configure(text=f"{len(self.pak)} files")

    def _filter_tree(self):
        query = self.search_var.get().lower()
        self.tree.delete(*self.tree.get_children())
        if not self.pak:
            return
        if not query:
            self._populate_tree()
            return

        # Flat list of matches
        for entry in self.pak.entries:
            name = entry.filename.lower()
            if query in name:
                icon = get_file_icon(entry.filename)
                display = f"{icon} {entry.filename}  ({format_size(entry.size)})"
                self.tree.insert("", "end", text=display, values=(entry.filename,))

    def _get_selected_entry(self) -> Optional[PAK2Entry]:
        sel = self.tree.selection()
        if not sel or not self.pak:
            return None
        values = self.tree.item(sel[0], "values")
        if not values:
            return None
        filename = values[0]
        return self.pak.get(filename)

    def _on_tree_select(self, event):
        entry = self._get_selected_entry()
        if entry:
            self._update_preview(entry.filename)
            self.btn_extract.configure(state="normal")
            self.btn_replace.configure(state="normal")
            self.btn_delete.configure(state="normal")
        else:
            self._clear_preview()

    # ── Preview ───────────────────────────────────────

    def _update_preview(self, filename: str):
        entry = self.pak.get(filename)
        if entry is None:
            return

        self._hide_all_previews()

        name = os.path.basename(filename)
        # Detect content-level padding (some PS5 files have 00 bytes before magic)
        n_pad = 0
        data = entry.data
        if len(data) >= 4:
            for sig in [b"GFX", b"DDS ", b"CFX", b"SWF"]:
                idx = data.find(sig, 0, 4)
                if idx > 0 and all(b == 0 for b in data[:idx]):
                    n_pad = idx
                    break

        size_text = format_size(entry.size)
        if n_pad > 0:
            size_text += f" (has {n_pad}B content padding)"
        self.preview_name_label.configure(text=name)
        self.preview_size_label.configure(text=size_text)
        self.preview_info_frame.pack(side="bottom", fill="x", padx=0, pady=0)

        # Try image preview for image-like files
        ext_upper = filename.upper()
        is_image = any(ext_upper.endswith(e) for e in (".DDS", ".PNG", ".TGA"))
        is_gfx = ext_upper.endswith(".GFX") or ext_upper.endswith(".SWF")

        if is_image and len(data) > 0:
            self._show_image_preview(data)
        elif is_gfx and len(data) > 3 and data[:3] == b"GFX":
            self._show_gfx_preview(data)
        elif is_gfx and n_pad > 0 and len(data) > n_pad + 3:
            self._show_gfx_preview(data[n_pad:])  # preview without content padding
        else:
            self._show_hex_preview(data)

    def _show_image_preview(self, data: bytes):
        # Try decoding DDS
        img = try_decode_dds(data)
        if img is None and data[:4] == b"DDS ":
            self._show_hex_preview(data, note="(DDS image — format not supported for preview)")
            return

        if img is None:
            self._show_hex_preview(data)
            return

        from PIL import ImageTk
        img.thumbnail((500, 500))
        self._current_preview = ImageTk.PhotoImage(img)

        self.preview_image_label.configure(image=self._current_preview, text="")
        self.preview_image_label.pack(expand=True, fill="both", padx=10, pady=10)

    def _show_gfx_preview(self, data: bytes):
        self._show_hex_preview(data, note="(Scaleform GFX file — binary Flash format)")

    def _show_hex_preview(self, data: bytes, note: str = ""):
        lines = []
        if note:
            lines.append(f"# {note}")
            lines.append("")

        # Show first 2KB as hex dump
        preview_len = min(len(data), 2048)
        for i in range(0, preview_len, 16):
            chunk = data[i:i+16]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"{i:08X}  {hex_part:<48s}  {ascii_part}")

        if len(data) > preview_len:
            lines.append(f"... ({format_size(len(data) - preview_len)} more)")

        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        self.preview_text.insert("1.0", "\n".join(lines))
        self.preview_text.configure(state="disabled")
        self.preview_text.pack(expand=True, fill="both", padx=6, pady=6)

    def _hide_all_previews(self):
        self.preview_placeholder.pack_forget()
        self.preview_text.pack_forget()
        self.preview_image_label.pack_forget()
        self.preview_info_frame.pack_forget()

    def _clear_preview(self):
        self._hide_all_previews()
        self.preview_placeholder.pack(expand=True, fill="both")
        self.preview_name_label.configure(text="")
        self.preview_size_label.configure(text="")

    # ── State ─────────────────────────────────────────

    def _enable_actions(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.btn_save.configure(state=state)
        self.btn_export_all.configure(state=state)
        self.btn_import.configure(state=state)
        # Extract/Replace/Delete require selection, so stay disabled until tree select

    def _update_title(self):
        title = APP_TITLE
        if self.pak_path:
            title += f" — {os.path.basename(self.pak_path)}"
        if self.modified:
            title += " ●"
        self.title(title)

    def _show_about(self):
        messagebox.showinfo(
            "About",
            f"{APP_TITLE} v{APP_VERSION}\n\n"
            "PAK2 archive editor for Alien: Isolation\n"
            "Supports PC and PS5 PAK files.\n\n"
            "Reverse-engineered from OpenCAGE AlienPAK / CathodeLib.\n"
            "Built with Python + CustomTkinter (Material Design).",
        )

    def _on_close(self):
        if self.modified:
            answer = messagebox.askyesnocancel(
                "Unsaved Changes",
                "Save changes before closing?",
            )
            if answer is None:
                return  # Cancel
            if answer:
                self._save_pak()
        self.destroy()
        sys.exit(0)


# ── Entry point ───────────────────────────────────────────

def main():
    app = PAKEditor()
    app.mainloop()


if __name__ == "__main__":
    # Can pass a PAK file as argument
    app = PAKEditor()
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if os.path.exists(path):
            try:
                app.pak = PAK2(path)
                app.pak_path = path
                app._populate_tree()
                app._update_title()
                app._enable_actions(True)
                app.status_label.configure(text=f"Loaded: {os.path.basename(path)} — {len(app.pak)} files")
                app.status_count.configure(text=format_size(sum(e.size for e in app.pak.entries)))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open: {e}")
    app.mainloop()
