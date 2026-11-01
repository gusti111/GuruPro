import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter 
import os
import sys

# ==============================================================================
# FUNGSI PENCARI JALUR (RESOURCE PATH)
# ==============================================================================
def resource_path(relative_path):
    """ Dapatkan path absolut ke resource, wajib agar file JSON terbaca di EXE """
    try:
        # Jika dijalankan sebagai EXE (PyInstaller)
        base_path = sys._MEIPASS
    except Exception:
        # Jika dijalankan sebagai script Python biasa
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
    return os.path.join(base_path, relative_path)

# ==============================================================================
# KONFIGURASI DATABASE
# ==============================================================================
# Pastikan path ini sesuai dengan struktur foldermu: ProjectFolder/json/toko_kunci.json
KEY_PATH = resource_path(os.path.join("json", "toko_kunci.json")) 
db = None

def init_db():
    global db
    if not os.path.exists(KEY_PATH):
        print(f"❌ ERROR DATABASE: File kunci tidak ditemukan di '{KEY_PATH}'")
        return None
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(KEY_PATH)
            firebase_admin.initialize_app(cred)
            print("✅ SYSTEM: Koneksi ke Google Firebase BERHASIL!")
        
        db = firestore.client()
        return db
    except Exception as e:
        print(f"❌ ERROR KONEKSI: {e}")
        return None

# Jalankan inisialisasi otomatis saat file diimport
if db is None:
    init_db()

# ==============================================================================
# 1. FITUR AKUN (LOGIN, DAFTAR & PROFIL)
# ==============================================================================
def _hash_password(password):
    """Hash password with PBKDF2-HMAC-SHA256 and a unique random salt."""
    import hashlib
    import secrets
    iterations = 600_000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"

def _verify_password(password, stored_value):
    """Verify modern hashes; support legacy plaintext only for one-time migration."""
    import hashlib
    import hmac
    if not isinstance(stored_value, str):
        return False, False
    if not stored_value.startswith("pbkdf2_sha256$"):
        return hmac.compare_digest(password, stored_value), True
    try:
        algorithm, iterations, salt_hex, digest_hex = stored_value.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False, False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
            ).hex()
        return hmac.compare_digest(candidate, digest_hex), False
    except (ValueError, TypeError):
        return False, False

def cek_login(nip, password):
    """Validate credentials and migrate legacy plaintext after successful login."""
    if db is None:
        return False, "Database belum terhubung."
    try:
        docs = db.collection("users").where(
            filter=FieldFilter("nip", "==", nip)
        ).limit(1).stream()
        for doc in docs:
            user_data = doc.to_dict() or {}
            valid, is_legacy = _verify_password(password, user_data.get("password", ""))
            if not valid:
                return False, "NIP atau Kata Sandi salah!"
            if is_legacy:
                doc.reference.update({"password": _hash_password(password)})
                user_data["password"] = None
            user_data["doc_id"] = doc.id
            return True, user_data
        return False, "NIP atau Kata Sandi salah!"
    except Exception as e:
        return False, f"Error System: {e}"

def daftar_guru_baru(data_guru):
    """Register an account with a salted password hash, not plaintext."""
    if db is None:
        return False, "Database belum terhubung."
    try:
        users_ref = db.collection("users")
        cek_nip = users_ref.where(
            filter=FieldFilter("nip", "==", data_guru["nip"])
        ).limit(1).get()
        if len(list(cek_nip)) > 0:
            return False, "NIP ini sudah terdaftar!"
        account_data = dict(data_guru)
        account_data["password"] = _hash_password(account_data["password"])
        account_data["role"] = "guru"
        users_ref.add(account_data)
        return True, "Pendaftaran Berhasil"
    except Exception as e:
        return False, f"Gagal mendaftar: {e}"

def update_profil_guru(doc_id, data_baru):
    """Update profile fields; password must be changed through update_password()."""
    if db is None:
        return False, "Database belum terhubung."
    try:
        safe_data = dict(data_baru)
        safe_data.pop("password", None)
        db.collection("users").document(doc_id).update(safe_data)
        return True, "Profil diperbarui di Cloud!"
    except Exception as e:
        return False, f"Gagal update: {str(e)}"

def update_password(doc_id, password_baru):
    if db is None:
        return False
    try:
        db.collection("users").document(doc_id).update({
            "password": _hash_password(password_baru)
        })
        return True
    except Exception:
        return False

# ==============================================================================
# 2. FITUR KELAS & SISWA
# ==============================================================================
def tambah_kelas(data_kelas):
    if db is None: return False, "Database belum terhubung."
    try:
        db.collection('kelas').add(data_kelas)
        return True, f"Kelas {data_kelas['nama_kelas']} berhasil dibuat!"
    except Exception as e:
        return False, f"Gagal: {str(e)}"

def ambil_daftar_kelas(nip_guru):
    if db is None: return []
    try:
        docs = db.collection('kelas').where(filter=FieldFilter("nip_guru", "==", nip_guru)).stream()
        hasil = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            hasil.append(data)
        return hasil
    except:
        return []

def hapus_kelas(doc_id):
    if db is None: return False
    try:
        db.collection('kelas').document(doc_id).delete()
        return True
    except:
        return False

def simpan_daftar_siswa_massal(id_kelas, list_siswa):
    """ Menyimpan siswa dari Excel ke sub-koleksi kelas """
    if db is None: return False
    try:
        batch = db.batch()
        count = 0
        MAX_BATCH_SIZE = 400 # Batas aman Firestore batch

        for siswa in list_siswa:
            # Gunakan NIS sebagai ID Dokumen agar tidak duplikat
            siswa_ref = db.collection('kelas').document(id_kelas).collection('siswa').document(str(siswa['nis']))
            batch.set(siswa_ref, {
                "nis": str(siswa['nis']),
                "nama": siswa['nama'],
                "gender": siswa['gender']
            })
            count += 1
            
            # Jika batch penuh, commit dan buat batch baru
            if count >= MAX_BATCH_SIZE:
                batch.commit()
                batch = db.batch()
                count = 0
                
        if count > 0: batch.commit() # Commit sisa data
        return True
    except Exception as e:
        print(f"❌ Error Simpan Siswa: {e}")
        return False

def ambil_jumlah_siswa(id_kelas):
    """ Menghitung jumlah siswa di sub-koleksi 'siswa' """
    if db is None: return 0
    try:
        # Menggunakan aggregation query agar lebih hemat read quota (jika support)
        # Tapi untuk aman, pakai count() biasa dulu
        docs = db.collection('kelas').document(id_kelas).collection('siswa').count().get()
        return docs[0][0].value
    except:
        return 0

def ambil_siswa_per_kelas(id_kelas):
    """ Mengambil semua siswa dari sub-koleksi 'siswa' berdasarkan ID kelas """
    if db is None: return []
    try:
        # Mengakses sub-koleksi: kelas -> {id_kelas} -> siswa
        docs = db.collection('kelas').document(id_kelas).collection('siswa').order_by("nama").get()
        hasil = []
        for doc in docs:
            data = doc.to_dict()
            hasil.append(data)
        return hasil
    except Exception as e:
        print(f"❌ Error ambil siswa: {e}")
        return []

# ==============================================================================
# 3. FITUR ABSENSI & LAPORAN
# ==============================================================================
def simpan_absensi_ke_db(data_absensi):
    if db is None: return False, "Database putus."
    try:
        # Cek Duplikat (Agar tidak double input)
        cek = db.collection('absensi')\
                .where(filter=FieldFilter("id_kelas", "==", data_absensi['id_kelas']))\
                .where(filter=FieldFilter("pertemuan", "==", data_absensi['pertemuan']))\
                .limit(1).get()
                
        if len(list(cek)) > 0:
            # Jika sudah ada, UPDATE data lama
            doc_id = list(cek)[0].id
            db.collection('absensi').document(doc_id).set(data_absensi)
            return True, "Data absensi diperbarui!"
        else:
            # Jika belum ada, BUAT BARU
            db.collection('absensi').add(data_absensi)
            return True, "Data absensi berhasil disimpan!"
            
    except Exception as e:
        return False, str(e)

def ambil_rekap_absensi(id_kelas):
    if db is None: return []
    try:
        docs = db.collection('absensi').where(filter=FieldFilter("id_kelas", "==", id_kelas)).stream()
        # Urutkan berdasarkan pertemuan
        data = [doc.to_dict() for doc in docs]
        # Sort sederhana string "Pertemuan Ke-X"
        data.sort(key=lambda x: x.get('pertemuan', '')) 
        return data
    except:
        return []

# ==============================================================================
# 4. FITUR REMOTE & PERANGKAT
# ==============================================================================

def inisialisasi_sesi_remote(token, user_data):
    """ 
    FUNGSI UTAMA: Membuat sesi remote dengan data guru LENGKAP.
    Pastikan 'nama' dan 'nip' terisi agar muncul di HP.
    """
    if db is None: return False
    try:
        data_sesi = {
            "status": "waiting",
            "created_at": firestore.SERVER_TIMESTAMP,
            "token": token,
            # Data Guru dikirim ke Firebase agar HP bisa baca
            "nama_guru": user_data.get('nama_lengkap', user_data.get('nama', 'Guru')),
            "jabatan": user_data.get('jabatan', 'Guru Pengajar'),
            "mapel": user_data.get('mapel', '-'),
            "nip": user_data.get('nip', '-'),
            "role": "Admin",
            "custom_name": "Desktop Admin"
        }
        db.collection('remote_sessions').document(token).set(data_sesi)
        return True
    except Exception as e:
        print(f"Gagal buat sesi: {e}")
        return False

def update_status_remote(session_id, status_baru):
    """ Memberi tahu desktop bahwa HP sudah terhubung/terputus """
    if db is None: return False
    try:
        db.collection('remote_sessions').document(session_id).update({
            "status": status_baru,
            "last_update": firestore.SERVER_TIMESTAMP
        })
        return True
    except:
        return False

def pantau_sesi_remote(session_id, callback):
    """ Realtime listener untuk mendeteksi perubahan dari HP """
    if db is None: return
    doc_ref = db.collection('remote_sessions').document(session_id)
    doc_ref.on_snapshot(callback)