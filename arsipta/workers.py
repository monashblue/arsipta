from .common import *
from .models import *
from .storage import *
from .processing import *
from .spreadsheet import *
from .network import *


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

