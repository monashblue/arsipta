from .common import *
from .models import *
from .storage import *
from .processing import *


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

