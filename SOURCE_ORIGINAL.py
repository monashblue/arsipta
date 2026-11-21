#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARSIPTA - Sistem Katalog Arsip Perjanjian
Versi: 0.4.0-beta (Fase 4: Konektivitas Hybrid Server Mandiri & Sinkronisasi Tim)
Lisensi: MIT License
Target Platform: Windows 10/11 64-bit (Python 3.14.10, PySide6)
"""

import sys
import os
import csv
import json
import socket
import sqlite3
import hashlib
import shutil
import unittest
import tempfile
import threading
import time
import http.server
import socketserver
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any

try:
    import openpyxl
    from openpyxl.styles import Font as ExcelFont, PatternFill, Alignment
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

from PySide6.QtCore import (
    Qt, Signal, QObject, QDate, QRect, QRectF, QPoint, QThread
)
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QLineEdit, QFrame,
    QStackedWidget, QScrollArea, QDialog, QFormLayout,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QRadioButton, QButtonGroup, QComboBox, QDateEdit, QCheckBox,
    QAbstractItemView, QFileDialog, QProgressBar, QTextEdit
)

# ==============================================================================
# LAYER 1: KONFIGURASI, KONSTANTA, DAN MODEL DATA
# ==============================================================================

APP_NAME = "ARSIPTA"
APP_TAGLINE = "Sistem Katalog Arsip"
APP_VERSION = "0.4.0-beta (Fase 4: Konektivitas Hybrid Server Mandiri & Sinkronisasi Tim)"
DEFAULT_DB_FILENAME = "arsipta_katalog.db"
TEMP_WORK_DIR = "arsipta_temp_work"
DEFAULT_SERVER_PORT = 8080
DEFAULT_SERVER_HOST = "0.0.0.0"
DEFAULT_SERVER_TOKEN = "arsipta_secret_token_2026"
DEFAULT_CLIENT_TIMEOUT = 5.0


@dataclass
class ArchiveRecord:
    """Representasi satu entitas arsip perjanjian."""
    id: Optional[int]
    nomor_dokumen: str
    judul_perjanjian: str
    pihak_terkait: str
    topik: str
    tanggal_mulai: str       # Format YYYY-MM-DD
    tanggal_berakhir: str    # Format YYYY-MM-DD
    status: str              # 'Aktif' atau 'Inaktif'
    lokasi_fisik: str
    file_sumber: str
    diperbarui_pada: str

    def to_dict(self) -> Dict[str, Any]:
        """Konversi entitas arsip ke dictionary untuk serialisasi JSON/API."""
        return {
            "id": self.id,
            "nomor_dokumen": self.nomor_dokumen,
            "judul_perjanjian": self.judul_perjanjian,
            "pihak_terkait": self.pihak_terkait,
            "topik": self.topik,
            "tanggal_mulai": self.tanggal_mulai,
            "tanggal_berakhir": self.tanggal_berakhir,
            "status": self.status,
            "lokasi_fisik": self.lokasi_fisik,
            "file_sumber": self.file_sumber,
            "diperbarui_pada": self.diperbarui_pada,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArchiveRecord":
        """Membentuk objek ArchiveRecord dari dictionary data JSON/API."""
        return cls(
            id=data.get("id"),
            nomor_dokumen=str(data.get("nomor_dokumen", "")).strip(),
            judul_perjanjian=str(data.get("judul_perjanjian", "")).strip(),
            pihak_terkait=str(data.get("pihak_terkait", "")).strip(),
            topik=str(data.get("topik", "")).strip(),
            tanggal_mulai=str(data.get("tanggal_mulai", "")).strip(),
            tanggal_berakhir=str(data.get("tanggal_berakhir", "")).strip(),
            status=str(data.get("status", "Aktif")).strip(),
            lokasi_fisik=str(data.get("lokasi_fisik", "")).strip(),
            file_sumber=str(data.get("file_sumber", "")).strip(),
            diperbarui_pada=str(data.get("diperbarui_pada", "")).strip(),
        )


@dataclass
class FilterCriteria:
    """Parameter penyaringan katalog arsip."""
    search_text: str = ""
    topik: str = "Semua Topik"
    status: str = "Semua Status"
    retensi: str = "Semua Retensi"
    use_date_range: bool = False
    date_from: str = ""
    date_to: str = ""


@dataclass
class UserSession:
    """Menyimpan informasi sesi pengguna aktif (Mode Lokal atau Server Kantor)."""
    username: str
    nama_lengkap: str
    peran: str               # 'Arsiparis' atau 'Administrator'
    mode_koneksi: str        # 'Mode Lokal' atau 'Mode Server Kantor'
    server_url: str = ""
    server_token: str = ""
    terautentikasi: bool = True


@dataclass
class SyncReport:
    """Laporan hasil sinkronisasi data arsip dengan server kantor."""
    success: bool
    aksi: str = "two_way"            # 'two_way', 'pull', 'push'
    dikirim: int = 0
    diterima: int = 0
    diperbarui_lokal: int = 0
    diperbarui_server: int = 0
    konflik_diselesaikan: int = 0
    pesan: str = ""
    waktu: str = ""
    daftar_kesalahan: List[str] = field(default_factory=list)


@dataclass
class ServerAuditLog:
    """Catatan riwayat akses dan aktivitas pada Server Kantor."""
    id: Optional[int]
    waktu: str
    client_ip: str
    username: str
    endpoint: str
    aksi: str
    status_code: int
    detail: str


# ==============================================================================
# LAYER 2: PENYIMPANAN & SINKRONISASI HYBRID (SQLite + Kesiapan Server)
# ==============================================================================

class StorageEngine:
    """
    Mesin penyimpanan SQLite lokal yang aman dan mandiri.
    Menjamin aplikasi tetap berjalan penuh tanpa koneksi internet.
    """

    def __init__(self, db_path: str = DEFAULT_DB_FILENAME):
        self.db_path = db_path
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _hash_password(self, raw_password: str) -> str:
        salt = "arsipta_internal_salt_2026"
        raw_bytes = f"{salt}:{raw_password}".encode("utf-8")
        return hashlib.sha256(raw_bytes).hexdigest()

    def _init_database(self) -> None:
        """Membuat tabel arsip, pengguna, dan log aktivitas jika belum ada."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS archives (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nomor_dokumen TEXT UNIQUE NOT NULL,
                    judul_perjanjian TEXT NOT NULL,
                    pihak_terkait TEXT NOT NULL,
                    topik TEXT NOT NULL,
                    tanggal_mulai TEXT NOT NULL,
                    tanggal_berakhir TEXT NOT NULL,
                    status TEXT NOT NULL,
                    lokasi_fisik TEXT DEFAULT '',
                    file_sumber TEXT DEFAULT '',
                    diperbarui_pada TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    nama_lengkap TEXT NOT NULL,
                    peran TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recent_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nama_file TEXT NOT NULL,
                    jalur_file TEXT NOT NULL,
                    aksi TEXT NOT NULL,
                    waktu TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS server_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    waktu TEXT NOT NULL,
                    client_ip TEXT NOT NULL,
                    username TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    aksi TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    detail TEXT DEFAULT ''
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_meta (
                    kunci TEXT PRIMARY KEY,
                    nilai TEXT NOT NULL
                )
            """)

            cursor.execute("SELECT COUNT(*) FROM users")
            if cursor.fetchone()[0] == 0:
                default_users = [
                    (
                        "arsiparis",
                        self._hash_password("arsip123"),
                        "Arsiparis Utama",
                        "Arsiparis"
                    ),
                    (
                        "admin",
                        self._hash_password("admin123"),
                        "Koordinator Arsip",
                        "Administrator"
                    ),
                ]
                cursor.executemany("""
                    INSERT INTO users (username, password_hash, nama_lengkap, peran)
                    VALUES (?, ?, ?, ?)
                """, default_users)

            cursor.execute("SELECT COUNT(*) FROM archives")
            if cursor.fetchone()[0] == 0:
                self._seed_initial_data(cursor)

            conn.commit()

    def _seed_initial_data(self, cursor: sqlite3.Cursor) -> None:
        """Mengisi contoh arsip perjanjian realistis untuk pengujian awal."""
        today = date.today()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sample_records = [
            (
                "PKS/2025/001",
                "Perjanjian Kerja Sama Pengadaan Perangkat TI",
                "PT Nusantara Digital",
                "Pengadaan Barang & Jasa",
                (today - timedelta(days=300)).isoformat(),
                (today + timedelta(days=65)).isoformat(),
                "Aktif",
                "Lemari A - Rak 1 - Map 01",
                "Daftar_Arsip_2025.xlsx",
                now_str
            ),
            (
                "MOU/2024/014",
                "Nota Kesepahaman Pemeliharaan Gedung Kantor",
                "CV Graha Sentosa",
                "Fasilitas & Infrastruktur",
                (today - timedelta(days=400)).isoformat(),
                (today - timedelta(days=35)).isoformat(),
                "Inaktif",
                "Lemari B - Rak 3 - Box 04",
                "Daftar_Arsip_2024.xlsx",
                now_str
            ),
            (
                "PKS/2026/003",
                "Kontrak Sewa Layanan Cloud & Cadangan Data",
                "PT Awan Lintas Data",
                "Teknologi Informasi",
                (today - timedelta(days=60)).isoformat(),
                (today + timedelta(days=305)).isoformat(),
                "Aktif",
                "Lemari A - Rak 2 - Map 05",
                "Import_Januari_2026.xlsx",
                now_str
            ),
            (
                "SPK/2025/089",
                "Perjanjian Kerahasiaan (NDA) Audit Eksternal",
                "KAP Hendra & Rekan",
                "Hukum & Kepatuhan",
                (today - timedelta(days=340)).isoformat(),
                (today + timedelta(days=20)).isoformat(),
                "Aktif",
                "Brankas Dokumen Rahasia - B02",
                "Daftar_Arsip_2025.xlsx",
                now_str
            ),
            (
                "KTR/2023/042",
                "Kontrak Jasa Konsultasi Manajemen SDM",
                "PT Talenta Prima",
                "Sumber Daya Manusia",
                (today - timedelta(days=800)).isoformat(),
                (today - timedelta(days=435)).isoformat(),
                "Inaktif",
                "Gudang Arsip - Rak D - Box 12",
                "Arsip_Lama_2023.csv",
                now_str
            ),
            (
                "PKS/2025/112",
                "Perjanjian Sewa Kendaraan Operasional Lapangan",
                "PT Armada Jaya",
                "Fasilitas & Infrastruktur",
                (today - timedelta(days=380)).isoformat(),
                (today - timedelta(days=10)).isoformat(),
                "Aktif",
                "Lemari A - Rak 4 - Map 09",
                "Daftar_Arsip_2025.xlsx",
                now_str
            ),
        ]
        cursor.executemany("""
            INSERT INTO archives (
                nomor_dokumen, judul_perjanjian, pihak_terkait, topik,
                tanggal_mulai, tanggal_berakhir, status, lokasi_fisik,
                file_sumber, diperbarui_pada
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_records)

        time_short = datetime.now().strftime("%Y-%m-%d %H:%M")
        cursor.executemany("""
            INSERT INTO recent_files (nama_file, jalur_file, aksi, waktu)
            VALUES (?, ?, ?, ?)
        """, [
            (
                "Import_Januari_2026.xlsx",
                "D:/Arsip_Kantor/Import_Januari_2026.xlsx",
                "Impor Katalog",
                time_short
            ),
            (
                "Daftar_Arsip_2025.xlsx",
                "D:/Arsip_Kantor/Daftar_Arsip_2025.xlsx",
                "Impor Katalog",
                time_short
            ),
        ])

    def authenticate_user(
        self, username: str, password: str
    ) -> Optional[Dict[str, str]]:
        """Memverifikasi kredensial pengguna pada database lokal."""
        pwd_hash = self._hash_password(password)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT username, nama_lengkap, peran
                FROM users
                WHERE username = ? AND password_hash = ?
            """, (username.strip(), pwd_hash))
            row = cursor.fetchone()
            if row:
                return {
                    "username": row["username"],
                    "nama_lengkap": row["nama_lengkap"],
                    "peran": row["peran"]
                }
        return None

    def register_user(
        self,
        username: str,
        password: str,
        nama_lengkap: str,
        peran: str = "Arsiparis"
    ) -> Tuple[bool, str]:
        """Mendaftarkan akun arsiparis baru ke basis data."""
        clean_user = username.strip()
        clean_name = nama_lengkap.strip()
        if len(clean_user) < 3:
            return False, "Nama pengguna minimal 3 karakter."
        if len(password) < 4:
            return False, "Kata sandi minimal 4 karakter."
        if not clean_name:
            return False, "Nama lengkap wajib diisi."

        pwd_hash = self._hash_password(password)
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO users (username, password_hash, nama_lengkap, peran)
                    VALUES (?, ?, ?, ?)
                """, (clean_user, pwd_hash, clean_name, peran))
                conn.commit()
            return (
                True,
                f"Akun '{clean_user}' berhasil dibuat. "
                "Silakan masuk menggunakan akun tersebut."
            )
        except sqlite3.IntegrityError:
            return (
                False,
                f"Nama pengguna '{clean_user}' sudah terdaftar. "
                "Gunakan nama lain."
            )

    def get_all_archives(self) -> List[ArchiveRecord]:
        """Mengambil seluruh catatan arsip dari penyimpanan."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM archives ORDER BY id DESC")
            rows = cursor.fetchall()
            return [
                ArchiveRecord(
                    id=r["id"],
                    nomor_dokumen=r["nomor_dokumen"],
                    judul_perjanjian=r["judul_perjanjian"],
                    pihak_terkait=r["pihak_terkait"],
                    topik=r["topik"],
                    tanggal_mulai=r["tanggal_mulai"],
                    tanggal_berakhir=r["tanggal_berakhir"],
                    status=r["status"],
                    lokasi_fisik=r["lokasi_fisik"],
                    file_sumber=r["file_sumber"],
                    diperbarui_pada=r["diperbarui_pada"]
                )
                for r in rows
            ]

    def get_archive_by_id(self, archive_id: int) -> Optional[ArchiveRecord]:
        """Mengambil satu arsip berdasarkan ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM archives WHERE id = ?", (archive_id,))
            r = cursor.fetchone()
            if not r:
                return None
            return ArchiveRecord(
                id=r["id"],
                nomor_dokumen=r["nomor_dokumen"],
                judul_perjanjian=r["judul_perjanjian"],
                pihak_terkait=r["pihak_terkait"],
                topik=r["topik"],
                tanggal_mulai=r["tanggal_mulai"],
                tanggal_berakhir=r["tanggal_berakhir"],
                status=r["status"],
                lokasi_fisik=r["lokasi_fisik"],
                file_sumber=r["file_sumber"],
                diperbarui_pada=r["diperbarui_pada"]
            )

    def add_archive(self, rec: ArchiveRecord) -> Tuple[bool, str]:
        """Menyimpan arsip perjanjian baru ke database."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO archives (
                        nomor_dokumen, judul_perjanjian, pihak_terkait, topik,
                        tanggal_mulai, tanggal_berakhir, status, lokasi_fisik,
                        file_sumber, diperbarui_pada
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rec.nomor_dokumen.strip(),
                    rec.judul_perjanjian.strip(),
                    rec.pihak_terkait.strip(),
                    rec.topik.strip(),
                    rec.tanggal_mulai,
                    rec.tanggal_berakhir,
                    rec.status,
                    rec.lokasi_fisik.strip(),
                    rec.file_sumber.strip() or "Input Manual",
                    now_str
                ))
                conn.commit()
            return True, f"Arsip '{rec.nomor_dokumen}' berhasil ditambahkan."
        except sqlite3.IntegrityError:
            return (
                False,
                f"Nomor dokumen '{rec.nomor_dokumen}' sudah terdaftar. "
                "Gunakan nomor dokumen yang unik."
            )
        except Exception as exc:
            return False, f"Gagal menyimpan arsip: {exc}"

    def upsert_archive_batch(
        self, records: List[ArchiveRecord], update_existing: bool = False
    ) -> Tuple[int, int, int]:
        """
        Menyimpan sekumpulan arsip dari hasil impor secara transaksional.
        Mengembalikan tuple: (jumlah_ditambah, jumlah_diperbarui, jumlah_dilewati)
        """
        inserted = 0
        updated = 0
        skipped = 0
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            for rec in records:
                nomor = rec.nomor_dokumen.strip()
                cursor.execute(
                    "SELECT id FROM archives WHERE nomor_dokumen = ?",
                    (nomor,)
                )
                existing_row = cursor.fetchone()

                if existing_row is None:
                    cursor.execute("""
                        INSERT INTO archives (
                            nomor_dokumen, judul_perjanjian, pihak_terkait,
                            topik, tanggal_mulai, tanggal_berakhir, status,
                            lokasi_fisik, file_sumber, diperbarui_pada
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        nomor,
                        rec.judul_perjanjian.strip(),
                        rec.pihak_terkait.strip(),
                        rec.topik.strip(),
                        rec.tanggal_mulai,
                        rec.tanggal_berakhir,
                        rec.status,
                        rec.lokasi_fisik.strip(),
                        rec.file_sumber.strip(),
                        now_str
                    ))
                    inserted += 1
                elif update_existing:
                    cursor.execute("""
                        UPDATE archives SET
                            judul_perjanjian = ?,
                            pihak_terkait = ?,
                            topik = ?,
                            tanggal_mulai = ?,
                            tanggal_berakhir = ?,
                            status = ?,
                            lokasi_fisik = ?,
                            file_sumber = ?,
                            diperbarui_pada = ?
                        WHERE id = ?
                    """, (
                        rec.judul_perjanjian.strip(),
                        rec.pihak_terkait.strip(),
                        rec.topik.strip(),
                        rec.tanggal_mulai,
                        rec.tanggal_berakhir,
                        rec.status,
                        rec.lokasi_fisik.strip(),
                        rec.file_sumber.strip(),
                        now_str,
                        existing_row["id"]
                    ))
                    updated += 1
                else:
                    skipped += 1

            conn.commit()
        return inserted, updated, skipped

    def update_archive(
        self, rec: ArchiveRecord, custom_timestamp: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Memperbarui data arsip yang sudah ada."""
        if rec.id is None:
            return False, "ID arsip tidak valid untuk pembaruan."
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ts_to_use = custom_timestamp or (
            rec.diperbarui_pada
            if (rec.diperbarui_pada and rec.diperbarui_pada > now_str)
            else now_str
        )
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE archives SET
                        nomor_dokumen = ?,
                        judul_perjanjian = ?,
                        pihak_terkait = ?,
                        topik = ?,
                        tanggal_mulai = ?,
                        tanggal_berakhir = ?,
                        status = ?,
                        lokasi_fisik = ?,
                        diperbarui_pada = ?
                    WHERE id = ?
                """, (
                    rec.nomor_dokumen.strip(),
                    rec.judul_perjanjian.strip(),
                    rec.pihak_terkait.strip(),
                    rec.topik.strip(),
                    rec.tanggal_mulai,
                    rec.tanggal_berakhir,
                    rec.status,
                    rec.lokasi_fisik.strip(),
                    ts_to_use,
                    rec.id
                ))
                conn.commit()
            return True, f"Perubahan pada '{rec.nomor_dokumen}' berhasil disimpan."
        except sqlite3.IntegrityError:
            return (
                False,
                f"Nomor dokumen '{rec.nomor_dokumen}' sudah digunakan arsip lain."
            )
        except Exception as exc:
            return False, f"Gagal memperbarui arsip: {exc}"

    def update_archive_status(
        self, archive_id: int, new_status: str
    ) -> Tuple[bool, str]:
        """Mengubah status Aktif/Inaktif secara cepat."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE archives
                    SET status = ?, diperbarui_pada = ?
                    WHERE id = ?
                """, (new_status, now_str, archive_id))
                conn.commit()
            return True, f"Status arsip berhasil diubah menjadi '{new_status}'."
        except Exception as exc:
            return False, f"Gagal mengubah status: {exc}"

    def delete_archive(self, archive_id: int) -> Tuple[bool, str]:
        """Menghapus catatan arsip dari basis data."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM archives WHERE id = ?", (archive_id,))
                conn.commit()
            return True, "Catatan arsip berhasil dihapus dari katalog."
        except Exception as exc:
            return False, f"Gagal menghapus arsip: {exc}"

    def get_distinct_topics(self) -> List[str]:
        """Mengambil daftar topik unik yang tersedia."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT topik FROM archives ORDER BY topik ASC"
            )
            return [r["topik"] for r in cursor.fetchall() if r["topik"]]

    def get_recent_files(self, limit: int = 5) -> List[Dict[str, str]]:
        """Mengambil riwayat file yang baru diproses."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT nama_file, jalur_file, aksi, waktu
                FROM recent_files
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def log_recent_file(
        self, nama_file: str, jalur_file: str, aksi: str
    ) -> None:
        """Mencatat aktivitas pemrosesan file ke riwayat."""
        waktu_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO recent_files (nama_file, jalur_file, aksi, waktu)
                VALUES (?, ?, ?, ?)
            """, (nama_file, jalur_file, aksi, waktu_sekarang))
            conn.commit()

    def log_server_activity(
        self,
        client_ip: str,
        username: str,
        endpoint: str,
        aksi: str,
        status_code: int,
        detail: str = ""
    ) -> None:
        """Mencatat aktivitas akses klien pada server kantor ke tabel audit."""
        waktu_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO server_audit_logs (
                    waktu, client_ip, username, endpoint, aksi, status_code, detail
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (waktu_str, client_ip, username, endpoint, aksi, status_code, detail))
            conn.commit()

    def get_server_audit_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Mengambil riwayat log audit server kantor terbaru."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, waktu, client_ip, username, endpoint, aksi, status_code, detail
                FROM server_audit_logs
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def clear_server_audit_logs(self) -> None:
        """Membersihkan seluruh riwayat log audit server kantor."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM server_audit_logs")
            conn.commit()

    def get_sync_meta(self, key: str, default: str = "") -> str:
        """Mengambil konfigurasi atau status sinkronisasi berdasarkan kunci."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT nilai FROM sync_meta WHERE kunci = ?", (key,))
            row = cursor.fetchone()
            return row["nilai"] if row else default

    def set_sync_meta(self, key: str, val: str) -> None:
        """Menyimpan atau memperbarui metadata sinkronisasi."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sync_meta (kunci, nilai) VALUES (?, ?)
                ON CONFLICT(kunci) DO UPDATE SET nilai = excluded.nilai
            """, (key, str(val)))
            conn.commit()

    def get_archive_by_document_number(
        self, nomor_dokumen: str
    ) -> Optional[ArchiveRecord]:
        """Mengambil satu arsip berdasarkan nomor dokumen unik."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM archives WHERE nomor_dokumen = ?",
                (nomor_dokumen.strip(),)
            )
            r = cursor.fetchone()
            if not r:
                return None
            return ArchiveRecord(
                id=r["id"],
                nomor_dokumen=r["nomor_dokumen"],
                judul_perjanjian=r["judul_perjanjian"],
                pihak_terkait=r["pihak_terkait"],
                topik=r["topik"],
                tanggal_mulai=r["tanggal_mulai"],
                tanggal_berakhir=r["tanggal_berakhir"],
                status=r["status"],
                lokasi_fisik=r["lokasi_fisik"],
                file_sumber=r["file_sumber"],
                diperbarui_pada=r["diperbarui_pada"]
            )

    def reconcile_records(
        self, incoming_records: List[ArchiveRecord]
    ) -> Tuple[int, int, int, List[str]]:
        """
        Menyelaraskan data arsip masuk (dari klien atau server) secara cerdas.
        Aturan konflik: entitas dengan timestamp 'diperbarui_pada' terbaru yang menang.
        Mengembalikan: (jumlah_disisipkan, jumlah_diperbarui, jumlah_tetap, daftar_error)
        """
        inserted = 0
        updated = 0
        untouched = 0
        errors: List[str] = []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            for rec in incoming_records:
                nomor = rec.nomor_dokumen.strip()
                if not nomor:
                    continue
                cursor.execute(
                    "SELECT id, diperbarui_pada FROM archives WHERE nomor_dokumen = ?",
                    (nomor,)
                )
                existing = cursor.fetchone()

                if existing is None:
                    try:
                        cursor.execute("""
                            INSERT INTO archives (
                                nomor_dokumen, judul_perjanjian, pihak_terkait, topik,
                                tanggal_mulai, tanggal_berakhir, status, lokasi_fisik,
                                file_sumber, diperbarui_pada
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            nomor,
                            rec.judul_perjanjian.strip(),
                            rec.pihak_terkait.strip(),
                            rec.topik.strip(),
                            rec.tanggal_mulai,
                            rec.tanggal_berakhir,
                            rec.status,
                            rec.lokasi_fisik.strip(),
                            rec.file_sumber.strip() or "Sinkronisasi Server",
                            rec.diperbarui_pada or now_str
                        ))
                        inserted += 1
                    except Exception as exc:
                        errors.append(f"Gagal menyisipkan {nomor}: {exc}")
                else:
                    incoming_ts = rec.diperbarui_pada or ""
                    existing_ts = existing["diperbarui_pada"] or ""
                    if incoming_ts > existing_ts:
                        try:
                            cursor.execute("""
                                UPDATE archives SET
                                    judul_perjanjian = ?,
                                    pihak_terkait = ?,
                                    topik = ?,
                                    tanggal_mulai = ?,
                                    tanggal_berakhir = ?,
                                    status = ?,
                                    lokasi_fisik = ?,
                                    file_sumber = ?,
                                    diperbarui_pada = ?
                                WHERE id = ?
                            """, (
                                rec.judul_perjanjian.strip(),
                                rec.pihak_terkait.strip(),
                                rec.topik.strip(),
                                rec.tanggal_mulai,
                                rec.tanggal_berakhir,
                                rec.status,
                                rec.lokasi_fisik.strip(),
                                rec.file_sumber.strip() or "Sinkronisasi Server",
                                rec.diperbarui_pada or now_str,
                                existing["id"]
                            ))
                            updated += 1
                        except Exception as exc:
                            errors.append(f"Gagal memperbarui {nomor}: {exc}")
                    else:
                        untouched += 1
            conn.commit()

        return inserted, updated, untouched, errors


# ==============================================================================
# LAYER 3: MESIN PEMROSESAN, RETENSIMETER, & IMPOR/EKSPOR EXCEL/CSV
# ==============================================================================

class ArchiveProcessingEngine:
    """
    Mesin pemrosesan mandiri untuk analisis status arsip, penghitungan masa
    retensi, penyaringan multi-kriteria, dan validasi keamanan file.
    """

    @staticmethod
    def evaluate_retention(
        tanggal_berakhir_str: str, reference_date: Optional[date] = None
    ) -> Tuple[str, int]:
        """
        Menghitung sisa hari masa berlaku/retensi perjanjian.
        Mengembalikan tuple: (kategori_peringatan, selisih_hari)
        """
        ref = reference_date or date.today()
        try:
            end_date = date.fromisoformat(tanggal_berakhir_str)
        except ValueError:
            return ("Tanggal Tidak Valid", 0)

        delta_days = (end_date - ref).days
        if delta_days < 0:
            return ("Kedaluwarsa", delta_days)
        elif delta_days <= 30:
            return ("Kritis (<= 30 Hari)", delta_days)
        elif delta_days <= 90:
            return ("Perhatian (<= 90 Hari)", delta_days)
        else:
            return ("Aman", delta_days)

    @staticmethod
    def format_retention_label(
        record: ArchiveRecord, reference_date: Optional[date] = None
    ) -> Tuple[str, str, int]:
        """
        Menghasilkan label peringatan yang mudah dibaca beserta tingkat urgensi.
        Mengembalikan: (teks_tampilan, tingkat_urgensi, delta_days)
        """
        if record.status.lower() == "inaktif":
            return ("Arsip Inaktif", "inaktif", 99999)

        kategori, delta = ArchiveProcessingEngine.evaluate_retention(
            record.tanggal_berakhir, reference_date
        )
        if kategori == "Kedaluwarsa":
            return (f"Kedaluwarsa ({abs(delta)} hr lalu)", "danger", delta)
        elif kategori == "Kritis (<= 30 Hari)":
            return (f"Kritis (Sisa {delta} hr)", "danger", delta)
        elif kategori == "Perhatian (<= 90 Hari)":
            return (f"Perhatian (Sisa {delta} hr)", "warning", delta)
        elif kategori == "Aman":
            return (f"Aman (Sisa {delta} hr)", "safe", delta)
        return ("Tanggal Tidak Valid", "warning", 0)

    @staticmethod
    def filter_archives(
        records: List[ArchiveRecord],
        criteria: FilterCriteria,
        reference_date: Optional[date] = None
    ) -> List[ArchiveRecord]:
        """Menyaring daftar arsip berdasarkan seluruh kriteria aktif."""
        query = criteria.search_text.strip().lower()
        results: List[ArchiveRecord] = []

        for r in records:
            if query:
                haystack = " ".join([
                    r.nomor_dokumen,
                    r.judul_perjanjian,
                    r.pihak_terkait,
                    r.topik,
                    r.lokasi_fisik
                ]).lower()
                if query not in haystack:
                    continue

            if criteria.topik != "Semua Topik" and r.topik != criteria.topik:
                continue

            if (
                criteria.status != "Semua Status"
                and r.status.lower() != criteria.status.lower()
            ):
                continue

            if criteria.retensi != "Semua Retensi":
                if r.status.lower() != "aktif":
                    continue
                kat, _ = ArchiveProcessingEngine.evaluate_retention(
                    r.tanggal_berakhir, reference_date
                )
                if criteria.retensi == "Perlu Perhatian":
                    if kat not in (
                        "Kedaluwarsa",
                        "Kritis (<= 30 Hari)",
                        "Perhatian (<= 90 Hari)"
                    ):
                        continue
                elif kat != criteria.retensi:
                    continue

            if criteria.use_date_range:
                if criteria.date_from and r.tanggal_berakhir < criteria.date_from:
                    continue
                if criteria.date_to and r.tanggal_berakhir > criteria.date_to:
                    continue

            results.append(r)

        return results

    @staticmethod
    def get_retention_alerts(
        records: List[ArchiveRecord], reference_date: Optional[date] = None
    ) -> List[Tuple[ArchiveRecord, str, int]]:
        """
        Mengambil seluruh arsip aktif yang memasuki masa peringatan retensi,
        diurutkan dari yang paling mendesak.
        """
        alerts: List[Tuple[ArchiveRecord, str, int]] = []
        for r in records:
            if r.status.lower() != "aktif":
                continue
            kategori, delta = ArchiveProcessingEngine.evaluate_retention(
                r.tanggal_berakhir, reference_date
            )
            if kategori in (
                "Kedaluwarsa",
                "Kritis (<= 30 Hari)",
                "Perhatian (<= 90 Hari)"
            ):
                alerts.append((r, kategori, delta))

        alerts.sort(key=lambda item: item[2])
        return alerts

    @staticmethod
    def compute_dashboard_metrics(
        records: List[ArchiveRecord]
    ) -> Dict[str, Any]:
        """Menghitung metrik ringkasan untuk satu layar pemantauan."""
        total = len(records)
        aktif = sum(1 for r in records if r.status.lower() == "aktif")
        inaktif = sum(1 for r in records if r.status.lower() == "inaktif")

        alerts = ArchiveProcessingEngine.get_retention_alerts(records)
        peringatan_retensi = len(alerts)

        persen_aktif = round((aktif / total) * 100, 1) if total > 0 else 0.0
        persen_inaktif = round((inaktif / total) * 100, 1) if total > 0 else 0.0

        return {
            "total": total,
            "aktif": aktif,
            "inaktif": inaktif,
            "peringatan_retensi": peringatan_retensi,
            "persen_aktif": persen_aktif,
            "persen_inaktif": persen_inaktif
        }

    @staticmethod
    def create_safe_working_copy(source_path: str, work_dir: str) -> str:
        """
        Menjamin file asli tidak pernah ditimpa secara langsung dengan membuat
        salinan kerja yang aman sebelum pemrosesan dilakukan.
        """
        if not os.path.isfile(source_path):
            raise FileNotFoundError(
                f"File sumber tidak ditemukan: {source_path}"
            )
        os.makedirs(work_dir, exist_ok=True)
        base_name = os.path.basename(source_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"salinan_{timestamp}_{base_name}"
        dest_path = os.path.join(work_dir, safe_name)
        shutil.copy2(source_path, dest_path)
        return dest_path


class SpreadsheetIOEngine:
    """
    Mesin Impor dan Ekspor spreadsheet Excel (.xlsx) dan CSV (.csv).
    Selalu bekerja menggunakan salinan aman dan memvalidasi format file.
    """

    HEADER_ALIASES = {
        "nomor_dokumen": {
            "nomor dokumen", "no dokumen", "no. dokumen", "nomor", "no",
            "nomor surat", "no surat", "nomor_dokumen", "document_number"
        },
        "judul_perjanjian": {
            "judul perjanjian", "judul", "perihal", "nama perjanjian",
            "tentang", "judul_perjanjian", "title"
        },
        "pihak_terkait": {
            "pihak terkait", "pihak", "mitra", "vendor", "rekanan",
            "instansi", "pihak_terkait", "counterparty"
        },
        "topik": {
            "topik", "kategori", "bidang", "jenis", "topic", "category"
        },
        "tanggal_mulai": {
            "tanggal mulai", "tgl mulai", "mulai", "tanggal awal",
            "tanggal_mulai", "start_date"
        },
        "tanggal_berakhir": {
            "tanggal berakhir", "tgl berakhir", "berakhir", "jatuh tempo",
            "tanggal selesai", "tanggal_berakhir", "end_date"
        },
        "status": {
            "status", "status arsip", "keterangan status"
        },
        "lokasi_fisik": {
            "lokasi fisik", "lokasi", "rak", "lemari", "tempat simpan",
            "lokasi_fisik", "location"
        }
    }

    @staticmethod
    def normalize_date_value(raw_val: Any, fallback_date: str) -> str:
        """Mengonversi objek tanggal Excel atau string ke format YYYY-MM-DD."""
        if raw_val is None:
            return fallback_date
        if isinstance(raw_val, datetime):
            return raw_val.date().isoformat()
        if isinstance(raw_val, date):
            return raw_val.isoformat()

        text = str(raw_val).strip()
        if not text:
            return fallback_date

        # Coba format ISO (YYYY-MM-DD)
        try:
            return date.fromisoformat(text[:10]).isoformat()
        except ValueError:
            pass

        # Coba format umum Indonesia (DD/MM/YYYY atau DD-MM-YYYY)
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(text[:10], fmt).date().isoformat()
            except ValueError:
                continue

        return fallback_date

    @classmethod
    def _map_headers(cls, raw_headers: List[Any]) -> Dict[str, int]:
        """Memetakan indeks kolom spreadsheet ke nama kolom standar ARSIPTA."""
        mapping: Dict[str, int] = {}
        for idx, h in enumerate(raw_headers):
            if h is None:
                continue
            clean = str(h).strip().lower()
            for field_name, aliases in cls.HEADER_ALIASES.items():
                if clean in aliases and field_name not in mapping:
                    mapping[field_name] = idx
        return mapping

    @classmethod
    def parse_spreadsheet_file(
        cls, source_path: str, work_dir: str = TEMP_WORK_DIR
    ) -> Tuple[List[ArchiveRecord], List[str]]:
        """
        Membaca file .xlsx atau .csv melalui salinan kerja yang aman.
        Mengembalikan tuple: (daftar_ArchiveRecord_valid, daftar_peringatan_baris)
        """
        ext = os.path.splitext(source_path)[1].lower()
        if ext not in (".xlsx", ".csv"):
            raise ValueError(
                "Format file tidak didukung. Gunakan file .xlsx atau .csv."
            )

        safe_copy = ArchiveProcessingEngine.create_safe_working_copy(
            source_path, work_dir
        )
        source_filename = os.path.basename(source_path)
        rows_data: List[List[Any]] = []

        try:
            if ext == ".xlsx":
                if not OPENPYXL_AVAILABLE:
                    raise RuntimeError(
                        "Pustaka 'openpyxl' belum terpasang. "
                        "Jalankan: pip install openpyxl"
                    )
                wb = openpyxl.load_workbook(
                    safe_copy, read_only=True, data_only=True
                )
                ws = wb.active
                for row in ws.iter_rows(values_only=True):
                    rows_data.append(list(row))
                wb.close()
            else:
                raw_text = ""
                for enc in ("utf-8-sig", "utf-8", "latin-1"):
                    try:
                        with open(safe_copy, "r", encoding=enc) as f:
                            raw_text = f.read()
                        break
                    except UnicodeDecodeError:
                        continue

                if not raw_text.strip():
                    raise ValueError("File CSV kosong atau tidak dapat dibaca.")

                delimiter = ";" if raw_text.count(";") > raw_text.count(",") else ","
                reader = csv.reader(raw_text.splitlines(), delimiter=delimiter)
                for row in reader:
                    rows_data.append(row)
        except Exception as exc:
            raise ValueError(
                f"File rusak atau gagal diproses ({os.path.basename(source_path)}): {exc}"
            ) from exc
        finally:
            if os.path.exists(safe_copy):
                try:
                    os.remove(safe_copy)
                except OSError:
                    pass

        if len(rows_data) < 2:
            raise ValueError(
                "File harus memiliki minimal 1 baris judul kolom dan 1 baris data."
            )

        col_map = cls._map_headers(rows_data[0])
        required = ("nomor_dokumen", "judul_perjanjian")
        for req in required:
            if req not in col_map:
                raise ValueError(
                    f"Kolom wajib '{req.replace('_', ' ').title()}' "
                    "tidak ditemukan pada baris pertama file."
                )

        parsed_records: List[ArchiveRecord] = []
        warnings: List[str] = []
        today_iso = date.today().isoformat()
        next_year_iso = (date.today() + timedelta(days=365)).isoformat()

        for row_num, row in enumerate(rows_data[1:], start=2):
            if not row or all(
                (cell is None or str(cell).strip() == "") for cell in row
            ):
                continue

            def get_cell(field: str, default: str = "") -> Any:
                idx = col_map.get(field)
                if idx is None or idx >= len(row):
                    return default
                val = row[idx]
                return default if val is None else val

            nomor = str(get_cell("nomor_dokumen", "")).strip()
            judul = str(get_cell("judul_perjanjian", "")).strip()
            if not nomor or not judul:
                warnings.append(
                    f"Baris {row_num}: Dilewati karena Nomor Dokumen atau "
                    "Judul Perjanjian kosong."
                )
                continue

            pihak = str(get_cell("pihak_terkait", "Tidak Disebutkan")).strip()
            if not pihak:
                pihak = "Tidak Disebutkan"

            topik = str(get_cell("topik", "Umum")).strip() or "Umum"
            tgl_mulai = cls.normalize_date_value(
                get_cell("tanggal_mulai", today_iso), today_iso
            )
            tgl_berakhir = cls.normalize_date_value(
                get_cell("tanggal_berakhir", next_year_iso), next_year_iso
            )

            raw_status = str(get_cell("status", "")).strip().lower()
            if raw_status in ("aktif", "active"):
                status = "Aktif"
            elif raw_status in ("inaktif", "inactive", "nonaktif", "berakhir"):
                status = "Inaktif"
            else:
                status = "Inaktif" if tgl_berakhir < today_iso else "Aktif"

            lokasi = str(get_cell("lokasi_fisik", "")).strip()

            parsed_records.append(
                ArchiveRecord(
                    id=None,
                    nomor_dokumen=nomor,
                    judul_perjanjian=judul,
                    pihak_terkait=pihak,
                    topik=topik,
                    tanggal_mulai=tgl_mulai,
                    tanggal_berakhir=tgl_berakhir,
                    status=status,
                    lokasi_fisik=lokasi,
                    file_sumber=source_filename,
                    diperbarui_pada=""
                )
            )

        return parsed_records, warnings

    @staticmethod
    def export_records(
        records: List[ArchiveRecord], dest_path: str
    ) -> Tuple[bool, str]:
        """Mengekspor daftar arsip ke file .xlsx atau .csv."""
        ext = os.path.splitext(dest_path)[1].lower()
        headers = [
            "No. Dokumen",
            "Judul Perjanjian",
            "Pihak Terkait",
            "Topik",
            "Tanggal Mulai",
            "Tanggal Berakhir",
            "Status",
            "Peringatan Retensi",
            "Lokasi Fisik",
            "File Sumber"
        ]

        rows: List[List[str]] = []
        for rec in records:
            ret_text, _, _ = ArchiveProcessingEngine.format_retention_label(rec)
            rows.append([
                rec.nomor_dokumen,
                rec.judul_perjanjian,
                rec.pihak_terkait,
                rec.topik,
                rec.tanggal_mulai,
                rec.tanggal_berakhir,
                rec.status,
                ret_text,
                rec.lokasi_fisik,
                rec.file_sumber
            ])

        try:
            if ext == ".xlsx":
                if not OPENPYXL_AVAILABLE:
                    return (
                        False,
                        "Pustaka 'openpyxl' belum terpasang untuk ekspor Excel."
                    )
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Katalog Arsip ARSIPTA"

                ws.append(headers)
                header_fill = PatternFill(
                    start_color="1E3A8A", end_color="1E3A8A", fill_type="solid"
                )
                header_font = ExcelFont(color="FFFFFF", bold=True)

                for col_idx in range(1, len(headers) + 1):
                    cell = ws.cell(row=1, column=col_idx)
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal="left", vertical="center")

                for r in rows:
                    ws.append(r)

                ws.freeze_panes = "A2"
                for col in ws.columns:
                    max_len = 12
                    col_letter = col[0].column_letter
                    for cell in col:
                        val_len = len(str(cell.value or ""))
                        if val_len > max_len:
                            max_len = min(val_len, 48)
                    ws.column_dimensions[col_letter].width = max_len + 3

                wb.save(dest_path)
            else:
                with open(dest_path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    writer.writerows(rows)

            return (
                True,
                f"Berhasil mengekspor {len(records)} catatan arsip ke:\n{dest_path}"
            )
        except Exception as exc:
            return False, f"Gagal mengekspor file: {exc}"

    @staticmethod
    def generate_sample_template(dest_path: str) -> Tuple[bool, str]:
        """Membuat file template Excel (.xlsx) atau CSV (.csv) siap isi."""
        ext = os.path.splitext(dest_path)[1].lower()
        headers = [
            "No. Dokumen",
            "Judul Perjanjian",
            "Pihak Terkait",
            "Topik",
            "Tanggal Mulai",
            "Tanggal Berakhir",
            "Status",
            "Lokasi Fisik"
        ]
        today = date.today()
        sample_rows = [
            [
                "PKS/2026/101",
                "Perjanjian Pemeliharaan Mesin Fotokopi",
                "PT Sejahtera Abadi",
                "Fasilitas & Infrastruktur",
                today.isoformat(),
                (today + timedelta(days=365)).isoformat(),
                "Aktif",
                "Lemari A - Rak 1 - Map 10"
            ],
            [
                "MOU/2026/102",
                "Kesepakatan Pelatihan Literasi Digital",
                "Yayasan Pustaka Nusantara",
                "Kerja Sama Operasional",
                today.isoformat(),
                (today + timedelta(days=180)).isoformat(),
                "Aktif",
                "Lemari B - Rak 2 - Map 03"
            ]
        ]

        try:
            if ext == ".xlsx":
                if not OPENPYXL_AVAILABLE:
                    return False, "Pustaka 'openpyxl' belum terpasang."
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Template Impor ARSIPTA"
                ws.append(headers)
                for row in sample_rows:
                    ws.append(row)
                wb.save(dest_path)
            else:
                with open(dest_path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    writer.writerows(sample_rows)
            return True, f"Template berhasil dibuat di:\n{dest_path}"
        except Exception as exc:
            return False, f"Gagal membuat template: {exc}"




class ArsiptaServerService:
    """
    Layanan inti logika Server Kantor ARSIPTA.
    Menyediakan router dan handler permintaan RESTful JSON untuk status,
    autentikasi pengguna, pengelolaan arsip, dan sinkronisasi tim arsiparis.
    """

    def __init__(
        self, storage: StorageEngine, secret_token: str = DEFAULT_SERVER_TOKEN
    ):
        self.storage = storage
        self.secret_token = secret_token.strip()

    def handle_request(
        self,
        method: str,
        path: str,
        headers: Dict[str, str],
        body_bytes: bytes,
        client_ip: str = "127.0.0.1"
    ) -> Tuple[int, Dict[str, str], bytes]:
        """
        Menerima dan memproses permintaan HTTP, mengembalikan tuple:
        (status_code, response_headers, response_bytes)
        """
        parsed = urllib.parse.urlsplit(path)
        clean_path = parsed.path.rstrip("/") or "/"
        query_params = urllib.parse.parse_qs(parsed.query)

        h_lower = {k.lower(): v for k, v in headers.items()}
        req_token = (
            h_lower.get("x-arsipta-token")
            or query_params.get("token", [""])[0]
        )

        payload: Dict[str, Any] = {}
        if body_bytes:
            try:
                payload = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                payload = {}
        if not req_token and "token" in payload:
            req_token = str(payload["token"]).strip()

        def make_json_response(
            code: int, data: Dict[str, Any]
        ) -> Tuple[int, Dict[str, str], bytes]:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            res_headers = {
                "Content-Type": "application/json; charset=utf-8",
                "Content-Length": str(len(body)),
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, X-Arsipta-Token"
            }
            return code, res_headers, body

        if method == "OPTIONS":
            return make_json_response(200, {"success": True})

        # Endpoint 1: GET /api/status (Health Check Publik)
        if clean_path == "/api/status" and method == "GET":
            archives = self.storage.get_all_archives()
            res = {
                "success": True,
                "status": "online",
                "server_name": "ARSIPTA Server Kantor",
                "version": APP_VERSION,
                "hostname": socket.gethostname(),
                "total_archives": len(archives),
                "timestamp": datetime.now().isoformat()
            }
            self.storage.log_server_activity(
                client_ip, "publik", "/api/status", "STATUS", 200, "Pemeriksaan status server"
            )
            return make_json_response(200, res)

        # Endpoint 2: POST /api/auth (Login Pengguna ke Server)
        if clean_path == "/api/auth" and method == "POST":
            user_input = str(payload.get("username", "")).strip()
            pass_input = str(payload.get("password", ""))
            user_info = self.storage.authenticate_user(user_input, pass_input)
            if user_info:
                self.storage.log_server_activity(
                    client_ip, user_input, "/api/auth", "LOGIN", 200, "Berhasil masuk server"
                )
                return make_json_response(200, {
                    "success": True,
                    "message": f"Berhasil masuk sebagai {user_info['nama_lengkap']}.",
                    "user": user_info,
                    "token": self.secret_token
                })
            else:
                self.storage.log_server_activity(
                    client_ip, user_input or "anonim", "/api/auth", "LOGIN", 401, "Kredensial tidak valid"
                )
                return make_json_response(401, {
                    "success": False,
                    "error": "Nama pengguna atau kata sandi tidak sesuai."
                })

        # Verifikasi Token Keamanan untuk endpoint privat
        if self.secret_token and req_token != self.secret_token:
            self.storage.log_server_activity(
                client_ip, "anonim", clean_path, method, 401, "Ditolak: Token keamanan tidak valid"
            )
            return make_json_response(401, {
                "success": False,
                "error": "Akses ditolak: Token server tidak valid atau tidak disertakan."
            })

        # Endpoint 3: GET /api/archives (Daftar Seluruh Arsip)
        if clean_path == "/api/archives" and method == "GET":
            records = self.storage.get_all_archives()
            self.storage.log_server_activity(
                client_ip, "arsiparis", "/api/archives", "GET", 200, f"Mengunduh {len(records)} arsip"
            )
            return make_json_response(200, {
                "success": True,
                "count": len(records),
                "records": [r.to_dict() for r in records]
            })

        # Endpoint 4: POST /api/archives (Tambah Arsip Baru di Server)
        if clean_path == "/api/archives" and method == "POST":
            try:
                rec = ArchiveRecord.from_dict(payload)
                ok, msg = self.storage.add_archive(rec)
                if ok:
                    self.storage.log_server_activity(
                        client_ip, "arsiparis", "/api/archives", "POST", 201, f"Tambah arsip {rec.nomor_dokumen}"
                    )
                    return make_json_response(201, {
                        "success": True,
                        "message": msg,
                        "record": rec.to_dict()
                    })
                elif "sudah terdaftar" in msg:
                    self.storage.log_server_activity(
                        client_ip, "arsiparis", "/api/archives", "POST", 409, f"Duplikat {rec.nomor_dokumen}"
                    )
                    return make_json_response(409, {"success": False, "error": msg})
                else:
                    return make_json_response(400, {"success": False, "error": msg})
            except Exception as exc:
                return make_json_response(400, {"success": False, "error": f"Format arsip salah: {exc}"})

        # Endpoint 5: GET, PUT, DELETE /api/archives/<id>
        if clean_path.startswith("/api/archives/"):
            parts = clean_path.split("/")
            if len(parts) == 4 and parts[3].isdigit():
                arch_id = int(parts[3])
                if method == "GET":
                    rec = self.storage.get_archive_by_id(arch_id)
                    if rec:
                        return make_json_response(200, {"success": True, "record": rec.to_dict()})
                    return make_json_response(404, {"success": False, "error": "Arsip tidak ditemukan."})

                elif method == "PUT":
                    try:
                        rec = ArchiveRecord.from_dict(payload)
                        rec.id = arch_id
                        ok, msg = self.storage.update_archive(rec)
                        status_code = 200 if ok else 400
                        self.storage.log_server_activity(
                            client_ip, "arsiparis", clean_path, "PUT", status_code, msg
                        )
                        return make_json_response(status_code, {"success": ok, "message" if ok else "error": msg})
                    except Exception as exc:
                        return make_json_response(400, {"success": False, "error": str(exc)})

                elif method == "DELETE":
                    ok, msg = self.storage.delete_archive(arch_id)
                    status_code = 200 if ok else 400
                    self.storage.log_server_activity(
                        client_ip, "arsiparis", clean_path, "DELETE", status_code, msg
                    )
                    return make_json_response(status_code, {"success": ok, "message" if ok else "error": msg})

        # Endpoint 6: POST /api/sync (Sinkronisasi Dua Arah / Reconcile)
        if clean_path == "/api/sync" and method == "POST":
            client_user = str(payload.get("client_username", "klien"))
            raw_records = payload.get("records", [])
            client_records = [
                ArchiveRecord.from_dict(r)
                for r in raw_records
                if isinstance(r, dict)
            ]

            ins, upd, unt, errors = self.storage.reconcile_records(client_records)
            server_all = self.storage.get_all_archives()

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.storage.log_server_activity(
                client_ip,
                client_user,
                "/api/sync",
                "SYNC",
                200,
                f"Sync 2-arah (+{ins} baru, {upd} diupdate, {unt} tetap)"
            )
            return make_json_response(200, {
                "success": True,
                "server_time": now_str,
                "server_inserted": ins,
                "server_updated": upd,
                "server_untouched": unt,
                "server_errors": errors,
                "records": [r.to_dict() for r in server_all]
            })

        # Endpoint 7: GET /api/audit (Log Audit Server)
        if clean_path == "/api/audit" and method == "GET":
            logs = self.storage.get_server_audit_logs(limit=100)
            return make_json_response(200, {"success": True, "logs": logs})

        # Endpoint 8: POST /api/audit/clear (Bersihkan Log Audit Server)
        if clean_path == "/api/audit/clear" and method == "POST":
            self.storage.clear_server_audit_logs()
            return make_json_response(200, {"success": True, "message": "Log audit dibersihkan."})

        return make_json_response(404, {"success": False, "error": f"Endpoint '{clean_path}' tidak ditemukan."})


class ArsiptaHttpHandler(http.server.BaseHTTPRequestHandler):
    """Handler HTTP PySide6/Python Standard Library untuk permintaan Server Kantor."""
    server_version = "ARSIPTA-Server/0.4.0"

    def _dispatch(self, method: str):
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b""
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"

        headers_dict = {k: v for k, v in self.headers.items()}
        service: ArsiptaServerService = self.server.service

        code, res_headers, res_body = service.handle_request(
            method, self.path, headers_dict, body_bytes, client_ip
        )
        self.send_response(code)
        for h_key, h_val in res_headers.items():
            self.send_header(h_key, h_val)
        self.end_headers()
        self.wfile.write(res_body)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_OPTIONS(self):
        self._dispatch("OPTIONS")

    def log_message(self, format, *args):
        pass


class ArsiptaHttpServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Server HTTP multi-threaded mandiri untuk melayani multi-klien kantor."""
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: Tuple[str, int],
        handler_cls,
        service: ArsiptaServerService
    ):
        super().__init__(server_address, handler_cls)
        self.service = service


class SyncClientEngine:
    """
    Mesin Klien Sinkronisasi ARSIPTA.
    Menghubungkan klien desktop ke Server Kantor melalui protokol HTTP JSON.
    Mendukung mock_service untuk pengujian in-memory tanpa batas jaringan.
    """

    def __init__(self, mock_service: Optional[ArsiptaServerService] = None):
        self.mock_service = mock_service

    def _request(
        self,
        server_url: str,
        path: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        token: str = "",
        timeout: float = DEFAULT_CLIENT_TIMEOUT
    ) -> Tuple[int, Dict[str, Any], str]:
        clean_url = server_url.rstrip("/")
        full_path = path if path.startswith("/") else f"/{path}"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": f"ARSIPTA-Client/{APP_VERSION}"
        }
        if token:
            headers["X-Arsipta-Token"] = token

        body_bytes = json.dumps(data).encode("utf-8") if data is not None else b""

        if self.mock_service is not None:
            code, _, res_bytes = self.mock_service.handle_request(
                method, full_path, headers, body_bytes, client_ip="127.0.0.1"
            )
            try:
                res_json = json.loads(res_bytes.decode("utf-8")) if res_bytes else {}
            except Exception:
                res_json = {}
            err_msg = res_json.get("error", "") if code >= 400 else ""
            return code, res_json, err_msg

        target_url = f"{clean_url}{full_path}"
        req = urllib.request.Request(
            target_url,
            data=body_bytes if method in ("POST", "PUT") else None,
            headers=headers,
            method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = resp.status
                raw = resp.read()
                try:
                    res_json = json.loads(raw.decode("utf-8"))
                except Exception:
                    res_json = {}
                return code, res_json, ""
        except urllib.error.HTTPError as he:
            try:
                err_body = json.loads(he.read().decode("utf-8"))
                err_msg = err_body.get("error", str(he))
            except Exception:
                err_msg = str(he)
            return he.code, {}, err_msg
        except Exception as exc:
            return 0, {}, f"Gagal menghubungi server: {exc}"

    def ping(
        self, server_url: str, timeout: float = 4.0
    ) -> Tuple[bool, Dict[str, Any], str]:
        code, data, err = self._request(
            server_url, "/api/status", "GET", timeout=timeout
        )
        if code == 200 and data.get("success"):
            return True, data, ""
        return False, {}, err or f"Respon server tidak valid (HTTP {code})"

    def authenticate(
        self,
        server_url: str,
        username: str,
        password: str,
        timeout: float = 4.0
    ) -> Tuple[bool, Dict[str, Any], str]:
        payload = {"username": username, "password": password}
        code, data, err = self._request(
            server_url, "/api/auth", "POST", payload, timeout=timeout
        )
        if code == 200 and data.get("success"):
            return True, data, ""
        return False, {}, err or "Autentikasi server gagal."

    def pull_records(
        self,
        server_url: str,
        token: str = "",
        timeout: float = 8.0
    ) -> Tuple[bool, List[ArchiveRecord], str]:
        code, data, err = self._request(
            server_url, "/api/archives", "GET", token=token, timeout=timeout
        )
        if code == 200 and data.get("success"):
            records = [
                ArchiveRecord.from_dict(r)
                for r in data.get("records", [])
                if isinstance(r, dict)
            ]
            return True, records, ""
        return False, [], err or f"Gagal mengunduh arsip (HTTP {code})"

    def push_record(
        self,
        server_url: str,
        record: ArchiveRecord,
        token: str = "",
        timeout: float = 6.0
    ) -> Tuple[bool, str]:
        code, data, err = self._request(
            server_url,
            "/api/archives",
            "POST",
            record.to_dict(),
            token=token,
            timeout=timeout
        )
        if code in (200, 201) and data.get("success"):
            return True, data.get("message", "Berhasil disimpan di server.")
        return False, err or f"Gagal mengirim arsip ke server (HTTP {code})"

    def sync_two_way(
        self,
        server_url: str,
        local_storage: StorageEngine,
        token: str = "",
        username: str = "",
        timeout: float = 12.0
    ) -> Tuple[bool, SyncReport]:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        local_records = local_storage.get_all_archives()

        payload = {
            "token": token,
            "client_username": username or "arsiparis",
            "records": [r.to_dict() for r in local_records]
        }
        code, data, err = self._request(
            server_url,
            "/api/sync",
            "POST",
            payload,
            token=token,
            timeout=timeout
        )
        if code != 200 or not data.get("success"):
            report = SyncReport(
                success=False,
                aksi="two_way",
                dikirim=len(local_records),
                pesan=err or f"Gagal tersambung ke server kantor (HTTP {code})",
                waktu=now_str
            )
            return False, report

        server_records_raw = data.get("records", [])
        server_records = [
            ArchiveRecord.from_dict(r)
            for r in server_records_raw
            if isinstance(r, dict)
        ]

        ins, upd, unt, local_errs = local_storage.reconcile_records(server_records)
        server_ins = data.get("server_inserted", 0)
        server_upd = data.get("server_updated", 0)

        report = SyncReport(
            success=True,
            aksi="two_way",
            dikirim=len(local_records),
            diterima=len(server_records),
            diperbarui_lokal=upd,
            diperbarui_server=server_upd,
            konflik_diselesaikan=upd + server_upd,
            pesan=(
                f"Sinkronisasi dua arah sukses: "
                f"+{ins} disisipkan & {upd} diperbarui lokal, "
                f"+{server_ins} disisipkan & {server_upd} diperbarui di server."
            ),
            waktu=now_str,
            daftar_kesalahan=local_errs
        )
        local_storage.set_sync_meta("last_sync_time", now_str)
        local_storage.set_sync_meta("last_sync_report", report.pesan)
        return True, report

    def sync_pull(
        self,
        server_url: str,
        local_storage: StorageEngine,
        token: str = "",
        timeout: float = 10.0
    ) -> Tuple[bool, SyncReport]:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ok, records, err = self.pull_records(server_url, token, timeout=timeout)
        if not ok:
            return False, SyncReport(
                success=False, aksi="pull", pesan=err, waktu=now_str
            )
        ins, upd, unt, errs = local_storage.reconcile_records(records)
        report = SyncReport(
            success=True,
            aksi="pull",
            diterima=len(records),
            diperbarui_lokal=upd,
            pesan=f"Tarik data selesai: +{ins} baru disisipkan, {upd} diperbarui dari server.",
            waktu=now_str,
            daftar_kesalahan=errs
        )
        local_storage.set_sync_meta("last_sync_time", now_str)
        return True, report

    def sync_push(
        self,
        server_url: str,
        local_storage: StorageEngine,
        token: str = "",
        timeout: float = 10.0
    ) -> Tuple[bool, SyncReport]:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        local_records = local_storage.get_all_archives()
        payload = {
            "token": token,
            "client_username": "arsiparis",
            "records": [r.to_dict() for r in local_records]
        }
        code, data, err = self._request(
            server_url,
            "/api/sync",
            "POST",
            payload,
            token=token,
            timeout=timeout
        )
        if code != 200 or not data.get("success"):
            return False, SyncReport(
                success=False,
                aksi="push",
                dikirim=len(local_records),
                pesan=err,
                waktu=now_str
            )
        server_ins = data.get("server_inserted", 0)
        server_upd = data.get("server_updated", 0)
        report = SyncReport(
            success=True,
            aksi="push",
            dikirim=len(local_records),
            diperbarui_server=server_upd,
            pesan=f"Kirim data sukses: +{server_ins} arsip baru, {server_upd} diperbarui di server.",
            waktu=now_str
        )
        local_storage.set_sync_meta("last_sync_time", now_str)
        return True, report


# ==============================================================================
# LAYER 4: LOGIKA BISNIS, WORKER LATAR BELAKANG, & MANAJEMEN SESI
# ==============================================================================

class SpreadsheetJobWorker(QThread):
    """Worker thread agar proses impor dan ekspor tidak memblokir GUI."""
    progress = Signal(int, str)
    finished_job = Signal(bool, str, dict)

    def __init__(
        self,
        mode: str,
        db_path: str,
        file_path: str,
        update_existing: bool = False,
        records_to_export: Optional[List[ArchiveRecord]] = None
    ):
        super().__init__()
        self.mode = mode
        self.db_path = db_path
        self.file_path = file_path
        self.update_existing = update_existing
        self.records_to_export = records_to_export or []

    def run(self):
        try:
            storage = StorageEngine(self.db_path)
            if self.mode == "import":
                self.progress.emit(25, "Membuat salinan aman & membaca file...")
                records, warnings = SpreadsheetIOEngine.parse_spreadsheet_file(
                    self.file_path
                )
                self.progress.emit(
                    65, f"Menyimpan {len(records)} baris ke basis data..."
                )
                ins, upd, skip = storage.upsert_archive_batch(
                    records, self.update_existing
                )
                storage.log_recent_file(
                    os.path.basename(self.file_path),
                    self.file_path,
                    f"Impor (+{ins} baru, {upd} diperbarui)"
                )
                self.progress.emit(100, "Selesai.")
                summary_msg = (
                    f"Impor selesai!\n"
                    f"• Ditambahkan baru : {ins} arsip\n"
                    f"• Diperbarui       : {upd} arsip\n"
                    f"• Dilewati (duplikat): {skip} arsip"
                )
                self.finished_job.emit(
                    True,
                    summary_msg,
                    {
                        "inserted": ins,
                        "updated": upd,
                        "skipped": skip,
                        "warnings": warnings
                    }
                )
            elif self.mode == "export":
                self.progress.emit(
                    40,
                    f"Menulis {len(self.records_to_export)} arsip ke file..."
                )
                ok, msg = SpreadsheetIOEngine.export_records(
                    self.records_to_export, self.file_path
                )
                if ok:
                    storage.log_recent_file(
                        os.path.basename(self.file_path),
                        self.file_path,
                        f"Ekspor ({len(self.records_to_export)} arsip)"
                    )
                self.progress.emit(100, "Selesai.")
                self.finished_job.emit(ok, msg, {})
        except Exception as exc:
            self.finished_job.emit(False, str(exc), {})


class SyncJobWorker(QThread):
    """Worker latar belakang untuk proses sinkronisasi non-blocking."""
    progress = Signal(int, str)
    finished_job = Signal(bool, str, object)

    def __init__(
        self,
        client: SyncClientEngine,
        action: str,
        server_url: str,
        storage: StorageEngine,
        token: str = "",
        username: str = "",
        parent=None
    ):
        super().__init__(parent)
        self.client = client
        self.action = action
        self.server_url = server_url
        self.storage = storage
        self.token = token
        self.username = username

    def run(self):
        try:
            self.progress.emit(15, "Menghubungi Server Kantor...")
            if self.action == "pull":
                self.progress.emit(40, "Mengunduh arsip dari server...")
                ok, report = self.client.sync_pull(
                    self.server_url, self.storage, self.token
                )
            elif self.action == "push":
                self.progress.emit(40, "Mengunggah arsip lokal ke server...")
                ok, report = self.client.sync_push(
                    self.server_url, self.storage, self.token
                )
            else:
                self.progress.emit(35, "Menyelaraskan data dua arah dengan server...")
                ok, report = self.client.sync_two_way(
                    self.server_url, self.storage, self.token, self.username
                )

            self.progress.emit(100, "Proses sinkronisasi selesai.")
            self.finished_job.emit(ok, report.pesan, report)
        except Exception as exc:
            err_rep = SyncReport(
                success=False,
                aksi=self.action,
                pesan=f"Kesalahan internal sinkronisasi: {exc}",
                waktu=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            self.finished_job.emit(False, str(exc), err_rep)


class ServerHostWorker(QThread):
    """Worker latar belakang yang menjalankan server HTTP mandiri ARSIPTA."""
    server_state_changed = Signal(bool, str)

    def __init__(
        self,
        storage: StorageEngine,
        host: str = DEFAULT_SERVER_HOST,
        port: int = DEFAULT_SERVER_PORT,
        secret_token: str = DEFAULT_SERVER_TOKEN,
        parent=None
    ):
        super().__init__(parent)
        self.storage = storage
        self.host = host
        self.port = port
        self.secret_token = secret_token
        self.service = ArsiptaServerService(storage, secret_token)
        self.httpd: Optional[ArsiptaHttpServer] = None
        self._is_running = False

    def run(self):
        try:
            self.httpd = ArsiptaHttpServer(
                (self.host, self.port), ArsiptaHttpHandler, self.service
            )
            self._is_running = True
            self.server_state_changed.emit(
                True, f"Server kantor aktif di port {self.port}"
            )
            self.httpd.serve_forever()
        except Exception as exc:
            self._is_running = False
            self.server_state_changed.emit(
                False, f"Gagal menjalankan server kantor: {exc}"
            )
        finally:
            self._is_running = False
            self.server_state_changed.emit(False, "Server kantor dihentikan.")

    def stop(self):
        if self.httpd and self._is_running:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass
            self._is_running = False
        self.wait(2000)


class ArsiptaController(QObject):
    """
    Pengendali utama yang menjembatani penyimpanan, mesin pemrosesan,
    konektivitas server kantor mandiri, dan antarmuka pengguna tanpa memblokir thread UI.
    """
    data_updated = Signal()
    status_message = Signal(str)
    server_status_changed = Signal(bool, str)
    sync_finished = Signal(bool, str, object)

    def __init__(self, storage: StorageEngine):
        super().__init__()
        self.storage = storage
        self.engine = ArchiveProcessingEngine()
        self.active_filter = FilterCriteria()
        self.sync_client = SyncClientEngine()
        self.server_worker: Optional[ServerHostWorker] = None
        self.server_token = DEFAULT_SERVER_TOKEN
        self.last_sync_report: Optional[SyncReport] = None
        self.auto_sync_enabled = True

        self.session = UserSession(
            username="arsiparis",
            nama_lengkap="Arsiparis Utama",
            peran="Arsiparis",
            mode_koneksi="Mode Lokal",
            server_url="http://localhost:8080",
            server_token=self.server_token
        )

    def get_summary(self) -> Dict[str, Any]:
        records = self.storage.get_all_archives()
        return self.engine.compute_dashboard_metrics(records)

    def get_archives(self) -> List[ArchiveRecord]:
        return self.storage.get_all_archives()

    def get_archive_by_id(self, archive_id: int) -> Optional[ArchiveRecord]:
        return self.storage.get_archive_by_id(archive_id)

    def search_archives(
        self, criteria: FilterCriteria
    ) -> Tuple[List[ArchiveRecord], int]:
        self.active_filter = criteria
        all_records = self.storage.get_all_archives()
        filtered = self.engine.filter_archives(all_records, criteria)
        return filtered, len(all_records)

    def get_filtered_archives_snapshot(self) -> List[ArchiveRecord]:
        filtered, _ = self.search_archives(self.active_filter)
        return filtered

    def get_topics(self) -> List[str]:
        return self.storage.get_distinct_topics()

    def get_retention_watchlist(self) -> List[Tuple[ArchiveRecord, str, int]]:
        all_records = self.storage.get_all_archives()
        return self.engine.get_retention_alerts(all_records)

    def create_archive(self, record: ArchiveRecord) -> Tuple[bool, str]:
        ok, msg = self.storage.add_archive(record)
        if ok:
            self.data_updated.emit()
            if self.session.mode_koneksi == "Mode Server Kantor" and self.auto_sync_enabled:
                try:
                    self.sync_client.push_record(
                        self.session.server_url, record, self.server_token
                    )
                except Exception:
                    pass
        return ok, msg

    def edit_archive(self, record: ArchiveRecord) -> Tuple[bool, str]:
        ok, msg = self.storage.update_archive(record)
        if ok:
            self.data_updated.emit()
            if self.session.mode_koneksi == "Mode Server Kantor" and self.auto_sync_enabled:
                try:
                    self.sync_client.push_record(
                        self.session.server_url, record, self.server_token
                    )
                except Exception:
                    pass
        return ok, msg

    def set_archive_status(
        self, archive_id: int, new_status: str
    ) -> Tuple[bool, str]:
        ok, msg = self.storage.update_archive_status(archive_id, new_status)
        if ok:
            self.data_updated.emit()
        return ok, msg

    def remove_archive(self, archive_id: int) -> Tuple[bool, str]:
        ok, msg = self.storage.delete_archive(archive_id)
        if ok:
            self.data_updated.emit()
        return ok, msg

    def get_recent_files(self) -> List[Dict[str, str]]:
        return self.storage.get_recent_files()

    def switch_session(
        self, username: str, password: str, mode: str, server_url: str, server_token: str = ""
    ) -> Tuple[bool, str]:
        """Memvalidasi login lokal dan mengatur mode kerja."""
        user_data = self.storage.authenticate_user(username, password)
        if not user_data:
            return False, "Nama pengguna atau kata sandi tidak sesuai."

        clean_url = server_url.strip()
        if mode == "Mode Server Kantor" and not clean_url:
            return (
                False,
                "Alamat URL server kantor wajib diisi saat memilih Mode Server Kantor."
            )

        if server_token.strip():
            self.server_token = server_token.strip()

        self.session = UserSession(
            username=user_data["username"],
            nama_lengkap=user_data["nama_lengkap"],
            peran=user_data["peran"],
            mode_koneksi=mode,
            server_url=clean_url if mode == "Mode Server Kantor" else "",
            server_token=self.server_token,
            terautentikasi=True
        )
        self.data_updated.emit()
        return (
            True,
            f"Berhasil masuk sebagai {self.session.nama_lengkap} dalam {mode}."
        )

    def register_new_account(
        self, username: str, password: str, nama_lengkap: str
    ) -> Tuple[bool, str]:
        return self.storage.register_user(username, password, nama_lengkap)

    def is_server_running(self) -> bool:
        """Mengecek apakah server host mandiri aktif di aplikasi ini."""
        return self.server_worker is not None and self.server_worker.isRunning()

    def start_office_server(
        self,
        port: int = DEFAULT_SERVER_PORT,
        host: str = DEFAULT_SERVER_HOST,
        token: str = ""
    ) -> Tuple[bool, str]:
        """Menjalankan server host mandiri di thread terpisah."""
        if self.is_server_running():
            return False, "Server kantor sudah berjalan pada komputer ini."
        tok = token.strip() or self.server_token
        self.server_token = tok
        self.server_worker = ServerHostWorker(
            self.storage, host=host, port=port, secret_token=tok
        )
        self.server_worker.server_state_changed.connect(self._on_server_state_changed)
        self.server_worker.start()
        return True, f"Memulai server kantor pada port {port}..."

    def _on_server_state_changed(self, running: bool, msg: str):
        self.server_status_changed.emit(running, msg)
        self.data_updated.emit()

    def stop_office_server(self) -> Tuple[bool, str]:
        """Menghentikan server host mandiri."""
        if not self.is_server_running():
            return False, "Server kantor tidak sedang berjalan."
        if self.server_worker:
            self.server_worker.stop()
            self.server_worker = None
        self.server_status_changed.emit(False, "Server kantor dihentikan.")
        self.data_updated.emit()
        return True, "Server kantor berhasil dihentikan."

    def get_local_ip_addresses(self) -> List[str]:
        """Mendapatkan daftar alamat IP lokal pada antarmuka jaringan komputer ini."""
        ips: List[str] = []
        try:
            hostname = socket.gethostname()
            _, _, addrs = socket.gethostbyname_ex(hostname)
            for a in addrs:
                if not a.startswith("127.") and a not in ips:
                    ips.append(a)
        except Exception:
            pass
        if not ips:
            ips.append("127.0.0.1")
        return ips

    def test_remote_server(self, server_url: str) -> Tuple[bool, str, Dict[str, Any]]:
        """Menguji konektivitas ke alamat server kantor."""
        clean_url = server_url.strip()
        if not clean_url:
            return False, "Alamat URL server tidak boleh kosong.", {}
        ok, data, err = self.sync_client.ping(clean_url)
        if ok:
            name = data.get("server_name", "ARSIPTA Server")
            ver = data.get("version", "")
            tot = data.get("total_archives", 0)
            return True, f"Terhubung ke {name} ({ver}) — {tot} arsip tersedia.", data
        return False, err or "Server tidak merespon.", {}

    def trigger_sync(
        self,
        action: str = "two_way",
        on_progress=None,
        on_finished=None
    ) -> SyncJobWorker:
        """Menjalankan proses sinkronisasi melalui SyncJobWorker non-blocking."""
        worker = SyncJobWorker(
            client=self.sync_client,
            action=action,
            server_url=self.session.server_url or "http://localhost:8080",
            storage=self.storage,
            token=self.server_token,
            username=self.session.username
        )
        if on_progress:
            worker.progress.connect(on_progress)

        def _on_done(ok: bool, msg: str, report: object):
            if isinstance(report, SyncReport):
                self.last_sync_report = report
            self.sync_finished.emit(ok, msg, report)
            self.data_updated.emit()
            if on_finished:
                on_finished(ok, msg, report)

        worker.finished_job.connect(_on_done)
        worker.start()
        return worker


# ==============================================================================
# LAYER 5: ANTARMUKA PENGGUNA DESKTOP (PySide6 UI & Tema Terang/Gelap)
# ==============================================================================

class ThemeManager:
    """Mengelola palet warna profesional yang konsisten untuk tema Terang dan Gelap."""

    LIGHT = {
        "bg_window": "#F7F7F5",
        "bg_sidebar": "#EFEFEB",
        "bg_card": "#FFFFFF",
        "bg_subtle": "#FAFAF8",
        "bg_input": "#FFFFFF",
        "bg_hover": "#E6E8E1",
        "bg_active": "#E2E4DC",
        "border": "#D2D6CE",
        "border_soft": "#E2E4E0",
        "text_primary": "#181A18",
        "text_secondary": "#424842",
        "text_muted": "#687068",
        "accent": "#1B4D3E",
        "accent_hover": "#143A2F",
        "accent_text": "#FFFFFF",
        "danger": "#DC2626",
        "danger_hover": "#B91C1C",
        "badge_bg": "#EAF3ED",
        "badge_text": "#1E5631",
        "scrollbar_bg": "#F7F7F5",
        "scrollbar_handle": "#C9CEC6",
    }

    DARK = {
        "bg_window": "#0F172A",
        "bg_sidebar": "#1E293B",
        "bg_card": "#1E293B",
        "bg_subtle": "#0F172A",
        "bg_input": "#0F172A",
        "bg_hover": "#334155",
        "bg_active": "#1E3A8A",
        "border": "#334155",
        "border_soft": "#334155",
        "text_primary": "#F8FAFC",
        "text_secondary": "#CBD5E1",
        "text_muted": "#94A3B8",
        "accent": "#3B82F6",
        "accent_hover": "#60A5FA",
        "accent_text": "#FFFFFF",
        "danger": "#EF4444",
        "danger_hover": "#DC2626",
        "badge_bg": "#1E3A8A",
        "badge_text": "#93C5FD",
        "scrollbar_bg": "#0F172A",
        "scrollbar_handle": "#475569",
    }

    @classmethod
    def build_stylesheet(cls, dark_mode: bool) -> str:
        t = cls.DARK if dark_mode else cls.LIGHT
        return f"""
        QMainWindow, QDialog, QWidget#MainContentArea, QWidget#ScrollContainer {{
            background-color: {t['bg_window']};
            color: {t['text_primary']};
            font-family: "Segoe UI", "Plus Jakarta Sans", "Inter", sans-serif;
            font-size: 13px;
        }}
        QScrollArea {{
            background-color: {t['bg_window']};
            border: none;
        }}
        QScrollArea > QWidget > QWidget {{
            background-color: {t['bg_window']};
        }}
        QFrame#Sidebar {{
            background-color: {t['bg_sidebar']};
            border-right: 1px solid {t['border_soft']};
        }}
        QFrame.Card {{
            background-color: {t['bg_card']};
            border: 1px solid {t['border_soft']};
            border-radius: 10px;
        }}
        QFrame.SubtleBox {{
            background-color: {t['bg_subtle']};
            border: 1px solid {t['border_soft']};
            border-radius: 8px;
        }}
        QFrame.ClickableCard {{
            background-color: {t['bg_card']};
            border: 1px solid {t['border_soft']};
            border-radius: 10px;
        }}
        QFrame.ClickableCard:hover {{
            border: 1px solid {t['accent']};
            background-color: {t['bg_hover']};
        }}
        QLabel {{
            background-color: transparent;
            color: {t['text_primary']};
        }}
        QLabel.TitleLarge {{
            font-size: 22px;
            font-weight: 700;
            color: {t['text_primary']};
        }}
        QLabel.SectionTitle {{
            font-size: 15px;
            font-weight: 600;
            color: {t['text_primary']};
        }}
        QLabel.MutedText {{
            color: {t['text_secondary']};
            font-size: 12px;
        }}
        QLabel.HintText {{
            color: {t['text_muted']};
            font-size: 11px;
        }}
        QLabel.MetricValue {{
            font-size: 26px;
            font-weight: 700;
            color: {t['text_primary']};
        }}
        QLabel.StatusBadge {{
            background-color: {t['badge_bg']};
            color: {t['badge_text']};
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 11px;
            font-weight: 600;
        }}
        QPushButton.NavButton {{
            text-align: left;
            padding: 10px 14px;
            border-radius: 8px;
            border: none;
            background-color: transparent;
            color: {t['text_secondary']};
            font-weight: 500;
        }}
        QPushButton.NavButton:hover {{
            background-color: {t['bg_hover']};
            color: {t['text_primary']};
        }}
        QPushButton.NavButton[active="true"] {{
            background-color: {t['bg_active']};
            color: {t['accent']};
            font-weight: 600;
        }}
        QPushButton.PrimaryButton {{
            background-color: {t['accent']};
            color: {t['accent_text']};
            border: none;
            border-radius: 7px;
            padding: 8px 16px;
            font-weight: 600;
        }}
        QPushButton.PrimaryButton:hover {{
            background-color: {t['accent_hover']};
        }}
        QPushButton.SecondaryButton {{
            background-color: {t['bg_card']};
            color: {t['text_primary']};
            border: 1px solid {t['border']};
            border-radius: 7px;
            padding: 8px 14px;
            font-weight: 500;
        }}
        QPushButton.SecondaryButton:hover {{
            background-color: {t['bg_hover']};
        }}
        QPushButton.DangerButton {{
            background-color: {t['danger']};
            color: #FFFFFF;
            border: none;
            border-radius: 7px;
            padding: 8px 14px;
            font-weight: 600;
        }}
        QPushButton.DangerButton:hover {{
            background-color: {t['danger_hover']};
        }}
        QLineEdit, QComboBox, QDateEdit, QTextEdit {{
            background-color: {t['bg_input']};
            color: {t['text_primary']};
            border: 1px solid {t['border']};
            border-radius: 7px;
            padding: 6px 10px;
            min-height: 20px;
        }}
        QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled {{
            background-color: {t['bg_subtle']};
            color: {t['text_muted']};
        }}
        QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{
            border: 1px solid {t['accent']};
        }}
        QComboBox QAbstractItemView {{
            background-color: {t['bg_card']};
            color: {t['text_primary']};
            selection-background-color: {t['bg_active']};
            selection-color: {t['text_primary']};
            border: 1px solid {t['border']};
        }}
        QProgressBar {{
            background-color: {t['bg_subtle']};
            border: 1px solid {t['border']};
            border-radius: 6px;
            text-align: center;
            color: {t['text_primary']};
            height: 18px;
        }}
        QProgressBar::chunk {{
            background-color: {t['accent']};
            border-radius: 5px;
        }}
        QTableWidget {{
            font-size: 12px;
            background-color: {t['bg_card']};
            color: {t['text_primary']};
            border: 1px solid {t['border_soft']};
            border-radius: 8px;
            gridline-color: {t['border_soft']};
            selection-background-color: {t['bg_active']};
            selection-color: {t['text_primary']};
        }}
        QTableWidget::item {{
            padding: 8px 10px;
            color: {t['text_primary']};
            border-bottom: 1px solid {t['border_soft']};
        }}
        QTableWidget::item:selected {{
            background-color: {t['bg_active']};
            color: {t['text_primary']};
        }}
        QHeaderView::section {{
            background-color: {t['bg_subtle']};
            color: {t['text_secondary']};
            padding: 10px 9px;
            border: none;
            border-bottom: 1px solid {t['border_soft']};
            font-weight: 600;
        }}
        QTableCornerButton::section {{
            background-color: {t['bg_subtle']};
            border: none;
            border-bottom: 1px solid {t['border_soft']};
        }}
        QScrollBar:vertical {{
            background: {t['scrollbar_bg']};
            width: 10px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {t['scrollbar_handle']};
            min-height: 24px;
            border-radius: 5px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QMessageBox {{
            background-color: {t['bg_card']};
            color: {t['text_primary']};
        }}
        """


class VisibleCheckBox(QCheckBox):
    """Kotak centang kontras tinggi yang jelas terlihat di Mode Terang & Gelap."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.dark_mode = False
        self.setCursor(Qt.PointingHandCursor)

    def set_theme(self, dark_mode: bool):
        self.dark_mode = dark_mode
        self.update()

    def sizeHint(self):
        sh = super().sizeHint()
        sh.setWidth(sh.width() + 10)
        return sh

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        box_size = 18
        y_offset = (self.height() - box_size) // 2
        box_rect = QRect(2, y_offset, box_size, box_size)

        if self.isChecked():
            fill_color = (
                QColor("#3B82F6") if self.dark_mode else QColor("#2563EB")
            )
            border_color = fill_color
        else:
            fill_color = (
                QColor("#0F172A") if self.dark_mode else QColor("#FFFFFF")
            )
            border_color = (
                QColor("#94A3B8") if self.dark_mode else QColor("#475569")
            )

        painter.setPen(QPen(border_color, 1.8))
        painter.setBrush(fill_color)
        painter.drawRoundedRect(box_rect, 4, 4)

        if self.isChecked():
            check_pen = QPen(QColor("#FFFFFF"), 2.2)
            check_pen.setCapStyle(Qt.RoundCap)
            check_pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(check_pen)
            p1 = QPoint(box_rect.left() + 4, box_rect.top() + 9)
            p2 = QPoint(box_rect.left() + 8, box_rect.top() + 13)
            p3 = QPoint(box_rect.left() + 14, box_rect.top() + 5)
            painter.drawPolyline([p1, p2, p3])

        text_color = QColor("#F8FAFC") if self.dark_mode else QColor("#0F172A")
        painter.setPen(text_color)
        font = self.font()
        font.setWeight(QFont.Medium)
        painter.setFont(font)
        text_rect = QRect(
            box_rect.right() + 8,
            0,
            self.width() - (box_rect.right() + 8),
            self.height()
        )
        painter.drawText(
            text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text()
        )


class VisibleRadioButton(QRadioButton):
    """Tombol pilihan radio kontras tinggi untuk Mode Terang & Gelap."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.dark_mode = False
        self.setCursor(Qt.PointingHandCursor)

    def set_theme(self, dark_mode: bool):
        self.dark_mode = dark_mode
        self.update()

    def sizeHint(self):
        sh = super().sizeHint()
        sh.setWidth(sh.width() + 10)
        return sh

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        circle_size = 18
        y_offset = (self.height() - circle_size) // 2
        circle_rect = QRect(2, y_offset, circle_size, circle_size)

        if self.isChecked():
            border_color = (
                QColor("#3B82F6") if self.dark_mode else QColor("#2563EB")
            )
        else:
            border_color = (
                QColor("#94A3B8") if self.dark_mode else QColor("#475569")
            )
        fill_color = QColor("#0F172A") if self.dark_mode else QColor("#FFFFFF")

        painter.setPen(QPen(border_color, 1.8))
        painter.setBrush(fill_color)
        painter.drawEllipse(circle_rect)

        if self.isChecked():
            inner_rect = circle_rect.adjusted(4, 4, -4, -4)
            painter.setPen(Qt.NoPen)
            painter.setBrush(border_color)
            painter.drawEllipse(inner_rect)

        text_color = QColor("#F8FAFC") if self.dark_mode else QColor("#0F172A")
        painter.setPen(text_color)
        font = self.font()
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        text_rect = QRect(
            circle_rect.right() + 8,
            0,
            self.width() - (circle_rect.right() + 8),
            self.height()
        )
        painter.drawText(
            text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text()
        )


class SortableTableItem(QTableWidgetItem):
    """Item tabel yang mendukung pengurutan numerik/tanggal secara akurat."""

    def __init__(self, text: str, sort_key: Any = None):
        super().__init__(text)
        self.sort_key = sort_key if sort_key is not None else text.lower()

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, SortableTableItem):
            try:
                return self.sort_key < other.sort_key
            except TypeError:
                return str(self.sort_key) < str(other.sort_key)
        return super().__lt__(other)


class ClickableCard(QFrame):
    """Kartu interaktif dengan sinyal klik dan kursor penunjuk."""
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "ClickableCard")
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class StatusCompositionWidget(QWidget):
    """
    Visualisasi Grafik Donat (Donut Chart) + Batang Proporsi
    untuk membandingkan Arsip Aktif vs Arsip Inaktif secara langsung.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.aktif_count = 0
        self.inaktif_count = 0
        self.dark_mode = False
        self.setMinimumHeight(145)
        self.setMaximumHeight(160)

    def set_values(self, aktif: int, inaktif: int):
        self.aktif_count = max(0, aktif)
        self.inaktif_count = max(0, inaktif)
        self.update()

    def set_theme(self, dark_mode: bool):
        self.dark_mode = dark_mode
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()

        total = self.aktif_count + self.inaktif_count
        aktif_pct = (self.aktif_count / total * 100.0) if total > 0 else 0.0
        inaktif_pct = (self.inaktif_count / total * 100.0) if total > 0 else 0.0

        color_aktif = QColor("#10B981")
        color_inaktif = (
            QColor("#64748B") if self.dark_mode else QColor("#94A3B8")
        )
        color_empty = (
            QColor("#334155") if self.dark_mode else QColor("#E2E8F0")
        )
        color_center_bg = (
            QColor("#1E293B") if self.dark_mode else QColor("#FFFFFF")
        )
        text_primary = (
            QColor("#F8FAFC") if self.dark_mode else QColor("#0F172A")
        )
        text_secondary = (
            QColor("#CBD5E1") if self.dark_mode else QColor("#475569")
        )

        # 1. Gambar Grafik Donat di Sisi Kiri
        donut_size = min(124, rect.height() - 16)
        donut_x = 12
        donut_y = (rect.height() - donut_size) // 2
        outer_rect = QRectF(donut_x, donut_y, donut_size, donut_size)

        painter.setPen(Qt.NoPen)
        if total == 0:
            painter.setBrush(color_empty)
            painter.drawEllipse(outer_rect)
        else:
            aktif_span = int(round((self.aktif_count / total) * 360 * 16))
            inaktif_span = (360 * 16) - aktif_span

            if aktif_span > 0:
                painter.setBrush(color_aktif)
                painter.drawPie(outer_rect, 90 * 16, -aktif_span)
            if inaktif_span > 0:
                painter.setBrush(color_inaktif)
                painter.drawPie(
                    outer_rect, (90 * 16) - aktif_span, -inaktif_span
                )

        # Lubang tengah Donat
        hole_margin = donut_size * 0.27
        inner_rect = outer_rect.adjusted(
            hole_margin, hole_margin, -hole_margin, -hole_margin
        )
        painter.setBrush(color_center_bg)
        painter.drawEllipse(inner_rect)

        # Angka total di tengah Donat
        painter.setPen(text_primary)
        f_num = QFont("Segoe UI", 15, QFont.Bold)
        painter.setFont(f_num)
        painter.drawText(
            inner_rect.adjusted(0, -8, 0, 0),
            Qt.AlignCenter,
            str(total)
        )
        painter.setPen(text_secondary)
        f_lbl = QFont("Segoe UI", 8)
        painter.setFont(f_lbl)
        painter.drawText(
            inner_rect.adjusted(0, 18, 0, 0),
            Qt.AlignCenter,
            "Total"
        )

        # 2. Gambar Legenda & Batang Perbandingan di Sisi Kanan
        right_x = donut_x + donut_size + 28
        right_w = max(120, rect.width() - right_x - 16)

        # Baris Arsip Aktif
        y_aktif = donut_y + 12
        painter.setBrush(color_aktif)
        painter.drawRoundedRect(right_x, y_aktif + 3, 12, 12, 3, 3)

        painter.setPen(text_primary)
        painter.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        painter.drawText(
            right_x + 20,
            y_aktif,
            right_w - 20,
            18,
            Qt.AlignLeft | Qt.AlignVCenter,
            f"Arsip Aktif: {self.aktif_count} dokumen ({aktif_pct:.1f}%)"
        )

        bar_aktif_rect = QRect(right_x, y_aktif + 22, right_w, 12)
        clip_a = QPainterPath()
        clip_a.addRoundedRect(QRectF(bar_aktif_rect), 6, 6)
        painter.save()
        painter.setClipPath(clip_a)
        painter.fillRect(bar_aktif_rect, color_empty)
        if total > 0 and self.aktif_count > 0:
            w_a = int((self.aktif_count / total) * right_w)
            painter.fillRect(
                right_x, y_aktif + 22, w_a, 12, color_aktif
            )
        painter.restore()

        # Baris Arsip Inaktif
        y_inaktif = y_aktif + 52
        painter.setBrush(color_inaktif)
        painter.drawRoundedRect(right_x, y_inaktif + 3, 12, 12, 3, 3)

        painter.setPen(text_primary)
        painter.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        painter.drawText(
            right_x + 20,
            y_inaktif,
            right_w - 20,
            18,
            Qt.AlignLeft | Qt.AlignVCenter,
            f"Arsip Inaktif: {self.inaktif_count} dokumen ({inaktif_pct:.1f}%)"
        )

        bar_inaktif_rect = QRect(right_x, y_inaktif + 22, right_w, 12)
        clip_i = QPainterPath()
        clip_i.addRoundedRect(QRectF(bar_inaktif_rect), 6, 6)
        painter.save()
        painter.setClipPath(clip_i)
        painter.fillRect(bar_inaktif_rect, color_empty)
        if total > 0 and self.inaktif_count > 0:
            w_i = int((self.inaktif_count / total) * right_w)
            painter.fillRect(
                right_x, y_inaktif + 22, w_i, 12, color_inaktif
            )
        painter.restore()


class ArchiveFormDialog(QDialog):
    """Dialog formulir untuk menambah atau mengubah catatan arsip perjanjian."""

    def __init__(
        self,
        controller: ArsiptaController,
        dark_mode: bool,
        existing: Optional[ArchiveRecord] = None,
        parent=None
    ):
        super().__init__(parent)
        self.controller = controller
        self.existing = existing
        is_edit = existing is not None

        self.setWindowTitle(
            "Ubah Data Arsip Perjanjian"
            if is_edit
            else "Tambah Arsip Perjanjian Baru"
        )
        self.setMinimumWidth(480)
        self.setStyleSheet(ThemeManager.build_stylesheet(dark_mode))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        title = QLabel(
            f"Edit Dokumen: {existing.nomor_dokumen}"
            if is_edit
            else "Input Arsip Perjanjian Baru"
        )
        title.setProperty("class", "SectionTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.input_nomor = QLineEdit(existing.nomor_dokumen if is_edit else "")
        self.input_nomor.setPlaceholderText("Contoh: PKS/2026/015")

        self.input_judul = QLineEdit(
            existing.judul_perjanjian if is_edit else ""
        )
        self.input_judul.setPlaceholderText(
            "Contoh: Perjanjian Kerja Sama Pemeliharaan Server"
        )

        self.input_pihak = QLineEdit(existing.pihak_terkait if is_edit else "")
        self.input_pihak.setPlaceholderText("Contoh: PT Mitra Teknologi")

        self.combo_topik = QComboBox()
        self.combo_topik.setEditable(True)
        default_topics = [
            "Pengadaan Barang & Jasa",
            "Teknologi Informasi",
            "Fasilitas & Infrastruktur",
            "Hukum & Kepatuhan",
            "Sumber Daya Manusia",
            "Keuangan & Perbankan",
            "Kerja Sama Operasional",
        ]
        existing_topics = self.controller.get_topics()
        merged_topics = sorted(list(set(default_topics + existing_topics)))
        self.combo_topik.addItems(merged_topics)
        if is_edit:
            self.combo_topik.setCurrentText(existing.topik)

        self.date_mulai = QDateEdit()
        self.date_mulai.setCalendarPopup(True)
        self.date_mulai.setDisplayFormat("yyyy-MM-dd")
        if is_edit:
            self.date_mulai.setDate(
                QDate.fromString(existing.tanggal_mulai, "yyyy-MM-dd")
            )
        else:
            self.date_mulai.setDate(QDate.currentDate())

        self.date_berakhir = QDateEdit()
        self.date_berakhir.setCalendarPopup(True)
        self.date_berakhir.setDisplayFormat("yyyy-MM-dd")
        if is_edit:
            self.date_berakhir.setDate(
                QDate.fromString(existing.tanggal_berakhir, "yyyy-MM-dd")
            )
        else:
            self.date_berakhir.setDate(QDate.currentDate().addYears(1))

        self.combo_status = QComboBox()
        self.combo_status.addItems(["Aktif", "Inaktif"])
        if is_edit:
            self.combo_status.setCurrentText(existing.status)

        self.input_lokasi = QLineEdit(existing.lokasi_fisik if is_edit else "")
        self.input_lokasi.setPlaceholderText("Contoh: Lemari A - Rak 2 - Map 04")

        form.addRow("Nomor Dokumen *:", self.input_nomor)
        form.addRow("Judul Perjanjian *:", self.input_judul)
        form.addRow("Pihak Terkait *:", self.input_pihak)
        form.addRow("Topik / Kategori *:", self.combo_topik)
        form.addRow("Tanggal Mulai:", self.date_mulai)
        form.addRow("Tanggal Berakhir:", self.date_berakhir)
        form.addRow("Status Arsip:", self.combo_status)
        form.addRow("Lokasi Penyimpanan:", self.input_lokasi)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Batal")
        btn_cancel.setProperty("class", "SecondaryButton")
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Simpan Perubahan" if is_edit else "Simpan Arsip")
        btn_save.setProperty("class", "PrimaryButton")
        btn_save.clicked.connect(self._handle_save)

        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _handle_save(self):
        nomor = self.input_nomor.text().strip()
        judul = self.input_judul.text().strip()
        pihak = self.input_pihak.text().strip()
        topik = self.combo_topik.currentText().strip()
        tgl_mulai = self.date_mulai.date().toString("yyyy-MM-dd")
        tgl_berakhir = self.date_berakhir.date().toString("yyyy-MM-dd")

        if not nomor or not judul or not pihak or not topik:
            QMessageBox.warning(
                self,
                "Data Belum Lengkap",
                "Nomor Dokumen, Judul Perjanjian, Pihak Terkait, "
                "dan Topik wajib diisi."
            )
            return

        if tgl_berakhir < tgl_mulai:
            QMessageBox.warning(
                self,
                "Rentang Tanggal Tidak Valid",
                "Tanggal Berakhir tidak boleh lebih awal dari Tanggal Mulai."
            )
            return

        record = ArchiveRecord(
            id=self.existing.id if self.existing else None,
            nomor_dokumen=nomor,
            judul_perjanjian=judul,
            pihak_terkait=pihak,
            topik=topik,
            tanggal_mulai=tgl_mulai,
            tanggal_berakhir=tgl_berakhir,
            status=self.combo_status.currentText(),
            lokasi_fisik=self.input_lokasi.text().strip(),
            file_sumber=(
                self.existing.file_sumber if self.existing else "Input Manual"
            ),
            diperbarui_pada=""
        )

        if self.existing:
            ok, msg = self.controller.edit_archive(record)
        else:
            ok, msg = self.controller.create_archive(record)

        if ok:
            QMessageBox.information(self, "Berhasil", msg)
            self.accept()
        else:
            QMessageBox.warning(self, "Gagal Menyimpan", msg)


class RegisterAccountDialog(QDialog):
    """Dialog pendaftaran akun arsiparis baru."""

    def __init__(
        self, controller: ArsiptaController, dark_mode: bool, parent=None
    ):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Daftar Akun Arsiparis Baru")
        self.setMinimumWidth(400)
        self.setStyleSheet(ThemeManager.build_stylesheet(dark_mode))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Buat Akun Arsiparis Baru")
        title.setProperty("class", "SectionTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        self.input_nama = QLineEdit()
        self.input_nama.setPlaceholderText("Contoh: Budi Santoso")

        self.input_user = QLineEdit()
        self.input_user.setPlaceholderText("Contoh: budi_arsip")

        self.input_pass = QLineEdit()
        self.input_pass.setEchoMode(QLineEdit.Password)
        self.input_pass.setPlaceholderText("Minimal 4 karakter")

        form.addRow("Nama Lengkap:", self.input_nama)
        form.addRow("Nama Pengguna:", self.input_user)
        form.addRow("Kata Sandi:", self.input_pass)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Batal")
        btn_cancel.setProperty("class", "SecondaryButton")
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Simpan Akun")
        btn_save.setProperty("class", "PrimaryButton")
        btn_save.clicked.connect(self._handle_register)

        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _handle_register(self):
        ok, msg = self.controller.register_new_account(
            self.input_user.text(),
            self.input_pass.text(),
            self.input_nama.text()
        )
        if ok:
            QMessageBox.information(self, "Akun Terdaftar", msg)
            self.accept()
        else:
            QMessageBox.warning(self, "Gagal Mendaftar", msg)


class SessionModeDialog(QDialog):
    """Dialog pengaturan akun arsiparis dan pemilihan mode kerja."""

    def __init__(
        self, controller: ArsiptaController, dark_mode: bool, parent=None
    ):
        super().__init__(parent)
        self.controller = controller
        self.dark_mode = dark_mode
        self.setWindowTitle("Pengaturan Akun & Mode Kerja Arsiparis")
        self.setMinimumWidth(480)
        self.setStyleSheet(ThemeManager.build_stylesheet(dark_mode))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        lbl_header = QLabel("Akun Arsiparis & Mode Kerja")
        lbl_header.setProperty("class", "SectionTitle")
        layout.addWidget(lbl_header)

        info_box = QFrame()
        info_box.setProperty("class", "SubtleBox")
        info_layout = QVBoxLayout(info_box)
        info_layout.setContentsMargins(12, 10, 12, 10)
        lbl_explain = QLabel(
            "Aplikasi ini mendukung kerja mandiri maupun tim:\n"
            "• Mode Lokal: Data tersimpan di PC ini saja tanpa butuh jaringan.\n"
            "• Mode Server Kantor: Menghubungkan ke server lokal perusahaan "
            "agar setiap arsiparis yang masuk memakai akun yang sama melihat "
            "daftar arsip yang sama."
        )
        lbl_explain.setProperty("class", "MutedText")
        lbl_explain.setWordWrap(True)
        info_layout.addWidget(lbl_explain)
        layout.addWidget(info_box)

        mode_box = QFrame()
        mode_box.setProperty("class", "Card")
        mode_layout = QVBoxLayout(mode_box)
        mode_layout.setContentsMargins(14, 12, 14, 12)
        mode_layout.setSpacing(8)

        lbl_mode_title = QLabel("1. Pilih Mode Penyimpanan & Kerja")
        lbl_mode_title.setProperty("class", "SectionTitle")
        mode_layout.addWidget(lbl_mode_title)

        self.radio_lokal = VisibleRadioButton(
            "Mode Lokal (Mandiri di Komputer Ini)"
        )
        self.radio_server = VisibleRadioButton(
            "Mode Server Kantor (Sinkronisasi Tim / Hybrid)"
        )
        self.radio_lokal.set_theme(dark_mode)
        self.radio_server.set_theme(dark_mode)

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.radio_lokal)
        self.mode_group.addButton(self.radio_server)

        is_server = (
            self.controller.session.mode_koneksi == "Mode Server Kantor"
        )
        self.radio_server.setChecked(is_server)
        self.radio_lokal.setChecked(not is_server)

        self.input_server = QLineEdit(
            self.controller.session.server_url or "http://localhost:8080"
        )
        self.input_server.setPlaceholderText(
            "Contoh: http://192.168.1.100:8080"
        )

        self.lbl_server_hint = QLabel()
        self.lbl_server_hint.setProperty("class", "HintText")

        server_row = QHBoxLayout()
        server_row.addWidget(self.input_server)
        self.btn_test_conn = QPushButton("Uji Koneksi")
        self.btn_test_conn.setProperty("class", "SecondaryButton")
        self.btn_test_conn.setCursor(Qt.PointingHandCursor)
        self.btn_test_conn.clicked.connect(self._test_server_connection)
        server_row.addWidget(self.btn_test_conn)

        mode_layout.addWidget(self.radio_lokal)
        mode_layout.addWidget(self.radio_server)
        mode_layout.addLayout(server_row)
        mode_layout.addWidget(self.lbl_server_hint)
        layout.addWidget(mode_box)

        self.radio_lokal.toggled.connect(self._update_server_field_state)
        self._update_server_field_state()

        cred_box = QFrame()
        cred_box.setProperty("class", "Card")
        cred_layout = QVBoxLayout(cred_box)
        cred_layout.setContentsMargins(14, 12, 14, 12)
        cred_layout.setSpacing(8)

        lbl_cred_title = QLabel("2. Identitas Akun Arsiparis")
        lbl_cred_title.setProperty("class", "SectionTitle")
        cred_layout.addWidget(lbl_cred_title)

        form = QFormLayout()
        form.setSpacing(8)
        self.input_user = QLineEdit(self.controller.session.username)
        self.input_user.setPlaceholderText("Masukkan nama pengguna")

        self.input_pass = QLineEdit()
        self.input_pass.setEchoMode(QLineEdit.Password)
        self.input_pass.setPlaceholderText("Masukkan kata sandi")

        form.addRow("Nama Pengguna:", self.input_user)
        form.addRow("Kata Sandi:", self.input_pass)
        cred_layout.addLayout(form)

        lbl_default_hint = QLabel(
            "Akun bawaan uji coba: arsiparis / arsip123  atau  admin / admin123"
        )
        lbl_default_hint.setProperty("class", "HintText")
        cred_layout.addWidget(lbl_default_hint)
        layout.addWidget(cred_box)

        btn_row = QHBoxLayout()
        btn_register = QPushButton("Buat Akun Baru")
        btn_register.setProperty("class", "SecondaryButton")
        btn_register.clicked.connect(self._open_register)

        btn_cancel = QPushButton("Batal")
        btn_cancel.setProperty("class", "SecondaryButton")
        btn_cancel.clicked.connect(self.reject)

        btn_submit = QPushButton("Masuk & Terapkan")
        btn_submit.setProperty("class", "PrimaryButton")
        btn_submit.clicked.connect(self._handle_login)

        btn_row.addWidget(btn_register)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_submit)
        layout.addLayout(btn_row)

    def _update_server_field_state(self):
        use_server = self.radio_server.isChecked()
        self.input_server.setEnabled(use_server)
        self.btn_test_conn.setEnabled(use_server)
        if use_server:
            self.lbl_server_hint.setText(
                "Masukkan alamat IP/URL server kantor tempat database bersama berada."
            )
        else:
            self.lbl_server_hint.setText(
                "Alamat server dinonaktifkan karena Anda memilih Mode Lokal."
            )

    def _test_server_connection(self):
        url = self.input_server.text().strip()
        if not url:
            QMessageBox.warning(self, "Alamat Kosong", "Masukkan alamat server kantor terlebih dahulu.")
            return
        ok, msg, data = self.controller.test_remote_server(url)
        if ok:
            name = data.get("server_name", "ARSIPTA Server")
            ver = data.get("version", "")
            tot = data.get("total_archives", 0)
            self.lbl_server_hint.setText(f"✓ Terhubung ke {name} ({ver}) — {tot} arsip tersedia.")
            self.lbl_server_hint.setStyleSheet("color: #16A34A; font-weight: 600;")
        else:
            self.lbl_server_hint.setText(f"✗ Gagal terhubung: {msg}")
            self.lbl_server_hint.setStyleSheet("color: #DC2626; font-weight: 600;")

    def _open_register(self):
        dlg = RegisterAccountDialog(self.controller, self.dark_mode, self)
        dlg.exec()

    def _handle_login(self):
        selected_mode = (
            "Mode Server Kantor"
            if self.radio_server.isChecked()
            else "Mode Lokal"
        )
        ok, msg = self.controller.switch_session(
            self.input_user.text(),
            self.input_pass.text(),
            selected_mode,
            self.input_server.text()
        )
        if ok:
            QMessageBox.information(self, "Sesi Diterapkan", msg)
            self.accept()
        else:
            QMessageBox.warning(self, "Gagal Masuk", msg)


class DashboardPage(QWidget):
    """Halaman utama Dashboard penyambut dan pemantauan satu layar."""

    navigate_requested = Signal(int)
    open_session_requested = Signal()

    def __init__(self, controller: ArsiptaController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._setup_ui()
        self.refresh_data()
        self.controller.data_updated.connect(self.refresh_data)

    def _setup_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        container.setObjectName("ScrollContainer")
        self.main_layout = QVBoxLayout(container)
        self.main_layout.setContentsMargins(28, 24, 28, 24)
        self.main_layout.setSpacing(20)

        header_row = QHBoxLayout()
        welcome_col = QVBoxLayout()
        self.lbl_welcome = QLabel(f"Selamat Datang di {APP_NAME}")
        self.lbl_welcome.setProperty("class", "TitleLarge")
        self.lbl_sub = QLabel(
            "Pantau seluruh arsip perjanjian, masa retensi, "
            "dan sinkronisasi tim dalam satu layar."
        )
        self.lbl_sub.setProperty("class", "MutedText")
        welcome_col.addWidget(self.lbl_welcome)
        welcome_col.addWidget(self.lbl_sub)

        self.search_tools = QLineEdit()
        self.search_tools.setPlaceholderText(
            "Cari alat atau fitur (misal: katalog, excel, retensi, akun)..."
        )
        self.search_tools.setFixedWidth(340)
        self.search_tools.textChanged.connect(self._filter_feature_cards)

        header_row.addLayout(welcome_col)
        header_row.addStretch()
        header_row.addWidget(self.search_tools)
        self.main_layout.addLayout(header_row)

        stats_grid = QGridLayout()
        stats_grid.setSpacing(14)

        self.card_total, self.val_total = self._create_metric_card(
            "Total Arsip Perjanjian", "0", "Seluruh dokumen tercatat"
        )
        self.card_aktif, self.val_aktif = self._create_metric_card(
            "Arsip Aktif", "0", "Perjanjian masih berlaku"
        )
        self.card_inaktif, self.val_inaktif = self._create_metric_card(
            "Arsip Inaktif", "0", "Perjanjian berakhir / arsip statis"
        )
        self.card_retensi, self.val_retensi = self._create_metric_card(
            "Peringatan Retensi", "0", "Jatuh tempo <= 90 hari / lewat"
        )

        stats_grid.addWidget(self.card_total, 0, 0)
        stats_grid.addWidget(self.card_aktif, 0, 1)
        stats_grid.addWidget(self.card_inaktif, 0, 2)
        stats_grid.addWidget(self.card_retensi, 0, 3)
        self.main_layout.addLayout(stats_grid)

        # Kartu Grafik Komposisi Status Aktif vs Inaktif
        comp_card = QFrame()
        comp_card.setProperty("class", "Card")
        comp_layout = QVBoxLayout(comp_card)
        comp_layout.setContentsMargins(18, 16, 18, 16)
        comp_layout.setSpacing(8)

        comp_title = QLabel("Komposisi Status Arsip (Aktif vs Inaktif)")
        comp_title.setProperty("class", "SectionTitle")
        self.status_chart = StatusCompositionWidget()

        comp_layout.addWidget(comp_title)
        comp_layout.addWidget(self.status_chart)
        self.main_layout.addWidget(comp_card)

        lbl_quick = QLabel("Akses Cepat & Modul Fitur")
        lbl_quick.setProperty("class", "SectionTitle")
        self.main_layout.addWidget(lbl_quick)

        self.cards_grid = QGridLayout()
        self.cards_grid.setSpacing(14)

        self.feature_definitions = [
            (
                "Katalog Arsip Utama",
                "Telusuri, urutkan kolom, tambah/ubah arsip, dan filter "
                "real-time seluruh arsip perjanjian.",
                1,
                "katalog cari filter daftar tambah ubah"
            ),
            (
                "Pemantau Masa Retensi",
                "Cek perjanjian yang mendekati jatuh tempo "
                "dan lakukan perpanjangan atau alih inaktif.",
                2,
                "retensi peringatan jatuh tempo perpanjang"
            ),
            (
                "Impor & Ekspor Excel/CSV",
                "Migrasi daftar Excel lama tanpa merusak file asli serta "
                "unduh laporan CSV/XLSX.",
                3,
                "excel csv impor ekspor template"
            ),
            (
                "Akun Tim & Mode Kerja",
                "Pilih kerja mandiri (lokal) atau hubungkan ke server "
                "kantor agar tampilan tim seragam.",
                -1,
                "akun hybrid server login sinkronisasi"
            ),
            (
                "Sinkronisasi Server Kantor",
                "Hubungkan ke server kantor atau jadikan komputer ini server host "
                "agar seluruh staf tersambung ke database yang sama.",
                4,
                "server hybrid host sinkronisasi jaringan lan ip port"
            ),
        ]

        self.feature_widgets: List[Tuple[ClickableCard, str]] = []
        for idx, (title, desc, page_idx, keywords) in enumerate(
            self.feature_definitions
        ):
            card = ClickableCard()
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(16, 14, 16, 14)
            c_layout.setSpacing(6)

            t_lbl = QLabel(title)
            t_lbl.setProperty("class", "SectionTitle")
            d_lbl = QLabel(desc)
            d_lbl.setProperty("class", "MutedText")
            d_lbl.setWordWrap(True)

            c_layout.addWidget(t_lbl)
            c_layout.addWidget(d_lbl)
            if page_idx == -1:
                card.clicked.connect(self.open_session_requested.emit)
            else:
                card.clicked.connect(
                    lambda p=page_idx: self.navigate_requested.emit(p)
                )

            self.cards_grid.addWidget(card, idx // 2, idx % 2)
            self.feature_widgets.append(
                (card, f"{title.lower()} {desc.lower()} {keywords}")
            )

        self.main_layout.addLayout(self.cards_grid)

        recent_card = QFrame()
        recent_card.setProperty("class", "Card")
        recent_layout = QVBoxLayout(recent_card)
        recent_layout.setContentsMargins(18, 16, 18, 16)
        recent_layout.setSpacing(10)

        recent_title = QLabel("File yang Baru Diproses")
        recent_title.setProperty("class", "SectionTitle")
        recent_layout.addWidget(recent_title)

        self.table_recent = QTableWidget(0, 4)
        self.table_recent.setHorizontalHeaderLabels(
            ["Nama File", "Jalur Lokasi", "Aktivitas", "Waktu"]
        )
        self.table_recent.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.table_recent.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_recent.setMaximumHeight(150)
        recent_layout.addWidget(self.table_recent)

        self.main_layout.addWidget(recent_card)

        footer_row = QHBoxLayout()
        self.lbl_session_info = QLabel()
        self.lbl_session_info.setProperty("class", "MutedText")
        lbl_ver = QLabel(f"{APP_NAME} v{APP_VERSION} • Lisensi MIT")
        lbl_ver.setProperty("class", "MutedText")
        footer_row.addWidget(self.lbl_session_info)
        footer_row.addStretch()
        footer_row.addWidget(lbl_ver)
        self.main_layout.addLayout(footer_row)

        self.main_layout.addStretch()
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _create_metric_card(
        self, title: str, initial_val: str, subtitle: str
    ) -> Tuple[QFrame, QLabel]:
        card = QFrame()
        card.setProperty("class", "Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        lbl_t = QLabel(title)
        lbl_t.setProperty("class", "MutedText")
        lbl_v = QLabel(initial_val)
        lbl_v.setProperty("class", "MetricValue")
        lbl_s = QLabel(subtitle)
        lbl_s.setProperty("class", "HintText")

        layout.addWidget(lbl_t)
        layout.addWidget(lbl_v)
        layout.addWidget(lbl_s)
        return card, lbl_v

    def _filter_feature_cards(self, text: str):
        query = text.strip().lower()
        for card, searchable in self.feature_widgets:
            card.setVisible(query == "" or query in searchable)

    def set_theme(self, dark_mode: bool):
        self.status_chart.set_theme(dark_mode)

    def refresh_data(self):
        metrics = self.controller.get_summary()
        self.val_total.setText(str(metrics["total"]))
        self.val_aktif.setText(str(metrics["aktif"]))
        self.val_inaktif.setText(str(metrics["inaktif"]))
        self.val_retensi.setText(str(metrics["peringatan_retensi"]))

        self.status_chart.set_values(metrics["aktif"], metrics["inaktif"])

        recent = self.controller.get_recent_files()
        self.table_recent.setRowCount(len(recent))
        for row_idx, item in enumerate(recent):
            self.table_recent.setItem(
                row_idx, 0, QTableWidgetItem(item["nama_file"])
            )
            self.table_recent.setItem(
                row_idx, 1, QTableWidgetItem(item["jalur_file"])
            )
            self.table_recent.setItem(
                row_idx, 2, QTableWidgetItem(item["aksi"])
            )
            self.table_recent.setItem(
                row_idx, 3, QTableWidgetItem(item["waktu"])
            )

        sess = self.controller.session
        host_status = " • Server Host Aktif" if self.controller.is_server_running() else ""
        sync_meta = self.controller.storage.get_sync_meta("last_sync_time", "Belum pernah")
        self.lbl_session_info.setText(
            f"Pengguna Aktif: {sess.nama_lengkap} (@{sess.username}) • "
            f"Status Kerja: {sess.mode_koneksi}{host_status} • "
            f"Terakhir Sinkronisasi: {sync_meta}"
        )


class CatalogPage(QWidget):
    """
    Halaman Katalog Arsip Interaktif:
    - Pencarian real-time
    - Filter topik, status, peringatan retensi, dan rentang tanggal berakhir
    - Reset filter instan
    - Pengurutan kolom interaktif
    - Tambah, Ubah, Hapus, dan Pintasan Ekspor Hasil Filter
    """

    export_filtered_requested = Signal()

    def __init__(self, controller: ArsiptaController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.dark_mode = False
        self._setup_ui()
        self.reload_topics()
        self.apply_filters()
        self.controller.data_updated.connect(self._on_data_changed)

    def set_theme(self, dark_mode: bool):
        self.dark_mode = dark_mode
        self.chk_date_range.set_theme(dark_mode)
        self.apply_filters()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(14)

        top_row = QHBoxLayout()
        title_col = QVBoxLayout()
        lbl_title = QLabel("Katalog Arsip Perjanjian")
        lbl_title.setProperty("class", "TitleLarge")
        lbl_sub = QLabel(
            "Cari secara real-time, saring kategori, urutkan kolom, "
            "dan kelola catatan perjanjian."
        )
        lbl_sub.setProperty("class", "MutedText")
        title_col.addWidget(lbl_title)
        title_col.addWidget(lbl_sub)

        btn_export_quick = QPushButton("Ekspor Hasil Filter")
        btn_export_quick.setProperty("class", "SecondaryButton")
        btn_export_quick.setCursor(Qt.PointingHandCursor)
        btn_export_quick.clicked.connect(self.export_filtered_requested.emit)

        btn_add = QPushButton("+ Tambah Arsip")
        btn_add.setProperty("class", "PrimaryButton")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.clicked.connect(self._open_add_dialog)

        btn_edit = QPushButton("Ubah Terpilih")
        btn_edit.setProperty("class", "SecondaryButton")
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.clicked.connect(self._open_edit_dialog)

        btn_delete = QPushButton("Hapus Terpilih")
        btn_delete.setProperty("class", "DangerButton")
        btn_delete.setCursor(Qt.PointingHandCursor)
        btn_delete.clicked.connect(self._delete_selected)

        top_row.addLayout(title_col)
        top_row.addStretch()
        top_row.addWidget(btn_export_quick)
        top_row.addWidget(btn_add)
        top_row.addWidget(btn_edit)
        top_row.addWidget(btn_delete)
        layout.addLayout(top_row)

        filter_card = QFrame()
        filter_card.setProperty("class", "Card")
        f_layout = QVBoxLayout(filter_card)
        f_layout.setContentsMargins(16, 14, 16, 14)
        f_layout.setSpacing(10)

        row1 = QHBoxLayout()
        row1.setSpacing(10)

        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText(
            "Pencarian real-time (No. Dokumen, Judul, Pihak, Lokasi)..."
        )
        self.input_search.textChanged.connect(self.apply_filters)

        self.combo_topik = QComboBox()
        self.combo_topik.setMinimumWidth(180)
        self.combo_topik.currentIndexChanged.connect(self.apply_filters)

        self.combo_status = QComboBox()
        self.combo_status.addItems(["Semua Status", "Aktif", "Inaktif"])
        self.combo_status.setMinimumWidth(130)
        self.combo_status.currentIndexChanged.connect(self.apply_filters)

        self.combo_retensi = QComboBox()
        self.combo_retensi.addItems([
            "Semua Retensi",
            "Perlu Perhatian",
            "Kedaluwarsa",
            "Kritis (<= 30 Hari)",
            "Perhatian (<= 90 Hari)",
            "Aman"
        ])
        self.combo_retensi.setMinimumWidth(175)
        self.combo_retensi.currentIndexChanged.connect(self.apply_filters)

        row1.addWidget(self.input_search, stretch=2)
        row1.addWidget(self.combo_topik)
        row1.addWidget(self.combo_status)
        row1.addWidget(self.combo_retensi)
        f_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(10)

        self.chk_date_range = VisibleCheckBox(
            "Aktifkan Filter Rentang Tanggal Berakhir:"
        )
        self.chk_date_range.toggled.connect(self._toggle_date_inputs)

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.setDate(QDate.currentDate().addYears(-2))
        self.date_from.setEnabled(False)
        self.date_from.dateChanged.connect(self.apply_filters)

        lbl_sd = QLabel("s.d.")
        lbl_sd.setProperty("class", "MutedText")

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setDate(QDate.currentDate().addYears(2))
        self.date_to.setEnabled(False)
        self.date_to.dateChanged.connect(self.apply_filters)

        btn_reset = QPushButton("Reset Filter")
        btn_reset.setProperty("class", "SecondaryButton")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.clicked.connect(self.reset_filters)

        self.lbl_count = QLabel("Menampilkan 0 dari 0 arsip")
        self.lbl_count.setProperty("class", "MutedText")

        row2.addWidget(self.chk_date_range)
        row2.addWidget(self.date_from)
        row2.addWidget(lbl_sd)
        row2.addWidget(self.date_to)
        row2.addWidget(btn_reset)
        row2.addStretch()
        row2.addWidget(self.lbl_count)
        f_layout.addLayout(row2)

        layout.addWidget(filter_card)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "No. Dokumen",
            "Judul Perjanjian",
            "Pihak Terkait",
            "Topik",
            "Tgl Mulai",
            "Tgl Berakhir",
            "Status",
            "Peringatan Retensi",
            "Lokasi Fisik"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.setShowGrid(False)
        self.table.doubleClicked.connect(self._open_edit_dialog)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)

        layout.addWidget(self.table)

    def _toggle_date_inputs(self, checked: bool):
        self.date_from.setEnabled(checked)
        self.date_to.setEnabled(checked)
        self.apply_filters()

    def reload_topics(self):
        current = self.combo_topik.currentText()
        self.combo_topik.blockSignals(True)
        self.combo_topik.clear()
        self.combo_topik.addItem("Semua Topik")
        self.combo_topik.addItems(self.controller.get_topics())
        idx = self.combo_topik.findText(current)
        if idx >= 0:
            self.combo_topik.setCurrentIndex(idx)
        self.combo_topik.blockSignals(False)

    def reset_filters(self):
        self.input_search.blockSignals(True)
        self.combo_topik.blockSignals(True)
        self.combo_status.blockSignals(True)
        self.combo_retensi.blockSignals(True)
        self.chk_date_range.blockSignals(True)

        self.input_search.clear()
        self.combo_topik.setCurrentIndex(0)
        self.combo_status.setCurrentIndex(0)
        self.combo_retensi.setCurrentIndex(0)
        self.chk_date_range.setChecked(False)
        self.chk_date_range.update()
        self.date_from.setEnabled(False)
        self.date_to.setEnabled(False)

        self.input_search.blockSignals(False)
        self.combo_topik.blockSignals(False)
        self.combo_status.blockSignals(False)
        self.combo_retensi.blockSignals(False)
        self.chk_date_range.blockSignals(False)

        self.apply_filters()

    def _on_data_changed(self):
        self.reload_topics()
        self.apply_filters()

    def apply_filters(self):
        criteria = FilterCriteria(
            search_text=self.input_search.text(),
            topik=self.combo_topik.currentText() or "Semua Topik",
            status=self.combo_status.currentText() or "Semua Status",
            retensi=self.combo_retensi.currentText() or "Semua Retensi",
            use_date_range=self.chk_date_range.isChecked(),
            date_from=self.date_from.date().toString("yyyy-MM-dd"),
            date_to=self.date_to.date().toString("yyyy-MM-dd")
        )
        filtered, total_all = self.controller.search_archives(criteria)
        self.lbl_count.setText(
            f"Menampilkan {len(filtered)} dari {total_all} arsip "
            "(Klik judul kolom untuk mengurutkan)"
        )
        self._populate_table(filtered)

    def _populate_table(self, records: List[ArchiveRecord]):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(records))

        for row_idx, rec in enumerate(records):
            item_nomor = SortableTableItem(rec.nomor_dokumen)
            item_nomor.setData(Qt.UserRole, rec.id)

            item_judul = SortableTableItem(rec.judul_perjanjian)
            item_pihak = SortableTableItem(rec.pihak_terkait)
            item_topik = SortableTableItem(rec.topik)
            item_mulai = SortableTableItem(rec.tanggal_mulai, rec.tanggal_mulai)
            item_akhir = SortableTableItem(
                rec.tanggal_berakhir, rec.tanggal_berakhir
            )

            item_status = SortableTableItem(rec.status)
            if rec.status.lower() == "aktif":
                item_status.setForeground(
                    QColor("#34D399" if self.dark_mode else "#059669")
                )
            else:
                item_status.setForeground(
                    QColor("#94A3B8" if self.dark_mode else "#64748B")
                )

            ret_text, urgency, delta_days = (
                ArchiveProcessingEngine.format_retention_label(rec)
            )
            item_retensi = SortableTableItem(ret_text, delta_days)
            if urgency == "danger":
                item_retensi.setForeground(
                    QColor("#F87171" if self.dark_mode else "#DC2626")
                )
            elif urgency == "warning":
                item_retensi.setForeground(
                    QColor("#FBBF24" if self.dark_mode else "#D97706")
                )
            elif urgency == "safe":
                item_retensi.setForeground(
                    QColor("#34D399" if self.dark_mode else "#059669")
                )

            item_lokasi = SortableTableItem(rec.lokasi_fisik)

            self.table.setItem(row_idx, 0, item_nomor)
            self.table.setItem(row_idx, 1, item_judul)
            self.table.setItem(row_idx, 2, item_pihak)
            self.table.setItem(row_idx, 3, item_topik)
            self.table.setItem(row_idx, 4, item_mulai)
            self.table.setItem(row_idx, 5, item_akhir)
            self.table.setItem(row_idx, 6, item_status)
            self.table.setItem(row_idx, 7, item_retensi)
            self.table.setItem(row_idx, 8, item_lokasi)

        self.table.setSortingEnabled(True)

    def _get_selected_archive_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        return item.data(Qt.UserRole)

    def _open_add_dialog(self):
        dlg = ArchiveFormDialog(self.controller, self.dark_mode, None, self)
        dlg.exec()

    def _open_edit_dialog(self):
        archive_id = self._get_selected_archive_id()
        if archive_id is None:
            QMessageBox.information(
                self,
                "Pilih Arsip",
                "Silakan pilih satu baris arsip pada tabel terlebih dahulu."
            )
            return
        record = self.controller.get_archive_by_id(archive_id)
        if not record:
            QMessageBox.warning(self, "Galat", "Data arsip tidak ditemukan.")
            return
        dlg = ArchiveFormDialog(self.controller, self.dark_mode, record, self)
        dlg.exec()

    def _delete_selected(self):
        archive_id = self._get_selected_archive_id()
        if archive_id is None:
            QMessageBox.information(
                self,
                "Pilih Arsip",
                "Silakan pilih baris arsip yang ingin dihapus."
            )
            return
        record = self.controller.get_archive_by_id(archive_id)
        if not record:
            return

        reply = QMessageBox.question(
            self,
            "Konfirmasi Hapus Arsip",
            f"Apakah Anda yakin ingin menghapus arsip:\n"
            f"{record.nomor_dokumen} - {record.judul_perjanjian}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ok, msg = self.controller.remove_archive(archive_id)
            if ok:
                QMessageBox.information(self, "Terhapus", msg)
            else:
                QMessageBox.warning(self, "Gagal Menghapus", msg)


class RetentionPage(QWidget):
    """Halaman Pemantauan Masa Retensi Arsip."""

    def __init__(self, controller: ArsiptaController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.dark_mode = False
        self._setup_ui()
        self.refresh_data()
        self.controller.data_updated.connect(self.refresh_data)

    def set_theme(self, dark_mode: bool):
        self.dark_mode = dark_mode
        self.refresh_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(16)

        top_row = QHBoxLayout()
        title_col = QVBoxLayout()
        lbl_title = QLabel("Pemantauan Masa Retensi Perjanjian")
        lbl_title.setProperty("class", "TitleLarge")
        lbl_sub = QLabel(
            "Daftar perjanjian aktif yang mendekati berakhir atau telah "
            "melewati batas waktu (diurutkan dari paling mendesak)."
        )
        lbl_sub.setProperty("class", "MutedText")
        title_col.addWidget(lbl_title)
        title_col.addWidget(lbl_sub)

        btn_extend = QPushButton("Perpanjang / Ubah Tanggal")
        btn_extend.setProperty("class", "PrimaryButton")
        btn_extend.setCursor(Qt.PointingHandCursor)
        btn_extend.clicked.connect(self._extend_selected)

        btn_inactivate = QPushButton("Set Status Inaktif")
        btn_inactivate.setProperty("class", "SecondaryButton")
        btn_inactivate.setCursor(Qt.PointingHandCursor)
        btn_inactivate.clicked.connect(self._inactivate_selected)

        top_row.addLayout(title_col)
        top_row.addStretch()
        top_row.addWidget(btn_extend)
        top_row.addWidget(btn_inactivate)
        layout.addLayout(top_row)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(14)

        self.card_exp, self.val_exp = self._make_urgency_card(
            "Sudah Kedaluwarsa", "0", "Melewati tanggal berakhir"
        )
        self.card_crit, self.val_crit = self._make_urgency_card(
            "Kritis (<= 30 Hari)", "0", "Segera butuh adendum / penutupan"
        )
        self.card_warn, self.val_warn = self._make_urgency_card(
            "Perhatian (<= 90 Hari)", "0", "Jadwalkan evaluasi perjanjian"
        )

        cards_row.addWidget(self.card_exp)
        cards_row.addWidget(self.card_crit)
        cards_row.addWidget(self.card_warn)
        layout.addLayout(cards_row)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Tingkat Peringatan",
            "Sisa Waktu",
            "No. Dokumen",
            "Judul Perjanjian",
            "Pihak Terkait",
            "Tanggal Berakhir",
            "Lokasi Fisik"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._extend_selected)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)

        layout.addWidget(self.table)

    def _make_urgency_card(
        self, title: str, initial: str, desc: str
    ) -> Tuple[QFrame, QLabel]:
        card = QFrame()
        card.setProperty("class", "Card")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(16, 14, 16, 14)
        c_layout.setSpacing(4)

        lbl_t = QLabel(title)
        lbl_t.setProperty("class", "MutedText")
        lbl_v = QLabel(initial)
        lbl_v.setProperty("class", "MetricValue")
        lbl_d = QLabel(desc)
        lbl_d.setProperty("class", "HintText")

        c_layout.addWidget(lbl_t)
        c_layout.addWidget(lbl_v)
        c_layout.addWidget(lbl_d)
        return card, lbl_v

    def refresh_data(self):
        watchlist = self.controller.get_retention_watchlist()

        count_exp = sum(1 for _, kat, _ in watchlist if kat == "Kedaluwarsa")
        count_crit = sum(
            1 for _, kat, _ in watchlist if kat == "Kritis (<= 30 Hari)"
        )
        count_warn = sum(
            1 for _, kat, _ in watchlist if kat == "Perhatian (<= 90 Hari)"
        )

        self.val_exp.setText(str(count_exp))
        self.val_crit.setText(str(count_crit))
        self.val_warn.setText(str(count_warn))

        self.table.setRowCount(len(watchlist))
        for row_idx, (rec, kategori, delta) in enumerate(watchlist):
            item_kat = QTableWidgetItem(kategori)
            item_kat.setData(Qt.UserRole, rec.id)

            if kategori in ("Kedaluwarsa", "Kritis (<= 30 Hari)"):
                item_kat.setForeground(
                    QColor("#F87171" if self.dark_mode else "#DC2626")
                )
            else:
                item_kat.setForeground(
                    QColor("#FBBF24" if self.dark_mode else "#D97706")
                )

            sisa_str = (
                f"Lewat {abs(delta)} hari"
                if delta < 0
                else f"Sisa {delta} hari"
            )
            self.table.setItem(row_idx, 0, item_kat)
            self.table.setItem(row_idx, 1, QTableWidgetItem(sisa_str))
            self.table.setItem(row_idx, 2, QTableWidgetItem(rec.nomor_dokumen))
            self.table.setItem(
                row_idx, 3, QTableWidgetItem(rec.judul_perjanjian)
            )
            self.table.setItem(row_idx, 4, QTableWidgetItem(rec.pihak_terkait))
            self.table.setItem(
                row_idx, 5, QTableWidgetItem(rec.tanggal_berakhir)
            )
            self.table.setItem(row_idx, 6, QTableWidgetItem(rec.lokasi_fisik))

    def _get_selected_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _extend_selected(self):
        archive_id = self._get_selected_id()
        if archive_id is None:
            QMessageBox.information(
                self,
                "Pilih Dokumen",
                "Pilih salah satu baris perjanjian pada daftar peringatan."
            )
            return
        rec = self.controller.get_archive_by_id(archive_id)
        if rec:
            dlg = ArchiveFormDialog(self.controller, self.dark_mode, rec, self)
            dlg.exec()

    def _inactivate_selected(self):
        archive_id = self._get_selected_id()
        if archive_id is None:
            QMessageBox.information(
                self,
                "Pilih Dokumen",
                "Pilih perjanjian yang akan diubah statusnya menjadi Inaktif."
            )
            return
        rec = self.controller.get_archive_by_id(archive_id)
        if not rec:
            return

        reply = QMessageBox.question(
            self,
            "Alih Status ke Arsip Inaktif",
            f"Ubah status '{rec.nomor_dokumen}' menjadi Inaktif?\n"
            "Dokumen akan tetap tersimpan di katalog dan keluar dari daftar "
            "peringatan aktif.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            ok, msg = self.controller.set_archive_status(archive_id, "Inaktif")
            if ok:
                QMessageBox.information(self, "Status Diperbarui", msg)


class ImportExportPage(QWidget):
    """
    Halaman Impor & Ekspor Excel / CSV (Fase 3):
    - Impor file .xlsx / .csv tanpa mengubah file sumber asli
    - Pemilihan kebijakan duplikat (Lewati vs Perbarui)
    - Pembuatan template Excel/CSV siap uji
    - Ekspor seluruh katalog atau hanya hasil filter aktif ke .xlsx / .csv
    """

    def __init__(self, controller: ArsiptaController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.dark_mode = False
        self.worker: Optional[SpreadsheetJobWorker] = None
        self._setup_ui()
        self.refresh_counts()
        self.controller.data_updated.connect(self.refresh_counts)

    def set_theme(self, dark_mode: bool):
        self.dark_mode = dark_mode
        self.radio_dup_skip.set_theme(dark_mode)
        self.radio_dup_update.set_theme(dark_mode)
        self.radio_exp_all.set_theme(dark_mode)
        self.radio_exp_filtered.set_theme(dark_mode)

    def _setup_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        container.setObjectName("ScrollContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(18)

        lbl_title = QLabel("Impor & Ekspor Data Excel / CSV")
        lbl_title.setProperty("class", "TitleLarge")
        lbl_sub = QLabel(
            "Migrasikan daftar Excel lama ke katalog ARSIPTA secara aman "
            "atau unduh laporan siap cetak."
        )
        lbl_sub.setProperty("class", "MutedText")
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sub)

        # Grid 2 Kolom: Kartu Impor & Kartu Ekspor
        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)

        # --- KARTU 1: IMPOR ---
        import_card = QFrame()
        import_card.setProperty("class", "Card")
        imp_layout = QVBoxLayout(import_card)
        imp_layout.setContentsMargins(20, 18, 20, 18)
        imp_layout.setSpacing(12)

        imp_title = QLabel("1. Impor dari Excel (.xlsx) atau CSV (.csv)")
        imp_title.setProperty("class", "SectionTitle")
        imp_desc = QLabel(
            "Sistem akan menyalin file ke area kerja sementara terlebih dahulu "
            "sehingga file Excel asli Anda tidak pernah berubah atau terkunci."
        )
        imp_desc.setProperty("class", "MutedText")
        imp_desc.setWordWrap(True)

        self.radio_dup_skip = VisibleRadioButton(
            "Lewati jika Nomor Dokumen sudah ada"
        )
        self.radio_dup_update = VisibleRadioButton(
            "Perbarui data jika Nomor Dokumen sudah ada"
        )
        self.radio_dup_skip.setChecked(True)

        dup_group = QButtonGroup(self)
        dup_group.addButton(self.radio_dup_skip)
        dup_group.addButton(self.radio_dup_update)

        imp_btn_row = QHBoxLayout()
        self.btn_import = QPushButton("Pilih File & Mulai Impor...")
        self.btn_import.setProperty("class", "PrimaryButton")
        self.btn_import.setCursor(Qt.PointingHandCursor)
        self.btn_import.clicked.connect(self._start_import_dialog)

        self.btn_template = QPushButton("Buat Template Excel (.xlsx)")
        self.btn_template.setProperty("class", "SecondaryButton")
        self.btn_template.setCursor(Qt.PointingHandCursor)
        self.btn_template.clicked.connect(self._create_template_dialog)

        imp_btn_row.addWidget(self.btn_import)
        imp_btn_row.addWidget(self.btn_template)

        imp_layout.addWidget(imp_title)
        imp_layout.addWidget(imp_desc)
        imp_layout.addWidget(self.radio_dup_skip)
        imp_layout.addWidget(self.radio_dup_update)
        imp_layout.addSpacing(4)
        imp_layout.addLayout(imp_btn_row)
        imp_layout.addStretch()

        # --- KARTU 2: EKSPOR ---
        export_card = QFrame()
        export_card.setProperty("class", "Card")
        exp_layout = QVBoxLayout(export_card)
        exp_layout.setContentsMargins(20, 18, 20, 18)
        exp_layout.setSpacing(12)

        exp_title = QLabel("2. Ekspor Laporan Katalog")
        exp_title.setProperty("class", "SectionTitle")
        exp_desc = QLabel(
            "Unduh daftar katalog lengkap beserta perhitungan status retensi "
            "terbaru dalam format Microsoft Excel atau CSV."
        )
        exp_desc.setProperty("class", "MutedText")
        exp_desc.setWordWrap(True)

        self.radio_exp_all = VisibleRadioButton("Seluruh Katalog Arsip (0 dokumen)")
        self.radio_exp_filtered = VisibleRadioButton(
            "Hanya Hasil Filter Aktif di Katalog (0 dokumen)"
        )
        self.radio_exp_all.setChecked(True)

        exp_group = QButtonGroup(self)
        exp_group.addButton(self.radio_exp_all)
        exp_group.addButton(self.radio_exp_filtered)

        exp_btn_row = QHBoxLayout()
        self.btn_export_xlsx = QPushButton("Ekspor ke Excel (.xlsx)")
        self.btn_export_xlsx.setProperty("class", "PrimaryButton")
        self.btn_export_xlsx.setCursor(Qt.PointingHandCursor)
        self.btn_export_xlsx.clicked.connect(
            lambda: self._start_export_dialog("xlsx")
        )

        self.btn_export_csv = QPushButton("Ekspor ke CSV (.csv)")
        self.btn_export_csv.setProperty("class", "SecondaryButton")
        self.btn_export_csv.setCursor(Qt.PointingHandCursor)
        self.btn_export_csv.clicked.connect(
            lambda: self._start_export_dialog("csv")
        )

        exp_btn_row.addWidget(self.btn_export_xlsx)
        exp_btn_row.addWidget(self.btn_export_csv)

        exp_layout.addWidget(exp_title)
        exp_layout.addWidget(exp_desc)
        exp_layout.addWidget(self.radio_exp_all)
        exp_layout.addWidget(self.radio_exp_filtered)
        exp_layout.addSpacing(4)
        exp_layout.addLayout(exp_btn_row)
        exp_layout.addStretch()

        cards_row.addWidget(import_card, stretch=1)
        cards_row.addWidget(export_card, stretch=1)
        layout.addLayout(cards_row)

        # Panel Status Proses & Log Hasil
        log_card = QFrame()
        log_card.setProperty("class", "Card")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(20, 16, 20, 16)
        log_layout.setSpacing(10)

        log_title = QLabel("Status Pemrosesan & Ringkasan Hasil")
        log_title.setProperty("class", "SectionTitle")

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Siap memproses file")

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(130)
        self.log_output.setPlaceholderText(
            "Hasil impor atau ekspor file akan ditampilkan di sini..."
        )

        log_layout.addWidget(log_title)
        log_layout.addWidget(self.progress_bar)
        log_layout.addWidget(self.log_output)
        layout.addWidget(log_card)

        layout.addStretch()
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def refresh_counts(self):
        all_count = len(self.controller.get_archives())
        filtered_count = len(self.controller.get_filtered_archives_snapshot())
        self.radio_exp_all.setText(
            f"Seluruh Katalog Arsip ({all_count} dokumen)"
        )
        self.radio_exp_filtered.setText(
            f"Hanya Hasil Filter Aktif di Katalog ({filtered_count} dokumen)"
        )
        self.radio_exp_all.update()
        self.radio_exp_filtered.update()

    def select_filtered_export_mode(self):
        self.refresh_counts()
        self.radio_exp_filtered.setChecked(True)
        self.radio_exp_filtered.update()

    def _set_controls_enabled(self, enabled: bool):
        self.btn_import.setEnabled(enabled)
        self.btn_template.setEnabled(enabled)
        self.btn_export_xlsx.setEnabled(enabled)
        self.btn_export_csv.setEnabled(enabled)

    def _create_template_dialog(self):
        default_name = "Template_Katalog_ARSIPTA.xlsx"
        dest_path, _ = QFileDialog.getSaveFileName(
            self,
            "Simpan Template Impor Excel",
            default_name,
            "File Excel (*.xlsx);;File CSV (*.csv)"
        )
        if not dest_path:
            return
        ok, msg = SpreadsheetIOEngine.generate_sample_template(dest_path)
        if ok:
            self.log_output.setPlainText(msg)
            QMessageBox.information(self, "Template Dibuat", msg)
        else:
            QMessageBox.warning(self, "Gagal", msg)

    def _start_import_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Pilih File Excel atau CSV untuk Diimpor",
            "",
            "Spreadsheet (*.xlsx *.csv);;File Excel (*.xlsx);;File CSV (*.csv)"
        )
        if not file_path:
            return

        self._set_controls_enabled(False)
        self.progress_bar.setValue(5)
        self.progress_bar.setFormat("Memulai impor...")
        self.log_output.setPlainText(f"Memproses file: {file_path}\n...")

        self.worker = SpreadsheetJobWorker(
            mode="import",
            db_path=self.controller.storage.db_path,
            file_path=file_path,
            update_existing=self.radio_dup_update.isChecked()
        )
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.finished_job.connect(self._on_worker_finished)
        self.worker.start()

    def _start_export_dialog(self, fmt: str):
        if self.radio_exp_filtered.isChecked():
            records = self.controller.get_filtered_archives_snapshot()
        else:
            records = self.controller.get_archives()

        if not records:
            QMessageBox.information(
                self,
                "Data Kosong",
                "Tidak ada catatan arsip untuk diekspor pada pilihan saat ini."
            )
            return

        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        default_name = f"Laporan_Katalog_ARSIPTA_{stamp}.{fmt}"
        filter_str = (
            "File Excel (*.xlsx)" if fmt == "xlsx" else "File CSV (*.csv)"
        )
        dest_path, _ = QFileDialog.getSaveFileName(
            self,
            "Simpan Laporan Katalog",
            default_name,
            filter_str
        )
        if not dest_path:
            return

        self._set_controls_enabled(False)
        self.progress_bar.setValue(10)
        self.progress_bar.setFormat("Menyiapkan ekspor...")

        self.worker = SpreadsheetJobWorker(
            mode="export",
            db_path=self.controller.storage.db_path,
            file_path=dest_path,
            records_to_export=records
        )
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.finished_job.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_progress(self, pct: int, text: str):
        self.progress_bar.setValue(pct)
        self.progress_bar.setFormat(f"{text} ({pct}%)")

    def _on_worker_finished(self, ok: bool, msg: str, meta: dict):
        self._set_controls_enabled(True)
        self.progress_bar.setValue(100 if ok else 0)
        self.progress_bar.setFormat("Selesai" if ok else "Gagal")

        lines = [msg]
        warnings = meta.get("warnings", [])
        if warnings:
            lines.append("\nCatatan Baris:")
            lines.extend(warnings[:15])
        self.log_output.setPlainText("\n".join(lines))

        if ok:
            self.controller.data_updated.emit()
            QMessageBox.information(self, "Proses Selesai", msg)
        else:
            QMessageBox.warning(self, "Terjadi Kesalahan", msg)


class ServerSyncPage(QWidget):
    """
    Halaman Sinkronisasi Server Kantor & Server Mandiri (Hybrid).
    Menghubungkan klien staf arsiparis ke server kantor atau
    menjadikan komputer ini sebagai host server mandiri.
    """

    def __init__(self, controller: ArsiptaController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.dark_mode = False
        self._setup_ui()
        self.refresh_data()
        self.controller.data_updated.connect(self.refresh_data)
        self.controller.server_status_changed.connect(self._on_server_status_changed)
        self.controller.sync_finished.connect(self._on_sync_finished)

    def _setup_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        container.setObjectName("ScrollContainer")
        self.main_layout = QVBoxLayout(container)
        self.main_layout.setContentsMargins(28, 24, 28, 24)
        self.main_layout.setSpacing(16)

        # Header Halaman
        header_box = QVBoxLayout()
        header_box.setSpacing(4)
        lbl_title = QLabel("Sinkronisasi Server Kantor & Server Mandiri (Hybrid)")
        lbl_title.setProperty("class", "TitleLarge")
        lbl_desc = QLabel(
            "Hubungkan beberapa komputer staf ke satu basis data arsip yang sama secara aman di jaringan kantor."
        )
        lbl_desc.setProperty("class", "MutedText")
        header_box.addWidget(lbl_title)
        header_box.addWidget(lbl_desc)
        self.main_layout.addLayout(header_box)

        # Banner Ringkasan Status
        self.banner_card = QFrame()
        self.banner_card.setProperty("class", "Card")
        b_layout = QGridLayout(self.banner_card)
        b_layout.setContentsMargins(18, 14, 18, 14)
        b_layout.setSpacing(10)

        lbl_t_mode = QLabel("Mode Kerja Klien")
        lbl_t_mode.setProperty("class", "HintText")
        self.lbl_b_mode = QLabel()
        self.lbl_b_mode.setStyleSheet("font-weight: 600; font-size: 13px;")

        lbl_t_url = QLabel("Alamat Server Terhubung")
        lbl_t_url.setProperty("class", "HintText")
        self.lbl_b_url = QLabel()
        self.lbl_b_url.setStyleSheet("font-weight: 600; font-size: 13px;")

        lbl_t_host = QLabel("Server Mandiri di PC Ini")
        lbl_t_host.setProperty("class", "HintText")
        self.lbl_b_host = QLabel()
        self.lbl_b_host.setStyleSheet("font-weight: 600; font-size: 13px;")

        lbl_t_sync = QLabel("Terakhir Sinkronisasi")
        lbl_t_sync.setProperty("class", "HintText")
        self.lbl_b_sync = QLabel()
        self.lbl_b_sync.setStyleSheet("font-weight: 600; font-size: 13px;")

        b_layout.addWidget(lbl_t_mode, 0, 0)
        b_layout.addWidget(self.lbl_b_mode, 1, 0)
        b_layout.addWidget(lbl_t_url, 0, 1)
        b_layout.addWidget(self.lbl_b_url, 1, 1)
        b_layout.addWidget(lbl_t_host, 0, 2)
        b_layout.addWidget(self.lbl_b_host, 1, 2)
        b_layout.addWidget(lbl_t_sync, 0, 3)
        b_layout.addWidget(self.lbl_b_sync, 1, 3)

        self.main_layout.addWidget(self.banner_card)

        # Tab Switcher (Klien vs Server Host)
        tab_buttons_row = QHBoxLayout()
        self.btn_tab_client = QPushButton("💻 Klien Sinkronisasi Tim")
        self.btn_tab_server = QPushButton("🏢 Server Mandiri (Pusat Data Host)")
        self.btn_tab_client.setCursor(Qt.PointingHandCursor)
        self.btn_tab_server.setCursor(Qt.PointingHandCursor)
        self.btn_tab_client.clicked.connect(lambda: self.switch_tab(0))
        self.btn_tab_server.clicked.connect(lambda: self.switch_tab(1))

        tab_buttons_row.addWidget(self.btn_tab_client)
        tab_buttons_row.addWidget(self.btn_tab_server)
        tab_buttons_row.addStretch()
        self.main_layout.addLayout(tab_buttons_row)

        self.tab_stack = QStackedWidget()
        self.page_client = self._create_client_panel()
        self.page_server = self._create_server_panel()
        self.tab_stack.addWidget(self.page_client)
        self.tab_stack.addWidget(self.page_server)
        self.main_layout.addWidget(self.tab_stack)

        scroll.setWidget(container)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        self.switch_tab(0)

    def _create_metric_tile(self, label: str) -> Tuple[QFrame, QLabel]:
        tile = QFrame()
        tile.setProperty("class", "SubtleBox")
        t_layout = QVBoxLayout(tile)
        t_layout.setContentsMargins(12, 10, 12, 10)
        t_layout.setSpacing(4)
        lbl_sub = QLabel(label)
        lbl_sub.setProperty("class", "HintText")
        val_lbl = QLabel("0")
        val_lbl.setProperty("class", "MetricValue")
        t_layout.addWidget(lbl_sub)
        t_layout.addWidget(val_lbl)
        return tile, val_lbl

    def _create_client_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # Kartu Pengaturan Koneksi
        conn_card = QFrame()
        conn_card.setProperty("class", "Card")
        cc_layout = QVBoxLayout(conn_card)
        cc_layout.setContentsMargins(18, 16, 18, 16)
        cc_layout.setSpacing(10)

        lbl_conn_title = QLabel("Pengaturan Koneksi ke Server Kantor")
        lbl_conn_title.setProperty("class", "SectionTitle")
        cc_layout.addWidget(lbl_conn_title)

        form = QFormLayout()
        form.setSpacing(8)
        self.input_client_url = QLineEdit(self.controller.session.server_url or "http://localhost:8080")
        self.input_client_url.setPlaceholderText("Contoh: http://192.168.1.100:8080")

        self.input_client_token = QLineEdit(self.controller.server_token)
        self.input_client_token.setEchoMode(QLineEdit.Password)
        self.input_client_token.setPlaceholderText("Token rahasia server")

        form.addRow("URL Server:", self.input_client_url)
        form.addRow("Token Akses Tim:", self.input_client_token)
        cc_layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.btn_test_conn = QPushButton("Uji Koneksi Server")
        self.btn_test_conn.setProperty("class", "SecondaryButton")
        self.btn_test_conn.setCursor(Qt.PointingHandCursor)
        self.btn_test_conn.clicked.connect(self._handle_test_connection)

        self.btn_preset_local = QPushButton("Gunakan Localhost (8080)")
        self.btn_preset_local.setProperty("class", "SecondaryButton")
        self.btn_preset_local.setCursor(Qt.PointingHandCursor)
        self.btn_preset_local.clicked.connect(lambda: self.input_client_url.setText("http://localhost:8080"))

        self.btn_apply_server_mode = QPushButton("Terapkan Mode Server Kantor")
        self.btn_apply_server_mode.setProperty("class", "PrimaryButton")
        self.btn_apply_server_mode.setCursor(Qt.PointingHandCursor)
        self.btn_apply_server_mode.clicked.connect(self._handle_apply_server_mode)

        btn_row.addWidget(self.btn_test_conn)
        btn_row.addWidget(self.btn_preset_local)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_apply_server_mode)
        cc_layout.addLayout(btn_row)

        self.lbl_client_feedback = QLabel()
        self.lbl_client_feedback.setProperty("class", "HintText")
        cc_layout.addWidget(self.lbl_client_feedback)
        layout.addWidget(conn_card)

        # Kartu Operasi Sinkronisasi
        sync_card = QFrame()
        sync_card.setProperty("class", "Card")
        sc_layout = QVBoxLayout(sync_card)
        sc_layout.setContentsMargins(18, 16, 18, 16)
        sc_layout.setSpacing(10)

        lbl_sync_op = QLabel("Aksi Sinkronisasi Data Arsip")
        lbl_sync_op.setProperty("class", "SectionTitle")
        sc_layout.addWidget(lbl_sync_op)

        actions_row = QHBoxLayout()
        self.btn_sync_two_way = QPushButton("🔄 Sinkronisasi Dua Arah (Penuh)")
        self.btn_sync_two_way.setProperty("class", "PrimaryButton")
        self.btn_sync_two_way.setCursor(Qt.PointingHandCursor)
        self.btn_sync_two_way.clicked.connect(lambda: self._start_sync("two_way"))

        self.btn_sync_pull = QPushButton("⬇ Tarik Data dari Server (Pull)")
        self.btn_sync_pull.setProperty("class", "SecondaryButton")
        self.btn_sync_pull.setCursor(Qt.PointingHandCursor)
        self.btn_sync_pull.clicked.connect(lambda: self._start_sync("pull"))

        self.btn_sync_push = QPushButton("⬆ Kirim Data ke Server (Push)")
        self.btn_sync_push.setProperty("class", "SecondaryButton")
        self.btn_sync_push.setCursor(Qt.PointingHandCursor)
        self.btn_sync_push.clicked.connect(lambda: self._start_sync("push"))

        actions_row.addWidget(self.btn_sync_two_way)
        actions_row.addWidget(self.btn_sync_pull)
        actions_row.addWidget(self.btn_sync_push)
        actions_row.addStretch()
        sc_layout.addLayout(actions_row)

        self.chk_auto_sync = VisibleCheckBox(
            "Otomatis sinkronisasi data arsip ke server saat menambah atau memperbarui arsip"
        )
        self.chk_auto_sync.setChecked(self.controller.auto_sync_enabled)
        self.chk_auto_sync.toggled.connect(self._toggle_auto_sync)
        sc_layout.addWidget(self.chk_auto_sync)

        self.progress_sync = QProgressBar()
        self.progress_sync.setVisible(False)
        self.lbl_sync_status = QLabel()
        self.lbl_sync_status.setProperty("class", "HintText")
        sc_layout.addWidget(self.progress_sync)
        sc_layout.addWidget(self.lbl_sync_status)

        layout.addWidget(sync_card)

        # Kartu Ringkasan & Riwayat Sinkronisasi
        history_card = QFrame()
        history_card.setProperty("class", "Card")
        hc_layout = QVBoxLayout(history_card)
        hc_layout.setContentsMargins(18, 16, 18, 16)
        hc_layout.setSpacing(10)

        lbl_hist_title = QLabel("Hasil & Riwayat Sinkronisasi")
        lbl_hist_title.setProperty("class", "SectionTitle")
        hc_layout.addWidget(lbl_hist_title)

        grid_metrics = QGridLayout()
        grid_metrics.setSpacing(10)
        self.tile_pushed, self.val_pushed = self._create_metric_tile("Arsip Dikirim")
        self.tile_pulled, self.val_pulled = self._create_metric_tile("Arsip Diterima")
        self.tile_updated, self.val_updated = self._create_metric_tile("Diperbarui Lokal")
        self.tile_conflicts, self.val_conflicts = self._create_metric_tile("Konflik Diselesaikan")

        grid_metrics.addWidget(self.tile_pushed, 0, 0)
        grid_metrics.addWidget(self.tile_pulled, 0, 1)
        grid_metrics.addWidget(self.tile_updated, 0, 2)
        grid_metrics.addWidget(self.tile_conflicts, 0, 3)
        hc_layout.addLayout(grid_metrics)

        self.txt_sync_log = QTextEdit()
        self.txt_sync_log.setReadOnly(True)
        self.txt_sync_log.setMaximumHeight(130)
        self.txt_sync_log.setPlaceholderText("Riwayat aktivitas sinkronisasi akan muncul di sini...")
        hc_layout.addWidget(self.txt_sync_log)

        layout.addWidget(history_card)
        return w

    def _create_server_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # Kartu Kontrol Server
        ctrl_card = QFrame()
        ctrl_card.setProperty("class", "Card")
        cc_layout = QVBoxLayout(ctrl_card)
        cc_layout.setContentsMargins(18, 16, 18, 16)
        cc_layout.setSpacing(10)

        lbl_srv_title = QLabel("Kontrol Server Kantor Mandiri (Pusat Data Host)")
        lbl_srv_title.setProperty("class", "SectionTitle")
        cc_layout.addWidget(lbl_srv_title)

        form = QFormLayout()
        form.setSpacing(8)
        self.input_server_port = QLineEdit(str(DEFAULT_SERVER_PORT))
        self.input_server_port.setFixedWidth(120)

        token_row = QHBoxLayout()
        self.input_server_token = QLineEdit(self.controller.server_token)
        self.btn_gen_token = QPushButton("Acak Token Baru")
        self.btn_gen_token.setProperty("class", "SecondaryButton")
        self.btn_gen_token.clicked.connect(self._generate_random_token)
        token_row.addWidget(self.input_server_token)
        token_row.addWidget(self.btn_gen_token)

        form.addRow("Port Server:", self.input_server_port)
        form.addRow("Token Akses Tim:", token_row)
        cc_layout.addLayout(form)

        row_toggle = QHBoxLayout()
        self.btn_toggle_server = QPushButton("🚀 Jalankan Server Kantor")
        self.btn_toggle_server.setProperty("class", "PrimaryButton")
        self.btn_toggle_server.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_server.clicked.connect(self._toggle_server_host)

        self.lbl_server_host_badge = QLabel("○ Server Nonaktif")
        self.lbl_server_host_badge.setProperty("class", "StatusBadge")

        row_toggle.addWidget(self.btn_toggle_server)
        row_toggle.addWidget(self.lbl_server_host_badge)
        row_toggle.addStretch()
        cc_layout.addLayout(row_toggle)
        layout.addWidget(ctrl_card)

        # Kartu Alamat Jaringan & Panduan Rekan
        net_card = QFrame()
        net_card.setProperty("class", "Card")
        nc_layout = QVBoxLayout(net_card)
        nc_layout.setContentsMargins(18, 16, 18, 16)
        nc_layout.setSpacing(10)

        lbl_net_title = QLabel("Alamat Akses Jaringan Lokal (LAN / Wi-Fi)")
        lbl_net_title.setProperty("class", "SectionTitle")
        nc_layout.addWidget(lbl_net_title)

        self.lbl_hostname = QLabel()
        self.lbl_ip_addresses = QLabel()
        self.lbl_ip_addresses.setWordWrap(True)

        nc_layout.addWidget(self.lbl_hostname)
        nc_layout.addWidget(self.lbl_ip_addresses)

        btn_copy_row = QHBoxLayout()
        self.btn_copy_url = QPushButton("📋 Salin URL Server Utama")
        self.btn_copy_url.setProperty("class", "SecondaryButton")
        self.btn_copy_url.setCursor(Qt.PointingHandCursor)
        self.btn_copy_url.clicked.connect(self._copy_server_url)
        btn_copy_row.addWidget(self.btn_copy_url)
        btn_copy_row.addStretch()
        nc_layout.addLayout(btn_copy_row)

        guide_box = QFrame()
        guide_box.setProperty("class", "SubtleBox")
        gb_layout = QVBoxLayout(guide_box)
        gb_layout.setContentsMargins(12, 10, 12, 10)
        lbl_guide = QLabel(
            "Panduan untuk rekan arsiparis di komputer lain:\n"
            "1. Hubungkan komputer rekan ke jaringan Wi-Fi/LAN kantor yang sama.\n"
            "2. Buka ARSIPTA di laptop rekan, lalu masuk ke menu Sinkronisasi Server.\n"
            "3. Masukkan salah satu URL server di atas beserta Token Akses Tim.\n"
            "4. Klik 'Uji Koneksi Server', lalu lakukan 'Sinkronisasi Dua Arah'."
        )
        lbl_guide.setProperty("class", "MutedText")
        lbl_guide.setWordWrap(True)
        gb_layout.addWidget(lbl_guide)
        nc_layout.addWidget(guide_box)

        layout.addWidget(net_card)

        # Kartu Log Akses & Audit Real-time
        audit_card = QFrame()
        audit_card.setProperty("class", "Card")
        ac_layout = QVBoxLayout(audit_card)
        ac_layout.setContentsMargins(18, 16, 18, 16)
        ac_layout.setSpacing(10)

        row_audit_hdr = QHBoxLayout()
        lbl_audit_title = QLabel("Log Akses & Audit Server Real-time")
        lbl_audit_title.setProperty("class", "SectionTitle")
        self.btn_refresh_audit = QPushButton("🔄 Segarkan Log")
        self.btn_refresh_audit.setProperty("class", "SecondaryButton")
        self.btn_refresh_audit.clicked.connect(self._load_audit_logs)
        self.btn_clear_audit = QPushButton("🗑 Bersihkan Log")
        self.btn_clear_audit.setProperty("class", "SecondaryButton")
        self.btn_clear_audit.clicked.connect(self._clear_audit_logs)

        row_audit_hdr.addWidget(lbl_audit_title)
        row_audit_hdr.addStretch()
        row_audit_hdr.addWidget(self.btn_refresh_audit)
        row_audit_hdr.addWidget(self.btn_clear_audit)
        ac_layout.addLayout(row_audit_hdr)

        self.table_audit = QTableWidget(0, 5)
        self.table_audit.setHorizontalHeaderLabels([
            "Waktu", "IP Klien", "Pengguna", "Aksi", "Status"
        ])
        self.table_audit.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_audit.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_audit.setMaximumHeight(180)
        ac_layout.addWidget(self.table_audit)

        layout.addWidget(audit_card)
        return w

    def switch_tab(self, index: int):
        self.tab_stack.setCurrentIndex(index)
        self._update_tab_buttons(index)
        if index == 1:
            self._load_audit_logs()
            self._update_network_info()

    def _update_tab_buttons(self, active_index: int):
        self.btn_tab_client.setProperty("class", "PrimaryButton" if active_index == 0 else "SecondaryButton")
        self.btn_tab_server.setProperty("class", "PrimaryButton" if active_index == 1 else "SecondaryButton")
        self.btn_tab_client.style().unpolish(self.btn_tab_client)
        self.btn_tab_client.style().polish(self.btn_tab_client)
        self.btn_tab_server.style().unpolish(self.btn_tab_server)
        self.btn_tab_server.style().polish(self.btn_tab_server)

    def refresh_data(self):
        sess = self.controller.session
        self.lbl_b_mode.setText(sess.mode_koneksi)
        self.lbl_b_url.setText(sess.server_url or "Mode Lokal (Mandiri)")

        is_running = self.controller.is_server_running()
        port = self.input_server_port.text().strip() or str(DEFAULT_SERVER_PORT)
        if is_running:
            self.lbl_b_host.setText(f"● Aktif (Port {port})")
            self.lbl_b_host.setStyleSheet("color: #16A34A; font-weight: 600;")
            self.lbl_server_host_badge.setText(f"● Server Aktif (Port {port})")
            self.btn_toggle_server.setText("⏹ Hentikan Server Kantor")
            self.btn_toggle_server.setProperty("class", "DangerButton")
        else:
            self.lbl_b_host.setText("○ Nonaktif")
            self.lbl_b_host.setStyleSheet("color: #64748B; font-weight: 600;")
            self.lbl_server_host_badge.setText("○ Server Nonaktif")
            self.btn_toggle_server.setText("🚀 Jalankan Server Kantor")
            self.btn_toggle_server.setProperty("class", "PrimaryButton")

        self.btn_toggle_server.style().unpolish(self.btn_toggle_server)
        self.btn_toggle_server.style().polish(self.btn_toggle_server)

        last_sync = self.controller.storage.get_sync_meta("last_sync_time", "Belum pernah")
        self.lbl_b_sync.setText(last_sync)
        self._update_network_info()

        rep = self.controller.last_sync_report
        if rep:
            self.val_pushed.setText(str(rep.dikirim))
            self.val_pulled.setText(str(rep.diterima))
            self.val_updated.setText(str(rep.diperbarui_lokal))
            self.val_conflicts.setText(str(rep.konflik_diselesaikan))

    def _update_network_info(self):
        port = self.input_server_port.text().strip() or str(DEFAULT_SERVER_PORT)
        hostname = socket.gethostname()
        self.lbl_hostname.setText(f"Nama Host Komputer: {hostname}")

        ips = self.controller.get_local_ip_addresses()
        lines = [f"• http://{ip}:{port}" for ip in ips]
        lines.append(f"• http://localhost:{port}")
        self.lbl_ip_addresses.setText("URL Tersedia:\n" + "\n".join(lines))

    def _copy_server_url(self):
        port = self.input_server_port.text().strip() or str(DEFAULT_SERVER_PORT)
        ips = self.controller.get_local_ip_addresses()
        primary_ip = ips[0] if ips else "localhost"
        url = f"http://{primary_ip}:{port}"
        clipboard = QApplication.clipboard()
        clipboard.setText(url)
        QMessageBox.information(
            self,
            "URL Disalin",
            f"Alamat server berhasil disalin ke clipboard:\n{url}\n\n"
            "Bagikan URL ini kepada rekan arsiparis di kantor Anda."
        )

    def _generate_random_token(self):
        import secrets
        tok = "arsipta_" + secrets.token_hex(4)
        self.input_server_token.setText(tok)
        self.controller.server_token = tok

    def _toggle_server_host(self):
        if self.controller.is_server_running():
            ok, msg = self.controller.stop_office_server()
            if ok:
                self._append_log(f"[HOST] {msg}")
            else:
                QMessageBox.warning(self, "Gagal Menghentikan Server", msg)
        else:
            try:
                port = int(self.input_server_port.text().strip() or str(DEFAULT_SERVER_PORT))
            except ValueError:
                QMessageBox.warning(self, "Port Tidak Valid", "Port server harus berupa angka numerik.")
                return
            token = self.input_server_token.text().strip()
            ok, msg = self.controller.start_office_server(port=port, token=token)
            self._append_log(f"[HOST] {msg}")

    def _on_server_status_changed(self, is_running: bool, msg: str):
        self._append_log(f"[SERVER] {msg}")
        self.refresh_data()
        self._load_audit_logs()

    def _handle_test_connection(self):
        url = self.input_client_url.text().strip()
        if not url:
            QMessageBox.warning(self, "URL Kosong", "Masukkan alamat URL server kantor terlebih dahulu.")
            return
        ok, msg, data = self.controller.test_remote_server(url)
        if ok:
            name = data.get("server_name", "ARSIPTA Server")
            ver = data.get("version", "")
            tot = data.get("total_archives", 0)
            self.lbl_client_feedback.setText(f"✓ Terhubung ke {name} ({ver}) — {tot} arsip tersedia.")
            self.lbl_client_feedback.setStyleSheet("color: #16A34A; font-weight: 600;")
            self._append_log(f"[KONEKSI] Sukses terhubung ke {url} ({tot} arsip).")
        else:
            self.lbl_client_feedback.setText(f"✗ Gagal terhubung: {msg}")
            self.lbl_client_feedback.setStyleSheet("color: #DC2626; font-weight: 600;")
            self._append_log(f"[KONEKSI] Gagal terhubung ke {url}: {msg}")

    def _handle_apply_server_mode(self):
        url = self.input_client_url.text().strip()
        tok = self.input_client_token.text().strip()
        if not url:
            QMessageBox.warning(self, "URL Kosong", "Masukkan URL server kantor terlebih dahulu.")
            return
        self.controller.server_token = tok
        self.controller.session.mode_koneksi = "Mode Server Kantor"
        self.controller.session.server_url = url
        self.controller.session.server_token = tok
        self.controller.data_updated.emit()
        QMessageBox.information(
            self,
            "Mode Diterapkan",
            f"ARSIPTA kini berjalan dalam Mode Server Kantor terhubung ke:\n{url}"
        )
        self._append_log(f"[MODE] Beralih ke Mode Server Kantor: {url}")

    def _toggle_auto_sync(self, checked: bool):
        self.controller.auto_sync_enabled = checked
        status_txt = "diaktifkan" if checked else "dinonaktifkan"
        self._append_log(f"[PENGATURAN] Sinkronisasi otomatis {status_txt}.")

    def _start_sync(self, action: str):
        url = self.input_client_url.text().strip()
        if not url:
            QMessageBox.warning(self, "URL Kosong", "Masukkan URL server kantor terlebih dahulu.")
            return

        self.btn_sync_two_way.setEnabled(False)
        self.btn_sync_pull.setEnabled(False)
        self.btn_sync_push.setEnabled(False)
        self.progress_sync.setVisible(True)
        self.progress_sync.setValue(10)
        self.lbl_sync_status.setText("Memulai sinkronisasi...")
        self._append_log(f"[SYNC] Memulai sinkronisasi aksi '{action}'...")

        def _on_progress(val, text):
            self.progress_sync.setValue(val)
            self.lbl_sync_status.setText(text)

        def _on_finished(ok, msg, report):
            self.btn_sync_two_way.setEnabled(True)
            self.btn_sync_pull.setEnabled(True)
            self.btn_sync_push.setEnabled(True)
            self.progress_sync.setVisible(False)
            self.lbl_sync_status.setText(msg)
            self._append_log(f"[SYNC] {msg}")
            if ok:
                QMessageBox.information(self, "Sinkronisasi Berhasil", msg)
            else:
                QMessageBox.warning(self, "Sinkronisasi Terkendala", msg)

        self.controller.session.server_url = url
        self.controller.server_token = self.input_client_token.text().strip()
        self.controller.trigger_sync(action, on_progress=_on_progress, on_finished=_on_finished)

    def _on_sync_finished(self, ok: bool, msg: str, report: object):
        self.refresh_data()

    def _append_log(self, text: str):
        now = datetime.now().strftime("%H:%M:%S")
        self.txt_sync_log.append(f"[{now}] {text}")

    def _load_audit_logs(self):
        logs = self.controller.storage.get_server_audit_logs(limit=50)
        self.table_audit.setRowCount(len(logs))
        for row, l in enumerate(logs):
            self.table_audit.setItem(row, 0, QTableWidgetItem(l["waktu"]))
            self.table_audit.setItem(row, 1, QTableWidgetItem(l["client_ip"]))
            self.table_audit.setItem(row, 2, QTableWidgetItem(l["username"]))
            self.table_audit.setItem(row, 3, QTableWidgetItem(l["aksi"]))
            status_item = QTableWidgetItem(str(l["status_code"]))
            if l["status_code"] in (200, 201):
                status_item.setForeground(QColor("#16A34A"))
            else:
                status_item.setForeground(QColor("#DC2626"))
            self.table_audit.setItem(row, 4, status_item)

    def _clear_audit_logs(self):
        confirm = QMessageBox.question(
            self,
            "Bersihkan Log",
            "Apakah Anda yakin ingin menghapus seluruh catatan log audit server?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.controller.storage.clear_server_audit_logs()
            self._load_audit_logs()

    def set_theme(self, dark_mode: bool):
        self.dark_mode = dark_mode
        self.chk_auto_sync.set_theme(dark_mode)
        self._update_tab_buttons(self.tab_stack.currentIndex())


class MainWindow(QMainWindow):
    """Jendela Utama Aplikasi ARSIPTA."""

    def __init__(self, controller: ArsiptaController):
        super().__init__()
        self.controller = controller
        self.dark_mode = False

        self.setWindowTitle(f"{APP_NAME} - {APP_TAGLINE}")
        self.resize(1360, 900)
        self.setMinimumSize(1120, 720)

        self._setup_ui()
        self._apply_theme()
        self._refresh_sidebar_session()
        self.controller.data_updated.connect(self._refresh_sidebar_session)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(12, 20, 12, 16)
        sb_layout.setSpacing(5)

        brand_title = QLabel(APP_NAME)
        brand_title.setProperty("class", "TitleLarge")
        brand_sub = QLabel(APP_TAGLINE)
        brand_sub.setProperty("class", "MutedText")

        sb_layout.addWidget(brand_title)
        sb_layout.addWidget(brand_sub)
        sb_layout.addSpacing(16)

        self.nav_buttons: List[QPushButton] = []
        nav_items = [
            ("Dashboard Utama", 0),
            ("Katalog Arsip", 1),
            ("Peringatan Retensi", 2),
            ("Impor & Ekspor", 3),
            ("Sinkronisasi Server", 4),
        ]

        for label, index in nav_items:
            btn = QPushButton(label)
            btn.setProperty("class", "NavButton")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(
                lambda checked=False, i=index: self.switch_page(i)
            )
            sb_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sb_layout.addStretch()

        session_card = QFrame()
        session_card.setProperty("class", "SubtleBox")
        sc_layout = QVBoxLayout(session_card)
        sc_layout.setContentsMargins(10, 10, 10, 10)
        sc_layout.setSpacing(6)

        self.lbl_sb_user = QLabel("Arsiparis Utama")
        self.lbl_sb_user.setStyleSheet("font-weight: 600;")
        self.lbl_sb_mode = QLabel("Mode Lokal")
        self.lbl_sb_mode.setProperty("class", "StatusBadge")

        self.btn_login = QPushButton("Ganti Akun / Mode Kerja")
        self.btn_login.setProperty("class", "SecondaryButton")
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.clicked.connect(self._open_login_dialog)

        sc_layout.addWidget(self.lbl_sb_user)
        sc_layout.addWidget(self.lbl_sb_mode)
        sc_layout.addWidget(self.btn_login)
        sb_layout.addWidget(session_card)

        sb_layout.addSpacing(6)

        self.btn_theme = QPushButton("Ubah ke Mode Gelap")
        self.btn_theme.setProperty("class", "SecondaryButton")
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.clicked.connect(self._toggle_theme)
        sb_layout.addWidget(self.btn_theme)

        content_wrapper = QWidget()
        content_wrapper.setObjectName("MainContentArea")
        cw_layout = QVBoxLayout(content_wrapper)
        cw_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        self.page_dashboard = DashboardPage(self.controller)
        self.page_dashboard.navigate_requested.connect(self.switch_page)
        self.page_dashboard.open_session_requested.connect(
            self._open_login_dialog
        )

        self.page_katalog = CatalogPage(self.controller)
        self.page_katalog.export_filtered_requested.connect(
            self._jump_to_filtered_export
        )

        self.page_retensi = RetentionPage(self.controller)
        self.page_io = ImportExportPage(self.controller)

        self.page_hybrid = ServerSyncPage(self.controller)

        self.stack.addWidget(self.page_dashboard)
        self.stack.addWidget(self.page_katalog)
        self.stack.addWidget(self.page_retensi)
        self.stack.addWidget(self.page_io)
        self.stack.addWidget(self.page_hybrid)

        cw_layout.addWidget(self.stack)

        root_layout.addWidget(sidebar)
        root_layout.addWidget(content_wrapper)

        self.switch_page(0)

    def _jump_to_filtered_export(self):
        self.page_io.select_filtered_export_mode()
        self.switch_page(3)

    def _refresh_sidebar_session(self):
        sess = self.controller.session
        self.lbl_sb_user.setText(f"{sess.nama_lengkap} (@{sess.username})")
        host_badge = " (Host)" if self.controller.is_server_running() else ""
        self.lbl_sb_mode.setText(f"{sess.mode_koneksi}{host_badge}")

    def switch_page(self, index: int):
        self.stack.setCurrentIndex(index)
        if index == 3:
            self.page_io.refresh_counts()
        for i, btn in enumerate(self.nav_buttons):
            btn.setProperty("active", "true" if i == index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.btn_theme.setText(
            "Ubah ke Mode Terang" if self.dark_mode else "Ubah ke Mode Gelap"
        )
        self._apply_theme()

    def _apply_theme(self):
        self.setStyleSheet(ThemeManager.build_stylesheet(self.dark_mode))
        self.page_dashboard.set_theme(self.dark_mode)
        self.page_katalog.set_theme(self.dark_mode)
        self.page_retensi.set_theme(self.dark_mode)
        self.page_io.set_theme(self.dark_mode)
        self.page_hybrid.set_theme(self.dark_mode)

    def closeEvent(self, event):
        if self.controller.is_server_running():
            self.controller.stop_office_server()
        super().closeEvent(event)

    def _open_login_dialog(self):
        dialog = SessionModeDialog(self.controller, self.dark_mode, self)
        dialog.exec()


# ==============================================================================
# RANGKAIAN PENGUJIAN OTOMATIS (Automated Test Suite - Fase 1, 2, 3, & 4)
# ==============================================================================

class TestArsiptaSuite(unittest.TestCase):
    """Pengujian otomatis untuk seluruh modul inti Fase 1 hingga Fase 3."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_arsipta.db")
        self.storage = StorageEngine(self.db_path)
        self.controller = ArsiptaController(self.storage)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_initial_seed_and_metrics(self):
        metrics = self.controller.get_summary()
        self.assertEqual(metrics["total"], 6)
        self.assertEqual(metrics["aktif"], 4)
        self.assertEqual(metrics["inaktif"], 2)
        self.assertEqual(metrics["peringatan_retensi"], 3)

    def test_02_retention_calculator(self):
        ref = date(2026, 6, 1)
        self.assertEqual(
            ArchiveProcessingEngine.evaluate_retention("2026-05-01", ref)[0],
            "Kedaluwarsa"
        )
        self.assertEqual(
            ArchiveProcessingEngine.evaluate_retention("2026-06-20", ref)[0],
            "Kritis (<= 30 Hari)"
        )
        self.assertEqual(
            ArchiveProcessingEngine.evaluate_retention("2026-08-15", ref)[0],
            "Perhatian (<= 90 Hari)"
        )
        self.assertEqual(
            ArchiveProcessingEngine.evaluate_retention("2027-01-01", ref)[0],
            "Aman"
        )

    def test_03_user_authentication_register_and_work_mode(self):
        ok_fail, _ = self.controller.switch_session(
            "arsiparis", "salah", "Mode Lokal", ""
        )
        self.assertFalse(ok_fail)

        ok_reg, _ = self.controller.register_new_account(
            "magang01", "rahasia123", "Anak Magang Arsip"
        )
        self.assertTrue(ok_reg)

        ok_server_empty, _ = self.controller.switch_session(
            "magang01", "rahasia123", "Mode Server Kantor", ""
        )
        self.assertFalse(ok_server_empty)

        ok_success, _ = self.controller.switch_session(
            "magang01",
            "rahasia123",
            "Mode Server Kantor",
            "http://10.0.0.5:8080"
        )
        self.assertTrue(ok_success)
        self.assertEqual(
            self.controller.session.mode_koneksi, "Mode Server Kantor"
        )

    def test_04_safe_working_copy_preserves_original(self):
        orig_file = os.path.join(self.temp_dir, "dokumen_asli.csv")
        with open(orig_file, "w", encoding="utf-8") as f:
            f.write("nomor,judul\n001,Kontrak Asli\n")

        work_dir = os.path.join(self.temp_dir, "kerja")
        copy_path = ArchiveProcessingEngine.create_safe_working_copy(
            orig_file, work_dir
        )

        self.assertTrue(os.path.exists(copy_path))
        self.assertNotEqual(orig_file, copy_path)
        with open(orig_file, "r", encoding="utf-8") as f:
            self.assertIn("Kontrak Asli", f.read())

    def test_05_archive_crud_and_duplicate_guard(self):
        new_rec = ArchiveRecord(
            id=None,
            nomor_dokumen="PKS/2026/999",
            judul_perjanjian="Kontrak Uji Coba Sistem",
            pihak_terkait="PT Uji Coba",
            topik="Teknologi Informasi",
            tanggal_mulai="2026-01-01",
            tanggal_berakhir="2027-01-01",
            status="Aktif",
            lokasi_fisik="Rak Z - 01",
            file_sumber="Manual",
            diperbarui_pada=""
        )
        ok_add, _ = self.controller.create_archive(new_rec)
        self.assertTrue(ok_add)

        ok_dup, _ = self.controller.create_archive(new_rec)
        self.assertFalse(ok_dup)

        all_items = self.controller.get_archives()
        created = next(
            r for r in all_items if r.nomor_dokumen == "PKS/2026/999"
        )
        created.judul_perjanjian = "Kontrak Uji Coba (Revisi)"
        ok_edit, _ = self.controller.edit_archive(created)
        self.assertTrue(ok_edit)

        updated = self.controller.get_archive_by_id(created.id)
        self.assertEqual(updated.judul_perjanjian, "Kontrak Uji Coba (Revisi)")

        ok_del, _ = self.controller.remove_archive(created.id)
        self.assertTrue(ok_del)
        self.assertIsNone(self.controller.get_archive_by_id(created.id))

    def test_06_realtime_search_and_multi_filter(self):
        res_search, _ = self.controller.search_archives(
            FilterCriteria(search_text="Nusantara")
        )
        self.assertEqual(len(res_search), 1)
        self.assertEqual(res_search[0].nomor_dokumen, "PKS/2025/001")

        res_inaktif, _ = self.controller.search_archives(
            FilterCriteria(status="Inaktif")
        )
        self.assertEqual(len(res_inaktif), 2)

        res_perhatian, _ = self.controller.search_archives(
            FilterCriteria(retensi="Perlu Perhatian")
        )
        self.assertEqual(len(res_perhatian), 3)

    def test_07_date_range_filter(self):
        today = date.today()
        criteria = FilterCriteria(
            use_date_range=True,
            date_from=(today - timedelta(days=50)).isoformat(),
            date_to=(today + timedelta(days=30)).isoformat()
        )
        res, _ = self.controller.search_archives(criteria)
        self.assertGreaterEqual(len(res), 2)
        for item in res:
            self.assertGreaterEqual(item.tanggal_berakhir, criteria.date_from)
            self.assertLessEqual(item.tanggal_berakhir, criteria.date_to)

    def test_08_retention_watchlist_and_status_switch(self):
        watchlist = self.controller.get_retention_watchlist()
        self.assertEqual(len(watchlist), 3)
        self.assertLessEqual(watchlist[0][2], watchlist[1][2])

        target_id = watchlist[0][0].id
        ok, _ = self.controller.set_archive_status(target_id, "Inaktif")
        self.assertTrue(ok)
        self.assertEqual(len(self.controller.get_retention_watchlist()), 2)

    def test_09_generate_and_import_csv_safe_copy(self):
        csv_path = os.path.join(self.temp_dir, "template_uji.csv")
        ok_tpl, _ = SpreadsheetIOEngine.generate_sample_template(csv_path)
        self.assertTrue(ok_tpl)

        work_dir = os.path.join(self.temp_dir, "work")
        records, warnings = SpreadsheetIOEngine.parse_spreadsheet_file(
            csv_path, work_dir
        )
        self.assertEqual(len(records), 2)
        self.assertEqual(len(warnings), 0)

        ins, upd, skip = self.storage.upsert_archive_batch(
            records, update_existing=False
        )
        self.assertEqual(ins, 2)
        self.assertEqual(upd, 0)
        self.assertEqual(skip, 0)

    def test_10_generate_and_import_xlsx_with_duplicate_update(self):
        if not OPENPYXL_AVAILABLE:
            self.skipTest("openpyxl tidak tersedia")
        xlsx_path = os.path.join(self.temp_dir, "template_uji.xlsx")
        ok_tpl, _ = SpreadsheetIOEngine.generate_sample_template(xlsx_path)
        self.assertTrue(ok_tpl)

        work_dir = os.path.join(self.temp_dir, "work")
        records, _ = SpreadsheetIOEngine.parse_spreadsheet_file(
            xlsx_path, work_dir
        )
        ins1, _, _ = self.storage.upsert_archive_batch(
            records, update_existing=False
        )
        self.assertEqual(ins1, 2)

        # Impor ulang dengan mode lewati
        ins2, upd2, skip2 = self.storage.upsert_archive_batch(
            records, update_existing=False
        )
        self.assertEqual(ins2, 0)
        self.assertEqual(skip2, 2)

        # Impor ulang dengan mode perbarui
        records[0].judul_perjanjian = "Judul Diperbarui dari Excel"
        ins3, upd3, skip3 = self.storage.upsert_archive_batch(
            records, update_existing=True
        )
        self.assertEqual(upd3, 2)
        self.assertEqual(skip3, 0)

    def test_11_export_filtered_xlsx_and_csv(self):
        inaktif_records, _ = self.controller.search_archives(
            FilterCriteria(status="Inaktif")
        )
        out_csv = os.path.join(self.temp_dir, "ekspor_inaktif.csv")
        ok_csv, _ = SpreadsheetIOEngine.export_records(inaktif_records, out_csv)
        self.assertTrue(ok_csv)
        self.assertTrue(os.path.isfile(out_csv))

        if OPENPYXL_AVAILABLE:
            out_xlsx = os.path.join(self.temp_dir, "ekspor_inaktif.xlsx")
            ok_xlsx, _ = SpreadsheetIOEngine.export_records(
                inaktif_records, out_xlsx
            )
            self.assertTrue(ok_xlsx)
            self.assertTrue(os.path.isfile(out_xlsx))

    def test_12_corrupted_file_handling(self):
        bad_file = os.path.join(self.temp_dir, "rusak.xlsx")
        with open(bad_file, "wb") as f:
            f.write(b"BUKAN_FILE_EXCEL_VALID_12345")

        work_dir = os.path.join(self.temp_dir, "work")
        with self.assertRaises(ValueError):
            SpreadsheetIOEngine.parse_spreadsheet_file(bad_file, work_dir)

    def test_13_server_service_status_and_ping(self):
        service = ArsiptaServerService(self.storage, "tok123")
        client = SyncClientEngine(mock_service=service)
        ok, data, err = client.ping("http://server:8080")
        self.assertTrue(ok)
        self.assertEqual(data["status"], "online")
        self.assertEqual(data["total_archives"], 6)
        self.assertEqual(data["version"], APP_VERSION)

    def test_14_server_auth_and_token_protection(self):
        token = "secret_suite_tok"
        service = ArsiptaServerService(self.storage, token)
        client = SyncClientEngine(mock_service=service)

        ok_login, udata, _ = client.authenticate("http://server:8080", "arsiparis", "arsip123")
        self.assertTrue(ok_login)
        self.assertEqual(udata["user"]["peran"], "Arsiparis")

        ok_bad, _, _ = client.authenticate("http://server:8080", "arsiparis", "salahpass")
        self.assertFalse(ok_bad)

        ok_no_tok, _, _ = client.pull_records("http://server:8080", token="")
        self.assertFalse(ok_no_tok)

        ok_tok, recs, _ = client.pull_records("http://server:8080", token=token)
        self.assertTrue(ok_tok)
        self.assertEqual(len(recs), 6)

    def test_15_server_crud_and_duplicate_prevention(self):
        token = "tok_crud"
        service = ArsiptaServerService(self.storage, token)
        client = SyncClientEngine(mock_service=service)

        new_rec = ArchiveRecord(
            id=None,
            nomor_dokumen="PKS/SUITE/901",
            judul_perjanjian="Perjanjian Uji Server Suite",
            pihak_terkait="PT Mitra Test",
            topik="Teknologi Informasi",
            tanggal_mulai="2026-01-01",
            tanggal_berakhir="2027-01-01",
            status="Aktif",
            lokasi_fisik="Server Room",
            file_sumber="Suite",
            diperbarui_pada="2026-11-21 10:00:00"
        )
        ok_add, _ = client.push_record("http://server:8080", new_rec, token=token)
        self.assertTrue(ok_add)

        ok_dup, err_dup = client.push_record("http://server:8080", new_rec, token=token)
        self.assertFalse(ok_dup)
        self.assertIn("sudah terdaftar", err_dup)

        ok_list, items, _ = client.pull_records("http://server:8080", token=token)
        self.assertTrue(ok_list)
        self.assertEqual(len(items), 7)

    def test_16_two_way_synchronization_and_conflict_resolution(self):
        server_storage = self.storage
        client_db = os.path.join(self.temp_dir, "client_suite.db")
        client_storage = StorageEngine(client_db)
        token = "sync_suite_token"
        service = ArsiptaServerService(server_storage, token)
        client_engine = SyncClientEngine(mock_service=service)

        client_rec = ArchiveRecord(
            id=None,
            nomor_dokumen="PKS/CLI/999",
            judul_perjanjian="Kontrak Mandiri Client",
            pihak_terkait="PT Klien Suite",
            topik="Pengadaan Barang & Jasa",
            tanggal_mulai="2026-02-01",
            tanggal_berakhir="2027-02-01",
            status="Aktif",
            lokasi_fisik="Rak Klien",
            file_sumber="Manual",
            diperbarui_pada="2026-11-21 12:00:00"
        )
        client_storage.add_archive(client_rec)

        server_rec = ArchiveRecord(
            id=None,
            nomor_dokumen="PKS/SRV/999",
            judul_perjanjian="Kontrak Mandiri Server",
            pihak_terkait="PT Server Suite",
            topik="Infrastruktur",
            tanggal_mulai="2026-03-01",
            tanggal_berakhir="2027-03-01",
            status="Aktif",
            lokasi_fisik="Rak Server",
            file_sumber="Manual",
            diperbarui_pada="2026-11-21 12:00:00"
        )
        server_storage.add_archive(server_rec)

        # Konflik update: Klien revisi PKS/2025/001 dengan timestamp lebih baru
        pks001 = client_storage.get_all_archives()
        target = next(r for r in pks001 if r.nomor_dokumen == "PKS/2025/001")
        target.judul_perjanjian = "Revisi PKS 001 dari Suite Klien"
        target.diperbarui_pada = "2026-11-21 15:00:00"
        client_storage.update_archive(target)

        ok_sync, report = client_engine.sync_two_way(
            "http://server:8080", client_storage, token=token, username="arsiparis"
        )
        self.assertTrue(ok_sync)
        self.assertTrue(report.success)
        self.assertGreaterEqual(report.dikirim, 7)
        self.assertGreaterEqual(report.diterima, 7)

        server_dict = {r.nomor_dokumen: r for r in server_storage.get_all_archives()}
        client_dict = {r.nomor_dokumen: r for r in client_storage.get_all_archives()}

        self.assertIn("PKS/CLI/999", server_dict)
        self.assertIn("PKS/SRV/999", server_dict)
        self.assertIn("PKS/CLI/999", client_dict)
        self.assertIn("PKS/SRV/999", client_dict)
        self.assertEqual(server_dict["PKS/2025/001"].judul_perjanjian, "Revisi PKS 001 dari Suite Klien")
        self.assertEqual(client_dict["PKS/2025/001"].judul_perjanjian, "Revisi PKS 001 dari Suite Klien")
        self.assertEqual(len(server_dict), 8)
        self.assertEqual(len(client_dict), 8)

    def test_17_audit_logging_and_offline_resilience(self):
        service = ArsiptaServerService(self.storage, "tok_audit")
        client = SyncClientEngine(mock_service=service)
        client.ping("http://server:8080")

        logs = self.storage.get_server_audit_logs()
        self.assertGreater(len(logs), 0)
        self.assertEqual(logs[0]["endpoint"], "/api/status")

        offline_client = SyncClientEngine(mock_service=None)
        ok_off, rep_off = offline_client.sync_two_way(
            "http://127.0.0.1:59999", self.storage, token="bad", timeout=0.5
        )
        self.assertFalse(ok_off)
        self.assertFalse(rep_off.success)
        self.assertIn("Gagal", rep_off.pesan)
        self.assertGreaterEqual(len(self.storage.get_all_archives()), 6)


def run_automated_tests() -> bool:
    """Menjalankan seluruh unit test dan menampilkan hasilnya."""
    print("=== MENJALANKAN PENGUJIAN OTOMATIS ARSIPTA (FASE 1, 2, 3, & 4) ===")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestArsiptaSuite)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


def run_headless_server(port: int = DEFAULT_SERVER_PORT, token: str = DEFAULT_SERVER_TOKEN):
    """Menjalankan ARSIPTA dalam mode server mandiri tanpa GUI (Headless Console Mode)."""
    print("=" * 65)
    print(f" {APP_NAME} - {APP_TAGLINE} | HEADLESS SERVER HOST")
    print(f" Versi: {APP_VERSION}")
    print("=" * 65)

    storage = StorageEngine(DEFAULT_DB_FILENAME)
    service = ArsiptaServerService(storage, token)
    httpd = ArsiptaHttpServer((DEFAULT_SERVER_HOST, port), ArsiptaHttpHandler, service)

    hostname = socket.gethostname()
    ips = []
    try:
        _, _, addrs = socket.gethostbyname_ex(hostname)
        ips = [a for a in addrs if not a.startswith("127.")]
    except Exception:
        pass
    if not ips:
        ips = ["127.0.0.1"]

    print(f"\n[+] Server berjalan pada port {port}")
    print(f"[+] Token Akses Server : {token}")
    print(f"[+] Alamat Hostname    : {hostname}")
    print("[+] URL Akses Jaringan :")
    for ip in ips:
        print(f"    • http://{ip}:{port}")
    print(f"    • http://localhost:{port}")
    print(f"[+] Total Arsip di Database: {len(storage.get_all_archives())} arsip")
    print("\nTekan Ctrl+C untuk menghentikan server kantor secara aman...\n")
    sys.stdout.flush()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Menerima sinyal berhenti, mematikan server...")
    finally:
        httpd.shutdown()
        httpd.server_close()
        print("[✓] Server kantor berhasil dimatikan secara bersih.")


# ==============================================================================
# TITIK MASUK APLIKASI (Entry Point)
# ==============================================================================

def main():
    if "--test" in sys.argv:
        success = run_automated_tests()
        sys.exit(0 if success else 1)

    if "--server" in sys.argv:
        port = DEFAULT_SERVER_PORT
        token = DEFAULT_SERVER_TOKEN
        idx = sys.argv.index("--server")
        if len(sys.argv) > idx + 1 and sys.argv[idx + 1].isdigit():
            port = int(sys.argv[idx + 1])
        if len(sys.argv) > idx + 2:
            token = sys.argv[idx + 2]
        run_headless_server(port, token)
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(APP_NAME)
    app.setFont(QFont("Segoe UI", 10))

    storage = StorageEngine(DEFAULT_DB_FILENAME)
    controller = ArsiptaController(storage)

    window = MainWindow(controller)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()