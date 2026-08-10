from PyQt6.QtWidgets import (QWidget, QLabel, QPushButton, QFrame, QVBoxLayout, 
                             QHBoxLayout, QSpacerItem, QSizePolicy, QInputDialog, 
                             QMessageBox, QFileDialog)
from PyQt6.QtCore import Qt, QSize
from backend import database
import pandas as pd

class KelasController:
    def __init__(self, main_window):
        self.main = main_window
        self.dataset_kelas = [] 

    def setup_halaman_kelas(self):
        """Menghubungkan elemen UI statis dari Qt Designer"""
        try:
            # 1. Bersihkan koneksi lama
            try: self.main.btnBuatKelas.clicked.disconnect()
            except: pass
            
            # 2. Hubungkan Tombol "+ Buat Kelas Baru" yang ada di header
            self.main.btnBuatKelas.clicked.connect(self.aksi_buat_kelas)
            
            # 3. Filter & Pencarian
            self.main.inputCariKelas.textChanged.connect(self.refresh_tampilan)
            self.main.comboFilterSemester.currentIndexChanged.connect(self.refresh_tampilan)

            if self.main.comboFilterSemester.count() == 0:
                self.main.comboFilterSemester.addItems(["Semua Semester", "Ganjil", "Genap"])

            # [PENTING] Baris ini DIHAPUS agar tidak freeze saat start up.
            # Data hanya akan dimuat saat tombol sidebar "Data Kelas" diklik.
            # self.muat_data_database() 
            
        except Exception as e:
            print(f"⚠️ Error Setup Kelas: {e}")

    def muat_data_database(self):
        """Ambil data dari Firebase Cloud"""
        nip = self.main.user.get('nip')
        if not nip: return
        self.dataset_kelas = database.ambil_daftar_kelas(nip)
        self.refresh_tampilan()

    def refresh_tampilan(self):
        """Render Kartu Kelas secara dinamis ke dalam scrollContentKelas"""
        container = self.main.scrollContentKelas
        layout = container.layout()
        if not layout:
            layout = QVBoxLayout(container)
            container.setLayout(layout)
            layout.setContentsMargins(15, 15, 15, 15)
            layout.setSpacing(20)
        
        # Hapus kartu lama agar tidak tumpang tindih
        while layout.count():
            item = layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        keyword = self.main.inputCariKelas.text().lower()
        filter_sem = self.main.comboFilterSemester.currentText()

        # Filter data
        data_tampil = [d for d in self.dataset_kelas if 
                       (filter_sem == "Semua Semester" or d.get('semester') == filter_sem) and
                       (keyword in d.get('nama_kelas', '').lower() or keyword in d.get('mata_pelajaran', '').lower())]

        self.main.lblTotalKelas.setText(f"Menampilkan {len(data_tampil)} Kelas")

        if not data_tampil:
            lbl = QLabel("Belum ada data kelas.")
            lbl.setStyleSheet("color: #94A3B8; font-size: 14px; font-style: italic;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)
        else:
            for data in reversed(data_tampil):
                # Sinkronkan jumlah siswa dari Firebase realtime
                data['jumlah_siswa'] = database.ambil_jumlah_siswa(data['id'])
                card = self.buat_kartu_ui(data)
                layout.addWidget(card)
            layout.addStretch()

    def buat_kartu_ui(self, data):
        """Membangun kartu dengan Action Strip (Hapus, Impor, Masuk)"""
        card = QFrame()
        card.setMinimumHeight(180)
        card.setStyleSheet("""
            QFrame { background-color: white; border: 1px solid #E2E8F0; border-radius: 20px; }
            QFrame:hover { border-color: #2563EB; }
        """)

        main_layout = QHBoxLayout(card)
        
        # Aksen Biru di Samping
        accent = QFrame()
        accent.setFixedWidth(8)
        accent.setStyleSheet("background-color: #2563EB; border-radius: 4px; border:none;")
        main_layout.addWidget(accent)

        # Bagian Informasi (Kiri)
        info_v = QVBoxLayout()
        info_v.setContentsMargins(15, 10, 15, 10)
        
        lbl_mapel = QLabel(data.get('mata_pelajaran', 'Mapel'))
        lbl_mapel.setStyleSheet("font-size: 18px; font-weight: 800; color: #1E293B; border:none;")
        
        lbl_kelas = QLabel(f"{data.get('nama_kelas')} | 👥 {data.get('jumlah_siswa', 0)} Siswa")
        lbl_kelas.setStyleSheet("font-size: 14px; color: #3B82F6; font-weight: 700; border:none;")
        
        lbl_jadwal = QLabel(f"📅 {data.get('jadwal')}")
        lbl_jadwal.setStyleSheet("font-size: 12px; color: #64748B; border:none;")

        info_v.addWidget(lbl_mapel)
        info_v.addWidget(lbl_kelas)
        info_v.addWidget(lbl_jadwal)
        info_v.addStretch()
        main_layout.addLayout(info_v)

        # Bagian Tombol Aksi (Kanan)
        btn_v = QVBoxLayout()
        btn_v.setSpacing(8)
        
        btn_masuk = QPushButton("Masuk Kelas")
        btn_masuk.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_masuk.setStyleSheet("QPushButton{background:#2563EB; color:white; font-weight:800; border-radius:10px; padding:12px; min-width:140px;} QPushButton:hover{background:#1D4ED8;}")
        btn_masuk.clicked.connect(lambda: self.aksi_masuk_kelas(data))

        btn_h = QHBoxLayout()
        # TOMBOL IMPOR EXCEL (Sekarang di dalam kartu!)
        btn_impor = QPushButton("Impor")
        btn_impor.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_impor.setStyleSheet("QPushButton{background:#F0FDF4; color:#166534; border:1px solid #BBF7D0; font-weight:700; border-radius:8px; padding:8px;} QPushButton:hover{background:#DCFCE7;}")
        btn_impor.clicked.connect(lambda _, id_k=data['id'], nm_k=data['nama_kelas']: self.aksi_import_siswa_langsung(id_k, nm_k))

        btn_hapus = QPushButton("Hapus")
        btn_hapus.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_hapus.setStyleSheet("QPushButton{background:#FFF1F2; color:#BE123C; border:1px solid #FECDD3; font-weight:700; border-radius:8px; padding:8px;} QPushButton:hover{background:#FFE4E6;}")
        btn_hapus.clicked.connect(lambda _, id_k=data['id'], nm_k=data['nama_kelas']: self.aksi_hapus_kelas(id_k, nm_k))

        btn_h.addWidget(btn_impor)
        btn_h.addWidget(btn_hapus)
        
        btn_v.addStretch()
        btn_v.addWidget(btn_masuk)
        btn_v.addLayout(btn_h)
        main_layout.addLayout(btn_v)

        return card

    def aksi_buat_kelas(self):
        """Memunculkan Input Dialog untuk membuat kelas baru"""
        if not self.main.user: return
        nama, ok = QInputDialog.getText(self.main, "Buat Kelas", "Nama Kelas (Misal: X-IPA 1):")
        if not ok or not nama: return
        mapel, ok = QInputDialog.getText(self.main, "Buat Kelas", "Mata Pelajaran:")
        if not ok or not mapel: return
        sem, ok = QInputDialog.getItem(self.main, "Semester", "Pilih Semester:", ["Ganjil", "Genap"], 0, False)
        if not ok: return
        jadwal, ok = QInputDialog.getText(self.main, "Jadwal", "Input Hari & Jam:")
        if not ok or not jadwal: return

        data_baru = {
            "nip_guru": self.main.user['nip'],
            "nama_kelas": nama,
            "mata_pelajaran": mapel,
            "semester": sem,
            "jadwal": jadwal
        }
        
        sukses, pesan = database.tambah_kelas(data_baru)
        if sukses:
            QMessageBox.information(self.main, "Sukses", pesan)
            self.muat_data_database()
        else:
            QMessageBox.warning(self.main, "Gagal", pesan)

    def aksi_import_siswa_langsung(self, id_kelas, nama_kelas):
        """Fitur Impor Excel yang lebih aman untuk NIS"""
        file_path, _ = QFileDialog.getOpenFileName(self.main, f"Impor Siswa ke {nama_kelas}", "", "Excel (*.xlsx *.xls)")
        if not file_path: return

        try:
            # [PENTING] Gunakan dtype={'nis': str} agar NIS tidak jadi float (12345.0)
            df = pd.read_excel(file_path, dtype={'nis': str})
            
            # Normalisasi nama kolom (kecil semua)
            df.columns = df.columns.str.lower()
            
            # Bersihkan data (hapus baris kosong)
            df = df.dropna(subset=['nis', 'nama'])

            # Konversi dataframe ke list dictionary
            list_siswa = df.to_dict(orient='records')

            if database.simpan_daftar_siswa_massal(id_kelas, list_siswa):
                QMessageBox.information(self.main, "Sukses", f"Berhasil mengimpor {len(list_siswa)} siswa ke {nama_kelas}")
                self.muat_data_database() # Refresh agar jumlah siswa update
            else:
                QMessageBox.critical(self.main, "Gagal", "Gagal menyimpan ke Firebase.")
        except Exception as e:
            QMessageBox.critical(self.main, "Error", f"Pastikan file Excel benar (nis, nama, gender).\nError: {e}")

    def aksi_hapus_kelas(self, doc_id, nama_kelas):
        if QMessageBox.question(self.main, "Hapus", f"Hapus kelas '{nama_kelas}'?") == QMessageBox.StandardButton.Yes:
            if database.hapus_kelas(doc_id):
                self.muat_data_database()

    def aksi_masuk_kelas(self, data_kelas):
        self.main.stackedWidget.setCurrentWidget(self.main.pageMengajar)
        self.main.btnNavKelas.setChecked(False)
        self.main.btnNavMengajar.setChecked(True)
        if hasattr(self.main, 'mengajar_ctrl'):
            self.main.mengajar_ctrl.buka_kelas_spesifik(data_kelas['id'], data_kelas['nama_kelas'])