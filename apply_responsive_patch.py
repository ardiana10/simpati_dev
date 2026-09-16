# -*- coding: utf-8 -*-
"""
apply_responsive_patch.py — menerapkan integrasi `responsive.py` ke Simpati.py
=============================================================================

Menjalankan 7 penggantian teks yang persis sama dengan yang dijelaskan di
INTEGRASI_RESPONSIVE.md, membuat backup lebih dulu, lalu memverifikasi bahwa
hasilnya masih valid secara sintaks.

Pemakaian (dari folder tempat Simpati.py berada):

    python apply_responsive_patch.py                 # terapkan
    python apply_responsive_patch.py --dry-run       # lihat saja, tanpa menulis
    python apply_responsive_patch.py --undo          # kembalikan dari backup

Aman dijalankan dua kali: penggantian yang sudah pernah diterapkan dilewati.
"""

import argparse
import py_compile
import shutil
import sys
import tempfile
from pathlib import Path

TARGET = "Simpati.py"
BACKUP = "Simpati.py.bak"


# (nama, teks_lama, teks_baru, jumlah_yang_diharapkan, penanda_sudah_dipatch)
#
# Penanda dipakai untuk idempotensi: bila string itu sudah ada di file, patch
# dilewati. Ini penting untuk patch 1 & 2, yang teks lamanya tetap muncul di
# dalam teks penggantinya sehingga tidak bisa dideteksi dari teks lama saja.
PATCHES = [
    (
        "1. Import modul responsive",
        "from about_dialog import show_about_dialog",
        "import responsive\nfrom about_dialog import show_about_dialog",
        1,
        "\nimport responsive\n",
    ),
    (
        "2. Pasang lapisan adaptasi di main()",
        '    app = QApplication(sys.argv)\n'
        '    app.setApplicationName("SIMPATI")\n'
        '    app.setStyle(QStyleFactory.create("Fusion"))',

        '    responsive.setup_high_dpi()   # WAJIB sebelum QApplication dibuat\n'
        '    app = QApplication(sys.argv)\n'
        '    app.setApplicationName("SIMPATI")\n'
        '    app.setStyle(QStyleFactory.create("Fusion"))\n'
        '    responsive.install(app)       # skala + auto-scroll dialog',
        1,
        "responsive.install(app)",
    ),
    (
        "3. Tabel: Stretch -> adaptif",
        "        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)",
        "        responsive.make_table_responsive(self.table)",
        11,
        None,
    ),
    (
        "4. Tabel utama MainWindow",
        "        self.table.verticalHeader().setDefaultSectionSize(24)\n"
        "        self.table.horizontalHeader().setFixedHeight(24)",
        "        responsive.make_table_responsive(self.table, row_h=24, header_h=24)",
        1,
        None,
    ),
    (
        "5. Lebar dock filter (MainWindow)",
        "            fixed_width = 320",
        "            fixed_width = responsive.dock_width(320)",
        1,
        None,
    ),
    (
        "6. FixedDockWidget.setWidget longgar",
        "        super().setWidget(widget)\n"
        "        widget.setFixedWidth(self._fixed_width)",
        "        super().setWidget(widget)\n"
        "        widget.setMinimumWidth(0)\n"
        "        widget.setMaximumWidth(self._fixed_width)",
        1,
        None,
    ),
    (
        "7. Lebar internal FilterSidebar",
        "        self._dock_width = 260  # Lebar dock harus selaras dengan FixedDockWidget",
        "        self._dock_width = responsive.dock_width(320)  # proporsional terhadap layar",
        1,
        None,
    ),
]


def undo(path: Path) -> int:
    bak = path.with_name(BACKUP)
    if not bak.exists():
        print(f"[GAGAL] Backup tidak ditemukan: {bak}")
        return 1
    shutil.copy2(bak, path)
    print(f"[OK] {path.name} dikembalikan dari {bak.name}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=TARGET, help="path ke Simpati.py")
    ap.add_argument("--dry-run", action="store_true", help="tampilkan rencana saja")
    ap.add_argument("--undo", action="store_true", help="kembalikan dari backup")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"[GAGAL] Tidak menemukan {path}. Jalankan dari folder Simpati.py.")
        return 1

    if args.undo:
        return undo(path)

    if not (path.parent / "responsive.py").exists():
        print("[GAGAL] responsive.py belum ada di folder yang sama dengan Simpati.py.")
        return 1

    src = path.read_text(encoding="utf-8")
    original = src

    applied, skipped, missing = 0, 0, 0
    print(f"Memproses {path}  ({len(src.splitlines())} baris)\n")

    for name, old, new, expect, guard in PATCHES:
        marker = guard if guard is not None else new
        if marker in src:
            print(f"  [LEWAT ] {name} — sudah diterapkan sebelumnya")
            skipped += 1
            continue
        found = src.count(old)
        if found == 0:
            if src.count(new) > 0:
                print(f"  [LEWAT ] {name} — sudah diterapkan sebelumnya")
                skipped += 1
            else:
                print(f"  [TIDAK ] {name} — pola tidak ditemukan, terapkan manual")
                missing += 1
            continue
        if found != expect:
            print(f"  [PERIKSA] {name} — ditemukan {found}x, diharapkan {expect}x")
        src = src.replace(old, new)
        print(f"  [OK    ] {name} — {found} penggantian")
        applied += 1

    print(f"\nRingkasan: {applied} diterapkan, {skipped} dilewati, {missing} perlu manual")

    if src == original:
        print("Tidak ada perubahan yang ditulis.")
        return 0

    # Verifikasi sintaks sebelum menimpa file asli.
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as tmp:
        tmp.write(src)
        tmp_path = Path(tmp.name)
    try:
        py_compile.compile(str(tmp_path), doraise=True)
    except py_compile.PyCompileError as e:
        print(f"\n[BATAL] Hasil patch tidak lolos cek sintaks:\n{e}")
        print("File asli TIDAK diubah.")
        return 1
    finally:
        tmp_path.unlink(missing_ok=True)

    if args.dry_run:
        print("\n(--dry-run) Sintaks hasil patch OK. File asli tidak ditulis.")
        return 0

    bak = path.with_name(BACKUP)
    if not bak.exists():
        shutil.copy2(path, bak)
        print(f"\nBackup dibuat: {bak.name}")
    else:
        print(f"\nBackup lama dipertahankan: {bak.name}")

    path.write_text(src, encoding="utf-8")
    print(f"Selesai. {path.name} sudah dipatch dan lolos cek sintaks.")
    print("Jalankan aplikasi; konsol akan menampilkan baris [responsive] saat start.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
