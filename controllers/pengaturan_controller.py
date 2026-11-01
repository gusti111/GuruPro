from PyQt6.QtWidgets import QMessageBox, QFileDialog, QInputDialog, QLineEdit, QComboBox, QLabel
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QPen, QColor, QImage
from PyQt6.QtCore import Qt, QRectF, QBuffer, QIODevice
from backend import database
from datetime import datetime
import pandas as pd 
import os
import shutil 
import base64 # Library wajib untuk kirim foto ke Web App

class PengaturanController:
    def __init__(self, main_window):
        self.main = main_window
        # Variabel sementara untuk menampung foto baru sebelum tombol Simpan diklik
        self.temp_foto_path = None 
        # Widget tambahan untuk Jabatan (Kita buat lewat kode)
        self.comboJabatan = None 

    def setup_halaman_pengaturan(self):
        """Menghubungkan tombol UI dengan fungsi logika di controller"""
        try:
            # 1. SETUP TAMBAHAN UI (Inject Widget Baru: Dropdown Jabatan)
            self.setup_ui_tambahan()

            # 2. Putuskan koneksi lama untuk mencegah double execution
            try: self.main.btnSimpanProfil.clicked.disconnect()
            except: pass
            
            # 3. Hubungkan Signal & Slot
            self.main.btnSimpanProfil.clicked.connect(self.aksi_simpan_profil)
            self.main.btnGantiFoto.clicked.connect(self.aksi_ganti_foto)
            self.main.btnGantiPass.clicked.connect(self.aksi_ganti_password)
            self.main.btnBackupData.clicked.connect(self.aksi_backup_data)
            self.main.btnResetApp.clicked.connect(self.aksi_reset_aplikasi)

            # 4. Muat Data User ke Formulir
            self.muat_data_profil()

        except Exception as e:
            print(f"⚠️ Error Setup Pengaturan: {e}")

    def setup_ui_tambahan(self):
        """Menambahkan Dropdown Jabatan secara programatis ke dalam Layout"""
        # Cek apakah sudah pernah dibuat agar tidak double
        if self.comboJabatan is not None: return

        try:
            # Ambil Layout di dalam kartu Profil (verticalLayout_24 adalah wadah Mapel)
            # Kita akan menyisipkan Jabatan SEBELUM input Mapel
            # Cara aman: Ambil parent dari inputEditMapel, lalu ambil layout-nya
            layout_parent = self.main.inputEditMapel.parentWidget().layout()
            
            # Buat Label Baru
            lbl_jabatan = QLabel("Jabatan / Posisi di Sekolah")
            lbl_jabatan.setStyleSheet("color: #64748B; font-weight: 700; font-size: 13px; margin-bottom: 5px; margin-top: 10px;")
            
            # Buat Dropdown Baru
            self.comboJabatan = QComboBox()
            self.comboJabatan.addItems([
                "Guru Mata Pelajaran", 
                "Wali Kelas", 
                "Wali Kelas & Guru Mapel", 
                "Kepala Laboratorium",
                "Staff Pengajar"
            ])
            self.comboJabatan.setStyleSheet("""
                QComboBox { background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 8px; padding: 10px 15px; font-weight: 600; color: #1E293B; }
                QComboBox::drop-down { border: none; }
            """)

            # Masukkan ke Layout (Di posisi index 0 & 1 agar berada di atas Mapel)
            # Layout container biasanya punya urutan widget. Kita selipkan di awal.
            if layout_parent:
                layout_parent.insertWidget(0, self.comboJabatan)
                layout_parent.insertWidget(0, lbl_jabatan)
        except Exception as e:
            print(f"Gagal inject UI Jabatan: {e}")

    def muat_data_profil(self):
        """Mengambil data user dari memori aplikasi dan menampilkannya di UI"""
        user = self.main.user
        if not user: return

        # 1. Isi Data Teks
        self.main.inputEditNama.setText(user.get('nama_lengkap', ''))
        self.main.inputEditNIP.setReadOnly(True)
        self.main.inputEditNIP.setToolTip("NIP merupakan identitas akun dan tidak dapat diubah dari halaman profil.")
        self.main.inputEditNIP.setText(user.get('nip', ''))
        self.main.inputEditMapel.setText(user.get('mapel', ''))

        # 2. Isi Dropdown Jabatan (Jika ada datanya)
        if self.comboJabatan:
            jabatan_saved = user.get('jabatan', 'Guru Mata Pelajaran')
            index = self.comboJabatan.findText(jabatan_saved)
            if index >= 0:
                self.comboJabatan.setCurrentIndex(index)

        # 3. Isi Foto Profil (Load dari Lokal Laptop)
        foto_path = user.get('foto_path')
        if foto_path and os.path.exists(foto_path):
            self.tampilkan_foto_lingkaran(foto_path, self.main.lblFotoProfilSetting, size=80)
            self.tampilkan_foto_lingkaran(foto_path, self.main.lblFotoUser, size=40)
        else:
            self.main.lblFotoProfilSetting.clear()
            self.main.lblFotoProfilSetting.setText("FOTO")
            self.main.lblFotoProfilSetting.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def aksi_ganti_foto(self):
        """Memilih foto dan menampilkan preview (Belum disimpan permanen)"""
        file_path, _ = QFileDialog.getOpenFileName(self.main, "Pilih Foto Profil", "", "Images (*.png *.jpg *.jpeg)")
        if not file_path: return

        # Simpan path di variabel sementara
        self.temp_foto_path = file_path
        
        # Tampilkan preview agar user yakin
        self.tampilkan_foto_lingkaran(file_path, self.main.lblFotoProfilSetting, size=80)

    def aksi_simpan_profil(self):
        """Menyimpan perubahan profil (Teks, Jabatan & Foto Base64) ke Firebase & Lokal"""
        nama_baru = self.main.inputEditNama.text()
        nip_baru = self.main.inputEditNIP.text()
        mapel_baru = self.main.inputEditMapel.text()
        jabatan_baru = self.comboJabatan.currentText() if self.comboJabatan else "Guru Mata Pelajaran"
        
        if not nama_baru or not nip_baru:
            QMessageBox.warning(self.main, "Peringatan", "Nama dan NIP wajib diisi!")
            return

        nip_akun = str(self.main.user.get('nip', '')).strip()
        if nip_baru.strip() != nip_akun:
            self.main.inputEditNIP.setText(nip_akun)
            QMessageBox.warning(
                self.main, "NIP Tidak Dapat Diubah",
                "NIP adalah identitas login akun. Perubahan NIP harus dilakukan melalui proses administrasi akun."
            )
            return

        # NIP is immutable; only supported profile fields are sent to the API.
        data_update = {
            "nama_lengkap": nama_baru,
            "mapel": mapel_baru,
            "jabatan": jabatan_baru # <--- FIELD BARU DISIMPAN
        }

        # === LOGIKA PENYIMPANAN FOTO (LOKAL + CLOUD) ===
        if self.temp_foto_path:
            try:
                # A. SIMPAN LOKAL (Agar Desktop Cepat & Hemat Kuota)
                save_dir = "assets/profil"
                if not os.path.exists(save_dir):
                    os.makedirs(save_dir)
                
                ext = os.path.splitext(self.temp_foto_path)[1]
                nama_file_foto = f"profil_{nip_baru}{ext}"
                target_path = os.path.join(save_dir, nama_file_foto)
                
                shutil.copy2(self.temp_foto_path, target_path)
                data_update['foto_path'] = target_path # Simpan path lokal
                
                # B. KONVERSI KE BASE64 (Agar Muncul di Web App/HP)
                image = QImage(self.temp_foto_path)
                if not image.isNull():
                    # Resize dulu biar database gak berat (Max 300px)
                    image_small = image.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    
                    # Simpan ke Memory Buffer sebagai JPG
                    ba = QBuffer()
                    ba.open(QIODevice.OpenModeFlag.WriteOnly)
                    image_small.save(ba, "JPG", quality=80)
                    
                    # Ubah ke string Base64
                    byte_data = ba.data().toBase64()
                    base64_str = "data:image/jpeg;base64," + str(byte_data, 'utf-8')
                    
                    data_update['foto_base64'] = base64_str # Simpan string gambar
                
                # Update UI
                self.tampilkan_foto_lingkaran(target_path, self.main.lblFotoUser, size=40)
                self.temp_foto_path = None

            except Exception as e:
                print(f"Gagal proses foto: {e}")
                QMessageBox.warning(self.main, "Warning Foto", f"Gagal memproses foto: {e}")

        # === UPDATE DATABASE ===
        doc_id = self.main.user.get('doc_id')
        sukses, pesan = database.update_profil_guru(doc_id, data_update)
        
        if sukses:
            QMessageBox.information(self.main, "Sukses", "Profil berhasil diperbarui!")
            
            # Update data di memori aplikasi (Realtime)
            self.main.user.update(data_update)
            self.main.lblNamaUser.setText(nama_baru)
        else:
            QMessageBox.critical(self.main, "Gagal", f"Gagal menyimpan ke server: {pesan}")

    def tampilkan_foto_lingkaran(self, path_gambar, label_target, size=80):
        """Helper function: Membuat gambar menjadi lingkaran & menaruh di Label"""
        try:
            source_pixmap = QPixmap(path_gambar)
            if source_pixmap.isNull(): return

            # Center Crop & Scaling
            if source_pixmap.width() < source_pixmap.height():
                scaled = source_pixmap.scaledToWidth(size, Qt.TransformationMode.SmoothTransformation)
            else:
                scaled = source_pixmap.scaledToHeight(size, Qt.TransformationMode.SmoothTransformation)

            # Kanvas Transparan
            final_pixmap = QPixmap(size, size)
            final_pixmap.fill(Qt.GlobalColor.transparent)

            painter = QPainter(final_pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            # Masking Lingkaran
            rect_f = QRectF(0, 0, size, size)
            path = QPainterPath()
            path.addEllipse(rect_f)
            painter.setClipPath(path)

            # Gambar di tengah
            x = (size - scaled.width()) // 2
            y = (size - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)

            # Border Halus
            pen = QPen(QColor("#CBD5E1"))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawEllipse(rect_f.adjusted(1, 1, -1, -1))
            painter.end()

            label_target.setPixmap(final_pixmap)
            label_target.setText("") 
            
        except Exception as e:
            print(f"Gagal render foto: {e}")

    # =========================================================================
    # FITUR BACKUP & SECURITY
    # =========================================================================
    def aksi_backup_data(self):
        """Mengekspor informasi akun ke file Excel beneran menggunakan pandas"""
        if not self.main.user:
            QMessageBox.warning(self.main, "Error", "Gagal mengambil data user untuk backup.")
            return

        nama_file = f"Backup_Profil_{self.main.user.get('nama_lengkap')}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self.main, "Simpan Backup Akun", nama_file, "Excel Files (*.xlsx)")
        
        if not path: return

        try:
            data_backup = [{
                "NAMA LENGKAP": self.main.user.get('nama_lengkap'),
                "NIP / NOMOR INDUK": self.main.user.get('nip'),
                "BIDANG STUDI": self.main.user.get('mapel'),
                "JABATAN": self.main.user.get('jabatan', '-'), # Sertakan Jabatan
                "HAK AKSES": self.main.user.get('role', 'Guru'),
                "WAKTU EKSPOR": datetime.now().strftime("%d-%m-%Y %H:%M:%S")
            }]

            df = pd.DataFrame(data_backup)
            df.to_excel(path, index=False, engine='openpyxl')
            
            QMessageBox.information(self.main, "Sukses", f"Data profil berhasil diekspor!\nLokasi: {path}")
            os.startfile(path)

        except Exception as e:
            QMessageBox.critical(self.main, "Error Backup", f"Gagal membuat file Excel: {str(e)}")

    def aksi_ganti_password(self):
        password_lama, ok = QInputDialog.getText(
            self.main, "Verifikasi", "Masukkan password saat ini:",
            QLineEdit.EchoMode.Password
        )
        if not ok or not password_lama:
            return

        pass_baru, ok = QInputDialog.getText(
            self.main, "Keamanan", "Masukkan password baru (minimal 10 karakter):",
            QLineEdit.EchoMode.Password
        )
        if not ok or not pass_baru:
            return
        if len(pass_baru) < 10 or len(pass_baru) > 128:
            QMessageBox.warning(self.main, "Peringatan", "Password baru harus 10–128 karakter.")
            return

        konfirmasi, ok = QInputDialog.getText(
            self.main, "Konfirmasi", "Ulangi password baru:",
            QLineEdit.EchoMode.Password
        )
        if not ok or konfirmasi != pass_baru:
            QMessageBox.warning(self.main, "Peringatan", "Konfirmasi password tidak cocok.")
            return

        doc_id = self.main.user.get('doc_id')
        sukses, pesan = database.update_password(doc_id, pass_baru, password_lama)
        if sukses:
            QMessageBox.information(
                self.main, "Sukses",
                pesan + "\\nSesi login akan diakhiri demi keamanan."
            )
            self.main.close()
        else:
            QMessageBox.warning(self.main, "Gagal", f"Gagal mengubah kata sandi: {pesan}")

    def aksi_reset_aplikasi(self):
        tanya = QMessageBox.question(self.main, "Reset Form", "Apakah Anda ingin mengosongkan formulir input profil?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if tanya == QMessageBox.StandardButton.Yes:
            self.main.inputEditNama.clear()
            self.main.inputEditNIP.clear()
            self.main.inputEditMapel.clear()
            # Reset Combo Jabatan
            if self.comboJabatan: self.comboJabatan.setCurrentIndex(0)
            
            self.main.lblFotoProfilSetting.clear()
            self.main.lblFotoProfilSetting.setText("FOTO")
            QMessageBox.information(self.main, "Info", "Formulir telah dibersihkan.")