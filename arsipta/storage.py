from .common import *
from .models import *


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

            # Bersihkan riwayat aktivitas contoh dari versi demo terdahulu.
            # Hanya baris dengan lokasi dummy bawaan yang dihapus; data arsip,
            # pengguna, dan riwayat impor/ekspor pada lokasi lain tetap utuh.
            cursor.execute("""
                DELETE FROM recent_files
                WHERE jalur_file LIKE 'D:/Arsip_Kantor/%'
                   OR jalur_file LIKE 'D:/Arsip Dinamis/Arsip Aktif/arsipta/%'
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

        # Riwayat file sengaja dibiarkan kosong pada instalasi baru.
        # Tabel recent_files hanya diisi ketika pengguna benar-benar
        # melakukan impor atau ekspor melalui aplikasi.

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

