from .common import *
from .models import *
from .storage import *


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

