from .common import *
from .models import *
from .storage import *
from .processing import *
from .spreadsheet import *
from .network import *
from .workers import *
from .controller import *
from .ui_components import *
from .ui_pages import *


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

