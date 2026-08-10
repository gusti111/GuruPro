from PyQt6.QtCore import QTimer, QDate, QTime, Qt
from PyQt6.QtWidgets import QMessageBox
from backend import database
from datetime import datetime

class DashboardController:
    def __init__(self, main_window):
        self.main = main_window
        
        # Timer Jam (Update tiap 1 detik)
        self.timer_jam = QTimer()
        
        # Timer Data (Update tiap 30 detik agar data sinkron dengan HP)
        self.timer_data = QTimer()
        
        self.kelas_aktif_sekarang = None
        self.list_kelas_hari_ini = [] # Menyimpan semua kelas hari ini

        # Mapping Hari Inggris -> Indonesia
        self.hari_indo = {
            "Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu",
            "Thursday": "Kamis", "Friday": "Jumat", "Saturday": "Sabtu", "Sunday": "Minggu"
        }
        
        # Mapping Bulan
        self.bulan_indo = {
            1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
            7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
        }

    def setup_halaman_dashboard(self):
        try:
            # 1. Jalankan Jam Digital
            self.update_waktu()
            self.timer_jam.timeout.connect(self.update_waktu)
            self.timer_jam.start(1000)

            # 2. Jalankan Auto-Refresh Data (Setiap 30 detik)
            self.muat_data_dashboard() # Load pertama
            self.timer_data.timeout.connect(self.muat_data_dashboard)
            self.timer_data.start(30000) 

            # 3. Koneksi Tombol "Mulai Kelas"
            try:
                # Disconnect dulu untuk mencegah double signal jika reload
                try: self.main.btnMulaiKelas.clicked.disconnect() 
                except: pass
                
                self.main.btnMulaiKelas.clicked.connect(self.aksi_pindah_ke_mengajar)
            except AttributeError:
                print("⚠️ Tombol 'btnMulaiKelas' tidak ditemukan di UI")

        except Exception as e:
            print(f"⚠️ Error Setup Dashboard: {e}")

    def update_waktu(self):
        """Mengupdate Label Jam dan Tanggal secara Realtime"""
        sekarang = datetime.now()
        
        # Format Jam
        jam_str = sekarang.strftime("%H:%M:%S")
        if hasattr(self.main, 'labelJam'):
            self.main.labelJam.setText(jam_str)
        
        # Format Tanggal
        hari_eng = sekarang.strftime("%A")
        hari_id = self.hari_indo.get(hari_eng, hari_eng)
        tanggal = sekarang.day
        bulan_id = self.bulan_indo[sekarang.month]
        tahun = sekarang.year
        
        tanggal_full = f"{hari_id}, {tanggal} {bulan_id} {tahun}"
        if hasattr(self.main, 'labelTanggal'):
            self.main.labelTanggal.setText(tanggal_full)

    def muat_data_dashboard(self):
        """Logika Pintar: Handle Multi-Kelas & Statistik"""
        try:
            nip = self.main.user.get('nip')
            if not nip: return

            # --- A. LOGIKA JADWAL HARI INI (MULTI CLASS SUPPORT) ---
            hari_ini_eng = datetime.now().strftime("%A")
            hari_ini = self.hari_indo.get(hari_ini_eng, hari_ini_eng)
            
            daftar_kelas = database.ambil_daftar_kelas(nip)
            self.list_kelas_hari_ini = [] # Reset list
            
            # Filter semua kelas di hari ini
            for kelas in daftar_kelas:
                jadwal_text = kelas.get('jadwal', '') # Misal: "Senin, 08.00 - 10.00"
                if hari_ini in jadwal_text:
                    self.list_kelas_hari_ini.append(kelas)

            jumlah_kelas = len(self.list_kelas_hari_ini)

            # Update UI Kartu Jadwal
            if jumlah_kelas > 0:
                # Ambil kelas pertama sebagai default untuk tombol "Mulai"
                self.kelas_aktif_sekarang = self.list_kelas_hari_ini[0] 
                
                self.main.lblJudulJadwal.setText(f"Ada {jumlah_kelas} Kelas Hari Ini")
                
                # Tampilkan detail kelas pertama
                info = f"{self.kelas_aktif_sekarang['nama_kelas']} | {self.kelas_aktif_sekarang['mata_pelajaran']}"
                if jumlah_kelas > 1:
                    info += f" (+{jumlah_kelas-1} lainnya)"
                
                self.main.lblIsiJadwal.setText(info)
                self.main.btnMulaiKelas.setEnabled(True)
                self.main.btnMulaiKelas.setText("Mulai Kelas")
                
                # Update Label "Kelas Aktif" (Sesuai screenshot HP kamu)
                if hasattr(self.main, 'lblKelasAktif'): 
                    self.main.lblKelasAktif.setText(str(jumlah_kelas))

            else:
                self.main.lblJudulJadwal.setText("Tidak Ada Jadwal")
                self.main.lblIsiJadwal.setText(f"Hari {hari_ini} kamu bebas tugas.")
                self.main.btnMulaiKelas.setEnabled(False)
                self.main.btnMulaiKelas.setText("Santai Dulu")
                self.kelas_aktif_sekarang = None
                
                if hasattr(self.main, 'lblKelasAktif'): 
                    self.main.lblKelasAktif.setText("0")

            # --- B. HITUNG STATISTIK KEHADIRAN ---
            total_hadir = 0
            total_data = 0
            
            for kelas in daftar_kelas:
                rekap = database.ambil_rekap_absensi(kelas['id']) 
                if rekap:
                    for sesi in rekap:
                        # [PENTING] Ambil data dari 'data_siswa' (sesuai format simpan baru) atau 'detail' (format lama)
                        detail = sesi.get('data_siswa') or sesi.get('detail') or []
                        
                        if detail:
                            total_data += len(detail)
                            # Hitung siswa yang statusnya 'Hadir' secara aman
                            total_hadir += sum(1 for s in detail if s.get('status') == 'Hadir')
            
            if total_data > 0:
                persen_hadir = int((total_hadir / total_data) * 100)
            else:
                persen_hadir = 0
                
            self.main.lblAngkaHadir.setText(f"{persen_hadir}%")
            
            # --- C. STATISTIK LAIN ---
            self.main.lblAngkaTugas.setText("0") 
            self.main.lblIsiInfo.setText("Sistem Stabil")
            
        except Exception as e:
            print(f"⚠️ Gagal memuat data dashboard: {e}")

    def aksi_pindah_ke_mengajar(self):
        """Pindah ke Halaman Mengajar"""
        if self.kelas_aktif_sekarang:
            # Pindah halaman
            self.main.stackedWidget.setCurrentWidget(self.main.pageMengajar)
            
            # Update Navigasi Sidebar (Visual)
            self.main.btnNavDashboard.setChecked(False)
            self.main.btnNavMengajar.setChecked(True)
            
            # Panggil fungsi di MengajarController
            if hasattr(self.main, 'mengajar_ctrl'):
                self.main.mengajar_ctrl.buka_kelas_spesifik(
                    self.kelas_aktif_sekarang['id'],
                    self.kelas_aktif_sekarang['nama_kelas']
                )