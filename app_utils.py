# -*- coding: utf-8 -*-
"""
app_utils.py — Fungsi utilitas umum untuk Aplikasi SIMPATI.
Berisi helper yang kompatibel untuk mode VSCode (dev) dan mode build (PyInstaller).
"""

import os
import sys
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize

def resource_path(relative_path: str) -> str:
    """
    Mengembalikan path absolut ke file resource (gambar, ikon, font, dsb)
    agar kompatibel di mode development maupun hasil build (.exe).
    """
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS  # Folder sementara PyInstaller
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def app_icon() -> QIcon:
    icon_path = resource_path("icons/iconKPU.ico")

    # 🔎 Biar ketahuan kalau path salah (sering kejadian saat dev/build)
    if not os.path.exists(icon_path):
        print(f"[WARN] Icon file tidak ditemukan: {icon_path}")
        return QIcon()

    ico = QIcon(icon_path)

    # ✅ Force-load ukuran umum (mencegah taskbar kotak pada first show)
    for s in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        _ = ico.pixmap(QSize(s, s))

    if ico.isNull():
        print(f"[WARN] QIcon kosong walau file ada: {icon_path}")

    return ico