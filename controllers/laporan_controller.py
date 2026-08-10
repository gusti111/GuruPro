from PyQt6.QtWidgets import QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog
from PyQt6.QtCore import Qt
from backend import database
from datetime import datetime
from google.cloud.firestore_v1.base_query import FieldFilter
import pandas as pd
import os

# --- LIBRARY PDF (REPORTLAB) ---
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    LIBRARY_PDF_ADA = True
except ImportError:
    LIBRARY_PDF_ADA = False

class LaporanController:
    def __init__(self, main_window):
        self.main = main_window
        self.map_kelas = {} 

    def setup_halaman_laporan(self):
        try:
            # 1. Setup Tabel (UPDATE: Tambah Kolom RATA NILAI)
            headers = ["NO", "NIS", "NAMA SISWA", "H", "S", "I", "A", "% HADIR", "RATA NILAI"]
            self.main.tableRekap.setColumnCount(len(headers))
            self.main.tableRekap.setHorizontalHeaderLabels(headers)
            
            # Styling Tabel
            header = self.main.tableRekap.horizontalHeader()
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) # Nama melar
            
            # Atur lebar kolom
            self.main.tableRekap.setColumnWidth(0, 40)  # NO
            self.main.tableRekap.setColumnWidth(1, 80)  # NIS
            self.main.tableRekap.setColumnWidth(3, 40)  # H
            self.main.tableRekap.setColumnWidth(4, 40)  # S
            self.main.tableRekap.setColumnWidth(5, 40)  # I
            self.main.tableRekap.setColumnWidth(6, 40)  # A
            self.main.tableRekap.setColumnWidth(7, 70)  # %
            self.main.tableRekap.setColumnWidth(8, 90)  # NILAI

            # 2. Isi Dropdown Bulan
            self.main.comboLapBulan.clear()
            self.main.comboLapBulan.addItems(["Semua Bulan", "Januari", "Februari", "Maret", "April", "Mei", "Juni", 
                                              "Juli", "Agustus", "September", "Oktober", "November", "Desember"])

            # 3. KONEKSI TOMBOL
            self.main.btnTampilkan.clicked.connect(self.aksi_tampilkan_laporan)
            self.main.btnExportExcel.clicked.connect(self.aksi_export_excel)
            self.main.btnCetakPDF.clicked.connect(self.aksi_cetak_pdf)

            # 4. Load Data Kelas
            # [PENTING] DI-COMMENT AGAR TIDAK FREEZE SAAT STARTUP (Lazy Loading)
            # Data akan dimuat otomatis oleh main.py saat tab Laporan diklik.
            # self.muat_list_kelas()

        except Exception as e:
            print(f"⚠️ Error Setup Laporan: {e}")

    def muat_list_kelas(self):
        """Mengambil daftar kelas milik guru dari Firestore"""
        nip = getattr(self.main, 'user', {}).get('nip')
        if not nip: return

        try:
            daftar_kelas = database.ambil_daftar_kelas(nip)
            self.main.comboLapKelas.clear()
            self.map_kelas = {} 

            for k in daftar_kelas:
                nama_tampil = k.get('nama_kelas', 'Tanpa Nama')
                id_asli = k.get('id')
                self.main.comboLapKelas.addItem(nama_tampil)
                self.map_kelas[nama_tampil] = id_asli
        except Exception as e:
            print(f"Error muat kelas: {e}")

    def aksi_tampilkan_laporan(self):
        """Logika Perhitungan & Agregasi Absensi (TERMASUK NILAI)"""
        nama_kelas = self.main.comboLapKelas.currentText()
        if not nama_kelas: return

        id_kelas = self.map_kelas.get(nama_kelas)
        filter_bulan = self.main.comboLapBulan.currentText()
        
        map_bulan_angka = {
            "Januari": 1, "Februari": 2, "Maret": 3, "April": 4, "Mei": 5, "Juni": 6,
            "Juli": 7, "Agustus": 8, "September": 9, "Oktober": 10, "November": 11, "Desember": 12
        }

        self.main.tableRekap.setRowCount(0)
        
        try:
            # -------------------------------------------------------
            # 1. AMBIL MASTER SISWA (Inisialisasi Data)
            # -------------------------------------------------------
            siswa_docs = database.db.collection("kelas").document(id_kelas).collection("siswa").stream()
            
            rekap_siswa = {} 
            for doc in siswa_docs:
                s = doc.to_dict()
                nis = str(s.get('nis', ''))
                nama = s.get('nama', 'Tanpa Nama')
                # Format Data: [H, S, I, A, TotalNilai]
                rekap_siswa[nis] = {
                    'nama': nama, 
                    'H': 0, 'S': 0, 'I': 0, 'A': 0, 
                    'total_nilai': 0
                }
            
            jumlah_siswa = len(rekap_siswa)

            # -------------------------------------------------------
            # 2. AMBIL DATA ABSENSI & HITUNG
            # -------------------------------------------------------
            docs = database.db.collection("absensi").where(filter=FieldFilter("id_kelas", "==", id_kelas)).stream()
            total_pertemuan_valid = 0

            for doc in docs:
                data = doc.to_dict()
                tanggal_ts = data.get('tanggal')
                
                # Filter Bulan
                if filter_bulan != "Semua Bulan" and tanggal_ts:
                    try:
                        if hasattr(tanggal_ts, 'month'): 
                            bulan_data = tanggal_ts.month
                        else: 
                            dt = datetime.fromtimestamp(tanggal_ts.timestamp())
                            bulan_data = dt.month
                        
                        if bulan_data != map_bulan_angka[filter_bulan]:
                            continue 
                    except: continue

                total_pertemuan_valid += 1
                
                # Loop Detail Siswa
                list_siswa = data.get('data_siswa') or data.get('detail') or []
                for s in list_siswa:
                    nis = str(s.get('nis'))
                    status = s.get('status')
                    
                    # Ambil nilai (handle jika kosong/string)
                    try: nilai = int(s.get('nilai', 0))
                    except: nilai = 0

                    if nis in rekap_siswa:
                        if status == "Hadir": 
                            rekap_siswa[nis]['H'] += 1
                            # Hanya tambahkan nilai jika hadir
                            rekap_siswa[nis]['total_nilai'] += nilai
                        elif status == "Sakit": rekap_siswa[nis]['S'] += 1
                        elif status == "Izin": rekap_siswa[nis]['I'] += 1
                        elif status == "Alpa": rekap_siswa[nis]['A'] += 1

            # -------------------------------------------------------
            # 3. RENDER TABEL
            # -------------------------------------------------------
            sorted_nis = sorted(rekap_siswa.keys(), key=lambda x: int(x) if str(x).isdigit() else str(x))
            self.main.tableRekap.setRowCount(len(sorted_nis))
            
            total_hadir_semua = 0
            nama_alpa_tertinggi = "-"
            max_alpa = -1

            for row, nis in enumerate(sorted_nis):
                data = rekap_siswa[nis]
                
                # Hitung Persentase Kehadiran
                persen = 0
                if total_pertemuan_valid > 0:
                    persen = (data['H'] / total_pertemuan_valid) * 100
                
                # Hitung Rata-rata Nilai
                # Rumus: Total Nilai / Jumlah Kehadiran (H)
                rata_nilai = 0
                if data['H'] > 0:
                    rata_nilai = data['total_nilai'] / data['H']

                total_hadir_semua += data['H']
                
                # Cek Alpa Tertinggi
                if data['A'] > max_alpa:
                    max_alpa = data['A']
                    if max_alpa > 0:
                        nama_alpa_tertinggi = f"{data['nama']} ({data['A']})"
                    else:
                        nama_alpa_tertinggi = "-"

                # --- ISI SEL TABEL ---
                # 0-2: Identitas
                self.main.tableRekap.setItem(row, 0, QTableWidgetItem(str(row+1)))
                self.main.tableRekap.setItem(row, 1, QTableWidgetItem(str(nis)))
                self.main.tableRekap.setItem(row, 2, QTableWidgetItem(data['nama']))
                
                # 3-6: H/S/I/A
                for col, key in enumerate(['H', 'S', 'I', 'A']):
                    item = QTableWidgetItem(str(data[key]))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.main.tableRekap.setItem(row, 3+col, item)

                # 7: Persentase (Warna-warni)
                item_persen = QTableWidgetItem(f"{persen:.1f}%")
                item_persen.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if persen < 50: item_persen.setForeground(Qt.GlobalColor.red)
                elif persen < 75: item_persen.setForeground(Qt.GlobalColor.darkYellow)
                else: item_persen.setForeground(Qt.GlobalColor.darkGreen)
                self.main.tableRekap.setItem(row, 7, item_persen)

                # 8: RATA NILAI (BARU!)
                item_nilai = QTableWidgetItem(f"{rata_nilai:.1f}")
                item_nilai.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # Warna nilai (Merah jika di bawah KKM 75)
                if rata_nilai < 75: 
                    item_nilai.setForeground(Qt.GlobalColor.red)
                    item_nilai.setToolTip("Di bawah KKM")
                else:
                    item_nilai.setForeground(Qt.GlobalColor.black)
                    
                self.main.tableRekap.setItem(row, 8, item_nilai)

            # -------------------------------------------------------
            # 4. UPDATE STATISTIK (Labels)
            # -------------------------------------------------------
            try:
                if hasattr(self.main, 'label_9'):
                    self.main.label_9.setText(str(total_pertemuan_valid))
                
                avg_kelas = 0
                pembagi = jumlah_siswa * total_pertemuan_valid
                if pembagi > 0:
                    avg_kelas = (total_hadir_semua / pembagi) * 100
                
                if hasattr(self.main, 'label_11'):
                    self.main.label_11.setText(f"{avg_kelas:.1f}%")

                if hasattr(self.main, 'label_13'):
                    self.main.label_13.setText(nama_alpa_tertinggi)

            except Exception as e:
                print(f"Error update label: {e}")

        except Exception as e:
            print(f"Error rekap: {e}")
            QMessageBox.warning(self.main, "Error", "Gagal menghitung rekap.")

    # =========================================================================
    # FITUR EKSPOR EXCEL (UPDATE: Include Nilai)
    # =========================================================================
    def aksi_export_excel(self):
        if self.main.tableRekap.rowCount() == 0:
            QMessageBox.warning(self.main, "Kosong", "Tampilkan data terlebih dahulu.")
            return

        nama_kelas = self.main.comboLapKelas.currentText()
        nama_file = f"Laporan_Absensi_{nama_kelas}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self.main, "Simpan Excel", nama_file, "Excel Files (*.xlsx)")
        if not path: return

        try:
            # Ambil semua kolom termasuk Nilai
            headers = [self.main.tableRekap.horizontalHeaderItem(col).text() for col in range(self.main.tableRekap.columnCount())]
            rows = []
            for row in range(self.main.tableRekap.rowCount()):
                row_data = []
                for col in range(self.main.tableRekap.columnCount()):
                    item = self.main.tableRekap.item(row, col)
                    row_data.append(item.text() if item else "")
                rows.append(row_data)

            df = pd.DataFrame(rows, columns=headers)
            df.to_excel(path, index=False)
            QMessageBox.information(self.main, "Sukses", f"Data berhasil diekspor ke: {path}")
            os.startfile(path)
        except Exception as e:
            QMessageBox.critical(self.main, "Error", f"Gagal simpan Excel: {e}")

    # =========================================================================
    # FITUR CETAK PDF (UPDATE: Include Nilai)
    # =========================================================================
    def aksi_cetak_pdf(self):
        if not LIBRARY_PDF_ADA:
            QMessageBox.critical(self.main, "Error", "Library 'reportlab' belum diinstall.")
            return

        if self.main.tableRekap.rowCount() == 0:
            QMessageBox.warning(self.main, "Data Kosong", "Tampilkan data terlebih dahulu.")
            return

        nama_kelas = self.main.comboLapKelas.currentText()
        path, _ = QFileDialog.getSaveFileName(self.main, "Simpan PDF", f"Laporan_{nama_kelas}.pdf", "PDF Files (*.pdf)")
        if not path: return

        try:
            doc = SimpleDocTemplate(path, pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()

            judul = Paragraph(f"<b>Laporan Kehadiran & Nilai Siswa</b>", styles['Title'])
            elements.append(judul)
            subjudul = Paragraph(f"Kelas: {nama_kelas}<br/>Bulan: {self.main.comboLapBulan.currentText()}", styles['Normal'])
            elements.append(subjudul)
            elements.append(Spacer(1, 20))

            # Header PDF: Tambahkan 'NILAI'
            data_tabel = [["NO", "NIS", "NAMA SISWA", "H", "S", "I", "A", "%", "NILAI"]]
            
            for row in range(self.main.tableRekap.rowCount()):
                baris = []
                for col in range(self.main.tableRekap.columnCount()):
                    item = self.main.tableRekap.item(row, col)
                    baris.append(item.text() if item else "")
                data_tabel.append(baris)

            tabel_pdf = Table(data_tabel)
            style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2563EB")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 0), (-1, -1), 8), # Perkecil font agar muat
            ])
            tabel_pdf.setStyle(style)
            elements.append(tabel_pdf)
            doc.build(elements)
            
            QMessageBox.information(self.main, "Sukses", f"PDF berhasil dibuat!\nLokasi: {path}")
            os.startfile(path)
        except Exception as e:
            QMessageBox.critical(self.main, "Gagal", f"Gagal membuat PDF: {e}")