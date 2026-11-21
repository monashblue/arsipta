from .common import *


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

