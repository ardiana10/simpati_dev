from PyQt6.QtCore import QObject, QTimer, QEvent, QDateTime
from otp_dialog import show_otp_dialog


class GlobalIdleWatcher(QObject):
    def __init__(self, app, timeout_ms=10 * 60 * 1000):
        super().__init__()
        self.app = app
        self.timeout_ms = timeout_ms

        # 🕒 Simpan waktu aktivitas terakhir (pakai UTC supaya stabil)
        self.last_activity = QDateTime.currentDateTimeUtc()

        # Flag: sedang terkunci
        self._locked = False

        # Timer hanya untuk CEK idle, bukan menghitung tepat 10 menit
        self.timer = QTimer(self)
        check_interval = min(5 * 1000, self.timeout_ms)  # cek tiap 5 detik atau kurang
        self.timer.setInterval(check_interval)
        self.timer.timeout.connect(self._check_idle)
        self.timer.start()

        app.installEventFilter(self)

    def eventFilter(self, obj, event):
        # Kalau lagi lock, biarkan event lewat tapi jangan update aktivitas
        if self._locked:
            return False

        if event.type() in (
            QEvent.Type.MouseMove,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.KeyPress,
            QEvent.Type.Wheel,
            QEvent.Type.FocusIn,
        ):
            # Reset aktivitas terakhir ke sekarang
            self.last_activity = QDateTime.currentDateTimeUtc()

            # Pastikan timer hidup (kalau sempat di-stop)
            if not self.timer.isActive():
                self.timer.start()

        return False

    def _check_idle(self):
        """Dipanggil periodik untuk mengecek berapa lama user idle."""
        if self._locked:
            return

        now = QDateTime.currentDateTimeUtc()
        elapsed_ms = self.last_activity.msecsTo(now)

        # Kalau sistem jam mundur (elapsed negatif), reset saja
        if elapsed_ms < 0:
            self.last_activity = now
            return

        if elapsed_ms >= self.timeout_ms:
            self._lock_now()

    def _lock_now(self):
        """Tampilkan dialog OTP dan kunci aplikasi saat idle terlalu lama."""
        if self._locked:
            return

        self._locked = True
        self.timer.stop()  # hentikan cek saat dialog OTP terbuka

        parent = self.app.activeWindow()
        ok = show_otp_dialog(parent)

        # Kalau OTP benar → unlock dan hidupkan lagi idle watcher
        if ok:
            self.last_activity = QDateTime.currentDateTimeUtc()
            self.timer.start()

        self._locked = False