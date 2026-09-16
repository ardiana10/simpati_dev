# -*- coding: utf-8 -*-
"""
responsive.py — Lapisan adaptasi layar untuk SIMPATI 2.0
========================================================

Tujuan
------
Membuat aplikasi tetap nyaman dipakai di laptop 11.6"–14" (1366x768, dan
varian ber-DPI-scaling 125%/150%) TANPA harus menyunting ribuan baris UI
yang sudah ada, dan TANPA mengubah tampilan di layar besar.

Cara kerja (3 lapis):
  1. METRIK  — menghitung faktor skala dari availableGeometry() layar aktif.
  2. PATCH   — membungkus QWidget.setFixedSize/​setMinimumSize/​setStyleSheet dll.
               sehingga setiap angka piksel hard-coded ikut menyusut & di-clamp
               agar tidak pernah melebihi area layar.
  3. RUNTIME — event filter global yang, saat sebuah QDialog tampil dan
               ternyata lebih tinggi dari layar, otomatis membungkus isinya
               dalam QScrollArea lalu menengahkannya.

Integrasi minimal (lihat INTEGRASI_RESPONSIVE.md):

    import responsive
    responsive.setup_high_dpi()          # SEBELUM QApplication dibuat
    app = QApplication(sys.argv)
    responsive.install(app)              # SESUDAH QApplication dibuat

Modul ini defensif: setiap patch dibungkus try/except, sehingga jika ada
API Qt yang berbeda di versi tertentu, aplikasi tetap jalan seperti biasa.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Optional, Iterable

from PyQt6.QtCore import Qt, QObject, QEvent, QTimer, QSize, QRect
from PyQt6.QtGui import QGuiApplication, QFont
from PyQt6.QtWidgets import (
    QApplication, QWidget, QDialog, QMainWindow, QScrollArea, QVBoxLayout,
    QAbstractItemView, QHeaderView, QTableView, QTableWidget, QFrame,
    QDockWidget, QSizePolicy,
)

QWIDGETSIZE_MAX = 16777215

# ---------------------------------------------------------------------------
# Konfigurasi dasar
# ---------------------------------------------------------------------------

#: Layar acuan tempat UI saat ini "terlihat pas" (laptop 15"–16" / desktop).
BASE_W, BASE_H = 1600, 900

#: Batas bawah & atas faktor skala. Batas atas 1.0 = layar besar TIDAK diubah.
SCALE_MIN, SCALE_MAX = 0.72, 1.00

#: Nilai px di bawah ini tidak pernah diskalakan (border, garis, radius kecil).
PX_SCALE_THRESHOLD = 6

#: Seberapa besar sebuah jendela/dialog boleh memakai area layar.
MAX_W_RATIO, MAX_H_RATIO = 0.96, 0.92

#: Penanda agar stylesheet tidak diskalakan dua kali.
_SHEET_MARK = "/*__rs__*/"


# ---------------------------------------------------------------------------
# Metrik layar
# ---------------------------------------------------------------------------

class Metrics:
    """Menghitung dan menyimpan metrik layar aktif."""

    def __init__(self) -> None:
        self._scale: Optional[float] = None
        self._rect: Optional[QRect] = None

    # -- internal ----------------------------------------------------------
    def _screen(self):
        try:
            scr = QGuiApplication.screenAt(QGuiApplication.primaryScreen().geometry().center())
            return scr or QGuiApplication.primaryScreen()
        except Exception:
            return QGuiApplication.primaryScreen()

    def refresh(self) -> None:
        """Hitung ulang metrik (panggil saat layar berganti / DPI berubah)."""
        self._scale = None
        self._rect = None

    # -- publik ------------------------------------------------------------
    def avail(self) -> QRect:
        """Area layar yang benar-benar bisa dipakai (sudah dikurangi taskbar)."""
        if self._rect is None:
            scr = self._screen()
            self._rect = scr.availableGeometry() if scr else QRect(0, 0, BASE_W, BASE_H)
        return self._rect

    @property
    def s(self) -> float:
        """Faktor skala 0.72–1.00 terhadap layar acuan 1600x900."""
        if self._scale is None:
            r = self.avail()
            raw = min(r.width() / BASE_W, r.height() / BASE_H)
            self._scale = max(SCALE_MIN, min(SCALE_MAX, raw))
        return self._scale

    @property
    def is_small(self) -> bool:
        """True untuk laptop kecil / DPI tinggi (tinggi logis <= 800 px)."""
        return self.avail().height() <= 800

    @property
    def is_tiny(self) -> bool:
        """True untuk kasus paling sempit (mis. 1366x768 @125% => 614 px)."""
        return self.avail().height() <= 660

    def px(self, v: float) -> int:
        """Skalakan satu nilai piksel desain ke layar saat ini."""
        try:
            v = float(v)
        except Exception:
            return v
        if abs(v) < PX_SCALE_THRESHOLD or v >= QWIDGETSIZE_MAX:
            return int(v)
        return int(round(v * self.s))

    def pt(self, v: float) -> int:
        """Skalakan ukuran font (pt) dengan lantai 8pt agar tetap terbaca."""
        try:
            return max(8, int(round(float(v) * self.s)))
        except Exception:
            return int(v)

    def max_w(self) -> int:
        return int(self.avail().width() * MAX_W_RATIO)

    def max_h(self) -> int:
        return int(self.avail().height() * MAX_H_RATIO)

    def clamp_w(self, w: int) -> int:
        return max(1, min(int(w), self.max_w()))

    def clamp_h(self, h: int) -> int:
        return max(1, min(int(h), self.max_h()))


#: Objek metrik global. Pakai `responsive.R.px(40)` di kode Anda.
R = Metrics()


# ---------------------------------------------------------------------------
# 1. High-DPI  (WAJIB dipanggil sebelum QApplication dibuat)
# ---------------------------------------------------------------------------

def setup_high_dpi() -> None:
    """Aktifkan penskalaan DPI pecahan (125%, 150%) dengan benar.

    Tanpa PassThrough, Qt membulatkan 125% menjadi 100% atau 200%, yang pada
    laptop 14" FHD membuat teks terlalu kecil atau elemen terpotong.
    Harus dipanggil SEBELUM `QApplication(sys.argv)`.
    """
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception:
        pass
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")


# ---------------------------------------------------------------------------
# 2. Patch ukuran hard-coded
# ---------------------------------------------------------------------------

_patched = False

#: Referensi ke metode asli QWidget, diambil saat modul di-import (belum di-patch).
#: Dipakai oleh helper internal agar nilai yang SUDAH diskalakan tidak terskala
#: untuk kedua kalinya oleh patch.
_ORIG = {
    "setFixedSize": QWidget.setFixedSize,
    "setFixedWidth": QWidget.setFixedWidth,
    "setFixedHeight": QWidget.setFixedHeight,
    "setMinimumSize": QWidget.setMinimumSize,
    "setMinimumWidth": QWidget.setMinimumWidth,
    "setMinimumHeight": QWidget.setMinimumHeight,
    "resize": QWidget.resize,
}


def raw(widget: QWidget, method: str, *args):
    """Panggil setter ukuran QWidget tanpa melewati patch penskalaan.

    Gunakan ini bila nilai yang Anda kirim SUDAH dalam piksel layar nyata
    (mis. hasil dari `R.px()` atau hasil pengukuran runtime).
    """
    fn = _ORIG.get(method)
    if fn is None:
        return getattr(widget, method)(*args)
    return fn(widget, *args)


def _as_wh(args) -> Optional[tuple]:
    """Terima (w, h) atau QSize; kembalikan tuple (w, h)."""
    if len(args) == 2:
        return int(args[0]), int(args[1])
    if len(args) == 1 and isinstance(args[0], QSize):
        return args[0].width(), args[0].height()
    return None


def _patch_sizes() -> None:
    """Bungkus API ukuran QWidget agar otomatis diskalakan & di-clamp."""
    global _patched
    if _patched:
        return

    o_fixed_size = _ORIG["setFixedSize"]
    o_fixed_w = _ORIG["setFixedWidth"]
    o_fixed_h = _ORIG["setFixedHeight"]
    o_min_size = _ORIG["setMinimumSize"]
    o_min_w = _ORIG["setMinimumWidth"]
    o_min_h = _ORIG["setMinimumHeight"]
    o_resize = _ORIG["resize"]

    def _top(self) -> bool:
        try:
            return self.isWindow()
        except Exception:
            return False

    def setFixedSize(self, *args):
        wh = _as_wh(args)
        if wh is None:
            return o_fixed_size(self, *args)
        w, h = R.px(wh[0]), R.px(wh[1])
        if _top(self):
            w, h = R.clamp_w(w), R.clamp_h(h)
        else:
            w, h = min(w, R.max_w()), min(h, R.max_h())
        return o_fixed_size(self, w, h)

    def setFixedWidth(self, w):
        w = R.px(w)
        return o_fixed_w(self, R.clamp_w(w) if _top(self) else min(w, R.max_w()))

    def setFixedHeight(self, h):
        h = R.px(h)
        return o_fixed_h(self, R.clamp_h(h) if _top(self) else min(h, R.max_h()))

    def setMinimumSize(self, *args):
        wh = _as_wh(args)
        if wh is None:
            return o_min_size(self, *args)
        # Minimum di-clamp lebih longgar: jendela tetap boleh dikecilkan user.
        w = min(R.px(wh[0]), int(R.avail().width() * 0.90))
        h = min(R.px(wh[1]), int(R.avail().height() * 0.86))
        return o_min_size(self, w, h)

    def setMinimumWidth(self, w):
        return o_min_w(self, min(R.px(w), int(R.avail().width() * 0.90)))

    def setMinimumHeight(self, h):
        return o_min_h(self, min(R.px(h), int(R.avail().height() * 0.86)))

    def resize(self, *args):
        wh = _as_wh(args)
        if wh is None:
            return o_resize(self, *args)
        w, h = wh
        if _top(self):
            w, h = R.clamp_w(R.px(w)), R.clamp_h(R.px(h))
        return o_resize(self, w, h)

    for name, fn in (
        ("setFixedSize", setFixedSize), ("setFixedWidth", setFixedWidth),
        ("setFixedHeight", setFixedHeight), ("setMinimumSize", setMinimumSize),
        ("setMinimumWidth", setMinimumWidth), ("setMinimumHeight", setMinimumHeight),
        ("resize", resize),
    ):
        try:
            setattr(QWidget, name, fn)
        except Exception:
            pass

    _patched = True


# ---------------------------------------------------------------------------
# 3. Patch stylesheet  (font-size / padding / min-height dalam px)
# ---------------------------------------------------------------------------

_PX_RE = re.compile(r"(?<![\w.-])(\d+)px")


def scale_stylesheet(sheet: str) -> str:
    """Skalakan seluruh nilai `Npx` di dalam stylesheet Qt.

    Nilai < 6px (border, garis pemisah) dibiarkan agar tidak hilang.
    """
    if not sheet or R.s >= 0.999 or _SHEET_MARK in sheet:
        return sheet

    def repl(m: re.Match) -> str:
        v = int(m.group(1))
        if v < PX_SCALE_THRESHOLD:
            return m.group(0)
        return f"{max(PX_SCALE_THRESHOLD, int(round(v * R.s)))}px"

    return _PX_RE.sub(repl, sheet) + _SHEET_MARK


def _patch_stylesheets() -> None:
    o_widget_ss = QWidget.setStyleSheet
    o_app_ss = QApplication.setStyleSheet

    def w_ss(self, sheet):
        return o_widget_ss(self, scale_stylesheet(sheet))

    def a_ss(self, sheet):
        return o_app_ss(self, scale_stylesheet(sheet))

    try:
        QWidget.setStyleSheet = w_ss
        QApplication.setStyleSheet = a_ss
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 4. Dialog: auto-fit + auto-scroll
# ---------------------------------------------------------------------------

def wrap_scrollable(dlg: QWidget, horizontal: bool = False) -> bool:
    """Pindahkan layout `dlg` ke dalam QScrollArea.

    Dipakai untuk dialog yang lebih tinggi dari layar: isinya tetap utuh,
    pengguna tinggal menggulir. Mengembalikan True jika berhasil dibungkus.
    """
    if dlg is None or dlg.property("_rs_wrapped"):
        return False
    old = dlg.layout()
    if old is None:
        return False
    try:
        inner = QWidget()
        inner.setObjectName("rsScrollBody")
        inner.setLayout(old)          # memindahkan layout & seluruh anaknya

        scroll = QScrollArea(dlg)
        scroll.setObjectName("rsScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded if horizontal
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(inner)
        # Latar transparan agar tema/stylesheet dialog tetap terlihat.
        scroll.viewport().setAutoFillBackground(False)
        scroll.setStyleSheet("QScrollArea#rsScrollArea{background:transparent;}"
                             "QWidget#rsScrollBody{background:transparent;}")

        outer = QVBoxLayout(dlg)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll)

        dlg.setProperty("_rs_wrapped", True)
        return True
    except Exception:
        return False


def fit_to_screen(w: QWidget, center: bool = True) -> None:
    """Pastikan sebuah jendela/dialog muat di layar; gulir jika perlu."""
    if w is None or not w.isWindow():
        return
    try:
        avail = R.avail()
        max_w, max_h = R.max_w(), R.max_h()

        hint = w.sizeHint()
        need_w = max(w.width(), hint.width())
        need_h = max(w.height(), hint.height())

        too_tall = need_h > max_h
        too_wide = need_w > max_w

        if too_tall or too_wide:
            # Lepas kunci ukuran tetap supaya bisa dikecilkan.
            if w.minimumHeight() > max_h or w.minimumWidth() > max_w:
                raw(w, "setMinimumSize",
                    min(w.minimumWidth(), max_w), min(w.minimumHeight(), max_h))
            w.setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX)
            wrap_scrollable(w, horizontal=too_wide)
            raw(w, "resize", min(need_w, max_w), min(need_h, max_h))

        if center:
            g = w.frameGeometry()
            g.moveCenter(avail.center())
            # Jangan sampai title bar keluar dari layar atas.
            x = max(avail.left(), min(g.left(), avail.right() - w.width()))
            y = max(avail.top(), min(g.top(), avail.bottom() - w.height()))
            w.move(x, y)
    except Exception:
        pass


class _ShowFilter(QObject):
    """Menangkap event Show pada dialog/jendela lalu merapikannya."""

    def eventFilter(self, obj, ev):
        try:
            if ev.type() == QEvent.Type.Show and isinstance(obj, QWidget) and obj.isWindow():
                if isinstance(obj, QDialog):
                    QTimer.singleShot(0, lambda o=obj: fit_to_screen(o))
                elif isinstance(obj, QMainWindow):
                    QTimer.singleShot(0, lambda o=obj: _fit_main_window(o))
        except Exception:
            pass
        return False


def _fit_main_window(w: QMainWindow) -> None:
    """Jendela utama: cukup dipastikan tidak melebihi layar (tanpa scroll wrap)."""
    try:
        if w.isMaximized() or w.isFullScreen():
            return
        if w.width() > R.max_w() or w.height() > R.max_h():
            raw(w, "resize", R.clamp_w(w.width()), R.clamp_h(w.height()))
        if R.is_small:
            # Di layar kecil, maksimalkan saja — ruang terlalu berharga.
            w.showMaximized()
    except Exception:
        pass


_filter: Optional[_ShowFilter] = None


# ---------------------------------------------------------------------------
# 5. Helper tabel
# ---------------------------------------------------------------------------

def make_table_responsive(table: QTableView,
                          min_col: int = 70,
                          comfort_col: int = 110,
                          max_col: int = 280,
                          row_h: int = 24,
                          header_h: int = 26) -> None:
    """Membuat QTableView/QTableWidget nyaman di layar sempit.

    Keputusan Stretch vs Interactive diambil dari perhitungan muat-tidaknya:
    bila `jumlah_kolom x comfort_col` masih muat di lebar layar, mode Stretch
    dipertahankan supaya tabel mengisi penuh (mis. tabel rekap 5 kolom).
    Bila tidak muat — mis. 20 kolom di layar 1366 px, yang hanya menyisakan
    ~65 px per kolom — mode diubah ke Interactive plus scroll horizontal
    sehingga tiap kolom punya lebar layak dan teks tidak terpotong.

    Selain itu: tinggi baris & header ikut faktor skala, scroll per piksel,
    dan teks di-elide (…) alih-alih terpotong mentah.
    """
    if table is None:
        return
    try:
        hdr = table.horizontalHeader()
        try:
            cols = table.model().columnCount() if table.model() is not None else 0
        except Exception:
            cols = 0

        hdr.setMinimumSectionSize(R.px(min_col))
        raw(hdr, "setFixedHeight", R.px(header_h))

        need = cols * R.px(comfort_col)
        fits = bool(cols) and need <= R.avail().width() * 0.92

        if fits:
            hdr.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        else:
            hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            hdr.setStretchLastSection(True)
            table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        table.verticalHeader().setDefaultSectionSize(R.px(row_h))
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        if fits:
            return
        # Batasi lebar kolom agar tidak ada satu kolom raksasa yang mendorong
        # sisanya keluar layar.
        cap = R.px(max_col)
        for c in range(cols):
            if hdr.sectionSize(c) > cap:
                hdr.resizeSection(c, cap)
    except Exception:
        pass


def autofit_columns(table: QTableView, max_col: int = 280) -> None:
    """Sesuaikan lebar kolom ke isi, dengan batas atas agar tetap terbaca."""
    try:
        table.resizeColumnsToContents()
        hdr = table.horizontalHeader()
        cap = R.px(max_col)
        for c in range(table.model().columnCount()):
            if hdr.sectionSize(c) > cap:
                hdr.resizeSection(c, cap)
    except Exception:
        pass


def apply_to_all_tables(root: QWidget, **kw) -> int:
    """Terapkan `make_table_responsive` ke seluruh tabel di dalam `root`."""
    n = 0
    try:
        for t in root.findChildren(QTableView):
            make_table_responsive(t, **kw)
            n += 1
    except Exception:
        pass
    return n


# ---------------------------------------------------------------------------
# 6. Helper sidebar / dock
# ---------------------------------------------------------------------------

def dock_width(preferred: int = 320, minimum: int = 230) -> int:
    """Lebar sidebar yang proporsional terhadap layar.

    1920 px → 320 px (tetap).  1366 px → ~272 px.  1093 px (125%) → ~245 px.
    Sidebar tidak boleh memakan lebih dari ~26% lebar layar, karena tabel
    di sebelahnya masih butuh ruang.
    """
    by_scale = int(preferred * R.s)
    by_ratio = int(R.avail().width() * 0.26)
    return max(minimum, min(preferred, by_scale, by_ratio))


def make_dock_responsive(dock: QDockWidget, body: Optional[QWidget] = None,
                         preferred: int = 320) -> None:
    """Kunci lebar dock secara proporsional dan pastikan isinya bisa digulir."""
    if dock is None:
        return
    try:
        w = dock_width(preferred)
        raw(dock, "setMinimumWidth", w)
        dock.setMaximumWidth(w)
        body = body or dock.widget()
        if body is not None:
            # Minimum saja, bukan fixed — agar tidak melawan layout dock.
            raw(body, "setMinimumWidth", 0)
            body.setMaximumWidth(QWIDGETSIZE_MAX)
            ensure_scrollable(body)
    except Exception:
        pass


def ensure_scrollable(w: QWidget) -> bool:
    """Bungkus `w` dengan QScrollArea bila belum punya satu pun di dalamnya."""
    try:
        if w.findChildren(QScrollArea):
            return False
        return wrap_scrollable(w)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 7. Entry point
# ---------------------------------------------------------------------------

def simulate_screen(width: int, height: int) -> None:
    """Paksa metrik memakai ukuran layar tertentu (untuk pengujian QA).

    Panggil SETELAH `install()`, mis. `responsive.simulate_screen(1366, 728)`
    agar bisa menguji tampilan laptop kecil dari monitor besar. Jangan dipakai
    di build produksi.
    """
    R._rect = QRect(0, 0, width, height)
    R._scale = None
    print(f"[responsive] SIMULASI layar {width}x{height} | skala {R.s:.2f}")


def install(app: QApplication,
            scale_sizes: bool = True,
            scale_styles: bool = True,
            auto_scroll_dialogs: bool = True,
            scale_font: bool = True,
            verbose: bool = True) -> None:
    """Pasang seluruh lapisan adaptasi. Panggil tepat setelah QApplication dibuat.

    Semua opsi bisa dimatikan satu per satu bila ada efek samping tak terduga
    pada bagian UI tertentu.
    """
    global _filter

    R.refresh()

    if scale_sizes:
        _patch_sizes()
    if scale_styles:
        _patch_stylesheets()

    if scale_font:
        try:
            f = app.font()
            base = f.pointSize() if f.pointSize() > 0 else 9
            f.setPointSize(R.pt(base))
            app.setFont(f)
        except Exception:
            pass

    if auto_scroll_dialogs:
        try:
            _filter = _ShowFilter()
            app.installEventFilter(_filter)
        except Exception:
            _filter = None

    # Hitung ulang bila pengguna memindah jendela ke monitor lain / ganti DPI.
    try:
        for scr in QGuiApplication.screens():
            scr.geometryChanged.connect(lambda *_: R.refresh())
            scr.logicalDotsPerInchChanged.connect(lambda *_: R.refresh())
    except Exception:
        pass

    if verbose:
        a = R.avail()
        print(f"[responsive] layar {a.width()}x{a.height()} | skala {R.s:.2f} | "
              f"small={R.is_small} tiny={R.is_tiny}")
