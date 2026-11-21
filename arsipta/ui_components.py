from .common import *
from .models import *
from .storage import *
from .processing import *
from .spreadsheet import *
from .network import *
from .workers import *
from .controller import *


class ThemeManager:
    """Mengelola palet warna profesional yang konsisten untuk tema Terang dan Gelap."""

    LIGHT = {
        "bg_window": "#F7F7F5",
        "bg_sidebar": "#EFEFEB",
        "bg_card": "#FFFFFF",
        "bg_subtle": "#FAFAF8",
        "bg_input": "#FFFFFF",
        "bg_hover": "#E6E8E1",
        "bg_active": "#E2E4DC",
        "border": "#D2D6CE",
        "border_soft": "#E2E4E0",
        "text_primary": "#181A18",
        "text_secondary": "#424842",
        "text_muted": "#687068",
        "accent": "#1B4D3E",
        "accent_hover": "#143A2F",
        "accent_text": "#FFFFFF",
        "danger": "#DC2626",
        "danger_hover": "#B91C1C",
        "badge_bg": "#EAF3ED",
        "badge_text": "#1E5631",
        "scrollbar_bg": "#F7F7F5",
        "scrollbar_handle": "#C9CEC6",
    }

    DARK = {
        "bg_window": "#0F172A",
        "bg_sidebar": "#1E293B",
        "bg_card": "#1E293B",
        "bg_subtle": "#0F172A",
        "bg_input": "#0F172A",
        "bg_hover": "#334155",
        "bg_active": "#1E3A8A",
        "border": "#334155",
        "border_soft": "#334155",
        "text_primary": "#F8FAFC",
        "text_secondary": "#CBD5E1",
        "text_muted": "#94A3B8",
        "accent": "#3B82F6",
        "accent_hover": "#60A5FA",
        "accent_text": "#FFFFFF",
        "danger": "#EF4444",
        "danger_hover": "#DC2626",
        "badge_bg": "#1E3A8A",
        "badge_text": "#93C5FD",
        "scrollbar_bg": "#0F172A",
        "scrollbar_handle": "#475569",
    }

    @classmethod
    def build_stylesheet(cls, dark_mode: bool) -> str:
        t = cls.DARK if dark_mode else cls.LIGHT
        return f"""
        QMainWindow, QDialog, QWidget#MainContentArea, QWidget#ScrollContainer {{
            background-color: {t['bg_window']};
            color: {t['text_primary']};
            font-family: "Segoe UI", "Plus Jakarta Sans", "Inter", sans-serif;
            font-size: 13px;
        }}
        QScrollArea {{
            background-color: {t['bg_window']};
            border: none;
        }}
        QScrollArea > QWidget > QWidget {{
            background-color: {t['bg_window']};
        }}
        QFrame#Sidebar {{
            background-color: {t['bg_sidebar']};
            border-right: 1px solid {t['border_soft']};
        }}
        QFrame.Card {{
            background-color: {t['bg_card']};
            border: 1px solid {t['border_soft']};
            border-radius: 10px;
        }}
        QFrame.SubtleBox {{
            background-color: {t['bg_subtle']};
            border: 1px solid {t['border_soft']};
            border-radius: 8px;
        }}
        QFrame.ClickableCard {{
            background-color: {t['bg_card']};
            border: 1px solid {t['border_soft']};
            border-radius: 10px;
        }}
        QFrame.ClickableCard:hover {{
            border: 1px solid {t['accent']};
            background-color: {t['bg_hover']};
        }}
        QLabel {{
            background-color: transparent;
            color: {t['text_primary']};
        }}
        QLabel.TitleLarge {{
            font-size: 22px;
            font-weight: 700;
            color: {t['text_primary']};
        }}
        QLabel.SectionTitle {{
            font-size: 15px;
            font-weight: 600;
            color: {t['text_primary']};
        }}
        QLabel.MutedText {{
            color: {t['text_secondary']};
            font-size: 12px;
        }}
        QLabel.HintText {{
            color: {t['text_muted']};
            font-size: 11px;
        }}
        QLabel.MetricValue {{
            font-size: 26px;
            font-weight: 700;
            color: {t['text_primary']};
        }}
        QLabel.StatusBadge {{
            background-color: {t['badge_bg']};
            color: {t['badge_text']};
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 11px;
            font-weight: 600;
        }}
        QPushButton.NavButton {{
            text-align: left;
            padding: 10px 14px;
            border-radius: 8px;
            border: none;
            background-color: transparent;
            color: {t['text_secondary']};
            font-weight: 500;
        }}
        QPushButton.NavButton:hover {{
            background-color: {t['bg_hover']};
            color: {t['text_primary']};
        }}
        QPushButton.NavButton[active="true"] {{
            background-color: {t['bg_active']};
            color: {t['accent']};
            font-weight: 600;
        }}
        QPushButton.PrimaryButton {{
            background-color: {t['accent']};
            color: {t['accent_text']};
            border: none;
            border-radius: 7px;
            padding: 8px 16px;
            font-weight: 600;
        }}
        QPushButton.PrimaryButton:hover {{
            background-color: {t['accent_hover']};
        }}
        QPushButton.SecondaryButton {{
            background-color: {t['bg_card']};
            color: {t['text_primary']};
            border: 1px solid {t['border']};
            border-radius: 7px;
            padding: 8px 14px;
            font-weight: 500;
        }}
        QPushButton.SecondaryButton:hover {{
            background-color: {t['bg_hover']};
        }}
        QPushButton.DangerButton {{
            background-color: {t['danger']};
            color: #FFFFFF;
            border: none;
            border-radius: 7px;
            padding: 8px 14px;
            font-weight: 600;
        }}
        QPushButton.DangerButton:hover {{
            background-color: {t['danger_hover']};
        }}
        QLineEdit, QComboBox, QDateEdit, QTextEdit {{
            background-color: {t['bg_input']};
            color: {t['text_primary']};
            border: 1px solid {t['border']};
            border-radius: 7px;
            padding: 6px 10px;
            min-height: 20px;
        }}
        QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled {{
            background-color: {t['bg_subtle']};
            color: {t['text_muted']};
        }}
        QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{
            border: 1px solid {t['accent']};
        }}
        QComboBox QAbstractItemView {{
            background-color: {t['bg_card']};
            color: {t['text_primary']};
            selection-background-color: {t['bg_active']};
            selection-color: {t['text_primary']};
            border: 1px solid {t['border']};
        }}
        QProgressBar {{
            background-color: {t['bg_subtle']};
            border: 1px solid {t['border']};
            border-radius: 6px;
            text-align: center;
            color: {t['text_primary']};
            height: 18px;
        }}
        QProgressBar::chunk {{
            background-color: {t['accent']};
            border-radius: 5px;
        }}
        QTableWidget {{
            font-size: 12px;
            background-color: {t['bg_card']};
            color: {t['text_primary']};
            border: 1px solid {t['border_soft']};
            border-radius: 8px;
            gridline-color: {t['border_soft']};
            selection-background-color: {t['bg_active']};
            selection-color: {t['text_primary']};
        }}
        QTableWidget::item {{
            padding: 8px 10px;
            color: {t['text_primary']};
            border-bottom: 1px solid {t['border_soft']};
        }}
        QTableWidget::item:selected {{
            background-color: {t['bg_active']};
            color: {t['text_primary']};
        }}
        QHeaderView::section {{
            background-color: {t['bg_subtle']};
            color: {t['text_secondary']};
            padding: 10px 9px;
            border: none;
            border-bottom: 1px solid {t['border_soft']};
            font-weight: 600;
        }}
        QTableCornerButton::section {{
            background-color: {t['bg_subtle']};
            border: none;
            border-bottom: 1px solid {t['border_soft']};
        }}
        QScrollBar:vertical {{
            background: {t['scrollbar_bg']};
            width: 10px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {t['scrollbar_handle']};
            min-height: 24px;
            border-radius: 5px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QMessageBox {{
            background-color: {t['bg_card']};
            color: {t['text_primary']};
        }}
        """


class VisibleCheckBox(QCheckBox):
    """Kotak centang kontras tinggi yang jelas terlihat di Mode Terang & Gelap."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.dark_mode = False
        self.setCursor(Qt.PointingHandCursor)

    def set_theme(self, dark_mode: bool):
        self.dark_mode = dark_mode
        self.update()

    def sizeHint(self):
        sh = super().sizeHint()
        sh.setWidth(sh.width() + 10)
        return sh

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        box_size = 18
        y_offset = (self.height() - box_size) // 2
        box_rect = QRect(2, y_offset, box_size, box_size)

        if self.isChecked():
            fill_color = (
                QColor("#3B82F6") if self.dark_mode else QColor("#2563EB")
            )
            border_color = fill_color
        else:
            fill_color = (
                QColor("#0F172A") if self.dark_mode else QColor("#FFFFFF")
            )
            border_color = (
                QColor("#94A3B8") if self.dark_mode else QColor("#475569")
            )

        painter.setPen(QPen(border_color, 1.8))
        painter.setBrush(fill_color)
        painter.drawRoundedRect(box_rect, 4, 4)

        if self.isChecked():
            check_pen = QPen(QColor("#FFFFFF"), 2.2)
            check_pen.setCapStyle(Qt.RoundCap)
            check_pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(check_pen)
            p1 = QPoint(box_rect.left() + 4, box_rect.top() + 9)
            p2 = QPoint(box_rect.left() + 8, box_rect.top() + 13)
            p3 = QPoint(box_rect.left() + 14, box_rect.top() + 5)
            painter.drawPolyline([p1, p2, p3])

        text_color = QColor("#F8FAFC") if self.dark_mode else QColor("#0F172A")
        painter.setPen(text_color)
        font = self.font()
        font.setWeight(QFont.Medium)
        painter.setFont(font)
        text_rect = QRect(
            box_rect.right() + 8,
            0,
            self.width() - (box_rect.right() + 8),
            self.height()
        )
        painter.drawText(
            text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text()
        )


class VisibleRadioButton(QRadioButton):
    """Tombol pilihan radio kontras tinggi untuk Mode Terang & Gelap."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.dark_mode = False
        self.setCursor(Qt.PointingHandCursor)

    def set_theme(self, dark_mode: bool):
        self.dark_mode = dark_mode
        self.update()

    def sizeHint(self):
        sh = super().sizeHint()
        sh.setWidth(sh.width() + 10)
        return sh

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        circle_size = 18
        y_offset = (self.height() - circle_size) // 2
        circle_rect = QRect(2, y_offset, circle_size, circle_size)

        if self.isChecked():
            border_color = (
                QColor("#3B82F6") if self.dark_mode else QColor("#2563EB")
            )
        else:
            border_color = (
                QColor("#94A3B8") if self.dark_mode else QColor("#475569")
            )
        fill_color = QColor("#0F172A") if self.dark_mode else QColor("#FFFFFF")

        painter.setPen(QPen(border_color, 1.8))
        painter.setBrush(fill_color)
        painter.drawEllipse(circle_rect)

        if self.isChecked():
            inner_rect = circle_rect.adjusted(4, 4, -4, -4)
            painter.setPen(Qt.NoPen)
            painter.setBrush(border_color)
            painter.drawEllipse(inner_rect)

        text_color = QColor("#F8FAFC") if self.dark_mode else QColor("#0F172A")
        painter.setPen(text_color)
        font = self.font()
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        text_rect = QRect(
            circle_rect.right() + 8,
            0,
            self.width() - (circle_rect.right() + 8),
            self.height()
        )
        painter.drawText(
            text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.text()
        )


class SortableTableItem(QTableWidgetItem):
    """Item tabel yang mendukung pengurutan numerik/tanggal secara akurat."""

    def __init__(self, text: str, sort_key: Any = None):
        super().__init__(text)
        self.sort_key = sort_key if sort_key is not None else text.lower()

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, SortableTableItem):
            try:
                return self.sort_key < other.sort_key
            except TypeError:
                return str(self.sort_key) < str(other.sort_key)
        return super().__lt__(other)


class ClickableCard(QFrame):
    """Kartu interaktif dengan sinyal klik dan kursor penunjuk."""
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "ClickableCard")
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class StatusCompositionWidget(QWidget):
    """
    Visualisasi Grafik Donat (Donut Chart) + Batang Proporsi
    untuk membandingkan Arsip Aktif vs Arsip Inaktif secara langsung.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.aktif_count = 0
        self.inaktif_count = 0
        self.dark_mode = False
        self.setMinimumHeight(145)
        self.setMaximumHeight(160)

    def set_values(self, aktif: int, inaktif: int):
        self.aktif_count = max(0, aktif)
        self.inaktif_count = max(0, inaktif)
        self.update()

    def set_theme(self, dark_mode: bool):
        self.dark_mode = dark_mode
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()

        total = self.aktif_count + self.inaktif_count
        aktif_pct = (self.aktif_count / total * 100.0) if total > 0 else 0.0
        inaktif_pct = (self.inaktif_count / total * 100.0) if total > 0 else 0.0

        color_aktif = QColor("#10B981")
        color_inaktif = (
            QColor("#64748B") if self.dark_mode else QColor("#94A3B8")
        )
        color_empty = (
            QColor("#334155") if self.dark_mode else QColor("#E2E8F0")
        )
        color_center_bg = (
            QColor("#1E293B") if self.dark_mode else QColor("#FFFFFF")
        )
        text_primary = (
            QColor("#F8FAFC") if self.dark_mode else QColor("#0F172A")
        )
        text_secondary = (
            QColor("#CBD5E1") if self.dark_mode else QColor("#475569")
        )

        # 1. Gambar Grafik Donat di Sisi Kiri
        donut_size = min(124, rect.height() - 16)
        donut_x = 12
        donut_y = (rect.height() - donut_size) // 2
        outer_rect = QRectF(donut_x, donut_y, donut_size, donut_size)

        painter.setPen(Qt.NoPen)
        if total == 0:
            painter.setBrush(color_empty)
            painter.drawEllipse(outer_rect)
        else:
            aktif_span = int(round((self.aktif_count / total) * 360 * 16))
            inaktif_span = (360 * 16) - aktif_span

            if aktif_span > 0:
                painter.setBrush(color_aktif)
                painter.drawPie(outer_rect, 90 * 16, -aktif_span)
            if inaktif_span > 0:
                painter.setBrush(color_inaktif)
                painter.drawPie(
                    outer_rect, (90 * 16) - aktif_span, -inaktif_span
                )

        # Lubang tengah Donat
        hole_margin = donut_size * 0.27
        inner_rect = outer_rect.adjusted(
            hole_margin, hole_margin, -hole_margin, -hole_margin
        )
        painter.setBrush(color_center_bg)
        painter.drawEllipse(inner_rect)

        # Angka total di tengah Donat
        painter.setPen(text_primary)
        f_num = QFont("Segoe UI", 15, QFont.Bold)
        painter.setFont(f_num)
        painter.drawText(
            inner_rect.adjusted(0, -8, 0, 0),
            Qt.AlignCenter,
            str(total)
        )
        painter.setPen(text_secondary)
        f_lbl = QFont("Segoe UI", 8)
        painter.setFont(f_lbl)
        painter.drawText(
            inner_rect.adjusted(0, 18, 0, 0),
            Qt.AlignCenter,
            "Total"
        )

        # 2. Gambar Legenda & Batang Perbandingan di Sisi Kanan
        right_x = donut_x + donut_size + 28
        right_w = max(120, rect.width() - right_x - 16)

        # Baris Arsip Aktif
        y_aktif = donut_y + 12
        painter.setBrush(color_aktif)
        painter.drawRoundedRect(right_x, y_aktif + 3, 12, 12, 3, 3)

        painter.setPen(text_primary)
        painter.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        painter.drawText(
            right_x + 20,
            y_aktif,
            right_w - 20,
            18,
            Qt.AlignLeft | Qt.AlignVCenter,
            f"Arsip Aktif: {self.aktif_count} dokumen ({aktif_pct:.1f}%)"
        )

        bar_aktif_rect = QRect(right_x, y_aktif + 22, right_w, 12)
        clip_a = QPainterPath()
        clip_a.addRoundedRect(QRectF(bar_aktif_rect), 6, 6)
        painter.save()
        painter.setClipPath(clip_a)
        painter.fillRect(bar_aktif_rect, color_empty)
        if total > 0 and self.aktif_count > 0:
            w_a = int((self.aktif_count / total) * right_w)
            painter.fillRect(
                right_x, y_aktif + 22, w_a, 12, color_aktif
            )
        painter.restore()

        # Baris Arsip Inaktif
        y_inaktif = y_aktif + 52
        painter.setBrush(color_inaktif)
        painter.drawRoundedRect(right_x, y_inaktif + 3, 12, 12, 3, 3)

        painter.setPen(text_primary)
        painter.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        painter.drawText(
            right_x + 20,
            y_inaktif,
            right_w - 20,
            18,
            Qt.AlignLeft | Qt.AlignVCenter,
            f"Arsip Inaktif: {self.inaktif_count} dokumen ({inaktif_pct:.1f}%)"
        )

        bar_inaktif_rect = QRect(right_x, y_inaktif + 22, right_w, 12)
        clip_i = QPainterPath()
        clip_i.addRoundedRect(QRectF(bar_inaktif_rect), 6, 6)
        painter.save()
        painter.setClipPath(clip_i)
        painter.fillRect(bar_inaktif_rect, color_empty)
        if total > 0 and self.inaktif_count > 0:
            w_i = int((self.inaktif_count / total) * right_w)
            painter.fillRect(
                right_x, y_inaktif + 22, w_i, 12, color_inaktif
            )
        painter.restore()


class ArchiveFormDialog(QDialog):
    """Dialog formulir untuk menambah atau mengubah catatan arsip perjanjian."""

    def __init__(
        self,
        controller: ArsiptaController,
        dark_mode: bool,
        existing: Optional[ArchiveRecord] = None,
        parent=None
    ):
        super().__init__(parent)
        self.controller = controller
        self.existing = existing
        is_edit = existing is not None

        self.setWindowTitle(
            "Ubah Data Arsip Perjanjian"
            if is_edit
            else "Tambah Arsip Perjanjian Baru"
        )
        self.setMinimumWidth(480)
        self.setStyleSheet(ThemeManager.build_stylesheet(dark_mode))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        title = QLabel(
            f"Edit Dokumen: {existing.nomor_dokumen}"
            if is_edit
            else "Input Arsip Perjanjian Baru"
        )
        title.setProperty("class", "SectionTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.input_nomor = QLineEdit(existing.nomor_dokumen if is_edit else "")
        self.input_nomor.setPlaceholderText("Contoh: PKS/2026/015")

        self.input_judul = QLineEdit(
            existing.judul_perjanjian if is_edit else ""
        )
        self.input_judul.setPlaceholderText(
            "Contoh: Perjanjian Kerja Sama Pemeliharaan Server"
        )

        self.input_pihak = QLineEdit(existing.pihak_terkait if is_edit else "")
        self.input_pihak.setPlaceholderText("Contoh: PT Mitra Teknologi")

        self.combo_topik = QComboBox()
        self.combo_topik.setEditable(True)
        default_topics = [
            "Pengadaan Barang & Jasa",
            "Teknologi Informasi",
            "Fasilitas & Infrastruktur",
            "Hukum & Kepatuhan",
            "Sumber Daya Manusia",
            "Keuangan & Perbankan",
            "Kerja Sama Operasional",
        ]
        existing_topics = self.controller.get_topics()
        merged_topics = sorted(list(set(default_topics + existing_topics)))
        self.combo_topik.addItems(merged_topics)
        if is_edit:
            self.combo_topik.setCurrentText(existing.topik)

        self.date_mulai = QDateEdit()
        self.date_mulai.setCalendarPopup(True)
        self.date_mulai.setDisplayFormat("yyyy-MM-dd")
        if is_edit:
            self.date_mulai.setDate(
                QDate.fromString(existing.tanggal_mulai, "yyyy-MM-dd")
            )
        else:
            self.date_mulai.setDate(QDate.currentDate())

        self.date_berakhir = QDateEdit()
        self.date_berakhir.setCalendarPopup(True)
        self.date_berakhir.setDisplayFormat("yyyy-MM-dd")
        if is_edit:
            self.date_berakhir.setDate(
                QDate.fromString(existing.tanggal_berakhir, "yyyy-MM-dd")
            )
        else:
            self.date_berakhir.setDate(QDate.currentDate().addYears(1))

        self.combo_status = QComboBox()
        self.combo_status.addItems(["Aktif", "Inaktif"])
        if is_edit:
            self.combo_status.setCurrentText(existing.status)

        self.input_lokasi = QLineEdit(existing.lokasi_fisik if is_edit else "")
        self.input_lokasi.setPlaceholderText("Contoh: Lemari A - Rak 2 - Map 04")

        form.addRow("Nomor Dokumen *:", self.input_nomor)
        form.addRow("Judul Perjanjian *:", self.input_judul)
        form.addRow("Pihak Terkait *:", self.input_pihak)
        form.addRow("Topik / Kategori *:", self.combo_topik)
        form.addRow("Tanggal Mulai:", self.date_mulai)
        form.addRow("Tanggal Berakhir:", self.date_berakhir)
        form.addRow("Status Arsip:", self.combo_status)
        form.addRow("Lokasi Penyimpanan:", self.input_lokasi)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Batal")
        btn_cancel.setProperty("class", "SecondaryButton")
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Simpan Perubahan" if is_edit else "Simpan Arsip")
        btn_save.setProperty("class", "PrimaryButton")
        btn_save.clicked.connect(self._handle_save)

        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _handle_save(self):
        nomor = self.input_nomor.text().strip()
        judul = self.input_judul.text().strip()
        pihak = self.input_pihak.text().strip()
        topik = self.combo_topik.currentText().strip()
        tgl_mulai = self.date_mulai.date().toString("yyyy-MM-dd")
        tgl_berakhir = self.date_berakhir.date().toString("yyyy-MM-dd")

        if not nomor or not judul or not pihak or not topik:
            QMessageBox.warning(
                self,
                "Data Belum Lengkap",
                "Nomor Dokumen, Judul Perjanjian, Pihak Terkait, "
                "dan Topik wajib diisi."
            )
            return

        if tgl_berakhir < tgl_mulai:
            QMessageBox.warning(
                self,
                "Rentang Tanggal Tidak Valid",
                "Tanggal Berakhir tidak boleh lebih awal dari Tanggal Mulai."
            )
            return

        record = ArchiveRecord(
            id=self.existing.id if self.existing else None,
            nomor_dokumen=nomor,
            judul_perjanjian=judul,
            pihak_terkait=pihak,
            topik=topik,
            tanggal_mulai=tgl_mulai,
            tanggal_berakhir=tgl_berakhir,
            status=self.combo_status.currentText(),
            lokasi_fisik=self.input_lokasi.text().strip(),
            file_sumber=(
                self.existing.file_sumber if self.existing else "Input Manual"
            ),
            diperbarui_pada=""
        )

        if self.existing:
            ok, msg = self.controller.edit_archive(record)
        else:
            ok, msg = self.controller.create_archive(record)

        if ok:
            QMessageBox.information(self, "Berhasil", msg)
            self.accept()
        else:
            QMessageBox.warning(self, "Gagal Menyimpan", msg)


class RegisterAccountDialog(QDialog):
    """Dialog pendaftaran akun arsiparis baru."""

    def __init__(
        self, controller: ArsiptaController, dark_mode: bool, parent=None
    ):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Daftar Akun Arsiparis Baru")
        self.setMinimumWidth(400)
        self.setStyleSheet(ThemeManager.build_stylesheet(dark_mode))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Buat Akun Arsiparis Baru")
        title.setProperty("class", "SectionTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        self.input_nama = QLineEdit()
        self.input_nama.setPlaceholderText("Contoh: Budi Santoso")

        self.input_user = QLineEdit()
        self.input_user.setPlaceholderText("Contoh: budi_arsip")

        self.input_pass = QLineEdit()
        self.input_pass.setEchoMode(QLineEdit.Password)
        self.input_pass.setPlaceholderText("Minimal 4 karakter")

        form.addRow("Nama Lengkap:", self.input_nama)
        form.addRow("Nama Pengguna:", self.input_user)
        form.addRow("Kata Sandi:", self.input_pass)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Batal")
        btn_cancel.setProperty("class", "SecondaryButton")
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Simpan Akun")
        btn_save.setProperty("class", "PrimaryButton")
        btn_save.clicked.connect(self._handle_register)

        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _handle_register(self):
        ok, msg = self.controller.register_new_account(
            self.input_user.text(),
            self.input_pass.text(),
            self.input_nama.text()
        )
        if ok:
            QMessageBox.information(self, "Akun Terdaftar", msg)
            self.accept()
        else:
            QMessageBox.warning(self, "Gagal Mendaftar", msg)


class SessionModeDialog(QDialog):
    """Dialog pengaturan akun arsiparis dan pemilihan mode kerja."""

    def __init__(
        self, controller: ArsiptaController, dark_mode: bool, parent=None
    ):
        super().__init__(parent)
        self.controller = controller
        self.dark_mode = dark_mode
        self.setWindowTitle("Pengaturan Akun & Mode Kerja Arsiparis")
        self.setMinimumWidth(480)
        self.setStyleSheet(ThemeManager.build_stylesheet(dark_mode))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        lbl_header = QLabel("Akun Arsiparis & Mode Kerja")
        lbl_header.setProperty("class", "SectionTitle")
        layout.addWidget(lbl_header)

        info_box = QFrame()
        info_box.setProperty("class", "SubtleBox")
        info_layout = QVBoxLayout(info_box)
        info_layout.setContentsMargins(12, 10, 12, 10)
        lbl_explain = QLabel(
            "Aplikasi ini mendukung kerja mandiri maupun tim:\n"
            "• Mode Lokal: Data tersimpan di PC ini saja tanpa butuh jaringan.\n"
            "• Mode Server Kantor: Menghubungkan ke server lokal perusahaan "
            "agar setiap arsiparis yang masuk memakai akun yang sama melihat "
            "daftar arsip yang sama."
        )
        lbl_explain.setProperty("class", "MutedText")
        lbl_explain.setWordWrap(True)
        info_layout.addWidget(lbl_explain)
        layout.addWidget(info_box)

        mode_box = QFrame()
        mode_box.setProperty("class", "Card")
        mode_layout = QVBoxLayout(mode_box)
        mode_layout.setContentsMargins(14, 12, 14, 12)
        mode_layout.setSpacing(8)

        lbl_mode_title = QLabel("1. Pilih Mode Penyimpanan & Kerja")
        lbl_mode_title.setProperty("class", "SectionTitle")
        mode_layout.addWidget(lbl_mode_title)

        self.radio_lokal = VisibleRadioButton(
            "Mode Lokal (Mandiri di Komputer Ini)"
        )
        self.radio_server = VisibleRadioButton(
            "Mode Server Kantor (Sinkronisasi Tim / Hybrid)"
        )
        self.radio_lokal.set_theme(dark_mode)
        self.radio_server.set_theme(dark_mode)

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.radio_lokal)
        self.mode_group.addButton(self.radio_server)

        is_server = (
            self.controller.session.mode_koneksi == "Mode Server Kantor"
        )
        self.radio_server.setChecked(is_server)
        self.radio_lokal.setChecked(not is_server)

        self.input_server = QLineEdit(
            self.controller.session.server_url or "http://localhost:8080"
        )
        self.input_server.setPlaceholderText(
            "Contoh: http://192.168.1.100:8080"
        )

        self.lbl_server_hint = QLabel()
        self.lbl_server_hint.setProperty("class", "HintText")

        server_row = QHBoxLayout()
        server_row.addWidget(self.input_server)
        self.btn_test_conn = QPushButton("Uji Koneksi")
        self.btn_test_conn.setProperty("class", "SecondaryButton")
        self.btn_test_conn.setCursor(Qt.PointingHandCursor)
        self.btn_test_conn.clicked.connect(self._test_server_connection)
        server_row.addWidget(self.btn_test_conn)

        mode_layout.addWidget(self.radio_lokal)
        mode_layout.addWidget(self.radio_server)
        mode_layout.addLayout(server_row)
        mode_layout.addWidget(self.lbl_server_hint)
        layout.addWidget(mode_box)

        self.radio_lokal.toggled.connect(self._update_server_field_state)
        self._update_server_field_state()

        cred_box = QFrame()
        cred_box.setProperty("class", "Card")
        cred_layout = QVBoxLayout(cred_box)
        cred_layout.setContentsMargins(14, 12, 14, 12)
        cred_layout.setSpacing(8)

        lbl_cred_title = QLabel("2. Identitas Akun Arsiparis")
        lbl_cred_title.setProperty("class", "SectionTitle")
        cred_layout.addWidget(lbl_cred_title)

        form = QFormLayout()
        form.setSpacing(8)
        self.input_user = QLineEdit(self.controller.session.username)
        self.input_user.setPlaceholderText("Masukkan nama pengguna")

        self.input_pass = QLineEdit()
        self.input_pass.setEchoMode(QLineEdit.Password)
        self.input_pass.setPlaceholderText("Masukkan kata sandi")

        form.addRow("Nama Pengguna:", self.input_user)
        form.addRow("Kata Sandi:", self.input_pass)
        cred_layout.addLayout(form)

        lbl_default_hint = QLabel(
            "Akun bawaan uji coba: arsiparis / arsip123  atau  admin / admin123"
        )
        lbl_default_hint.setProperty("class", "HintText")
        cred_layout.addWidget(lbl_default_hint)
        layout.addWidget(cred_box)

        btn_row = QHBoxLayout()
        btn_register = QPushButton("Buat Akun Baru")
        btn_register.setProperty("class", "SecondaryButton")
        btn_register.clicked.connect(self._open_register)

        btn_cancel = QPushButton("Batal")
        btn_cancel.setProperty("class", "SecondaryButton")
        btn_cancel.clicked.connect(self.reject)

        btn_submit = QPushButton("Masuk & Terapkan")
        btn_submit.setProperty("class", "PrimaryButton")
        btn_submit.clicked.connect(self._handle_login)

        btn_row.addWidget(btn_register)
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_submit)
        layout.addLayout(btn_row)

    def _update_server_field_state(self):
        use_server = self.radio_server.isChecked()
        self.input_server.setEnabled(use_server)
        self.btn_test_conn.setEnabled(use_server)
        if use_server:
            self.lbl_server_hint.setText(
                "Masukkan alamat IP/URL server kantor tempat database bersama berada."
            )
        else:
            self.lbl_server_hint.setText(
                "Alamat server dinonaktifkan karena Anda memilih Mode Lokal."
            )

    def _test_server_connection(self):
        url = self.input_server.text().strip()
        if not url:
            QMessageBox.warning(self, "Alamat Kosong", "Masukkan alamat server kantor terlebih dahulu.")
            return
        ok, msg, data = self.controller.test_remote_server(url)
        if ok:
            name = data.get("server_name", "ARSIPTA Server")
            ver = data.get("version", "")
            tot = data.get("total_archives", 0)
            self.lbl_server_hint.setText(f"✓ Terhubung ke {name} ({ver}) — {tot} arsip tersedia.")
            self.lbl_server_hint.setStyleSheet("color: #16A34A; font-weight: 600;")
        else:
            self.lbl_server_hint.setText(f"✗ Gagal terhubung: {msg}")
            self.lbl_server_hint.setStyleSheet("color: #DC2626; font-weight: 600;")

    def _open_register(self):
        dlg = RegisterAccountDialog(self.controller, self.dark_mode, self)
        dlg.exec()

    def _handle_login(self):
        selected_mode = (
            "Mode Server Kantor"
            if self.radio_server.isChecked()
            else "Mode Lokal"
        )
        ok, msg = self.controller.switch_session(
            self.input_user.text(),
            self.input_pass.text(),
            selected_mode,
            self.input_server.text()
        )
        if ok:
            QMessageBox.information(self, "Sesi Diterapkan", msg)
            self.accept()
        else:
            QMessageBox.warning(self, "Gagal Masuk", msg)

