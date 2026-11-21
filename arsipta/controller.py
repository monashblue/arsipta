from .common import *
from .models import *
from .storage import *
from .processing import *
from .spreadsheet import *
from .network import *
from .workers import *


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

