from PyQt6.QtWidgets import QTableWidgetItem, QComboBox, QMessageBox, QHeaderView, QSpinBox
from PyQt6.QtCore import Qt
from backend import database
from datetime import datetime
from google.cloud.firestore_v1.base_query import FieldFilter

# PASTIKAN NAMA CLASS INI PERSIS 'MengajarController' (Huruf Besar M)
class MengajarController:
    def __init__(self, main_window):
        self.main = main_window
        self.id_kelas_aktif = None
        self.nama_kelas_aktif = None
        self.id_dokumen_aktif = None # ID Dokumen Firebase (untuk mode Edit)

    def setup_halaman_mengajar(self):
        """Inisialisasi Event Listener"""
        try:
            # 1. Setup Tabel (Kolom & Header)
            self.main.tableAbsensi.setColumnCount(6)
            self.main.tableAbsensi.setHorizontalHeaderLabels(["NO", "NIS", "NAMA SISWA", "L/P", "STATUS", "NILAI"])
            
            # --- PERBAIKAN TAMPILAN TABEL ---
            self.main.tableAbsensi.verticalHeader().setDefaultSectionSize(45) 
            self.main.tableAbsensi.verticalHeader().setVisible(False) 
            
            header = self.main.tableAbsensi.horizontalHeader()
            
            # Atur Lebar Kolom (Dipisah per baris agar tidak error syntax)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            self.main.tableAbsensi.setColumnWidth(0, 40)
            
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            self.main.tableAbsensi.setColumnWidth(1, 90)
            
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
            self.main.tableAbsensi.setColumnWidth(3, 50)
            
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
            self.main.tableAbsensi.setColumnWidth(4, 140) 
            
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
            self.main.tableAbsensi.setColumnWidth(5, 80)

            # 2. Koneksi Tombol (Try-Except Multi-line)
            try:
                self.main.btnMulaiSesi.clicked.disconnect()
            except:
                pass
            self.main.btnMulaiSesi.clicked.connect(self.aksi_mulai_absensi)
            
            try:
                self.main.btnSimpanAbsensi.clicked.disconnect()
            except:
                pass
            self.main.btnSimpanAbsensi.clicked.connect(self.aksi_simpan)

            # 3. Koneksi Dropdown Pertemuan (FITUR BARU: Cek Data Saat Ganti Pertemuan)
            try:
                self.main.comboPertemuan.currentIndexChanged.disconnect()
            except:
                pass
            self.main.comboPertemuan.currentIndexChanged.connect(self.cek_data_pertemuan_lama)

            # 4. Isi Dropdown Pertemuan
            self.main.comboPertemuan.clear()
            for i in range(1, 17):
                self.main.comboPertemuan.addItem(f"Pertemuan Ke-{i}")

        except Exception as e:
            print(f"⚠️ Error Setup Mengajar: {e}")

    def buka_kelas_spesifik(self, id_kelas, nama_kelas):
        """Dipanggil saat masuk kelas"""
        self.id_kelas_aktif = id_kelas
        self.nama_kelas_aktif = nama_kelas
        self.id_dokumen_aktif = None # Reset ID dokumen
        
        self.main.lblJudulMengajar.setText(f"MENGAJAR: {nama_kelas.upper()}")
        
        self.main.comboPilihKelas.clear()
        self.main.comboPilihKelas.addItem(nama_kelas, id_kelas)
        self.main.comboPilihKelas.setCurrentIndex(0)
        
        # Reset Tabel & Input
        self.main.tableAbsensi.setRowCount(0)
        self.main.lblTotalHadir.setText("Klik 'Mulai Absensi'...")
        
        if hasattr(self.main, 'inputMateri'): self.main.inputMateri.clear()
        if hasattr(self.main, 'inputCatatanJurnal'): self.main.inputCatatanJurnal.clear()

        # Cek otomatis pertemuan pertama saat buka kelas
        self.cek_data_pertemuan_lama()

    def cek_data_pertemuan_lama(self):
        """
        Mengecek apakah pertemuan yang dipilih sudah ada di database.
        Jika ada, load datanya agar tidak duplikat saat disimpan.
        """
        if not self.id_kelas_aktif: return

        pertemuan_dipilih = self.main.comboPertemuan.currentText()
        print(f"🔍 Mengecek data: {self.nama_kelas_aktif} - {pertemuan_dipilih}")

        try:
            # Query ke Firebase
            docs = database.db.collection('absensi')\
                .where(filter=FieldFilter("id_kelas", "==", self.id_kelas_aktif))\
                .where(filter=FieldFilter("pertemuan", "==", pertemuan_dipilih))\
                .stream()

            ketemu = False
            for doc in docs:
                # DATA DITEMUKAN (Mode Edit)
                data = doc.to_dict()
                self.id_dokumen_aktif = doc.id  # Simpan ID untuk update nanti
                
                # Load Materi & Catatan
                if hasattr(self.main, 'inputMateri'): 
                    self.main.inputMateri.setText(data.get('materi', ''))
                if hasattr(self.main, 'inputCatatanJurnal'): 
                    self.main.inputCatatanJurnal.setText(data.get('catatan_jurnal', ''))
                
                # Load Data Siswa
                list_siswa = data.get('data_siswa', []) or data.get('detail', [])
                self.render_tabel_dengan_data(list_siswa)
                
                print(f"✅ Data lama ditemukan! ID: {doc.id}")
                self.main.btnSimpanAbsensi.setText("Update Absensi")
                ketemu = True
                break 

            if not ketemu:
                # DATA BARU (Mode Create)
                print("ℹ️ Belum ada data untuk pertemuan ini.")
                self.id_dokumen_aktif = None
                self.main.tableAbsensi.setRowCount(0)
                self.main.lblTotalHadir.setText("Klik 'Mulai Absensi' untuk data baru")
                
                if hasattr(self.main, 'inputMateri'): self.main.inputMateri.clear()
                if hasattr(self.main, 'inputCatatanJurnal'): self.main.inputCatatanJurnal.clear()
                self.main.btnSimpanAbsensi.setText("Simpan Absensi")

        except Exception as e:
            print(f"Error cek pertemuan: {e}")

    def aksi_mulai_absensi(self):
        """Tombol 'Mulai Absensi' - Hanya load master jika data belum ada"""
        if not self.id_kelas_aktif:
            QMessageBox.warning(self.main, "Peringatan", "Silakan pilih kelas terlebih dahulu!")
            return

        # Jika sedang menampilkan data lama, konfirmasi reset
        if self.id_dokumen_aktif:
            reply = QMessageBox.question(self.main, "Reset Data?", 
                                         "Data pertemuan ini sudah ada. Reset akan menghapus nilai yang sudah diinput. Lanjutkan?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return 

        daftar_siswa = database.ambil_siswa_per_kelas(self.id_kelas_aktif)
        if not daftar_siswa:
            QMessageBox.information(self.main, "Info", "Belum ada siswa di kelas ini.")
            return

        self.render_tabel_dengan_data(daftar_siswa, is_master_data=True)
        self.id_dokumen_aktif = None # Reset jadi mode create baru
        self.main.btnSimpanAbsensi.setText("Simpan Absensi")

    def render_tabel_dengan_data(self, list_data, is_master_data=False):
        """Render tabel fleksibel (bisa dari Master atau Riwayat)"""
        self.main.tableAbsensi.setRowCount(len(list_data))
        
        for baris, siswa in enumerate(list_data):
            # 1. NO, NIS, NAMA, GENDER
            self.main.tableAbsensi.setItem(baris, 0, QTableWidgetItem(str(baris + 1)))
            self.main.tableAbsensi.setItem(baris, 1, QTableWidgetItem(str(siswa.get('nis', '-'))))
            self.main.tableAbsensi.setItem(baris, 2, QTableWidgetItem("  " + siswa.get('nama', 'Tanpa Nama')))
            
            item_lp = QTableWidgetItem(siswa.get('gender', '-'))
            item_lp.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.main.tableAbsensi.setItem(baris, 3, item_lp)
            
            # 2. STATUS (COMBOBOX)
            combo_status = QComboBox()
            combo_status.addItems(["Hadir", "Sakit", "Izin", "Alpa"])
            combo_status.setStyleSheet("QComboBox { padding-left: 10px; border: 1px solid #CBD5E1; border-radius: 4px; }")
            combo_status.setProperty("baris", baris)
            combo_status.currentIndexChanged.connect(self.update_status_baris)
            
            # Set status terpilih
            status_sebelumnya = siswa.get('status', 'Hadir')
            index_status = combo_status.findText(status_sebelumnya)
            if index_status >= 0: combo_status.setCurrentIndex(index_status)
            
            self.main.tableAbsensi.setCellWidget(baris, 4, combo_status)

            # 3. NILAI (SPINBOX)
            spin_nilai = QSpinBox()
            spin_nilai.setRange(0, 100)
            spin_nilai.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Set nilai terpilih
            nilai_sebelumnya = int(siswa.get('nilai', 0))
            if is_master_data: 
                spin_nilai.setValue(75) # Default KKM
            else:
                spin_nilai.setValue(nilai_sebelumnya)

            # Style & State
            if status_sebelumnya == "Hadir":
                spin_nilai.setEnabled(True)
                spin_nilai.setStyleSheet("background-color: #F0FDF4; font-weight: bold;")
            else:
                spin_nilai.setEnabled(False)
                spin_nilai.setStyleSheet("background-color: #F1F5F9; color: #94A3B8;")

            self.main.tableAbsensi.setCellWidget(baris, 5, spin_nilai)

        self.hitung_total_hadir()

    def update_status_baris(self):
        sender = self.main.sender()
        if not isinstance(sender, QComboBox): return
        
        baris = sender.property("baris")
        status = sender.currentText()
        spin_nilai = self.main.tableAbsensi.cellWidget(baris, 5)
        
        if spin_nilai:
            if status == "Hadir":
                spin_nilai.setEnabled(True)
                if spin_nilai.value() == 0: spin_nilai.setValue(75)
                spin_nilai.setStyleSheet("background-color: #F0FDF4; font-weight: bold; border: 1px solid #86EFAC;")
            else:
                spin_nilai.setValue(0)
                spin_nilai.setEnabled(False)
                spin_nilai.setStyleSheet("background-color: #F1F5F9; color: #94A3B8; border: 1px solid #E2E8F0;")

        self.hitung_total_hadir()

    def hitung_total_hadir(self):
        jumlah_baris = self.main.tableAbsensi.rowCount()
        total_hadir = 0
        for i in range(jumlah_baris):
            widget = self.main.tableAbsensi.cellWidget(i, 4)
            if widget and widget.currentText() == "Hadir":
                total_hadir += 1
        self.main.lblTotalHadir.setText(f"Total Hadir: {total_hadir} / {jumlah_baris} Siswa")

    def aksi_simpan(self):
        """Simpan data: UPDATE jika ada ID lama, CREATE jika baru"""
        jumlah_baris = self.main.tableAbsensi.rowCount()
        if jumlah_baris == 0: return

        materi = self.main.inputMateri.text() if hasattr(self.main, 'inputMateri') else "-"
        catatan = self.main.inputCatatanJurnal.text() if hasattr(self.main, 'inputCatatanJurnal') else "-"

        if materi == "" or materi == "-":
            QMessageBox.warning(self.main, "Peringatan", "Harap isi Materi Pokok terlebih dahulu!")
            return

        detail_absensi = []
        for i in range(jumlah_baris):
            nis = self.main.tableAbsensi.item(i, 1).text()
            nama = self.main.tableAbsensi.item(i, 2).text().strip()
            status = self.main.tableAbsensi.cellWidget(i, 4).currentText()
            nilai = self.main.tableAbsensi.cellWidget(i, 5).value()
            
            detail_absensi.append({
                "nis": nis, "nama": nama, "status": status, "nilai": nilai
            })

        paket_data = {
            "id_kelas": self.id_kelas_aktif,
            "nama_kelas": self.nama_kelas_aktif,
            "pertemuan": self.main.comboPertemuan.currentText(),
            "materi": materi,
            "catatan_jurnal": catatan,
            "tanggal": database.firestore.SERVER_TIMESTAMP,
            "data_siswa": detail_absensi
        }

        try:
            if self.id_dokumen_aktif:
                # MODE UPDATE (Timpa data lama)
                database.db.collection('absensi').document(self.id_dokumen_aktif).set(paket_data)
                pesan = f"Data pertemuan '{materi}' berhasil DIPERBARUI!"
            else:
                # MODE CREATE (Buat baru)
                _, doc_ref = database.db.collection('absensi').add(paket_data)
                self.id_dokumen_aktif = doc_ref.id # Set ID agar next save jadi update
                pesan = f"Data pertemuan '{materi}' berhasil DISIMPAN!"
                self.main.btnSimpanAbsensi.setText("Update Absensi")

            QMessageBox.information(self.main, "Berhasil", pesan)
            
        except Exception as e:
            print(f"Error simpan: {e}")
            QMessageBox.critical(self.main, "Gagal", f"Gagal menyimpan: {e}")