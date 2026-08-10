from PyQt6.QtWidgets import (QWidget, QLabel, QPushButton, QFrame, QVBoxLayout, 
                             QHBoxLayout, QGridLayout, QScrollArea, QDialog, 
                             QMessageBox, QInputDialog, QSpacerItem, QSizePolicy)
from PyQt6.QtGui import QPixmap, QImage, QIcon, QFont, QCursor
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal
from google.cloud.firestore_v1.base_query import FieldFilter 
import qrcode
import io
import uuid
from datetime import datetime, timezone, timedelta
from backend import database
from firebase_admin import firestore 

# --- CLASS SINYAL (JEMBATAN THREADING - WAJIB ADA) ---
class DeviceSignals(QObject):
    update_data = pyqtSignal(list)        # Sinyal update data mentah
    device_connected = pyqtSignal(str)    
    request_refresh = pyqtSignal()        
    request_nav = pyqtSignal(int)         

class PerangkatController:
    def __init__(self, main_window):
        self.main = main_window
        self.layout_utama = None
        self.container_devices = None
        self.grid_devices = None
        self.dialog_qr = None
        self.current_qr_session = None
        self.listener_devices = None
        self.timer_cek = None
        
        # Simpan data lokal
        self.local_device_data = [] 
        
        # Timer UI Internal (Update tampilan tiap 5 detik)
        self.timer_ui_refresh = QTimer()
        self.timer_ui_refresh.timeout.connect(self.refresh_tampilan_internal)
        
        # Inisialisasi Sinyal
        self.signals = DeviceSignals()
        self.signals.update_data.connect(self.handle_database_update)
        self.signals.device_connected.connect(self.on_device_connected)
        self.signals.request_refresh.connect(self.handle_refresh)
        self.signals.request_nav.connect(self.handle_navigasi)

    def setup_halaman_perangkat(self):
        """Membangun ulang tampilan Perangkat"""
        try:
            self.bersihkan_ui_bawaan()

            if self.main.pagePerangkat.layout():
                QWidget().setLayout(self.main.pagePerangkat.layout())
            
            self.layout_utama = QVBoxLayout(self.main.pagePerangkat)
            self.layout_utama.setContentsMargins(40, 40, 40, 40)
            self.layout_utama.setSpacing(20)

            # HEADER
            header_layout = QHBoxLayout()
            lbl_judul = QLabel("Manajemen Perangkat")
            lbl_judul.setStyleSheet("font-size: 28px; font-weight: 900; color: #1E293B; letter-spacing: -0.5px;")
            
            self.btn_tambah = QPushButton("+ Hubungkan Baru")
            self.btn_tambah.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_tambah.setFixedHeight(45)
            self.btn_tambah.setStyleSheet("""
                QPushButton { background-color: #2563EB; color: white; border-radius: 12px; padding: 0 25px; font-weight: bold; font-size: 14px; border-bottom: 4px solid #1E40AF; }
                QPushButton:hover { background-color: #1D4ED8; margin-top: 2px; border-bottom: 2px solid #1E40AF; }
                QPushButton:disabled { background-color: #94A3B8; border: none; color: #F1F5F9; }
            """)
            self.btn_tambah.clicked.connect(self.buka_dialog_qr)

            header_layout.addWidget(lbl_judul)
            header_layout.addStretch()
            header_layout.addWidget(self.btn_tambah)
            self.layout_utama.addLayout(header_layout)

            # SCROLL AREA
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setStyleSheet("""
                QScrollArea { border: none; background: transparent; }
                QScrollBar:vertical { width: 8px; background: #F1F5F9; }
                QScrollBar::handle:vertical { background: #CBD5E1; border-radius: 4px; }
            """)
            
            self.container_devices = QWidget()
            self.container_devices.setStyleSheet("background-color: transparent;")
            
            self.grid_devices = QGridLayout(self.container_devices)
            self.grid_devices.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            self.grid_devices.setSpacing(25)
            
            scroll.setWidget(self.container_devices)
            self.layout_utama.addWidget(scroll)

            # [PENTING] Lazy Loading: Jangan load data di sini agar start-up cepat
            # self.muat_daftar_perangkat() 
            self.timer_ui_refresh.start(5000) 

        except Exception as e:
            print(f"⚠️ Error Setup Perangkat: {e}")

    def bersihkan_ui_bawaan(self):
        widgets_to_hide = ["lblJudulPerangkat", "cardQrContainer", "frame_4", "lblQrCode", "btnRefreshQr", "lblStatusKoneksi"]
        for name in widgets_to_hide:
            if hasattr(self.main, name):
                widget = getattr(self.main, name)
                if widget:
                    widget.setVisible(False)
                    widget.setParent(None)

    def muat_daftar_perangkat(self):
        user = getattr(self.main, 'user', {})
        nip = user.get('nip')
        if not nip: return

        # PERBAIKAN: HAPUS FILTER 'connected' agar bisa baca status 'disconnected'
        doc_ref = database.db.collection("remote_sessions").where(filter=FieldFilter("nip", "==", nip))
        
        def on_snapshot(docs, changes, read_time):
            data_list = []
            for doc in docs:
                d = doc.to_dict()
                d['id'] = doc.id
                # Filter manual: Tampilkan semua KECUALI yang masih 'waiting' (QR belum discan)
                if d.get('status') != 'waiting':
                    data_list.append(d)
            
            self.signals.update_data.emit(data_list)

            # Cek Command
            for change in changes:
                if change.type.name == 'MODIFIED':
                    doc_data = change.document.to_dict()
                    last_cmd = doc_data.get('last_command')
                    cmd = doc_data.get('command')
                    
                    if last_cmd == "refresh_ui":
                        database.db.collection("remote_sessions").document(change.document.id).update({"last_command": "none"})
                        self.signals.request_refresh.emit()

                    if cmd == "buka_dashboard":
                        database.db.collection("remote_sessions").document(change.document.id).update({"command": "none"})
                        self.signals.request_nav.emit(0)
                    elif cmd == "buka_kelas":
                        database.db.collection("remote_sessions").document(change.document.id).update({"command": "none"})
                        self.signals.request_nav.emit(1)

        if self.listener_devices: pass 
        self.listener_devices = doc_ref.on_snapshot(on_snapshot)

    def handle_database_update(self, data_list):
        self.local_device_data = data_list
        self.render_grid_devices()

    def refresh_tampilan_internal(self):
        """Update tampilan waktu/status tanpa request DB baru"""
        if self.local_device_data:
            self.render_grid_devices()

    def render_grid_devices(self):
        # Bersihkan Grid
        for i in reversed(range(self.grid_devices.count())): 
            widget = self.grid_devices.itemAt(i).widget()
            if widget: widget.setParent(None)

        if not self.local_device_data:
            self.tampilkan_empty_state()
            self.btn_tambah.setEnabled(True)
            self.btn_tambah.setText("+ Hubungkan Baru")
            return

        count = 0
        row, col = 0, 0
        max_col = 2 

        for data in self.local_device_data:
            card = self.buat_kartu_device(data)
            self.grid_devices.addWidget(card, row, col)
            col += 1
            if col >= max_col:
                col = 0
                row += 1
            count += 1

        if count >= 10:
            self.btn_tambah.setText(f"Limit Penuh ({count}/10)")
            self.btn_tambah.setEnabled(False)
        else:
            self.btn_tambah.setText(f"+ Hubungkan Baru ({count}/10)")
            self.btn_tambah.setEnabled(True)

    def tampilkan_empty_state(self):
        container_empty = QFrame()
        container_empty.setStyleSheet("background: transparent; border: none;")
        layout_empty = QVBoxLayout(container_empty)
        layout_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_empty.setSpacing(10)

        lbl_icon = QLabel("📱") 
        lbl_icon.setStyleSheet("font-size: 80px; color: #CBD5E1; border:none;")
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_judul = QLabel("Belum Ada Perangkat")
        lbl_judul.setStyleSheet("font-size: 18px; font-weight: 800; color: #64748B; border:none;")
        lbl_judul.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_sub = QLabel("Scan QR Code untuk menghubungkan HP Anda.")
        lbl_sub.setStyleSheet("font-size: 14px; color: #94A3B8; border:none;")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout_empty.addWidget(lbl_icon)
        layout_empty.addWidget(lbl_judul)
        layout_empty.addWidget(lbl_sub)
        self.grid_devices.addWidget(container_empty, 0, 0, 1, 2) 

    # --- LOGIKA STATUS & WAKTU CERDAS ---
    def hitung_status_detail(self, status_db, last_update_ts):
        """Menentukan status Online/Idle/Disconnected"""
        
        # 1. Cek Status Eksplisit (Logout dari HP)
        if status_db == "disconnected":
            return "🔴 Terputus (Log Out)", "#EF4444", "border-left: 6px solid #EF4444;"
        
        # 2. Cek Status Eksplisit (Diputus Admin)
        if status_db == "disconnected_by_host":
            return "🔴 Terputus (Oleh Admin)", "#EF4444", "border-left: 6px solid #EF4444;"

        if not last_update_ts:
            return "⚪ Menunggu Data...", "#64748B", "border-left: 6px solid #CBD5E1;"
        
        # 3. Cek Waktu (Idle vs Online)
        try:
            last_active = last_update_ts.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            diff = (now - last_active).total_seconds()
            
            # Toleransi 70 detik (HP kirim heartbeat tiap 30-60s)
            if diff < 70: 
                return "🟢 Online (Sedang Aktif)", "#10B981", "border-left: 6px solid #10B981;"
            else:
                menit = int(diff / 60)
                return f"⚪ Tidak Aktif ({menit} menit lalu)", "#F59E0B", "border-left: 6px solid #F59E0B;"
        except:
            return "⚪ Status Unknown", "#64748B", "border-left: 6px solid #CBD5E1;"

    def format_jam(self, timestamp):
        if not timestamp: return "-"
        try:
            # Sederhana: Tambah 7 jam untuk WIB
            dt = timestamp + timedelta(hours=7) 
            return dt.strftime("%d %b, %H:%M")
        except: return "-"

    def buat_kartu_device(self, data):
        card = QFrame()
        card.setFixedSize(450, 160)
        
        # Ambil Data Status
        status_db = data.get('status') # connected / disconnected
        last_up = data.get('last_update')
        created_at = data.get('created_at')
        
        # Hitung Status Tampilan
        stat_txt, stat_col, border_style = self.hitung_status_detail(status_db, last_up)
        
        waktu_login = self.format_jam(created_at)
        waktu_akses = self.format_jam(last_up)

        nama_tampil = data.get('custom_name') or data.get('connected_device', 'Unknown Device')
        nama_asli = data.get('connected_device', 'Unknown')

        card.setStyleSheet(f"""
            QFrame {{ background-color: white; border: 1px solid #E2E8F0; border-radius: 16px; {border_style} }}
            QFrame:hover {{ border-color: #3B82F6; background-color: #F8FAFC; }}
        """)
        
        layout = QHBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl_icon = QLabel("📱")
        lbl_icon.setStyleSheet("font-size: 48px; border: none; background: transparent;")
        layout.addWidget(lbl_icon)

        layout_info = QVBoxLayout()
        layout_info.setSpacing(2)
        
        lbl_nama = QLabel(nama_tampil)
        lbl_nama.setStyleSheet("font-size: 16px; font-weight: 800; color: #1E293B; border: none; background: transparent;")
        
        lbl_status = QLabel(stat_txt)
        lbl_status.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {stat_col}; border: none; background: transparent;")

        lbl_waktu = QLabel(f"Login: {waktu_login}\nAkses: {waktu_akses}")
        lbl_waktu.setStyleSheet("font-size: 11px; color: #64748B; margin-top: 5px; border: none; background: transparent;")

        layout_info.addWidget(lbl_nama)
        layout_info.addWidget(lbl_status)
        layout_info.addWidget(lbl_waktu)
        layout_info.addStretch()
        layout.addLayout(layout_info)

        # BUTTONS
        layout_btn = QVBoxLayout()
        layout_btn.setSpacing(8)
        
        # Tombol Khusus: Jika sudah terputus, ganti jadi "Hapus Riwayat"
        if "disconnected" in status_db:
             btn_aksi = QPushButton("Hapus Riwayat")
             btn_aksi.setCursor(Qt.CursorShape.PointingHandCursor)
             btn_aksi.setStyleSheet("QPushButton { background:#FEF2F2; color:#EF4444; border:1px solid #FECDD3; border-radius:6px; padding:6px; font-weight:700; font-size:11px; } QPushButton:hover { background:#FFE4E6; }")
             # Hapus dokumen dari Firestore
             btn_aksi.clicked.connect(lambda: database.db.collection("remote_sessions").document(data['id']).delete())
        else:
             btn_aksi = QPushButton("Putuskan")
             btn_aksi.setCursor(Qt.CursorShape.PointingHandCursor)
             btn_aksi.setStyleSheet("QPushButton { background:#FEF2F2; color:#EF4444; border:1px solid #FECDD3; border-radius:6px; padding:6px; font-weight:700; font-size:11px; } QPushButton:hover { background:#FFE4E6; }")
             btn_aksi.clicked.connect(lambda: self.aksi_putuskan(data['id']))

        btn_edit = QPushButton("Edit Nama")
        btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_edit.setStyleSheet("QPushButton { background-color: #EFF6FF; color: #2563EB; border: 1px solid #DBEAFE; border-radius: 6px; padding: 6px 12px; font-size: 11px; font-weight: 700; } QPushButton:hover { background-color: #DBEAFE; }")
        btn_edit.clicked.connect(lambda: self.aksi_ubah_nama(data['id'], nama_tampil))

        layout_btn.addWidget(btn_edit)
        layout_btn.addWidget(btn_aksi)
        layout.addLayout(layout_btn)

        return card

    # --- SISA KODE (QR, DIALOG) ---
    def buka_dialog_qr(self):
        self.dialog_qr = QDialog(self.main)
        self.dialog_qr.setWindowTitle("Scan QR Code")
        self.dialog_qr.setFixedSize(380, 480)
        self.dialog_qr.setStyleSheet("background-color: white;")
        layout = QVBoxLayout(self.dialog_qr)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)
        
        lbl_judul = QLabel("Scan untuk Menghubungkan")
        lbl_judul.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_judul.setStyleSheet("font-size: 18px; font-weight: 800; color: #1E293B;")
        
        self.lbl_qr_image = QLabel()
        self.lbl_qr_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_qr_image.setFixedSize(300, 300)
        self.lbl_qr_image.setStyleSheet("border: 2px dashed #CBD5E1; border-radius: 12px; margin: 0 auto;")

        lbl_info = QLabel("Buka Aplikasi Web GuruPro di HP,\nlalu arahkan kamera ke kode di atas.")
        lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_info.setStyleSheet("color: #64748B; font-size: 13px;")

        layout.addWidget(lbl_judul)
        layout.addWidget(self.lbl_qr_image, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_info)
        
        self.generate_qr_session()
        self.timer_cek = QTimer(self.dialog_qr)
        self.timer_cek.timeout.connect(self.cek_status_connect_dialog)
        self.timer_cek.start(1500) 
        self.dialog_qr.exec()

    def generate_qr_session(self):
        try:
            self.current_qr_session = str(uuid.uuid4())[:8]
            user = getattr(self.main, 'user', {})
            data = {
                "status": "waiting",
                "created_at": firestore.SERVER_TIMESTAMP,
                "last_update": firestore.SERVER_TIMESTAMP,
                "nama_guru": user.get('nama_lengkap', 'Guru'),
                "nip": user.get('nip', '-'),
                "jabatan": user.get('jabatan', 'Guru'),
                "mapel": user.get('mapel', '-'),
                "connected_device": "-",
                "custom_name": "" 
            }
            database.db.collection("remote_sessions").document(self.current_qr_session).set(data)
            link = f"https://gurupro-app-bc6cc.web.app/?sid={self.current_qr_session}"
            qr = qrcode.QRCode(box_size=10, border=1)
            qr.add_data(link)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            pixmap = QPixmap.fromImage(QImage.fromData(buffer.getvalue()))
            self.lbl_qr_image.setPixmap(pixmap.scaled(250, 250, Qt.AspectRatioMode.KeepAspectRatio))
        except Exception as e:
            print(f"Gagal generate QR: {e}")

    def cek_status_connect_dialog(self):
        if not self.current_qr_session: return
        doc = database.db.collection("remote_sessions").document(self.current_qr_session).get()
        if doc.exists:
            data = doc.to_dict()
            if data.get('status') == 'connected':
                self.timer_cek.stop()
                self.signals.device_connected.emit(data.get('connected_device'))

    def on_device_connected(self, device_name):
        if self.dialog_qr: self.dialog_qr.accept()
        QMessageBox.information(self.main, "Berhasil", f"Perangkat '{device_name}' berhasil terhubung!")

    def aksi_ubah_nama(self, doc_id, nama_lama):
        nama_baru, ok = QInputDialog.getText(self.main, "Ubah Nama Perangkat", "Berikan nama identitas:", text=nama_lama)
        if ok and nama_baru:
            database.db.collection("remote_sessions").document(doc_id).update({"custom_name": nama_baru})

    def aksi_putuskan(self, doc_id):
        if QMessageBox.question(self.main, "Konfirmasi", "Putuskan koneksi perangkat ini?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            database.db.collection("remote_sessions").document(doc_id).update({"status": "disconnected_by_host"})

    def handle_refresh(self):
        if hasattr(self.main, 'laporan_ctrl'):
            self.main.laporan_ctrl.aksi_tampilkan_laporan()

    def handle_navigasi(self, index):
        self.main.stackedWidget.setCurrentIndex(index)