from PyQt6.QtWidgets import (
    QDialog, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget, QApplication, QSizePolicy, QHBoxLayout, QFrame
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QRect, QEasingCurve
from PyQt6.QtGui import QPixmap, QFontMetrics, QFont
import pyotp
import sys

_otp_dialog_open = False

def get_otp_secret():
    from db_manager import get_connection
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT otp_secret FROM users LIMIT 1")
        row = cur.fetchone()
        if row:
            return row[0]
    except Exception:
        pass
    return None


class BlurOverlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        win = parent.windowHandle() if parent else None
        px = win.screen().grabWindow(int(parent.winId())) if win else QApplication.primaryScreen().grabWindow(0)
        img = px.toImage()
        blurred = self._blur_image(img, radius=18)
        self.label = QLabel(self)
        self.label.setPixmap(QPixmap.fromImage(blurred))
        self.label.setGeometry(0, 0, parent.width(), parent.height())
        self.setStyleSheet("background-color: rgba(0, 0, 0, 120);")
        self.setGeometry(parent.rect())
        self.show()
        self.raise_()

    def _blur_image(self, img, radius=12):
        from PyQt6.QtGui import QImage, QPainter
        blurred = QImage(img.size(), QImage.Format.Format_ARGB32)
        blurred.fill(Qt.GlobalColor.transparent)
        painter = QPainter(blurred)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawImage(0, 0, img)
        for _ in range(radius):
            painter.drawImage(
                QRect(1, 0, img.width() - 1, img.height()),
                blurred,
                QRect(0, 0, img.width() - 1, img.height())
            )
            painter.drawImage(
                QRect(0, 1, img.width(), img.height() - 1),
                blurred,
                QRect(0, 0, img.width(), img.height() - 1)
            )
        painter.end()
        return blurred


class OTPDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ok = False
        self.attempts = 0
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # =====================================================
        #  Hitung ukuran dialog + font berdasar ukuran layar
        # =====================================================
        screen_w, screen_h = 1280, 720
        if parent:
            screen_w, screen_h = parent.width(), parent.height()
        else:
            scr = QApplication.primaryScreen()
            if scr:
                geo = scr.availableGeometry()
                screen_w, screen_h = geo.width(), geo.height()

        font_size = max(14, int(screen_h * 0.018))

        otp_font = QFont()
        otp_font.setPointSize(font_size + 4)  # angka lebih besar
        otp_font.setBold(True)                # BOLD

        fm = QFontMetrics(otp_font)
        digits_w = fm.horizontalAdvance("000000")
        extra_spacing = 5 * (6 - 1)
        padding_and_margin = 40
        min_input_width = digits_w + extra_spacing + padding_and_margin

        target_w = int(screen_w * 0.32)
        target_h = int(screen_h * 0.25)
        dlg_w = max(380, min(target_w, 640))
        dlg_h = max(220, min(target_h, 360))
        dlg_w = max(dlg_w, min_input_width + 80)
        self.setFixedSize(dlg_w, dlg_h)

        self.wrapper = QWidget(self)
        self.wrapper.setObjectName("otpWrapper")
        self._update_wrapper_geometry()

        # =====================================================
        #  Layout utama
        # =====================================================
        layout = QVBoxLayout(self.wrapper)
        layout.setContentsMargins(
            int(dlg_w * 0.06), int(dlg_h * 0.08),
            int(dlg_w * 0.06), int(dlg_h * 0.06)
        )
        layout.setSpacing(0)  # spacing manual pakai addSpacing
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Jarak vertikal simetris antara info↔input dan input↔tombol
        gap = int(dlg_h * 0.06)

        # =====================================================
        #  Judul
        # =====================================================
        title = QLabel("🔒 Aplikasi Terkunci")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            QLabel {{
                font-size: {font_size + 3}pt;
                font-weight: 700;
                color: #ff6600;
            }}
        """)

        # =====================================================
        #  Info
        # =====================================================
        info = QLabel(
            "<b>Masukkan kode OTP untuk melanjutkan</b><br>"
            "<b><span style='color:#cc0000;'>Aplikasi akan ditutup jika 3x salah memasukkan OTP</span></b>"
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet(f"font-size: {max(11, font_size - 4)}pt; color: #555;")
        info.setTextFormat(Qt.TextFormat.RichText)

        # =====================================================
        #  FRAME KOTAK INPUT (border oranye)
        # =====================================================
        input_height = max(48, int((font_size + 4) * 2.2))

        input_frame = QFrame()
        input_frame.setObjectName("otpInputFrame")
        input_frame.setFixedWidth(min_input_width + 40)
        input_frame.setFixedHeight(input_height)
        input_frame.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        input_frame.setStyleSheet("""
            QFrame#otpInputFrame {
                border: 2px solid #ff6600;
                border-radius: 18px;
                background-color: #ffffff;
            }
        """)

        # QLineEdit di dalam frame
        self.inp = QLineEdit()
        self.inp.setFont(otp_font)
        self.inp.setMaxLength(6)
        self.inp.setAlignment(Qt.AlignmentFlag.AlignCenter)  # center kiri-kanan
        self.inp.setPlaceholderText("●●●●●●")
        self.inp.setFrame(False)  # hilangkan frame bawaan
        self.inp.setStyleSheet("""
            QLineEdit {
                border: none;              /* tidak ada kotak kedua */
                background: transparent;
                padding: 0;
                margin: 0;
                letter-spacing: 8px;       /* jarak antar digit */
            }
            QLineEdit:focus {
                border: none;
            }
        """)

        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(16, 8, 16, 8)  # kiri, atas, kanan, bawah
        input_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        input_layout.addWidget(self.inp)

        # =====================================================
        #  Tombol
        # =====================================================
        btn = QPushButton("Verifikasi OTP")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #ff6600;
                color: white;
                padding: {max(10, int(dlg_h * 0.05))}px;
                border-radius: 12px;
                font-size: {max(12, int(screen_h * 0.015))}pt;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #e65c00;
            }}
            QPushButton:pressed {{
                background-color: #d95300;
            }}
        """)
        btn.clicked.connect(self.verify)

        # =====================================================
        #  Susunan layout (simetris)
        # =====================================================
        layout.addWidget(title)
        layout.addWidget(info)
        layout.addSpacing(gap)
        layout.addWidget(input_frame, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(gap)
        layout.addWidget(btn)

        # Background wrapper
        self.wrapper.setStyleSheet("""
            QWidget#otpWrapper {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #ffffff,
                    stop:1 #f4f4f4
                );
                border-radius: 18px;
                border: 1px solid #dddddd;
            }
        """)

    # =========================================================
    #  Helper geometry wrapper
    # =========================================================
    def _update_wrapper_geometry(self):
        self.wrapper.setGeometry(0, 0, self.width(), self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_wrapper_geometry()

    def showEvent(self, event):
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is not None:
            geo = self.frameGeometry()
            center = parent.frameGeometry().center()
            geo.moveCenter(center)
            self.move(geo.topLeft())
        else:
            screen = QApplication.primaryScreen()
            if screen is not None:
                screen_geo = screen.availableGeometry()
                geo = self.frameGeometry()
                geo.moveCenter(screen_geo.center())
                self.move(geo.topLeft())

    # =========================================================
    #  Verifikasi OTP
    # =========================================================
    def verify(self):
        code = self.inp.text().strip()
        secret = get_otp_secret()
        try:
            totp = pyotp.TOTP(secret)
            if totp.verify(code):
                self.ok = True
                self.accept()
                return
        except Exception:
            pass

        self.attempts += 1
        self._shake()
        if self.attempts >= 3:
            QApplication.quit()
            sys.exit()

    # ==========================
    #  ANIMASI SHAKE
    # ==========================
    def _shake(self):
        anim = QPropertyAnimation(self.wrapper, b"geometry")
        rect = self.wrapper.geometry()
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

        anim.setDuration(300)
        anim.setKeyValueAt(0.0, QRect(x, y, w, h))
        anim.setKeyValueAt(0.25, QRect(x - 15, y, w, h))
        anim.setKeyValueAt(0.50, QRect(x + 15, y, w, h))
        anim.setKeyValueAt(0.75, QRect(x - 15, y, w, h))
        anim.setKeyValueAt(1.0, QRect(x, y, w, h))
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        anim.start()
        self._shake_anim = anim

# ======================================
#  Fungsi Global untuk memanggil OTP
# ======================================
def show_otp_dialog(parent=None):
    app = QApplication.instance()
    global _otp_dialog_open

    # 🔒 Cegah dialog dobel
    if _otp_dialog_open:
        if app is not None:
            for w in app.topLevelWidgets():
                if isinstance(w, OTPDialog) and w.isVisible():
                    w.raise_()
                    w.activateWindow()
                    break
        return False

    _otp_dialog_open = True
    overlay = None
    try:
        # Cari parent aktif bila tidak diberikan
        if parent is None and app is not None:
            parent = app.activeWindow()

        if parent is None and app is not None:
            for w in app.topLevelWidgets():
                if w.isVisible():
                    parent = w
                    break

        # Jika parent adalah dialog, tutup dulu agar overlay di window induk
        if isinstance(parent, QDialog):
            base = parent.parentWidget() or parent.window()
            try:
                parent.reject()
            except Exception:
                parent.close()
            parent = base

        # Pastikan parent adalah window teratas
        if isinstance(parent, QWidget):
            parent = parent.window()

            # 🟠 Jika window dalam keadaan minimize → bangunkan dulu
            ws = parent.windowState()
            if ws & Qt.WindowState.WindowMinimized:
                parent.setWindowState(ws & ~Qt.WindowState.WindowMinimized)
                parent.showNormal()
                parent.raise_()
                parent.activateWindow()
                QApplication.processEvents()

        # Mode tanpa parent (standalone)
        if parent is None:
            dlg = OTPDialog()
            dlg.exec()
            return dlg.ok

        # Mode dengan overlay blur di atas parent (sudah dipastikan tidak minimize)
        overlay = BlurOverlay(parent)
        dlg = OTPDialog(parent)
        dlg.exec()
        return dlg.ok

    finally:
        if overlay is not None:
            overlay.close()
        _otp_dialog_open = False