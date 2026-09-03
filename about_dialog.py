# about_dialog.py
#
# Dialog "About" bergaya overlay setengah layar.
# Menampilkan logo KPU, teks identitas, dan copyright.
# Klik di area luar kartu, tombol X, atau Esc untuk menutup.

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QWidget,
    QSizePolicy,
    QPushButton,
)


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        # ==== WINDOW / OVERLAY ====
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Dialog
        )
        # Tidak translucent: kita pakai background putih solid
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setModal(True)

        # Ukuran overlay mengikuti parent (nutup penuh)
        if parent is not None:
            # pakai geometry parent supaya benar-benar nutup
            self.setGeometry(parent.frameGeometry())
        else:
            self.resize(900, 600)

        # ==== LAYOUT LUAR (OVERLAY) ====
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ==== KARTU TENGAH ====
        self.card = QFrame(self)
        self.card.setObjectName("aboutCard")
        self.card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # ukuran awal adaptif
        self._update_card_size()

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(32, 24, 32, 24)
        card_layout.setSpacing(8)
        card_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )

        outer_layout.addWidget(self.card, 0, Qt.AlignmentFlag.AlignCenter)

        # ==== TOP BAR: tombol X di kanan atas ====
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        top_bar.addStretch()  # dorong X ke kanan

        self.close_btn = QPushButton("✕", self.card)
        self.close_btn.setObjectName("closeButton")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_btn.clicked.connect(self.accept)

        top_bar.addWidget(self.close_btn)
        card_layout.addLayout(top_bar)

        # ==== LOGO KPU ====
        logo_label = QLabel(self.card)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo_path = self._find_logo_path()
        if logo_path and os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    280,
                    280,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                logo_label.setPixmap(pixmap)
        else:
            logo_label.setText("KPU")
            logo_label.setStyleSheet(
                "font-size: 22px; font-weight: bold; color: #d32f2f;"
            )

        card_layout.addWidget(logo_label)

        # ==== TEKS UTAMA ====
        #title_line1 = QLabel("KOMISI PEMILIHAN UMUM", self.card)
        #title_line1.setObjectName("titleLine1")
        #title_line1.setAlignment(Qt.AlignmentFlag.AlignCenter)

        #title_line2 = QLabel("KABUPATEN TASIKMALAYA", self.card)
        #title_line2.setObjectName("titleLine2")
        #title_line2.setAlignment(Qt.AlignmentFlag.AlignCenter)

        #card_layout.addWidget(title_line1)
        #card_layout.addWidget(title_line2)

        #separator = QFrame(self.card)
        #separator.setFrameShape(QFrame.Shape.HLine)
        #separator.setFrameShadow(QFrame.Shadow.Sunken)
        #card_layout.addWidget(separator)

        # ==== DESKRIPSI APLIKASI ====
        desc = QLabel(self.card)
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setObjectName("descLabel")
        desc.setText(
            "Sistem Manajemen Data Pemilih\n"
            "untuk mendukung tahapan pemutakhiran data pemilih\n"
            "bagi PPS di lingkungan KPU Kabupaten Tasikmalaya."
        )
        card_layout.addWidget(desc)

        # Spacer fleksibel
        spacer = QWidget(self.card)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card_layout.addWidget(spacer)

        # ==== COPYRIGHT & HINT ====
        copyright_label = QLabel(
            "© 2025 DivRendatin KPU Kabupaten Tasikmalaya", self.card
        )
        copyright_label.setObjectName("copyrightLabel")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hint_label = QLabel("Pemilih Berdaulat Dimulai dari Data yang Akurat", self.card)
        hint_label.setObjectName("hintLabel")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card_layout.addWidget(copyright_label)
        card_layout.addWidget(hint_label)

        # ==== STYLESHEET ====
        self._apply_styles()

    # ---------------------------------------------------------
    #  Resize adaptif: card ikut menyesuaikan ukuran window
    # ---------------------------------------------------------
    def _update_card_size(self):
        """Sesuaikan ukuran card dengan ukuran jendela (adaptif)."""
        avail_w = max(self.width(), 400)
        avail_h = max(self.height(), 300)

        margin = 120             # jarak minimal dari tepi window
        min_w, min_h = 640, 360  # ukuran minimal supaya konten lega

        # target proporsional
        target_w = int(avail_w * 0.7)   # 70% lebar window
        target_h = int(avail_h * 0.6)   # 60% tinggi window

        # maksimum yang diizinkan (jaga supaya tidak nempel tepi)
        max_w = max(min_w, avail_w - margin)
        max_h = max(min_h, avail_h - margin)

        card_w = max(min_w, min(target_w, max_w))
        card_h = max(min_h, min(target_h, max_h))

        self.card.setFixedSize(card_w, card_h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_card_size()

    # ---------------------------------------------------------
    #  Helper: cari Simpati.png
    # ---------------------------------------------------------
    def _find_logo_path(self) -> str | None:
        here = os.path.dirname(os.path.abspath(__file__))
        candidate1 = os.path.join(here, "Simpati.png")
        if os.path.exists(candidate1):
            return candidate1
        return None

    # ---------------------------------------------------------
    #  Stylesheet
    # ---------------------------------------------------------
    def _apply_styles(self):
        self.setStyleSheet(
            """
        QDialog {
            /* overlay putih solid (tanpa blur) */
            background: rgba(255, 255, 255, 255);
        }
        QFrame#aboutCard {
            background-color: #ffffff;
            border-radius: 18px;
            border: 1px solid #dddddd;
        }
        QPushButton#closeButton {
            border: none;
            background-color: transparent;
            font-size: 11pt;
            font-weight: 600;
            color: #999999;
        }
        QPushButton#closeButton:hover {
            background-color: #f2f2f2;
            color: #555555;
            border-radius: 13px;
        }
        QPushButton#closeButton:pressed {
            background-color: #e0e0e0;
            color: #333333;
        }
        QLabel#titleLine1 {
            font-size: 16pt;
            font-weight: 700;
            letter-spacing: 2px;
            color: #333333;
        }
        QLabel#titleLine2 {
            font-size: 14pt;
            font-weight: 600;
            letter-spacing: 1.5px;
            color: #444444;
        }
        QLabel#descLabel {
            font-size: 10pt;
            color: #555555;
        }
        QLabel#copyrightLabel {
            font-size: 9pt;
            color: #777777;
        }
        QLabel#hintLabel {
            font-size: 8pt;
            color: #999999;
        }
        """
        )

    # ---------------------------------------------------------
    #  Klik di luar kartu → tutup dialog
    # ---------------------------------------------------------
    def mousePressEvent(self, event):
        pos = event.position().toPoint()
        w = self.childAt(pos)

        in_card = False
        if w is not None:
            temp = w
            while temp is not None:
                if temp is self.card:
                    in_card = True
                    break
                temp = temp.parentWidget()

        if not in_card:
            self.accept()  # tutup dialog
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)


def show_about_dialog(parent: QWidget | None = None):
    """
    Tampilkan AboutDialog dengan overlay putih solid (tanpa blur).
    """
    dlg = AboutDialog(parent)
    dlg.exec()