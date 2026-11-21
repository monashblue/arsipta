from .common import *
from .models import *
from .storage import *
from .processing import *
from .spreadsheet import *


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

