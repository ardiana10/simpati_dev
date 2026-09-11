# -*- coding: utf-8 -*-
"""
init_db.py – Inisialisasi tabel 'kecamatan' di SIMPATI.
Versi diperbaiki: tidak lagi membuka transaksi manual di atas koneksi
bersama (menyebabkan silent-fail "cannot start a transaction within a
transaction"), dan error sekarang dicatat ke file log agar terlihat
walau dijalankan sebagai EXE tanpa console.
"""

import sys
import sqlite3
import itertools
import traceback
from pathlib import Path

from kecamatan_data import data as KECAMATAN_DATA

try:
    # Jika dijalankan dari dalam SIMPATI (sudah ada db_manager)
    from db_manager import DB_PATH, get_connection, with_safe_db
    USE_GLOBAL_CONN = True
except ImportError:
    # Jika dijalankan manual (tanpa SIMPATI)
    from db_manager import DB_PATH, load_or_create_key
    USE_GLOBAL_CONN = False

LOG_PATH = Path(DB_PATH).parent / "init_kecamatan_error.log"


def _log_error(msg: str):
    """Catat error ke file log (print saja tidak kelihatan di EXE)."""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass
    print(msg)


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
    """)


def _insert_batches(conn, cur, data_list):
    """Insert data secara batch TANPA membuka transaksi manual di atas
    koneksi yang sudah dikelola pihak lain (with_safe_db / get_connection).
    sqlite3/sqlcipher3 otomatis membuka transaksi implisit begitu ada
    statement DML pertama, jadi kita cukup commit di akhir."""
    BATCH_SIZE = 1000
    it = iter(data_list)
    total = 0
    while True:
        batch = list(itertools.islice(it, BATCH_SIZE))
        if not batch:
            break
        cur.executemany(
            "INSERT INTO kecamatan (kabupaten, kecamatan, desa) VALUES (?, ?, ?)",
            batch
        )
        total += len(batch)
    conn.commit()
    return total


# ============================================================
# 🔹 Inisialisasi tabel kecamatan (super cepat kilat)
# ============================================================
def init_kecamatan():
    """Isi tabel 'kecamatan' hanya jika kosong (super cepat kilat)."""
    print("[INFO] Inisialisasi tabel 'kecamatan'...")

    # 🔎 Sanity check data sumber SEBELUM masuk ke DB
    data_list = list(KECAMATAN_DATA)  # paksa jadi list — aman kalau sumbernya generator
    if not data_list:
        _log_error("[ERROR] KECAMATAN_DATA kosong! Cek isi kecamatan_data.py "
                    "(mungkin generator yang sudah habis dipakai, atau file salah import).")
        return
    print(f"[INFO] {len(data_list)} baris siap dimasukkan (contoh baris pertama: {data_list[0]}).")

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
            total = _insert_batches(conn, cur, data_list)

            # 🔎 Verifikasi setelah commit — ini yang membuktikan datanya benar tersimpan
            cur.execute("SELECT COUNT(*) FROM kecamatan")
            verify_count = cur.fetchone()[0]
            if verify_count == 0:
                _log_error(f"[ERROR] Insert dijalankan ({total} baris) tapi COUNT setelah "
                            f"commit tetap 0. Kemungkinan koneksi 'conn' dari with_safe_db "
                            f"bukan koneksi persisten ke {DB_PATH}, atau ada rollback lain "
                            f"yang terjadi setelah fungsi ini selesai.")
            else:
                print(f"[✅] Data kecamatan berhasil dimasukkan ({verify_count} baris) ke simpati.db!")

        try:
            _isi_kecamatan()
        except Exception:
            _log_error("[ERROR] Gagal inisialisasi tabel kecamatan:\n" + traceback.format_exc())

    else:
        # ============================================================
        # 🧱 2. Mode standalone (SQLCipher/SQLite biasa)
        # ============================================================
        conn = None
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
            total = _insert_batches(conn, cur, data_list)

            cur.execute("SELECT COUNT(*) FROM kecamatan")
            verify_count = cur.fetchone()[0]
            conn.close()

            if verify_count == 0:
                _log_error(f"[ERROR] Insert dijalankan ({total} baris) tapi COUNT setelah commit tetap 0.")
            else:
                print(f"[✅] Data kecamatan berhasil dimasukkan ({verify_count} baris) ke simpati.db!")

        except Exception:
            _log_error("[ERROR] Gagal inisialisasi tabel kecamatan:\n" + traceback.format_exc())
            if conn is not None:
                conn.close()
            sys.exit(1)


if __name__ == "__main__":
    print("[RUN] Menjalankan init_kecamatan() manual...")
    init_kecamatan()
    print("[DONE] Selesai.")