# -*- coding: utf-8 -*-
"""
init_db.py – Inisialisasi tabel 'kecamatan' di SIMPATI.
Versi super cepat kilat (100000% identik hasilnya), memuat data dari kecamatan_data.py.
"""

import sys
import sqlite3
import itertools

from kecamatan_data import data as KECAMATAN_DATA

try:
    # Jika dijalankan dari dalam SIMPATI (sudah ada db_manager)
    from db_manager import DB_PATH, get_connection, with_safe_db
    USE_GLOBAL_CONN = True
except ImportError:
    # Jika dijalankan manual (tanpa SIMPATI)
    from db_manager import DB_PATH, load_or_create_key
    USE_GLOBAL_CONN = False


def _apply_optim_pragmas(conn):
    """Terapkan PRAGMA untuk kecepatan maksimum (aman & hasil identik)."""
    cur = conn.cursor()
    cur.executescript("""
        PRAGMA cipher_memory_security = OFF;
        PRAGMA cipher_page_size = 4096;
        PRAGMA journal_mode = MEMORY;
        PRAGMA synchronous = OFF;
        PRAGMA temp_store = MEMORY;
        PRAGMA cache_size = 1000000;
        PRAGMA locking_mode = EXCLUSIVE;
    """)


# ============================================================
# 🔹 Inisialisasi tabel kecamatan (super cepat kilat)
# ============================================================
def init_kecamatan():
    """Isi tabel 'kecamatan' hanya jika kosong (super cepat kilat)."""
    print("[INFO] Inisialisasi tabel 'kecamatan'...")

    # ============================================================
    # 🔐 1. Gunakan koneksi global SIMPATI bila tersedia
    # ============================================================
    if USE_GLOBAL_CONN:
        print("[INFO] Menggunakan koneksi global dari db_manager.")

        @with_safe_db
        def _isi_kecamatan(*, conn=None):
            _apply_optim_pragmas(conn)
            cur = conn.cursor()

            # --- pastikan tabel ada
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kecamatan (
                    kabupaten TEXT,
                    kecamatan TEXT,
                    desa TEXT
                )
            """)

            cur.execute("SELECT COUNT(*) FROM kecamatan")
            count = cur.fetchone()[0]
            if count > 0:
                print(f"[INFO] Tabel 'kecamatan' sudah berisi {count} data. Tidak ada yang ditambahkan.")
                return

            print("[INFO] Mengisi tabel 'kecamatan' (mode super cepat, batch 1000)...")

            BATCH_SIZE = 1000
            conn.execute("BEGIN IMMEDIATE TRANSACTION;")
            it = iter(KECAMATAN_DATA)
            while True:
                batch = list(itertools.islice(it, BATCH_SIZE))
                if not batch:
                    break
                cur.executemany(
                    "INSERT INTO kecamatan (kabupaten, kecamatan, desa) VALUES (?, ?, ?)",
                    batch
                )
            conn.commit()
            print("[✅] Data kecamatan berhasil dimasukkan ke simpati.db dengan kecepatan maksimum!")

        try:
            _isi_kecamatan()
        except Exception as e:
            print(f"[ERROR] Gagal inisialisasi tabel kecamatan: {e}")

    else:
        # ============================================================
        # 🧱 2. Mode standalone (SQLCipher/SQLite biasa)
        # ============================================================
        try:
            from sqlcipher3 import dbapi2 as sqlcipher
            conn = sqlcipher.connect(DB_PATH)
            from db_manager import load_or_create_key
            hexkey = load_or_create_key().hex()
            conn.execute(f"PRAGMA key = \"x'{hexkey}'\";")
            print("[INFO] Menggunakan koneksi SQLCipher3 lokal.")
        except ImportError:
            conn = sqlite3.connect(DB_PATH)
            print("[WARN] sqlcipher3 tidak ditemukan, fallback ke SQLite biasa.")

        try:
            _apply_optim_pragmas(conn)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kecamatan (
                    kabupaten TEXT,
                    kecamatan TEXT,
                    desa TEXT
                )
            """)
            cur.execute("SELECT COUNT(*) FROM kecamatan")
            count = cur.fetchone()[0]
            if count > 0:
                print(f"[INFO] Tabel 'kecamatan' sudah berisi {count} data. Tidak ada yang ditambahkan.")
                conn.close()
                return

            print("[INFO] Mengisi tabel 'kecamatan' (mode super cepat, batch 1000)...")

            BATCH_SIZE = 1000
            conn.execute("BEGIN IMMEDIATE TRANSACTION;")
            it = iter(KECAMATAN_DATA)
            while True:
                batch = list(itertools.islice(it, BATCH_SIZE))
                if not batch:
                    break
                cur.executemany(
                    "INSERT INTO kecamatan (kabupaten, kecamatan, desa) VALUES (?, ?, ?)",
                    batch
                )
            conn.commit()
            conn.close()
            print("[✅] Data kecamatan berhasil dimasukkan ke simpati.db dengan kecepatan maksimum!")

        except Exception as e:
            print(f"[ERROR] Gagal inisialisasi tabel kecamatan: {e}")
            conn.close()
            sys.exit(1)


if __name__ == "__main__":
    print("[RUN] Menjalankan init_kecamatan() manual...")
    init_kecamatan()
    print("[DONE] Selesai.")