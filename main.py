import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QButtonGroup, QLabel
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.uic import loadUi
from PyQt6.QtCore import Qt, QTimer 

# --- IMPORT MODULE ---
# Pastikan folder root terbaca agar import backend & controllers sukses
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend import database
from controllers.kelas_controller import KelasController
from controllers.mengajar_controller import MengajarController
from controllers.laporan_controller import LaporanController
from controllers.dashboard_controller import DashboardController
from controllers.pengaturan_controller import PengaturanController
from controllers.perangkat_controller import PerangkatController

# ==========================================================
# FUNGSI PENTING: PENCARI JALUR (RESOURCE PATH)
# ==========================================================
def resource_path(relative_path):
    """ Dapatkan path absolut ke resource, wajib untuk build EXE """
    try:
        # Jika dijalankan sebagai EXE (PyInstaller)
        base_path = sys._MEIPASS
    except Exception:
        # Jika dijalankan sebagai script Python biasa
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# ==========================================================
# 1. HALAMAN LOGIN
# ==========================================================
class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Load UI
        ui_path = resource_path(os.path.join("ui", "ui_login.ui"))
        loadUi(ui_path, self)
        
        # Set Icon Aplikasi
        try:
            icon_path = resource_path(os.path.join("asset", "logo.ico"))
            self.setWindowIcon(QIcon(icon_path))
        except:
            pass

        # [UPDATE] Tambahkan Logo di bawah tulisan GURU PRO dengan Smooth Transformation (Agar Tidak Burem)
        try:
            self.lblLogo = QLabel(self.cardLogin)
            
            # Prioritaskan logo.png jika ada, fallback ke logo.ico
            logo_rel = os.path.join("asset", "logo.png")
            if not os.path.exists(resource_path(logo_rel)):
                logo_rel = os.path.join("asset", "logo.ico")
                
            logo_path = resource_path(logo_rel)
            if os.path.exists(logo_path):
                pixmap = QPixmap(logo_path)
                
                # Gunakan SmoothTransformation agar gambar diperbesar dengan mulus dan tidak pecah
                scaled_pixmap = pixmap.scaled(
                    220, 220, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                
                self.lblLogo.setPixmap(scaled_pixmap)
                self.lblLogo.setAlignment(Qt.AlignmentFlag.AlignCenter)
                # Sisipkan logo tepat di bawah lblJudul (indeks 1 dalam layout)
                self.verticalLayout.insertWidget(1, self.lblLogo)
        except Exception as e:
            print(f"Gagal memuat logo di halaman login: {e}")

        # Sembunyikan password & set icon
        self.inputPass.setEchoMode(self.inputPass.EchoMode.Password)
        
        # Hubungkan tombol
        self.btnLogin.clicked.connect(self.proses_login)
        self.btnKeDaftar.clicked.connect(self.buka_register)

    def proses_login(self):
        nip = self.inputUser.text()
        password = self.inputPass.text()
        
        if not nip or not password:
            QMessageBox.warning(self, "Kosong", "NIP dan Password wajib diisi!")
            return

        # Efek Loading agar User tahu aplikasi sedang bekerja
        self.setCursor(Qt.CursorShape.WaitCursor)
        self.btnLogin.setText("Memuat...")
        self.btnLogin.setEnabled(False)

        # Gunakan QTimer agar UI sempat berubah sebelum proses berat dimulai
        QTimer.singleShot(100, lambda: self.eksekusi_cek_login(nip, password))

    def eksekusi_cek_login(self, nip, password):
        sukses, hasil = database.cek_login(nip, password)
        
        # Kembalikan tampilan tombol
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.btnLogin.setText("Masuk Aplikasi")
        self.btnLogin.setEnabled(True)

        if sukses:
            # Masuk ke Dashboard dengan membawa data user
            self.main_window = DashboardWindow(user_data=hasil)
            self.main_window.show()
            self.close()
        else:
            QMessageBox.critical(self, "Gagal Login", hasil)

    def buka_register(self):
        self.reg_window = RegisterWindow()
        self.reg_window.show()
        self.close()

# ==========================================================
# 2. HALAMAN DAFTAR (SIGN UP)
# ==========================================================
class RegisterWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ui_path = resource_path(os.path.join("ui", "ui_signup.ui"))
        loadUi(ui_path, self)
        
        # Set Icon
        try:
            icon_path = resource_path(os.path.join("asset", "logo.ico"))
            self.setWindowIcon(QIcon(icon_path))
        except: pass
        
        self.inputPassReg.setEchoMode(self.inputPassReg.EchoMode.Password)
        self.btnDaftar.clicked.connect(self.proses_daftar)
        self.btnKembaliLogin.clicked.connect(self.buka_login)

    def proses_daftar(self):
        data_baru = {
            "nama_lengkap": self.inputNamaReg.text(),
            "nip": self.inputNipReg.text(),
            "mapel": self.inputMapelReg.text(),
            "password": self.inputPassReg.text()
        }

        if not data_baru["nama_lengkap"] or not data_baru["nip"]:
            QMessageBox.warning(self, "Data Kurang", "Mohon lengkapi data profil!")
            return

        sukses, pesan = database.daftar_guru_baru(data_baru)
        if sukses:
            QMessageBox.information(self, "Sukses", "Akun berhasil dibuat! Silakan Login.")
            self.buka_login()
        else:
            QMessageBox.critical(self, "Gagal", pesan)

    def buka_login(self):
        self.login_window = LoginWindow()
        self.login_window.show()
        self.close()

# ==========================================================
# 3. DASHBOARD UTAMA
# ==========================================================
class DashboardWindow(QMainWindow):
    def __init__(self, user_data):
        super().__init__()
        ui_path = resource_path(os.path.join("ui", "ui_main.ui"))
        loadUi(ui_path, self)
        
        # Set Icon
        try:
            icon_path = resource_path(os.path.join("asset", "logo.ico"))
            self.setWindowIcon(QIcon(icon_path))
        except: pass
        
        self.user = user_data
        
        # Tampilkan Nama di Sidebar
        self.lblNamaUser.setText(self.user.get('nama_lengkap', 'Guru'))

        # INISIALISASI SEMUA CONTROLLER
        self.dashboard_ctrl = DashboardController(self)
        self.kelas_ctrl = KelasController(self)
        self.mengajar_ctrl = MengajarController(self)
        self.laporan_ctrl = LaporanController(self)
        self.pengaturan_ctrl = PengaturanController(self)
        self.perangkat_ctrl = PerangkatController(self)

        # Setup Awal Per Halaman
        self.dashboard_ctrl.setup_halaman_dashboard()
        self.kelas_ctrl.setup_halaman_kelas()
        self.mengajar_ctrl.setup_halaman_mengajar()
        self.laporan_ctrl.setup_halaman_laporan()
        self.pengaturan_ctrl.setup_halaman_pengaturan()
        self.perangkat_ctrl.setup_halaman_perangkat()

        # Navigasi Sidebar
        self.setup_navigasi()
        
        # Lazy Loading (Pindah ke halaman 0 setelah 100ms)
        self.btnNavDashboard.setChecked(True)
        QTimer.singleShot(100, lambda: self.pindah_halaman(0))

    def setup_navigasi(self):
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        nav_buttons = [
            self.btnNavDashboard, 
            self.btnNavKelas, 
            self.btnPerangkat,
            self.btnNavMengajar, 
            self.btnNavLaporan, 
            self.btnNavPengaturan
        ]

        for btn in nav_buttons:
            self.nav_group.addButton(btn) 
            btn.setCheckable(True)        
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus) 

        self.btnNavKeluar.setCheckable(False) 
        self.btnNavKeluar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btnNavKeluar.clicked.connect(self.logout)

        self.btnNavDashboard.clicked.connect(lambda: self.pindah_halaman(0))
        self.btnNavKelas.clicked.connect(lambda: self.pindah_halaman(1))
        self.btnPerangkat.clicked.connect(lambda: self.pindah_halaman(2))
        self.btnNavMengajar.clicked.connect(lambda: self.pindah_halaman(3))
        self.btnNavLaporan.clicked.connect(lambda: self.pindah_halaman(4))
        self.btnNavPengaturan.clicked.connect(lambda: self.pindah_halaman(5))

    def pindah_halaman(self, index):
        pages = [
            self.pageDashboard,   # 0
            self.pageKelas,       # 1
            self.pagePerangkat,   # 2
            self.pageMengajar,    # 3
            self.pageLaporan,     # 4
            self.pagePengaturan   # 5
        ]
        
        self.stackedWidget.setCurrentWidget(pages[index])

        if index == 0:
            self.dashboard_ctrl.muat_data_dashboard()
        elif index == 1:
            self.kelas_ctrl.muat_data_database()
        elif index == 2:
            self.perangkat_ctrl.muat_daftar_perangkat()
        elif index == 4:
            self.laporan_ctrl.muat_list_kelas()
        elif index == 5:
            self.pengaturan_ctrl.muat_data_profil()

    def logout(self):
        if QMessageBox.question(self, "Keluar", "Yakin ingin keluar?") == QMessageBox.StandardButton.Yes:
            database.logout()
            self.login = LoginWindow()
            self.login.show()
            self.close()

# ==========================================================
# EKSEKUSI UTAMA
# ==========================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    try:
        icon_path = resource_path(os.path.join("asset", "logo.ico"))
        app.setWindowIcon(QIcon(icon_path))
    except:
        pass
    
    window = LoginWindow()
    window.show()
    sys.exit(app.exec())
