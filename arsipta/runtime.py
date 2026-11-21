from pathlib import Path
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
from .testing import *


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

    # PyInstaller mengekstrak resource ke _MEIPASS; saat source,
    # resource berada di direktori proyek/assets.
    if getattr(sys, "frozen", False):
        resource_dir = Path(sys._MEIPASS)
    else:
        resource_dir = Path(__file__).resolve().parent.parent
    icon_path = resource_dir / "assets" / "icon" / "apps.ico"
    if icon_path.is_file():
        app_icon = QIcon(str(icon_path))
        app.setWindowIcon(app_icon)

    storage = StorageEngine(DEFAULT_DB_FILENAME)
    controller = ArsiptaController(storage)

    window = MainWindow(controller)
    window.show()
    sys.exit(app.exec())

