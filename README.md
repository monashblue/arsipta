# ARSIPTA — Paket build executable Windows (ONEFILE)

Aplikasi desktop Python + PySide6, penyimpanan SQLite, dan dukungan spreadsheet.

## Membuat executable `--onefile` (Windows 10/11 64-bit)

> Build harus dilakukan di Windows agar hasil `.exe` sesuai dengan Windows. File `.exe` tidak dapat dibangun secara valid dari lingkungan Linux/macOS.

1. Ekstrak seluruh ZIP ini, misalnya ke `C:\ARSIPTA`.
2. Pasang Python 3.11–3.13 64-bit. Aktifkan opsi **Add Python to PATH**.
3. Buka folder `ARSIPTA_Modular`, lalu klik dua kali `scripts\install_windows.bat`.
4. Setelah instalasi dependensi selesai, klik dua kali `scripts\build_exe_windows.bat`.
5. Tunggu hingga muncul `BUILD BERHASIL`.
6. File hasilnya ada di `dist\ARSIPTA.exe`. Untuk membagikan aplikasi, salin file `ARSIPTA.exe` tersebut saja.

Skrip build memakai PyInstaller `--onefile --windowed`, ikon `assets\icon\apps.ico`, dan menyertakan seluruh folder `assets`. Saat dijalankan, PyInstaller mengekstrak aset internal ke folder sementara; folder sementara ini bukan tempat penyimpanan database.

## Cara memasang / menjalankan pada komputer pengguna

1. Salin `ARSIPTA.exe` ke folder permanen, misalnya `C:\Aplikasi\ARSIPTA\`.
2. Klik dua kali `ARSIPTA.exe`.
3. Pada peluncuran pertama, Windows mungkin menampilkan peringatan SmartScreen. Jika file berasal dari sumber tepercaya, pilih **More info** lalu **Run anyway**.
4. Aplikasi membuat folder data dan menyalin database awal secara otomatis.
5. Jalankan aplikasi seperti biasa. Komputer pengguna tidak perlu memasang Python atau dependensi.

## Di mana database dan file tersimpan?

Database katalog SQLite disimpan di:

`%LOCALAPPDATA%\ARSIPTA\arsipta_katalog.db`

Contoh lokasi:

`C:\Users\<NamaPengguna>\AppData\Local\ARSIPTA\arsipta_katalog.db`

Folder `%LOCALAPPDATA%\ARSIPTA` dibuat otomatis saat aplikasi pertama kali dijalankan. Jika database belum ada, aplikasi menyalin database awal dari paket. Database yang sudah ada tidak ditimpa saat aplikasi dibuka kembali.

Jika terdapat database lama `arsipta_katalog.db` di samping executable/source, aplikasi mencoba menyalinnya ke folder data baru saat migrasi pertama agar data lama terbawa.

File hasil ekspor Excel/CSV dan template yang dibuat melalui aplikasi disimpan ke lokasi yang dipilih pengguna pada dialog **Save As**. File tersebut tidak otomatis masuk ke folder data ARSIPTA. Agar rapi, pilih/buat folder khusus seperti `Dokumen\ARSIPTA\Ekspor`.

**Penting:** cadangkan seluruh folder `%LOCALAPPDATA%\ARSIPTA` secara berkala. Jangan menghapus folder tersebut saat menghapus atau memindahkan executable karena berisi database utama.

## Catatan

- Untuk distribusi, cukup bagikan satu file `dist\ARSIPTA.exe`.
- Setiap akun Windows memiliki folder data dan database masing-masing.
- Jangan menyimpan database aktif di folder sementara PyInstaller (`_MEIPASS`).
- Tinjau dan ganti akun contoh serta token server bawaan sebelum pemakaian produksi.
- Mode pengujian/source: `python main.py --test`
- Mode server/source: `python main.py --server` atau `python main.py --server 8080 token-rahasia-anda`

## Menjalankan dari source (opsional)

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```


## Kondisi data awal versi Clean

- Contoh arsip katalog tetap disertakan sebagai data contoh.
- Riwayat **File yang Baru Diproses** dikosongkan pada instalasi baru; daftar ini baru terisi setelah pengguna benar-benar melakukan impor atau ekspor.
- Tidak ada file template impor atau laporan hasil pengujian yang disediakan sebagai file bawaan. Fitur membuat template impor secara manual tetap tersedia bila pengguna membutuhkannya.
