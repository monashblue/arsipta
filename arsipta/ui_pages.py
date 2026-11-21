from .common import *
from .models import *
from .storage import *
from .processing import *
from .spreadsheet import *
from .network import *
from .workers import *
from .controller import *
from .ui_components import *


class DashboardPage(QWidget):
    """Halaman utama Dashboard penyambut dan pemantauan satu layar."""

    navigate_requested = Signal(int)
    open_session_requested = Signal()

    def __init__(self, controller: ArsiptaController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._setup_ui()
        self.refresh_data()
        self.controller.data_updated.connect(self.refresh_data)

    def _setup_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        container.setObjectName("ScrollContainer")
        self.main_layout = QVBoxLayout(container)
        self.main_layout.setContentsMargins(28, 24, 28, 24)
        self.main_layout.setSpacing(20)

        header_row = QHBoxLayout()
        welcome_col = QVBoxLayout()
        self.lbl_welcome = QLabel(f"Selamat Datang di {APP_NAME}")
        self.lbl_welcome.setProperty("class", "TitleLarge")
        self.lbl_sub = QLabel(
            "Pantau seluruh arsip perjanjian, masa retensi, "
            "dan sinkronisasi tim dalam satu layar."
        )
        self.lbl_sub.setProperty("class", "MutedText")
        welcome_col.addWidget(self.lbl_welcome)
        welcome_col.addWidget(self.lbl_sub)

        self.search_tools = QLineEdit()
        self.search_tools.setPlaceholderText(
            "Cari alat atau fitur (misal: katalog, excel, retensi, akun)..."
        )
        self.search_tools.setFixedWidth(340)
        self.search_tools.textChanged.connect(self._filter_feature_cards)

        header_row.addLayout(welcome_col)
        header_row.addStretch()
        header_row.addWidget(self.search_tools)
        self.main_layout.addLayout(header_row)

        stats_grid = QGridLayout()
        stats_grid.setSpacing(14)

        self.card_total, self.val_total = self._create_metric_card(
            "Total Arsip Perjanjian", "0", "Seluruh dokumen tercatat"
        )
        self.card_aktif, self.val_aktif = self._create_metric_card(
            "Arsip Aktif", "0", "Perjanjian masih berlaku"
        )
        self.card_inaktif, self.val_inaktif = self._create_metric_card(
            "Arsip Inaktif", "0", "Perjanjian berakhir / arsip statis"
        )
        self.card_retensi, self.val_retensi = self._create_metric_card(
            "Peringatan Retensi", "0", "Jatuh tempo <= 90 hari / lewat"
        )

        stats_grid.addWidget(self.card_total, 0, 0)
        stats_grid.addWidget(self.card_aktif, 0, 1)
        stats_grid.addWidget(self.card_inaktif, 0, 2)
        stats_grid.addWidget(self.card_retensi, 0, 3)
        self.main_layout.addLayout(stats_grid)

        # Kartu Grafik Komposisi Status Aktif vs Inaktif
        comp_card = QFrame()
        comp_card.setProperty("class", "Card")
        comp_layout = QVBoxLayout(comp_card)
        comp_layout.setContentsMargins(18, 16, 18, 16)
        comp_layout.setSpacing(8)

        comp_title = QLabel("Komposisi Status Arsip (Aktif vs Inaktif)")
        comp_title.setProperty("class", "SectionTitle")
        self.status_chart = StatusCompositionWidget()

        comp_layout.addWidget(comp_title)
        comp_layout.addWidget(self.status_chart)
        self.main_layout.addWidget(comp_card)

        lbl_quick = QLabel("Akses Cepat & Modul Fitur")
        lbl_quick.setProperty("class", "SectionTitle")
        self.main_layout.addWidget(lbl_quick)

        self.cards_grid = QGridLayout()
        self.cards_grid.setSpacing(14)

        self.feature_definitions = [
            (
                "Katalog Arsip Utama",
                "Telusuri, urutkan kolom, tambah/ubah arsip, dan filter "
                "real-time seluruh arsip perjanjian.",
                1,
                "katalog cari filter daftar tambah ubah"
            ),
            (
                "Pemantau Masa Retensi",
                "Cek perjanjian yang mendekati jatuh tempo "
                "dan lakukan perpanjangan atau alih inaktif.",
                2,
                "retensi peringatan jatuh tempo perpanjang"
            ),
            (
                "Impor & Ekspor Excel/CSV",
                "Migrasi daftar Excel lama tanpa merusak file asli serta "
                "unduh laporan CSV/XLSX.",
                3,
                "excel csv impor ekspor template"
            ),
            (
                "Akun Tim & Mode Kerja",
                "Pilih kerja mandiri (lokal) atau hubungkan ke server "
                "kantor agar tampilan tim seragam.",
                -1,
                "akun hybrid server login sinkronisasi"
            ),
            (
                "Sinkronisasi Server Kantor",
                "Hubungkan ke server kantor atau jadikan komputer ini server host "
                "agar seluruh staf tersambung ke database yang sama.",
                4,
                "server hybrid host sinkronisasi jaringan lan ip port"
            ),
        ]

        self.feature_widgets: List[Tuple[ClickableCard, str]] = []
        for idx, (title, desc, page_idx, keywords) in enumerate(
            self.feature_definitions
        ):
            card = ClickableCard()
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(16, 14, 16, 14)
            c_layout.setSpacing(6)

            t_lbl = QLabel(title)
            t_lbl.setProperty("class", "SectionTitle")
            d_lbl = QLabel(desc)
            d_lbl.setProperty("class", "MutedText")
            d_lbl.setWordWrap(True)

            c_layout.addWidget(t_lbl)
            c_layout.addWidget(d_lbl)
            if page_idx == -1:
                card.clicked.connect(self.open_session_requested.emit)
            else:
                card.clicked.connect(
                    lambda p=page_idx: self.navigate_requested.emit(p)
                )

            self.cards_grid.addWidget(card, idx // 2, idx % 2)
            self.feature_widgets.append(
                (card, f"{title.lower()} {desc.lower()} {keywords}")
            )

        self.main_layout.addLayout(self.cards_grid)

        recent_card = QFrame()
        recent_card.setProperty("class", "Card")
        recent_layout = QVBoxLayout(recent_card)
        recent_layout.setContentsMargins(18, 16, 18, 16)
        recent_layout.setSpacing(10)

        recent_title = QLabel("File yang Baru Diproses")
        recent_title.setProperty("class", "SectionTitle")
        recent_layout.addWidget(recent_title)

        self.table_recent = QTableWidget(0, 4)
        self.table_recent.setHorizontalHeaderLabels(
            ["Nama File", "Jalur Lokasi", "Aktivitas", "Waktu"]
        )
        self.table_recent.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.table_recent.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_recent.setMaximumHeight(150)
        recent_layout.addWidget(self.table_recent)

        self.main_layout.addWidget(recent_card)

        footer_row = QHBoxLayout()
        self.lbl_session_info = QLabel()
        self.lbl_session_info.setProperty("class", "MutedText")
        lbl_ver = QLabel(f"{APP_NAME} v{APP_VERSION} • Lisensi MIT")
        lbl_ver.setProperty("class", "MutedText")
        footer_row.addWidget(self.lbl_session_info)
        footer_row.addStretch()
        footer_row.addWidget(lbl_ver)
        self.main_layout.addLayout(footer_row)

        self.main_layout.addStretch()
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _create_metric_card(
        self, title: str, initial_val: str, subtitle: str
    ) -> Tuple[QFrame, QLabel]:
        card = QFrame()
        card.setProperty("class", "Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        lbl_t = QLabel(title)
        lbl_t.setProperty("class", "MutedText")
        lbl_v = QLabel(initial_val)
        lbl_v.setProperty("class", "MetricValue")
        lbl_s = QLabel(subtitle)
        lbl_s.setProperty("class", "HintText")

        layout.addWidget(lbl_t)
        layout.addWidget(lbl_v)
        layout.addWidget(lbl_s)
        return card, lbl_v

    def _filter_feature_cards(self, text: str):
        query = text.strip().lower()
        for card, searchable in self.feature_widgets:
            card.setVisible(query == "" or query in searchable)

    def set_theme(self, dark_mode: bool):
        self.status_chart.set_theme(dark_mode)

    def refresh_data(self):
        metrics = self.controller.get_summary()
        self.val_total.setText(str(metrics["total"]))
        self.val_aktif.setText(str(metrics["aktif"]))
        self.val_inaktif.setText(str(metrics["inaktif"]))
        self.val_retensi.setText(str(metrics["peringatan_retensi"]))

        self.status_chart.set_values(metrics["aktif"], metrics["inaktif"])

        recent = self.controller.get_recent_files()
        self.table_recent.setRowCount(len(recent))
        for row_idx, item in enumerate(recent):
            self.table_recent.setItem(
                row_idx, 0, QTableWidgetItem(item["nama_file"])
            )
            self.table_recent.setItem(
                row_idx, 1, QTableWidgetItem(item["jalur_file"])
            )
            self.table_recent.setItem(
                row_idx, 2, QTableWidgetItem(item["aksi"])
            )
            self.table_recent.setItem(
                row_idx, 3, QTableWidgetItem(item["waktu"])
            )

        sess = self.controller.session
        host_status = " • Server Host Aktif" if self.controller.is_server_running() else ""
        sync_meta = self.controller.storage.get_sync_meta("last_sync_time", "Belum pernah")
        self.lbl_session_info.setText(
            f"Pengguna Aktif: {sess.nama_lengkap} (@{sess.username}) • "
            f"Status Kerja: {sess.mode_koneksi}{host_status} • "
            f"Terakhir Sinkronisasi: {sync_meta}"
        )


class CatalogPage(QWidget):
    """
    Halaman Katalog Arsip Interaktif:
    - Pencarian real-time
    - Filter topik, status, peringatan retensi, dan rentang tanggal berakhir
    - Reset filter instan
    - Pengurutan kolom interaktif
    - Tambah, Ubah, Hapus, dan Pintasan Ekspor Hasil Filter
    """

    export_filtered_requested = Signal()

    def __init__(self, controller: ArsiptaController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.dark_mode = False
        self._setup_ui()
        self.reload_topics()
        self.apply_filters()
        self.controller.data_updated.connect(self._on_data_changed)

    def set_theme(self, dark_mode: bool):
        self.dark_mode = dark_mode
        self.chk_date_range.set_theme(dark_mode)
        self.apply_filters()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(14)

        top_row = QHBoxLayout()
        title_col = QVBoxLayout()
        lbl_title = QLabel("Katalog Arsip Perjanjian")
        lbl_title.setProperty("class", "TitleLarge")
        lbl_sub = QLabel(
            "Cari secara real-time, saring kategori, urutkan kolom, "
            "dan kelola catatan perjanjian."
        )
        lbl_sub.setProperty("class", "MutedText")
        title_col.addWidget(lbl_title)
        title_col.addWidget(lbl_sub)

        btn_export_quick = QPushButton("Ekspor Hasil Filter")
        btn_export_quick.setProperty("class", "SecondaryButton")
        btn_export_quick.setCursor(Qt.PointingHandCursor)
        btn_export_quick.clicked.connect(self.export_filtered_requested.emit)

        btn_add = QPushButton("+ Tambah Arsip")
        btn_add.setProperty("class", "PrimaryButton")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.clicked.connect(self._open_add_dialog)

        btn_edit = QPushButton("Ubah Terpilih")
        btn_edit.setProperty("class", "SecondaryButton")
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.clicked.connect(self._open_edit_dialog)

        btn_delete = QPushButton("Hapus Terpilih")
        btn_delete.setProperty("class", "DangerButton")
        btn_delete.setCursor(Qt.PointingHandCursor)
        btn_delete.clicked.connect(self._delete_selected)

        top_row.addLayout(title_col)
        top_row.addStretch()
        top_row.addWidget(btn_export_quick)
        top_row.addWidget(btn_add)
        top_row.addWidget(btn_edit)
        top_row.addWidget(btn_delete)
        layout.addLayout(top_row)

        filter_card = QFrame()
        filter_card.setProperty("class", "Card")
        f_layout = QVBoxLayout(filter_card)
        f_layout.setContentsMargins(16, 14, 16, 14)
        f_layout.setSpacing(10)

        row1 = QHBoxLayout()
        row1.setSpacing(10)

        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText(
            "Pencarian real-time (No. Dokumen, Judul, Pihak, Lokasi)..."
        )
        self.input_search.textChanged.connect(self.apply_filters)

        self.combo_topik = QComboBox()
        self.combo_topik.setMinimumWidth(180)
        self.combo_topik.currentIndexChanged.connect(self.apply_filters)

        self.combo_status = QComboBox()
        self.combo_status.addItems(["Semua Status", "Aktif", "Inaktif"])
        self.combo_status.setMinimumWidth(130)
        self.combo_status.currentIndexChanged.connect(self.apply_filters)

        self.combo_retensi = QComboBox()
        self.combo_retensi.addItems([
            "Semua Retensi",
            "Perlu Perhatian",
            "Kedaluwarsa",
            "Kritis (<= 30 Hari)",
            "Perhatian (<= 90 Hari)",
            "Aman"
        ])
        self.combo_retensi.setMinimumWidth(175)
        self.combo_retensi.currentIndexChanged.connect(self.apply_filters)

        row1.addWidget(self.input_search, stretch=2)
        row1.addWidget(self.combo_topik)
        row1.addWidget(self.combo_status)
        row1.addWidget(self.combo_retensi)
        f_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(10)

        self.chk_date_range = VisibleCheckBox(
            "Aktifkan Filter Rentang Tanggal Berakhir:"
        )
        self.chk_date_range.toggled.connect(self._toggle_date_inputs)

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.setDate(QDate.currentDate().addYears(-2))
        self.date_from.setEnabled(False)
        self.date_from.dateChanged.connect(self.apply_filters)

        lbl_sd = QLabel("s.d.")
        lbl_sd.setProperty("class", "MutedText")

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setDate(QDate.currentDate().addYears(2))
        self.date_to.setEnabled(False)
        self.date_to.dateChanged.connect(self.apply_filters)

        btn_reset = QPushButton("Reset Filter")
        btn_reset.setProperty("class", "SecondaryButton")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.clicked.connect(self.reset_filters)

        self.lbl_count = QLabel("Menampilkan 0 dari 0 arsip")
        self.lbl_count.setProperty("class", "MutedText")

        row2.addWidget(self.chk_date_range)
        row2.addWidget(self.date_from)
        row2.addWidget(lbl_sd)
        row2.addWidget(self.date_to)
        row2.addWidget(btn_reset)
        row2.addStretch()
        row2.addWidget(self.lbl_count)
        f_layout.addLayout(row2)

        layout.addWidget(filter_card)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "No. Dokumen",
            "Judul Perjanjian",
            "Pihak Terkait",
            "Topik",
            "Tgl Mulai",
            "Tgl Berakhir",
            "Status",
            "Peringatan Retensi",
            "Lokasi Fisik"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.setShowGrid(False)
        self.table.doubleClicked.connect(self._open_edit_dialog)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)

        layout.addWidget(self.table)

    def _toggle_date_inputs(self, checked: bool):
        self.date_from.setEnabled(checked)
        self.date_to.setEnabled(checked)
        self.apply_filters()

    def reload_topics(self):
        current = self.combo_topik.currentText()
        self.combo_topik.blockSignals(True)
        self.combo_topik.clear()
        self.combo_topik.addItem("Semua Topik")
        self.combo_topik.addItems(self.controller.get_topics())
        idx = self.combo_topik.findText(current)
        if idx >= 0:
            self.combo_topik.setCurrentIndex(idx)
        self.combo_topik.blockSignals(False)

    def reset_filters(self):
        self.input_search.blockSignals(True)
        self.combo_topik.blockSignals(True)
        self.combo_status.blockSignals(True)
        self.combo_retensi.blockSignals(True)
        self.chk_date_range.blockSignals(True)

        self.input_search.clear()
        self.combo_topik.setCurrentIndex(0)
        self.combo_status.setCurrentIndex(0)
        self.combo_retensi.setCurrentIndex(0)
        self.chk_date_range.setChecked(False)
        self.chk_date_range.update()
        self.date_from.setEnabled(False)
        self.date_to.setEnabled(False)

        self.input_search.blockSignals(False)
        self.combo_topik.blockSignals(False)
        self.combo_status.blockSignals(False)
        self.combo_retensi.blockSignals(False)
        self.chk_date_range.blockSignals(False)

        self.apply_filters()

    def _on_data_changed(self):
        self.reload_topics()
        self.apply_filters()

    def apply_filters(self):
        criteria = FilterCriteria(
            search_text=self.input_search.text(),
            topik=self.combo_topik.currentText() or "Semua Topik",
            status=self.combo_status.currentText() or "Semua Status",
            retensi=self.combo_retensi.currentText() or "Semua Retensi",
            use_date_range=self.chk_date_range.isChecked(),
            date_from=self.date_from.date().toString("yyyy-MM-dd"),
            date_to=self.date_to.date().toString("yyyy-MM-dd")
        )
        filtered, total_all = self.controller.search_archives(criteria)
        self.lbl_count.setText(
            f"Menampilkan {len(filtered)} dari {total_all} arsip "
            "(Klik judul kolom untuk mengurutkan)"
        )
        self._populate_table(filtered)

    def _populate_table(self, records: List[ArchiveRecord]):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(records))

        for row_idx, rec in enumerate(records):
            item_nomor = SortableTableItem(rec.nomor_dokumen)
            item_nomor.setData(Qt.UserRole, rec.id)

            item_judul = SortableTableItem(rec.judul_perjanjian)
            item_pihak = SortableTableItem(rec.pihak_terkait)
            item_topik = SortableTableItem(rec.topik)
            item_mulai = SortableTableItem(rec.tanggal_mulai, rec.tanggal_mulai)
            item_akhir = SortableTableItem(
                rec.tanggal_berakhir, rec.tanggal_berakhir
            )

            item_status = SortableTableItem(rec.status)
            if rec.status.lower() == "aktif":
                item_status.setForeground(
                    QColor("#34D399" if self.dark_mode else "#059669")
                )
            else:
                item_status.setForeground(
                    QColor("#94A3B8" if self.dark_mode else "#64748B")
                )

            ret_text, urgency, delta_days = (
                ArchiveProcessingEngine.format_retention_label(rec)
            )
            item_retensi = SortableTableItem(ret_text, delta_days)
            if urgency == "danger":
                item_retensi.setForeground(
                    QColor("#F87171" if self.dark_mode else "#DC2626")
                )
            elif urgency == "warning":
                item_retensi.setForeground(
                    QColor("#FBBF24" if self.dark_mode else "#D97706")
                )
            elif urgency == "safe":
                item_retensi.setForeground(
                    QColor("#34D399" if self.dark_mode else "#059669")
                )

            item_lokasi = SortableTableItem(rec.lokasi_fisik)

            self.table.setItem(row_idx, 0, item_nomor)
            self.table.setItem(row_idx, 1, item_judul)
            self.table.setItem(row_idx, 2, item_pihak)
            self.table.setItem(row_idx, 3, item_topik)
            self.table.setItem(row_idx, 4, item_mulai)
            self.table.setItem(row_idx, 5, item_akhir)
            self.table.setItem(row_idx, 6, item_status)
            self.table.setItem(row_idx, 7, item_retensi)
            self.table.setItem(row_idx, 8, item_lokasi)

        self.table.setSortingEnabled(True)

    def _get_selected_archive_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        return item.data(Qt.UserRole)

    def _open_add_dialog(self):
        dlg = ArchiveFormDialog(self.controller, self.dark_mode, None, self)
        dlg.exec()

    def _open_edit_dialog(self):
        archive_id = self._get_selected_archive_id()
        if archive_id is None:
            QMessageBox.information(
                self,
                "Pilih Arsip",
                "Silakan pilih satu baris arsip pada tabel terlebih dahulu."
            )
            return
        record = self.controller.get_archive_by_id(archive_id)
        if not record:
            QMessageBox.warning(self, "Galat", "Data arsip tidak ditemukan.")
            return
        dlg = ArchiveFormDialog(self.controller, self.dark_mode, record, self)
        dlg.exec()

    def _delete_selected(self):
        archive_id = self._get_selected_archive_id()
        if archive_id is None:
            QMessageBox.information(
                self,
                "Pilih Arsip",
                "Silakan pilih baris arsip yang ingin dihapus."
            )
            return
        record = self.controller.get_archive_by_id(archive_id)
        if not record:
            return

        reply = QMessageBox.question(
            self,
            "Konfirmasi Hapus Arsip",
            f"Apakah Anda yakin ingin menghapus arsip:\n"
            f"{record.nomor_dokumen} - {record.judul_perjanjian}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            ok, msg = self.controller.remove_archive(archive_id)
            if ok:
                QMessageBox.information(self, "Terhapus", msg)
            else:
                QMessageBox.warning(self, "Gagal Menghapus", msg)


class RetentionPage(QWidget):
    """Halaman Pemantauan Masa Retensi Arsip."""

    def __init__(self, controller: ArsiptaController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.dark_mode = False
        self._setup_ui()
        self.refresh_data()
        self.controller.data_updated.connect(self.refresh_data)

    def set_theme(self, dark_mode: bool):
        self.dark_mode = dark_mode
        self.refresh_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(16)

        top_row = QHBoxLayout()
        title_col = QVBoxLayout()
        lbl_title = QLabel("Pemantauan Masa Retensi Perjanjian")
        lbl_title.setProperty("class", "TitleLarge")
        lbl_sub = QLabel(
            "Daftar perjanjian aktif yang mendekati berakhir atau telah "
            "melewati batas waktu (diurutkan dari paling mendesak)."
        )
        lbl_sub.setProperty("class", "MutedText")
        title_col.addWidget(lbl_title)
        title_col.addWidget(lbl_sub)

        btn_extend = QPushButton("Perpanjang / Ubah Tanggal")
        btn_extend.setProperty("class", "PrimaryButton")
        btn_extend.setCursor(Qt.PointingHandCursor)
        btn_extend.clicked.connect(self._extend_selected)

        btn_inactivate = QPushButton("Set Status Inaktif")
        btn_inactivate.setProperty("class", "SecondaryButton")
        btn_inactivate.setCursor(Qt.PointingHandCursor)
        btn_inactivate.clicked.connect(self._inactivate_selected)

        top_row.addLayout(title_col)
        top_row.addStretch()
        top_row.addWidget(btn_extend)
        top_row.addWidget(btn_inactivate)
        layout.addLayout(top_row)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(14)

        self.card_exp, self.val_exp = self._make_urgency_card(
            "Sudah Kedaluwarsa", "0", "Melewati tanggal berakhir"
        )
        self.card_crit, self.val_crit = self._make_urgency_card(
            "Kritis (<= 30 Hari)", "0", "Segera butuh adendum / penutupan"
        )
        self.card_warn, self.val_warn = self._make_urgency_card(
            "Perhatian (<= 90 Hari)", "0", "Jadwalkan evaluasi perjanjian"
        )

        cards_row.addWidget(self.card_exp)
        cards_row.addWidget(self.card_crit)
        cards_row.addWidget(self.card_warn)
        layout.addLayout(cards_row)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Tingkat Peringatan",
            "Sisa Waktu",
            "No. Dokumen",
            "Judul Perjanjian",
            "Pihak Terkait",
            "Tanggal Berakhir",
            "Lokasi Fisik"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._extend_selected)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)

        layout.addWidget(self.table)

    def _make_urgency_card(
        self, title: str, initial: str, desc: str
    ) -> Tuple[QFrame, QLabel]:
        card = QFrame()
        card.setProperty("class", "Card")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(16, 14, 16, 14)
        c_layout.setSpacing(4)

        lbl_t = QLabel(title)
        lbl_t.setProperty("class", "MutedText")
        lbl_v = QLabel(initial)
        lbl_v.setProperty("class", "MetricValue")
        lbl_d = QLabel(desc)
        lbl_d.setProperty("class", "HintText")

        c_layout.addWidget(lbl_t)
        c_layout.addWidget(lbl_v)
        c_layout.addWidget(lbl_d)
        return card, lbl_v

    def refresh_data(self):
        watchlist = self.controller.get_retention_watchlist()

        count_exp = sum(1 for _, kat, _ in watchlist if kat == "Kedaluwarsa")
        count_crit = sum(
            1 for _, kat, _ in watchlist if kat == "Kritis (<= 30 Hari)"
        )
        count_warn = sum(
            1 for _, kat, _ in watchlist if kat == "Perhatian (<= 90 Hari)"
        )

        self.val_exp.setText(str(count_exp))
        self.val_crit.setText(str(count_crit))
        self.val_warn.setText(str(count_warn))

        self.table.setRowCount(len(watchlist))
        for row_idx, (rec, kategori, delta) in enumerate(watchlist):
            item_kat = QTableWidgetItem(kategori)
            item_kat.setData(Qt.UserRole, rec.id)

            if kategori in ("Kedaluwarsa", "Kritis (<= 30 Hari)"):
                item_kat.setForeground(
                    QColor("#F87171" if self.dark_mode else "#DC2626")
                )
            else:
                item_kat.setForeground(
                    QColor("#FBBF24" if self.dark_mode else "#D97706")
                )

            sisa_str = (
                f"Lewat {abs(delta)} hari"
                if delta < 0
                else f"Sisa {delta} hari"
            )
            self.table.setItem(row_idx, 0, item_kat)
            self.table.setItem(row_idx, 1, QTableWidgetItem(sisa_str))
            self.table.setItem(row_idx, 2, QTableWidgetItem(rec.nomor_dokumen))
            self.table.setItem(
                row_idx, 3, QTableWidgetItem(rec.judul_perjanjian)
            )
            self.table.setItem(row_idx, 4, QTableWidgetItem(rec.pihak_terkait))
            self.table.setItem(
                row_idx, 5, QTableWidgetItem(rec.tanggal_berakhir)
            )
            self.table.setItem(row_idx, 6, QTableWidgetItem(rec.lokasi_fisik))

    def _get_selected_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _extend_selected(self):
        archive_id = self._get_selected_id()
        if archive_id is None:
            QMessageBox.information(
                self,
                "Pilih Dokumen",
                "Pilih salah satu baris perjanjian pada daftar peringatan."
            )
            return
        rec = self.controller.get_archive_by_id(archive_id)
        if rec:
            dlg = ArchiveFormDialog(self.controller, self.dark_mode, rec, self)
            dlg.exec()

    def _inactivate_selected(self):
        archive_id = self._get_selected_id()
        if archive_id is None:
            QMessageBox.information(
                self,
                "Pilih Dokumen",
                "Pilih perjanjian yang akan diubah statusnya menjadi Inaktif."
            )
            return
        rec = self.controller.get_archive_by_id(archive_id)
        if not rec:
            return

        reply = QMessageBox.question(
            self,
            "Alih Status ke Arsip Inaktif",
            f"Ubah status '{rec.nomor_dokumen}' menjadi Inaktif?\n"
            "Dokumen akan tetap tersimpan di katalog dan keluar dari daftar "
            "peringatan aktif.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            ok, msg = self.controller.set_archive_status(archive_id, "Inaktif")
            if ok:
                QMessageBox.information(self, "Status Diperbarui", msg)


class ImportExportPage(QWidget):
    """
    Halaman Impor & Ekspor Excel / CSV (Fase 3):
    - Impor file .xlsx / .csv tanpa mengubah file sumber asli
    - Pemilihan kebijakan duplikat (Lewati vs Perbarui)
    - Pembuatan template impor Excel/CSV sesuai kebutuhan pengguna
    - Ekspor seluruh katalog atau hanya hasil filter aktif ke .xlsx / .csv
    """

    def __init__(self, controller: ArsiptaController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.dark_mode = False
        self.worker: Optional[SpreadsheetJobWorker] = None
        self._setup_ui()
        self.refresh_counts()
        self.controller.data_updated.connect(self.refresh_counts)

    def set_theme(self, dark_mode: bool):
        self.dark_mode = dark_mode
        self.radio_dup_skip.set_theme(dark_mode)
        self.radio_dup_update.set_theme(dark_mode)
        self.radio_exp_all.set_theme(dark_mode)
        self.radio_exp_filtered.set_theme(dark_mode)

    def _setup_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        container.setObjectName("ScrollContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(18)

        lbl_title = QLabel("Impor & Ekspor Data Excel / CSV")
        lbl_title.setProperty("class", "TitleLarge")
        lbl_sub = QLabel(
            "Migrasikan daftar Excel lama ke katalog ARSIPTA secara aman "
            "atau unduh laporan siap cetak."
        )
        lbl_sub.setProperty("class", "MutedText")
        layout.addWidget(lbl_title)
        layout.addWidget(lbl_sub)

        # Grid 2 Kolom: Kartu Impor & Kartu Ekspor
        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)

        # --- KARTU 1: IMPOR ---
        import_card = QFrame()
        import_card.setProperty("class", "Card")
        imp_layout = QVBoxLayout(import_card)
        imp_layout.setContentsMargins(20, 18, 20, 18)
        imp_layout.setSpacing(12)

        imp_title = QLabel("1. Impor dari Excel (.xlsx) atau CSV (.csv)")
        imp_title.setProperty("class", "SectionTitle")
        imp_desc = QLabel(
            "Sistem akan menyalin file ke area kerja sementara terlebih dahulu "
            "sehingga file Excel asli Anda tidak pernah berubah atau terkunci."
        )
        imp_desc.setProperty("class", "MutedText")
        imp_desc.setWordWrap(True)

        self.radio_dup_skip = VisibleRadioButton(
            "Lewati jika Nomor Dokumen sudah ada"
        )
        self.radio_dup_update = VisibleRadioButton(
            "Perbarui data jika Nomor Dokumen sudah ada"
        )
        self.radio_dup_skip.setChecked(True)

        dup_group = QButtonGroup(self)
        dup_group.addButton(self.radio_dup_skip)
        dup_group.addButton(self.radio_dup_update)

        imp_btn_row = QHBoxLayout()
        self.btn_import = QPushButton("Pilih File & Mulai Impor...")
        self.btn_import.setProperty("class", "PrimaryButton")
        self.btn_import.setCursor(Qt.PointingHandCursor)
        self.btn_import.clicked.connect(self._start_import_dialog)

        self.btn_template = QPushButton("Buat Template Excel (.xlsx)")
        self.btn_template.setProperty("class", "SecondaryButton")
        self.btn_template.setCursor(Qt.PointingHandCursor)
        self.btn_template.clicked.connect(self._create_template_dialog)

        imp_btn_row.addWidget(self.btn_import)
        imp_btn_row.addWidget(self.btn_template)

        imp_layout.addWidget(imp_title)
        imp_layout.addWidget(imp_desc)
        imp_layout.addWidget(self.radio_dup_skip)
        imp_layout.addWidget(self.radio_dup_update)
        imp_layout.addSpacing(4)
        imp_layout.addLayout(imp_btn_row)
        imp_layout.addStretch()

        # --- KARTU 2: EKSPOR ---
        export_card = QFrame()
        export_card.setProperty("class", "Card")
        exp_layout = QVBoxLayout(export_card)
        exp_layout.setContentsMargins(20, 18, 20, 18)
        exp_layout.setSpacing(12)

        exp_title = QLabel("2. Ekspor Laporan Katalog")
        exp_title.setProperty("class", "SectionTitle")
        exp_desc = QLabel(
            "Unduh daftar katalog lengkap beserta perhitungan status retensi "
            "terbaru dalam format Microsoft Excel atau CSV."
        )
        exp_desc.setProperty("class", "MutedText")
        exp_desc.setWordWrap(True)

        self.radio_exp_all = VisibleRadioButton("Seluruh Katalog Arsip (0 dokumen)")
        self.radio_exp_filtered = VisibleRadioButton(
            "Hanya Hasil Filter Aktif di Katalog (0 dokumen)"
        )
        self.radio_exp_all.setChecked(True)

        exp_group = QButtonGroup(self)
        exp_group.addButton(self.radio_exp_all)
        exp_group.addButton(self.radio_exp_filtered)

        exp_btn_row = QHBoxLayout()
        self.btn_export_xlsx = QPushButton("Ekspor ke Excel (.xlsx)")
        self.btn_export_xlsx.setProperty("class", "PrimaryButton")
        self.btn_export_xlsx.setCursor(Qt.PointingHandCursor)
        self.btn_export_xlsx.clicked.connect(
            lambda: self._start_export_dialog("xlsx")
        )

        self.btn_export_csv = QPushButton("Ekspor ke CSV (.csv)")
        self.btn_export_csv.setProperty("class", "SecondaryButton")
        self.btn_export_csv.setCursor(Qt.PointingHandCursor)
        self.btn_export_csv.clicked.connect(
            lambda: self._start_export_dialog("csv")
        )

        exp_btn_row.addWidget(self.btn_export_xlsx)
        exp_btn_row.addWidget(self.btn_export_csv)

        exp_layout.addWidget(exp_title)
        exp_layout.addWidget(exp_desc)
        exp_layout.addWidget(self.radio_exp_all)
        exp_layout.addWidget(self.radio_exp_filtered)
        exp_layout.addSpacing(4)
        exp_layout.addLayout(exp_btn_row)
        exp_layout.addStretch()

        cards_row.addWidget(import_card, stretch=1)
        cards_row.addWidget(export_card, stretch=1)
        layout.addLayout(cards_row)

        # Panel Status Proses & Log Hasil
        log_card = QFrame()
        log_card.setProperty("class", "Card")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(20, 16, 20, 16)
        log_layout.setSpacing(10)

        log_title = QLabel("Status Pemrosesan & Ringkasan Hasil")
        log_title.setProperty("class", "SectionTitle")

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Siap memproses file")

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(130)
        self.log_output.setPlaceholderText(
            "Hasil impor atau ekspor file akan ditampilkan di sini..."
        )

        log_layout.addWidget(log_title)
        log_layout.addWidget(self.progress_bar)
        log_layout.addWidget(self.log_output)
        layout.addWidget(log_card)

        layout.addStretch()
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def refresh_counts(self):
        all_count = len(self.controller.get_archives())
        filtered_count = len(self.controller.get_filtered_archives_snapshot())
        self.radio_exp_all.setText(
            f"Seluruh Katalog Arsip ({all_count} dokumen)"
        )
        self.radio_exp_filtered.setText(
            f"Hanya Hasil Filter Aktif di Katalog ({filtered_count} dokumen)"
        )
        self.radio_exp_all.update()
        self.radio_exp_filtered.update()

    def select_filtered_export_mode(self):
        self.refresh_counts()
        self.radio_exp_filtered.setChecked(True)
        self.radio_exp_filtered.update()

    def _set_controls_enabled(self, enabled: bool):
        self.btn_import.setEnabled(enabled)
        self.btn_template.setEnabled(enabled)
        self.btn_export_xlsx.setEnabled(enabled)
        self.btn_export_csv.setEnabled(enabled)

    def _create_template_dialog(self):
        default_name = "Template_Katalog_ARSIPTA.xlsx"
        dest_path, _ = QFileDialog.getSaveFileName(
            self,
            "Simpan Template Impor Excel",
            default_name,
            "File Excel (*.xlsx);;File CSV (*.csv)"
        )
        if not dest_path:
            return
        ok, msg = SpreadsheetIOEngine.generate_sample_template(dest_path)
        if ok:
            self.log_output.setPlainText(msg)
            QMessageBox.information(self, "Template Dibuat", msg)
        else:
            QMessageBox.warning(self, "Gagal", msg)

    def _start_import_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Pilih File Excel atau CSV untuk Diimpor",
            "",
            "Spreadsheet (*.xlsx *.csv);;File Excel (*.xlsx);;File CSV (*.csv)"
        )
        if not file_path:
            return

        self._set_controls_enabled(False)
        self.progress_bar.setValue(5)
        self.progress_bar.setFormat("Memulai impor...")
        self.log_output.setPlainText(f"Memproses file: {file_path}\n...")

        self.worker = SpreadsheetJobWorker(
            mode="import",
            db_path=self.controller.storage.db_path,
            file_path=file_path,
            update_existing=self.radio_dup_update.isChecked()
        )
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.finished_job.connect(self._on_worker_finished)
        self.worker.start()

    def _start_export_dialog(self, fmt: str):
        if self.radio_exp_filtered.isChecked():
            records = self.controller.get_filtered_archives_snapshot()
        else:
            records = self.controller.get_archives()

        if not records:
            QMessageBox.information(
                self,
                "Data Kosong",
                "Tidak ada catatan arsip untuk diekspor pada pilihan saat ini."
            )
            return

        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        default_name = f"Laporan_Katalog_ARSIPTA_{stamp}.{fmt}"
        filter_str = (
            "File Excel (*.xlsx)" if fmt == "xlsx" else "File CSV (*.csv)"
        )
        dest_path, _ = QFileDialog.getSaveFileName(
            self,
            "Simpan Laporan Katalog",
            default_name,
            filter_str
        )
        if not dest_path:
            return

        self._set_controls_enabled(False)
        self.progress_bar.setValue(10)
        self.progress_bar.setFormat("Menyiapkan ekspor...")

        self.worker = SpreadsheetJobWorker(
            mode="export",
            db_path=self.controller.storage.db_path,
            file_path=dest_path,
            records_to_export=records
        )
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.finished_job.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_progress(self, pct: int, text: str):
        self.progress_bar.setValue(pct)
        self.progress_bar.setFormat(f"{text} ({pct}%)")

    def _on_worker_finished(self, ok: bool, msg: str, meta: dict):
        self._set_controls_enabled(True)
        self.progress_bar.setValue(100 if ok else 0)
        self.progress_bar.setFormat("Selesai" if ok else "Gagal")

        lines = [msg]
        warnings = meta.get("warnings", [])
        if warnings:
            lines.append("\nCatatan Baris:")
            lines.extend(warnings[:15])
        self.log_output.setPlainText("\n".join(lines))

        if ok:
            self.controller.data_updated.emit()
            QMessageBox.information(self, "Proses Selesai", msg)
        else:
            QMessageBox.warning(self, "Terjadi Kesalahan", msg)


class ServerSyncPage(QWidget):
    """
    Halaman Sinkronisasi Server Kantor & Server Mandiri (Hybrid).
    Menghubungkan klien staf arsiparis ke server kantor atau
    menjadikan komputer ini sebagai host server mandiri.
    """

    def __init__(self, controller: ArsiptaController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.dark_mode = False
        self._setup_ui()
        self.refresh_data()
        self.controller.data_updated.connect(self.refresh_data)
        self.controller.server_status_changed.connect(self._on_server_status_changed)
        self.controller.sync_finished.connect(self._on_sync_finished)

    def _setup_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        container.setObjectName("ScrollContainer")
        self.main_layout = QVBoxLayout(container)
        self.main_layout.setContentsMargins(28, 24, 28, 24)
        self.main_layout.setSpacing(16)

        # Header Halaman
        header_box = QVBoxLayout()
        header_box.setSpacing(4)
        lbl_title = QLabel("Sinkronisasi Server Kantor & Server Mandiri (Hybrid)")
        lbl_title.setProperty("class", "TitleLarge")
        lbl_desc = QLabel(
            "Hubungkan beberapa komputer staf ke satu basis data arsip yang sama secara aman di jaringan kantor."
        )
        lbl_desc.setProperty("class", "MutedText")
        header_box.addWidget(lbl_title)
        header_box.addWidget(lbl_desc)
        self.main_layout.addLayout(header_box)

        # Banner Ringkasan Status
        self.banner_card = QFrame()
        self.banner_card.setProperty("class", "Card")
        b_layout = QGridLayout(self.banner_card)
        b_layout.setContentsMargins(18, 14, 18, 14)
        b_layout.setSpacing(10)

        lbl_t_mode = QLabel("Mode Kerja Klien")
        lbl_t_mode.setProperty("class", "HintText")
        self.lbl_b_mode = QLabel()
        self.lbl_b_mode.setStyleSheet("font-weight: 600; font-size: 13px;")

        lbl_t_url = QLabel("Alamat Server Terhubung")
        lbl_t_url.setProperty("class", "HintText")
        self.lbl_b_url = QLabel()
        self.lbl_b_url.setStyleSheet("font-weight: 600; font-size: 13px;")

        lbl_t_host = QLabel("Server Mandiri di PC Ini")
        lbl_t_host.setProperty("class", "HintText")
        self.lbl_b_host = QLabel()
        self.lbl_b_host.setStyleSheet("font-weight: 600; font-size: 13px;")

        lbl_t_sync = QLabel("Terakhir Sinkronisasi")
        lbl_t_sync.setProperty("class", "HintText")
        self.lbl_b_sync = QLabel()
        self.lbl_b_sync.setStyleSheet("font-weight: 600; font-size: 13px;")

        b_layout.addWidget(lbl_t_mode, 0, 0)
        b_layout.addWidget(self.lbl_b_mode, 1, 0)
        b_layout.addWidget(lbl_t_url, 0, 1)
        b_layout.addWidget(self.lbl_b_url, 1, 1)
        b_layout.addWidget(lbl_t_host, 0, 2)
        b_layout.addWidget(self.lbl_b_host, 1, 2)
        b_layout.addWidget(lbl_t_sync, 0, 3)
        b_layout.addWidget(self.lbl_b_sync, 1, 3)

        self.main_layout.addWidget(self.banner_card)

        # Tab Switcher (Klien vs Server Host)
        tab_buttons_row = QHBoxLayout()
        self.btn_tab_client = QPushButton("💻 Klien Sinkronisasi Tim")
        self.btn_tab_server = QPushButton("🏢 Server Mandiri (Pusat Data Host)")
        self.btn_tab_client.setCursor(Qt.PointingHandCursor)
        self.btn_tab_server.setCursor(Qt.PointingHandCursor)
        self.btn_tab_client.clicked.connect(lambda: self.switch_tab(0))
        self.btn_tab_server.clicked.connect(lambda: self.switch_tab(1))

        tab_buttons_row.addWidget(self.btn_tab_client)
        tab_buttons_row.addWidget(self.btn_tab_server)
        tab_buttons_row.addStretch()
        self.main_layout.addLayout(tab_buttons_row)

        self.tab_stack = QStackedWidget()
        self.page_client = self._create_client_panel()
        self.page_server = self._create_server_panel()
        self.tab_stack.addWidget(self.page_client)
        self.tab_stack.addWidget(self.page_server)
        self.main_layout.addWidget(self.tab_stack)

        scroll.setWidget(container)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        self.switch_tab(0)

    def _create_metric_tile(self, label: str) -> Tuple[QFrame, QLabel]:
        tile = QFrame()
        tile.setProperty("class", "SubtleBox")
        t_layout = QVBoxLayout(tile)
        t_layout.setContentsMargins(12, 10, 12, 10)
        t_layout.setSpacing(4)
        lbl_sub = QLabel(label)
        lbl_sub.setProperty("class", "HintText")
        val_lbl = QLabel("0")
        val_lbl.setProperty("class", "MetricValue")
        t_layout.addWidget(lbl_sub)
        t_layout.addWidget(val_lbl)
        return tile, val_lbl

    def _create_client_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # Kartu Pengaturan Koneksi
        conn_card = QFrame()
        conn_card.setProperty("class", "Card")
        cc_layout = QVBoxLayout(conn_card)
        cc_layout.setContentsMargins(18, 16, 18, 16)
        cc_layout.setSpacing(10)

        lbl_conn_title = QLabel("Pengaturan Koneksi ke Server Kantor")
        lbl_conn_title.setProperty("class", "SectionTitle")
        cc_layout.addWidget(lbl_conn_title)

        form = QFormLayout()
        form.setSpacing(8)
        self.input_client_url = QLineEdit(self.controller.session.server_url or "http://localhost:8080")
        self.input_client_url.setPlaceholderText("Contoh: http://192.168.1.100:8080")

        self.input_client_token = QLineEdit(self.controller.server_token)
        self.input_client_token.setEchoMode(QLineEdit.Password)
        self.input_client_token.setPlaceholderText("Token rahasia server")

        form.addRow("URL Server:", self.input_client_url)
        form.addRow("Token Akses Tim:", self.input_client_token)
        cc_layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.btn_test_conn = QPushButton("Uji Koneksi Server")
        self.btn_test_conn.setProperty("class", "SecondaryButton")
        self.btn_test_conn.setCursor(Qt.PointingHandCursor)
        self.btn_test_conn.clicked.connect(self._handle_test_connection)

        self.btn_preset_local = QPushButton("Gunakan Localhost (8080)")
        self.btn_preset_local.setProperty("class", "SecondaryButton")
        self.btn_preset_local.setCursor(Qt.PointingHandCursor)
        self.btn_preset_local.clicked.connect(lambda: self.input_client_url.setText("http://localhost:8080"))

        self.btn_apply_server_mode = QPushButton("Terapkan Mode Server Kantor")
        self.btn_apply_server_mode.setProperty("class", "PrimaryButton")
        self.btn_apply_server_mode.setCursor(Qt.PointingHandCursor)
        self.btn_apply_server_mode.clicked.connect(self._handle_apply_server_mode)

        btn_row.addWidget(self.btn_test_conn)
        btn_row.addWidget(self.btn_preset_local)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_apply_server_mode)
        cc_layout.addLayout(btn_row)

        self.lbl_client_feedback = QLabel()
        self.lbl_client_feedback.setProperty("class", "HintText")
        cc_layout.addWidget(self.lbl_client_feedback)
        layout.addWidget(conn_card)

        # Kartu Operasi Sinkronisasi
        sync_card = QFrame()
        sync_card.setProperty("class", "Card")
        sc_layout = QVBoxLayout(sync_card)
        sc_layout.setContentsMargins(18, 16, 18, 16)
        sc_layout.setSpacing(10)

        lbl_sync_op = QLabel("Aksi Sinkronisasi Data Arsip")
        lbl_sync_op.setProperty("class", "SectionTitle")
        sc_layout.addWidget(lbl_sync_op)

        actions_row = QHBoxLayout()
        self.btn_sync_two_way = QPushButton("🔄 Sinkronisasi Dua Arah (Penuh)")
        self.btn_sync_two_way.setProperty("class", "PrimaryButton")
        self.btn_sync_two_way.setCursor(Qt.PointingHandCursor)
        self.btn_sync_two_way.clicked.connect(lambda: self._start_sync("two_way"))

        self.btn_sync_pull = QPushButton("⬇ Tarik Data dari Server (Pull)")
        self.btn_sync_pull.setProperty("class", "SecondaryButton")
        self.btn_sync_pull.setCursor(Qt.PointingHandCursor)
        self.btn_sync_pull.clicked.connect(lambda: self._start_sync("pull"))

        self.btn_sync_push = QPushButton("⬆ Kirim Data ke Server (Push)")
        self.btn_sync_push.setProperty("class", "SecondaryButton")
        self.btn_sync_push.setCursor(Qt.PointingHandCursor)
        self.btn_sync_push.clicked.connect(lambda: self._start_sync("push"))

        actions_row.addWidget(self.btn_sync_two_way)
        actions_row.addWidget(self.btn_sync_pull)
        actions_row.addWidget(self.btn_sync_push)
        actions_row.addStretch()
        sc_layout.addLayout(actions_row)

        self.chk_auto_sync = VisibleCheckBox(
            "Otomatis sinkronisasi data arsip ke server saat menambah atau memperbarui arsip"
        )
        self.chk_auto_sync.setChecked(self.controller.auto_sync_enabled)
        self.chk_auto_sync.toggled.connect(self._toggle_auto_sync)
        sc_layout.addWidget(self.chk_auto_sync)

        self.progress_sync = QProgressBar()
        self.progress_sync.setVisible(False)
        self.lbl_sync_status = QLabel()
        self.lbl_sync_status.setProperty("class", "HintText")
        sc_layout.addWidget(self.progress_sync)
        sc_layout.addWidget(self.lbl_sync_status)

        layout.addWidget(sync_card)

        # Kartu Ringkasan & Riwayat Sinkronisasi
        history_card = QFrame()
        history_card.setProperty("class", "Card")
        hc_layout = QVBoxLayout(history_card)
        hc_layout.setContentsMargins(18, 16, 18, 16)
        hc_layout.setSpacing(10)

        lbl_hist_title = QLabel("Hasil & Riwayat Sinkronisasi")
        lbl_hist_title.setProperty("class", "SectionTitle")
        hc_layout.addWidget(lbl_hist_title)

        grid_metrics = QGridLayout()
        grid_metrics.setSpacing(10)
        self.tile_pushed, self.val_pushed = self._create_metric_tile("Arsip Dikirim")
        self.tile_pulled, self.val_pulled = self._create_metric_tile("Arsip Diterima")
        self.tile_updated, self.val_updated = self._create_metric_tile("Diperbarui Lokal")
        self.tile_conflicts, self.val_conflicts = self._create_metric_tile("Konflik Diselesaikan")

        grid_metrics.addWidget(self.tile_pushed, 0, 0)
        grid_metrics.addWidget(self.tile_pulled, 0, 1)
        grid_metrics.addWidget(self.tile_updated, 0, 2)
        grid_metrics.addWidget(self.tile_conflicts, 0, 3)
        hc_layout.addLayout(grid_metrics)

        self.txt_sync_log = QTextEdit()
        self.txt_sync_log.setReadOnly(True)
        self.txt_sync_log.setMaximumHeight(130)
        self.txt_sync_log.setPlaceholderText("Riwayat aktivitas sinkronisasi akan muncul di sini...")
        hc_layout.addWidget(self.txt_sync_log)

        layout.addWidget(history_card)
        return w

    def _create_server_panel(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # Kartu Kontrol Server
        ctrl_card = QFrame()
        ctrl_card.setProperty("class", "Card")
        cc_layout = QVBoxLayout(ctrl_card)
        cc_layout.setContentsMargins(18, 16, 18, 16)
        cc_layout.setSpacing(10)

        lbl_srv_title = QLabel("Kontrol Server Kantor Mandiri (Pusat Data Host)")
        lbl_srv_title.setProperty("class", "SectionTitle")
        cc_layout.addWidget(lbl_srv_title)

        form = QFormLayout()
        form.setSpacing(8)
        self.input_server_port = QLineEdit(str(DEFAULT_SERVER_PORT))
        self.input_server_port.setFixedWidth(120)

        token_row = QHBoxLayout()
        self.input_server_token = QLineEdit(self.controller.server_token)
        self.btn_gen_token = QPushButton("Acak Token Baru")
        self.btn_gen_token.setProperty("class", "SecondaryButton")
        self.btn_gen_token.clicked.connect(self._generate_random_token)
        token_row.addWidget(self.input_server_token)
        token_row.addWidget(self.btn_gen_token)

        form.addRow("Port Server:", self.input_server_port)
        form.addRow("Token Akses Tim:", token_row)
        cc_layout.addLayout(form)

        row_toggle = QHBoxLayout()
        self.btn_toggle_server = QPushButton("🚀 Jalankan Server Kantor")
        self.btn_toggle_server.setProperty("class", "PrimaryButton")
        self.btn_toggle_server.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_server.clicked.connect(self._toggle_server_host)

        self.lbl_server_host_badge = QLabel("○ Server Nonaktif")
        self.lbl_server_host_badge.setProperty("class", "StatusBadge")

        row_toggle.addWidget(self.btn_toggle_server)
        row_toggle.addWidget(self.lbl_server_host_badge)
        row_toggle.addStretch()
        cc_layout.addLayout(row_toggle)
        layout.addWidget(ctrl_card)

        # Kartu Alamat Jaringan & Panduan Rekan
        net_card = QFrame()
        net_card.setProperty("class", "Card")
        nc_layout = QVBoxLayout(net_card)
        nc_layout.setContentsMargins(18, 16, 18, 16)
        nc_layout.setSpacing(10)

        lbl_net_title = QLabel("Alamat Akses Jaringan Lokal (LAN / Wi-Fi)")
        lbl_net_title.setProperty("class", "SectionTitle")
        nc_layout.addWidget(lbl_net_title)

        self.lbl_hostname = QLabel()
        self.lbl_ip_addresses = QLabel()
        self.lbl_ip_addresses.setWordWrap(True)

        nc_layout.addWidget(self.lbl_hostname)
        nc_layout.addWidget(self.lbl_ip_addresses)

        btn_copy_row = QHBoxLayout()
        self.btn_copy_url = QPushButton("📋 Salin URL Server Utama")
        self.btn_copy_url.setProperty("class", "SecondaryButton")
        self.btn_copy_url.setCursor(Qt.PointingHandCursor)
        self.btn_copy_url.clicked.connect(self._copy_server_url)
        btn_copy_row.addWidget(self.btn_copy_url)
        btn_copy_row.addStretch()
        nc_layout.addLayout(btn_copy_row)

        guide_box = QFrame()
        guide_box.setProperty("class", "SubtleBox")
        gb_layout = QVBoxLayout(guide_box)
        gb_layout.setContentsMargins(12, 10, 12, 10)
        lbl_guide = QLabel(
            "Panduan untuk rekan arsiparis di komputer lain:\n"
            "1. Hubungkan komputer rekan ke jaringan Wi-Fi/LAN kantor yang sama.\n"
            "2. Buka ARSIPTA di laptop rekan, lalu masuk ke menu Sinkronisasi Server.\n"
            "3. Masukkan salah satu URL server di atas beserta Token Akses Tim.\n"
            "4. Klik 'Uji Koneksi Server', lalu lakukan 'Sinkronisasi Dua Arah'."
        )
        lbl_guide.setProperty("class", "MutedText")
        lbl_guide.setWordWrap(True)
        gb_layout.addWidget(lbl_guide)
        nc_layout.addWidget(guide_box)

        layout.addWidget(net_card)

        # Kartu Log Akses & Audit Real-time
        audit_card = QFrame()
        audit_card.setProperty("class", "Card")
        ac_layout = QVBoxLayout(audit_card)
        ac_layout.setContentsMargins(18, 16, 18, 16)
        ac_layout.setSpacing(10)

        row_audit_hdr = QHBoxLayout()
        lbl_audit_title = QLabel("Log Akses & Audit Server Real-time")
        lbl_audit_title.setProperty("class", "SectionTitle")
        self.btn_refresh_audit = QPushButton("🔄 Segarkan Log")
        self.btn_refresh_audit.setProperty("class", "SecondaryButton")
        self.btn_refresh_audit.clicked.connect(self._load_audit_logs)
        self.btn_clear_audit = QPushButton("🗑 Bersihkan Log")
        self.btn_clear_audit.setProperty("class", "SecondaryButton")
        self.btn_clear_audit.clicked.connect(self._clear_audit_logs)

        row_audit_hdr.addWidget(lbl_audit_title)
        row_audit_hdr.addStretch()
        row_audit_hdr.addWidget(self.btn_refresh_audit)
        row_audit_hdr.addWidget(self.btn_clear_audit)
        ac_layout.addLayout(row_audit_hdr)

        self.table_audit = QTableWidget(0, 5)
        self.table_audit.setHorizontalHeaderLabels([
            "Waktu", "IP Klien", "Pengguna", "Aksi", "Status"
        ])
        self.table_audit.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_audit.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_audit.setMaximumHeight(180)
        ac_layout.addWidget(self.table_audit)

        layout.addWidget(audit_card)
        return w

    def switch_tab(self, index: int):
        self.tab_stack.setCurrentIndex(index)
        self._update_tab_buttons(index)
        if index == 1:
            self._load_audit_logs()
            self._update_network_info()

    def _update_tab_buttons(self, active_index: int):
        self.btn_tab_client.setProperty("class", "PrimaryButton" if active_index == 0 else "SecondaryButton")
        self.btn_tab_server.setProperty("class", "PrimaryButton" if active_index == 1 else "SecondaryButton")
        self.btn_tab_client.style().unpolish(self.btn_tab_client)
        self.btn_tab_client.style().polish(self.btn_tab_client)
        self.btn_tab_server.style().unpolish(self.btn_tab_server)
        self.btn_tab_server.style().polish(self.btn_tab_server)

    def refresh_data(self):
        sess = self.controller.session
        self.lbl_b_mode.setText(sess.mode_koneksi)
        self.lbl_b_url.setText(sess.server_url or "Mode Lokal (Mandiri)")

        is_running = self.controller.is_server_running()
        port = self.input_server_port.text().strip() or str(DEFAULT_SERVER_PORT)
        if is_running:
            self.lbl_b_host.setText(f"● Aktif (Port {port})")
            self.lbl_b_host.setStyleSheet("color: #16A34A; font-weight: 600;")
            self.lbl_server_host_badge.setText(f"● Server Aktif (Port {port})")
            self.btn_toggle_server.setText("⏹ Hentikan Server Kantor")
            self.btn_toggle_server.setProperty("class", "DangerButton")
        else:
            self.lbl_b_host.setText("○ Nonaktif")
            self.lbl_b_host.setStyleSheet("color: #64748B; font-weight: 600;")
            self.lbl_server_host_badge.setText("○ Server Nonaktif")
            self.btn_toggle_server.setText("🚀 Jalankan Server Kantor")
            self.btn_toggle_server.setProperty("class", "PrimaryButton")

        self.btn_toggle_server.style().unpolish(self.btn_toggle_server)
        self.btn_toggle_server.style().polish(self.btn_toggle_server)

        last_sync = self.controller.storage.get_sync_meta("last_sync_time", "Belum pernah")
        self.lbl_b_sync.setText(last_sync)
        self._update_network_info()

        rep = self.controller.last_sync_report
        if rep:
            self.val_pushed.setText(str(rep.dikirim))
            self.val_pulled.setText(str(rep.diterima))
            self.val_updated.setText(str(rep.diperbarui_lokal))
            self.val_conflicts.setText(str(rep.konflik_diselesaikan))

    def _update_network_info(self):
        port = self.input_server_port.text().strip() or str(DEFAULT_SERVER_PORT)
        hostname = socket.gethostname()
        self.lbl_hostname.setText(f"Nama Host Komputer: {hostname}")

        ips = self.controller.get_local_ip_addresses()
        lines = [f"• http://{ip}:{port}" for ip in ips]
        lines.append(f"• http://localhost:{port}")
        self.lbl_ip_addresses.setText("URL Tersedia:\n" + "\n".join(lines))

    def _copy_server_url(self):
        port = self.input_server_port.text().strip() or str(DEFAULT_SERVER_PORT)
        ips = self.controller.get_local_ip_addresses()
        primary_ip = ips[0] if ips else "localhost"
        url = f"http://{primary_ip}:{port}"
        clipboard = QApplication.clipboard()
        clipboard.setText(url)
        QMessageBox.information(
            self,
            "URL Disalin",
            f"Alamat server berhasil disalin ke clipboard:\n{url}\n\n"
            "Bagikan URL ini kepada rekan arsiparis di kantor Anda."
        )

    def _generate_random_token(self):
        import secrets
        tok = "arsipta_" + secrets.token_hex(4)
        self.input_server_token.setText(tok)
        self.controller.server_token = tok

    def _toggle_server_host(self):
        if self.controller.is_server_running():
            ok, msg = self.controller.stop_office_server()
            if ok:
                self._append_log(f"[HOST] {msg}")
            else:
                QMessageBox.warning(self, "Gagal Menghentikan Server", msg)
        else:
            try:
                port = int(self.input_server_port.text().strip() or str(DEFAULT_SERVER_PORT))
            except ValueError:
                QMessageBox.warning(self, "Port Tidak Valid", "Port server harus berupa angka numerik.")
                return
            token = self.input_server_token.text().strip()
            ok, msg = self.controller.start_office_server(port=port, token=token)
            self._append_log(f"[HOST] {msg}")

    def _on_server_status_changed(self, is_running: bool, msg: str):
        self._append_log(f"[SERVER] {msg}")
        self.refresh_data()
        self._load_audit_logs()

    def _handle_test_connection(self):
        url = self.input_client_url.text().strip()
        if not url:
            QMessageBox.warning(self, "URL Kosong", "Masukkan alamat URL server kantor terlebih dahulu.")
            return
        ok, msg, data = self.controller.test_remote_server(url)
        if ok:
            name = data.get("server_name", "ARSIPTA Server")
            ver = data.get("version", "")
            tot = data.get("total_archives", 0)
            self.lbl_client_feedback.setText(f"✓ Terhubung ke {name} ({ver}) — {tot} arsip tersedia.")
            self.lbl_client_feedback.setStyleSheet("color: #16A34A; font-weight: 600;")
            self._append_log(f"[KONEKSI] Sukses terhubung ke {url} ({tot} arsip).")
        else:
            self.lbl_client_feedback.setText(f"✗ Gagal terhubung: {msg}")
            self.lbl_client_feedback.setStyleSheet("color: #DC2626; font-weight: 600;")
            self._append_log(f"[KONEKSI] Gagal terhubung ke {url}: {msg}")

    def _handle_apply_server_mode(self):
        url = self.input_client_url.text().strip()
        tok = self.input_client_token.text().strip()
        if not url:
            QMessageBox.warning(self, "URL Kosong", "Masukkan URL server kantor terlebih dahulu.")
            return
        self.controller.server_token = tok
        self.controller.session.mode_koneksi = "Mode Server Kantor"
        self.controller.session.server_url = url
        self.controller.session.server_token = tok
        self.controller.data_updated.emit()
        QMessageBox.information(
            self,
            "Mode Diterapkan",
            f"ARSIPTA kini berjalan dalam Mode Server Kantor terhubung ke:\n{url}"
        )
        self._append_log(f"[MODE] Beralih ke Mode Server Kantor: {url}")

    def _toggle_auto_sync(self, checked: bool):
        self.controller.auto_sync_enabled = checked
        status_txt = "diaktifkan" if checked else "dinonaktifkan"
        self._append_log(f"[PENGATURAN] Sinkronisasi otomatis {status_txt}.")

    def _start_sync(self, action: str):
        url = self.input_client_url.text().strip()
        if not url:
            QMessageBox.warning(self, "URL Kosong", "Masukkan URL server kantor terlebih dahulu.")
            return

        self.btn_sync_two_way.setEnabled(False)
        self.btn_sync_pull.setEnabled(False)
        self.btn_sync_push.setEnabled(False)
        self.progress_sync.setVisible(True)
        self.progress_sync.setValue(10)
        self.lbl_sync_status.setText("Memulai sinkronisasi...")
        self._append_log(f"[SYNC] Memulai sinkronisasi aksi '{action}'...")

        def _on_progress(val, text):
            self.progress_sync.setValue(val)
            self.lbl_sync_status.setText(text)

        def _on_finished(ok, msg, report):
            self.btn_sync_two_way.setEnabled(True)
            self.btn_sync_pull.setEnabled(True)
            self.btn_sync_push.setEnabled(True)
            self.progress_sync.setVisible(False)
            self.lbl_sync_status.setText(msg)
            self._append_log(f"[SYNC] {msg}")
            if ok:
                QMessageBox.information(self, "Sinkronisasi Berhasil", msg)
            else:
                QMessageBox.warning(self, "Sinkronisasi Terkendala", msg)

        self.controller.session.server_url = url
        self.controller.server_token = self.input_client_token.text().strip()
        self.controller.trigger_sync(action, on_progress=_on_progress, on_finished=_on_finished)

    def _on_sync_finished(self, ok: bool, msg: str, report: object):
        self.refresh_data()

    def _append_log(self, text: str):
        now = datetime.now().strftime("%H:%M:%S")
        self.txt_sync_log.append(f"[{now}] {text}")

    def _load_audit_logs(self):
        logs = self.controller.storage.get_server_audit_logs(limit=50)
        self.table_audit.setRowCount(len(logs))
        for row, l in enumerate(logs):
            self.table_audit.setItem(row, 0, QTableWidgetItem(l["waktu"]))
            self.table_audit.setItem(row, 1, QTableWidgetItem(l["client_ip"]))
            self.table_audit.setItem(row, 2, QTableWidgetItem(l["username"]))
            self.table_audit.setItem(row, 3, QTableWidgetItem(l["aksi"]))
            status_item = QTableWidgetItem(str(l["status_code"]))
            if l["status_code"] in (200, 201):
                status_item.setForeground(QColor("#16A34A"))
            else:
                status_item.setForeground(QColor("#DC2626"))
            self.table_audit.setItem(row, 4, status_item)

    def _clear_audit_logs(self):
        confirm = QMessageBox.question(
            self,
            "Bersihkan Log",
            "Apakah Anda yakin ingin menghapus seluruh catatan log audit server?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.controller.storage.clear_server_audit_logs()
            self._load_audit_logs()

    def set_theme(self, dark_mode: bool):
        self.dark_mode = dark_mode
        self.chk_auto_sync.set_theme(dark_mode)
        self._update_tab_buttons(self.tab_stack.currentIndex())


class MainWindow(QMainWindow):
    """Jendela Utama Aplikasi ARSIPTA."""

    def __init__(self, controller: ArsiptaController):
        super().__init__()
        self.controller = controller
        self.dark_mode = False

        self.setWindowTitle(f"{APP_NAME} - {APP_TAGLINE}")
        # Ikon jendela mengikuti ikon aplikasi yang disetel pada QApplication.
        self.setWindowIcon(QApplication.windowIcon())
        self.resize(1360, 900)
        self.setMinimumSize(1120, 720)

        self._setup_ui()
        self._apply_theme()
        self._refresh_sidebar_session()
        self.controller.data_updated.connect(self._refresh_sidebar_session)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(12, 20, 12, 16)
        sb_layout.setSpacing(5)

        brand_title = QLabel(APP_NAME)
        brand_title.setProperty("class", "TitleLarge")
        brand_sub = QLabel(APP_TAGLINE)
        brand_sub.setProperty("class", "MutedText")

        sb_layout.addWidget(brand_title)
        sb_layout.addWidget(brand_sub)
        sb_layout.addSpacing(16)

        self.nav_buttons: List[QPushButton] = []
        nav_items = [
            ("Dashboard Utama", 0),
            ("Katalog Arsip", 1),
            ("Peringatan Retensi", 2),
            ("Impor & Ekspor", 3),
            ("Sinkronisasi Server", 4),
        ]

        for label, index in nav_items:
            btn = QPushButton(label)
            btn.setProperty("class", "NavButton")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(
                lambda checked=False, i=index: self.switch_page(i)
            )
            sb_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sb_layout.addStretch()

        session_card = QFrame()
        session_card.setProperty("class", "SubtleBox")
        sc_layout = QVBoxLayout(session_card)
        sc_layout.setContentsMargins(10, 10, 10, 10)
        sc_layout.setSpacing(6)

        self.lbl_sb_user = QLabel("Arsiparis Utama")
        self.lbl_sb_user.setStyleSheet("font-weight: 600;")
        self.lbl_sb_mode = QLabel("Mode Lokal")
        self.lbl_sb_mode.setProperty("class", "StatusBadge")

        self.btn_login = QPushButton("Ganti Akun / Mode Kerja")
        self.btn_login.setProperty("class", "SecondaryButton")
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.clicked.connect(self._open_login_dialog)

        sc_layout.addWidget(self.lbl_sb_user)
        sc_layout.addWidget(self.lbl_sb_mode)
        sc_layout.addWidget(self.btn_login)
        sb_layout.addWidget(session_card)

        sb_layout.addSpacing(6)

        self.btn_theme = QPushButton("Ubah ke Mode Gelap")
        self.btn_theme.setProperty("class", "SecondaryButton")
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.clicked.connect(self._toggle_theme)
        sb_layout.addWidget(self.btn_theme)

        content_wrapper = QWidget()
        content_wrapper.setObjectName("MainContentArea")
        cw_layout = QVBoxLayout(content_wrapper)
        cw_layout.setContentsMargins(0, 0, 0, 0)

        self.stack = QStackedWidget()
        self.page_dashboard = DashboardPage(self.controller)
        self.page_dashboard.navigate_requested.connect(self.switch_page)
        self.page_dashboard.open_session_requested.connect(
            self._open_login_dialog
        )

        self.page_katalog = CatalogPage(self.controller)
        self.page_katalog.export_filtered_requested.connect(
            self._jump_to_filtered_export
        )

        self.page_retensi = RetentionPage(self.controller)
        self.page_io = ImportExportPage(self.controller)

        self.page_hybrid = ServerSyncPage(self.controller)

        self.stack.addWidget(self.page_dashboard)
        self.stack.addWidget(self.page_katalog)
        self.stack.addWidget(self.page_retensi)
        self.stack.addWidget(self.page_io)
        self.stack.addWidget(self.page_hybrid)

        cw_layout.addWidget(self.stack)

        root_layout.addWidget(sidebar)
        root_layout.addWidget(content_wrapper)

        self.switch_page(0)

    def _jump_to_filtered_export(self):
        self.page_io.select_filtered_export_mode()
        self.switch_page(3)

    def _refresh_sidebar_session(self):
        sess = self.controller.session
        self.lbl_sb_user.setText(f"{sess.nama_lengkap} (@{sess.username})")
        host_badge = " (Host)" if self.controller.is_server_running() else ""
        self.lbl_sb_mode.setText(f"{sess.mode_koneksi}{host_badge}")

    def switch_page(self, index: int):
        self.stack.setCurrentIndex(index)
        if index == 3:
            self.page_io.refresh_counts()
        for i, btn in enumerate(self.nav_buttons):
            btn.setProperty("active", "true" if i == index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.btn_theme.setText(
            "Ubah ke Mode Terang" if self.dark_mode else "Ubah ke Mode Gelap"
        )
        self._apply_theme()

    def _apply_theme(self):
        self.setStyleSheet(ThemeManager.build_stylesheet(self.dark_mode))
        self.page_dashboard.set_theme(self.dark_mode)
        self.page_katalog.set_theme(self.dark_mode)
        self.page_retensi.set_theme(self.dark_mode)
        self.page_io.set_theme(self.dark_mode)
        self.page_hybrid.set_theme(self.dark_mode)

    def closeEvent(self, event):
        if self.controller.is_server_running():
            self.controller.stop_office_server()
        super().closeEvent(event)

    def _open_login_dialog(self):
        dialog = SessionModeDialog(self.controller, self.dark_mode, self)
        dialog.exec()

