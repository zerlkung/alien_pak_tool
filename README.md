# Alien PAK Tool 🎬

**PAK2 archive editor for Alien: Isolation (PC & PS5)**

Built with Python + CustomTkinter (Material Design).  
Reverse-engineered from [OpenCAGE](https://github.com/MattFiler/OpenCAGE) / [CathodeLib](https://github.com/OpenCAGE/CathodeLib).

---

## 🇹🇭 ภาษาไทย

### คืออะไร
โปรแกรมแก้ไขไฟล์ PAK2 ของเกม Alien: Isolation รองรับทั้ง PC (`UI.PAK`) และ PS5 (`UI_PS5.PAK`)  
ใช้ Python + CustomTkinter (Material Design GUI)

### วิธีติดตั้ง

```bash
pip install -r requirements.txt
```

### วิธีใช้

```bash
# เปิดโปรแกรม
python app.py

# หรือเปิดไฟล์ PAK โดยตรง
python app.py path/to/UI_PS5.PAK
```

### ฟีเจอร์
| ฟีเจอร์ | คำอธิบาย |
|---------|-----------|
| 📂 Open | เปิดไฟล์ PAK2 (PC/PS5) |
| 📤 Extract | ดึงไฟล์ออกมาแก้ไข |
| 🔄 Replace | แทนที่ไฟล์ (เก็บ alignment อัตโนมัติ) |
| ➕ Import | เพิ่มไฟล์ใหม่เข้า PAK |
| 🗑️ Delete | ลบไฟล์ออกจาก PAK |
| 📦 Extract All | ดึงทุกไฟล์ออกมาทีเดียว |
| 🔍 Search | ค้นหา/กรองไฟล์ |
| 🖼️ Preview | ดูตัวอย่างรูป DDS (BC1 decode) |
| 📋 Hex View | ดูข้อมูล binary แบบ hex dump |
| 💾 Save | บันทึก PAK |

### ไฟล์ที่แก้ไขได้ (PS5)
- `FONTS_EN.GFX`, `FONTS_RU.GFX` — Plain GFX แก้ด้วย [JPEXS](https://github.com/jindrapetrik/jpexs-decompiler)
- `GFXFONTLIB.GFX` — Plain GFX (บางไฟล์มี content padding)
- `*.DDS` — Texture files

### ไฟล์ที่เข้ารหัส (แก้ไขไม่ได้)
- PC `FONTS_EN.GFX`, `FONTS_RU.GFX` — เข้ารหัส
- PS5 บางไฟล์ — เข้ารหัส (ตัวเกม decrypt ตอน runtime)

### Workflow การแก้ไข GFX
1. `Extract` → ได้ไฟล์ .GFX สะอาด
2. แก้ไขด้วย [JPEXS Flash Decompiler](https://github.com/jindrapetrik/jpexs-decompiler)
3. `Replace` → เลือกไฟล์ที่แก้แล้ว → alignment ถูกจัดการอัตโนมัติ
4. `Save` → เขียนกลับ PAK

### เครดิต
- [OpenCAGE](https://github.com/MattFiler/OpenCAGE) — MattFiler & OpenCAGE team
- [CathodeLib](https://github.com/OpenCAGE/CathodeLib) — PAK2 format reverse-engineering
- [AlienBML](https://github.com/x1nixmzeng/AlienBML) — x1nixmzeng
- Alien: Isolation — Creative Assembly / SEGA
- Alien PAK Tool — zerlkung

---

## 🇬🇧 English

### What
PAK2 archive editor for Alien: Isolation. Supports PC (`UI.PAK`) and PS5 (`UI_PS5.PAK`) formats.  
Built with Python + CustomTkinter (Material Design GUI).

### Install

```bash
pip install -r requirements.txt
```

### Usage

```bash
# Launch GUI
python app.py

# Open PAK file directly
python app.py path/to/UI_PS5.PAK
```

### Features
| Feature | Description |
|---------|-------------|
| 📂 Open | Open PAK2 files (PC/PS5) |
| 📤 Extract | Extract selected file |
| 🔄 Replace | Replace file (auto-preserves alignment) |
| ➕ Import | Add new file to PAK |
| 🗑️ Delete | Remove file from PAK |
| 📦 Extract All | Batch extract all files |
| 🔍 Search | Filter files by name |
| 🖼️ Preview | DDS image preview (BC1 decoder) |
| 📋 Hex View | Binary hex dump viewer |
| 💾 Save | Write PAK back to disk |

### Editable files (PS5)
- `FONTS_EN.GFX`, `FONTS_RU.GFX` — Plain GFX (edit with [JPEXS](https://github.com/jindrapetrik/jpexs-decompiler))
- `GFXFONTLIB.GFX` — Plain GFX (some files have content-level padding)
- `*.DDS` — Texture files

### Encrypted files (not editable)
- PC `FONTS_EN.GFX`, `FONTS_RU.GFX` — Encrypted
- Some PS5 files — Encrypted (game decrypts at runtime)

### GFX Editing Workflow
1. `Extract` → Get clean .GFX file
2. Edit with [JPEXS Flash Decompiler](https://github.com/jindrapetrik/jpexs-decompiler)
3. `Replace` → Select edited file → alignment handled automatically
4. `Save` → Write back to PAK

### Credits
- [OpenCAGE](https://github.com/MattFiler/OpenCAGE) — MattFiler & OpenCAGE team
- [CathodeLib](https://github.com/OpenCAGE/CathodeLib) — PAK2 format reverse-engineering
- [AlienBML](https://github.com/x1nixmzeng/AlienBML) — x1nixmzeng
- Alien: Isolation — Creative Assembly / SEGA
- Alien PAK Tool — zerlkung

---

## 📁 Project Structure

```
alien_pak_tool/
  pak2.py          # PAK2 format parser (pure Python, no deps)
  app.py           # Material Design GUI (CustomTkinter)
  requirements.txt # Python dependencies
  run.bat          # Windows quick launch
  CLAUDE.md        # Claude Code project context
  README.md        # This file
```

## ⚠️ Notes

- **Back up your PAK files before editing!**
- PAK format uses 4-byte alignment between files — the tool handles this automatically
- Some PS5 files have extra null byte padding in their content (from the build tool, not PAK format)
- PS5 `FONTS_EN.GFX` is plain GFX and fully editable — use it as a base for font mods
- PC font files are encrypted — extract PS5 versions instead

## 🔧 Technical Details

### PAK2 Format
```
Header (16 bytes):
  "PAK2"        — magic (4 bytes)
  rel_offset    — uint32 (offset_table_pos - 16)
  num_files     — uint32
  alignment     — uint32 (always 4)

Name Table (rel_offset bytes):
  Null-terminated filenames

Offset Table (num_files × 4 bytes):
  Cumulative end-positions (uint32 LE)
  File i content: align_up(prev_end, 4) to offset_table[i]

File Data:
  Raw binary, 4-byte aligned between files
  No compression, no encryption (at PAK level)
```
