const crypto = require("node:crypto");
const admin = require("firebase-admin");
const { onRequest } = require("firebase-functions/v2/https");
const { defineSecret } = require("firebase-functions/params");

admin.initializeApp();

const db = admin.firestore();
const auth = admin.auth();
const API_KEY = defineSecret("FIREBASE_WEB_API_KEY");
const REGISTRATION_CODE = defineSecret("GURUPRO_REGISTRATION_CODE");
const REGION = "us-central1";
const HOSTING_ORIGIN = "https://gurupro-app-bc6cc.web.app";
const ALLOWED_ORIGINS = new Set([
  HOSTING_ORIGIN,
  "https://gurupro-app-bc6cc.firebaseapp.com",
  "http://localhost:5000",
  "http://127.0.0.1:5000",
]);

const now = () => admin.firestore.Timestamp.now();
const sha256 = (value) => crypto.createHash("sha256").update(String(value)).digest("hex");
const randomToken = (bytes = 32) => crypto.randomBytes(bytes).toString("base64url");
const cleanString = (value, max = 200) => typeof value === "string" ? value.trim().slice(0, max) : "";

function serializeForClient(value) {
  if (value instanceof admin.firestore.Timestamp) return value.toDate().toISOString();
  if (value instanceof Date) return value.toISOString();
  if (Array.isArray(value)) return value.map(serializeForClient);
  if (value && typeof value === "object") {
    const output = {};
    for (const [key, item] of Object.entries(value)) output[key] = serializeForClient(item);
    return output;
  }
  return value;
}

function fail(status, message, code = "request_failed") {
  const error = new Error(message);
  error.status = status;
  error.code = code;
  throw error;
}

const { hashPassword, verifyPassword } = require("./password_utils");

function publicProfile(data, uid) {
  const safe = { ...(data || {}) };
  delete safe.password;
  delete safe.password_hash;
  safe.doc_id = uid;
  return safe;
}

async function getUser(uid, claims) {
  const snap = await db.collection("users").doc(uid).get();
  if (!snap.exists) fail(401, "Akun tidak ditemukan.", "account_missing");
  const user = snap.data() || {};
  if (!claims || user.nip !== claims.nip || user.role !== claims.role) {
    fail(403, "Identitas akun tidak cocok.", "identity_mismatch");
  }
  return { ref: snap.ref, data: user };
}

function authServiceUrl(service, path) {
  const emulatorHost = process.env.FIREBASE_AUTH_EMULATOR_HOST;
  const base = emulatorHost
    ? "http://" + emulatorHost + "/" + service + ".googleapis.com/v1/"
    : "https://" + service + ".googleapis.com/v1/";
  const key = emulatorHost ? "fake-api-key" : API_KEY.value();
  if (!key) fail(503, "Secret FIREBASE_WEB_API_KEY belum dikonfigurasi.", "auth_exchange_unconfigured");
  return base + path + "?key=" + encodeURIComponent(key);
}

async function issueIdentityToken(uid) {
  // Client type and owner/session mapping live in persistent Auth custom claims
  // on this UID, so they survive refresh-token exchanges.
  const customToken = await auth.createCustomToken(uid);
  const url = authServiceUrl("identitytoolkit", "accounts:signInWithCustomToken");
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: customToken, returnSecureToken: true }),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok || !result.idToken || !result.refreshToken) {
    console.error("Firebase Auth token exchange failed:", result.error?.message || response.status);
    fail(502, "Gagal membuat sesi autentikasi Firebase.", "auth_exchange_failed");
  }
  return { idToken: result.idToken, refreshToken: result.refreshToken, expiresIn: Number(result.expiresIn || 3600) };
}

async function refreshIdentityToken(refreshToken) {
  const url = authServiceUrl("securetoken", "token");
  const body = new URLSearchParams({ grant_type: "refresh_token", refresh_token: refreshToken });
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok || !result.id_token) fail(401, "Sesi kedaluwarsa. Silakan masuk kembali.", "refresh_failed");
  return { idToken: result.id_token, refreshToken: result.refresh_token || refreshToken, expiresIn: Number(result.expires_in || 3600) };
}

async function ensureAuthUser(uid, nip, role) {
  try {
    const user = await auth.getUser(uid);
    if (user.disabled) fail(403, "Akun dinonaktifkan.", "account_disabled");
  } catch (error) {
    if (error.code !== "auth/user-not-found") throw error;
    await auth.createUser({ uid, disabled: false });
  }
  await auth.setCustomUserClaims(uid, { nip, role, client: "desktop" });
  await db.collection("users").doc(uid).set({ uid, nip, role }, { merge: true });
}

async function applyRateLimit(key, limit = 8, windowMs = 10 * 60 * 1000) {
  const ref = db.collection("_rate_limits").doc(sha256(key));
  const cutoff = Date.now() - windowMs;
  await db.runTransaction(async (tx) => {
    const snap = await tx.get(ref);
    const recent = (snap.exists ? (snap.data().attempts || []) : []).filter((time) => Number(time) > cutoff);
    if (recent.length >= limit) fail(429, "Terlalu banyak percobaan. Coba kembali beberapa menit lagi.", "rate_limited");
    recent.push(Date.now());
    tx.set(ref, { attempts: recent, updated_at: now() });
  });
}

async function bearerClaims(req, expectedClient) {
  const match = (req.get("authorization") || "").match(/^Bearer\s+(.+)$/i);
  if (!match) fail(401, "Autentikasi diperlukan.", "unauthenticated");
  let decoded;
  try { decoded = await auth.verifyIdToken(match[1], true); }
  catch { fail(401, "Sesi tidak valid atau sudah kedaluwarsa.", "invalid_token"); }
  if (!decoded.nip || !decoded.role || !["desktop", "remote"].includes(decoded.client) ||
      (expectedClient && decoded.client !== expectedClient)) {
    fail(403, "Akses tidak diizinkan.", "forbidden");
  }

  if (decoded.client === "remote") {
    const sid = cleanString(decoded.sid, 128);
    const ownerUid = cleanString(decoded.ownerUid, 128);
    if (!sid || !ownerUid) fail(403, "Sesi perangkat tidak valid.", "invalid_remote_session");
    await getUser(ownerUid, decoded);
    const session = await db.collection("remote_sessions").doc(sid).get();
    const sessionData = session.exists ? session.data() : null;
    if (!sessionData || sessionData.uid !== ownerUid || sessionData.device_uid !== decoded.uid ||
        sessionData.status !== "connected" ||
        (sessionData.expires_at && sessionData.expires_at.toMillis() < Date.now())) {
      fail(401, "Sesi perangkat telah dihentikan atau kedaluwarsa.", "remote_session_ended");
    }
  } else {
    await getUser(decoded.uid, decoded);
  }
  return decoded;
}

async function ownedClass(classId, claims) {
  const id = cleanString(classId, 150);
  if (!id) fail(400, "ID kelas wajib diisi.", "invalid_class_id");
  const ref = db.collection("kelas").doc(id);
  const snap = await ref.get();
  const data = snap.exists ? snap.data() : null;
  const ownerUid = claims.ownerUid || claims.uid;
  const owned = data && (data.uid ? data.uid === ownerUid : data.nip_guru === claims.nip);
  if (!owned) fail(404, "Kelas tidak ditemukan.", "class_not_found");
  if (!data.uid) {
    await ref.update({ uid: ownerUid, migrated_owner_at: now() });
    data.uid = ownerUid;
  }
  return { ref, data };
}

async function listClasses(claims) {
  const snap = await db.collection("kelas").where("nip_guru", "==", claims.nip).get();
  const ownerUid = claims.ownerUid || claims.uid;
  const visible = snap.docs.filter((doc) => !doc.data().uid || doc.data().uid === ownerUid);
  const legacy = visible.filter((doc) => !doc.data().uid);
  for (let i = 0; i < legacy.length; i += 400) {
    const batch = db.batch();
    legacy.slice(i, i + 400).forEach((doc) => batch.update(doc.ref, { uid: ownerUid, migrated_owner_at: now() }));
    await batch.commit();
  }
  return visible.map((doc) => ({ id: doc.id, ...doc.data(), uid: ownerUid }));
}

async function listStudents(classId, claims) {
  const { ref } = await ownedClass(classId, claims);
  const snap = await ref.collection("siswa").orderBy("nama").get();
  return snap.docs.map((doc) => ({ id: doc.id, ...doc.data() }));
}

async function saveAttendance(payload, claims) {
  const classId = cleanString(payload.id_kelas, 150);
  const meeting = cleanString(payload.pertemuan, 80);
  const { data: cls } = await ownedClass(classId, claims);
  if (!meeting) fail(400, "Pertemuan wajib diisi.", "invalid_meeting");
  const students = Array.isArray(payload.data_siswa) ? payload.data_siswa : [];
  if (students.length > 1000) fail(413, "Jumlah siswa melebihi batas.", "too_many_students");
  const rosterDocs = (await db.collection("kelas").doc(classId).collection("siswa").get()).docs;
  const rosterByNis = new Map(rosterDocs.map((doc) => {
    const row = doc.data();
    return [String(row.nis || doc.id), cleanString(row.nama, 150)];
  }));
  const seenNis = new Set();
  const safeStudents = students.map((student) => {
    const nis = cleanString(String(student.nis || ""), 40);
    if (!nis || !rosterByNis.has(nis) || seenNis.has(nis)) fail(400, "Daftar siswa absensi tidak valid.", "invalid_attendance_roster");
    seenNis.add(nis);
    return {
      nis,
      nama: rosterByNis.get(nis),
      status: ["Hadir", "Sakit", "Izin", "Alpa"].includes(student.status) ? student.status : "Alpa",
      nilai: student.status === "Hadir" ? Math.max(0, Math.min(100, Number(student.nilai) || 0)) : 0,
    };
  });
  const query = await db.collection("absensi").where("id_kelas", "==", classId).where("pertemuan", "==", meeting).limit(1).get();
  const ref = query.empty ? db.collection("absensi").doc() : query.docs[0].ref;
  await ref.set({
    id_kelas: classId,
    nama_kelas: cleanString(payload.nama_kelas, 150) || cleanString(cls.nama_kelas, 150),
    pertemuan: meeting, materi: cleanString(payload.materi, 300),
    catatan_jurnal: cleanString(payload.catatan_jurnal, 2000),
    tanggal: now(), data_siswa: safeStudents,
    sumber: cleanString(payload.sumber, 40) || "Desktop",
    nip_guru: claims.nip, uid: claims.ownerUid || claims.uid,
  });
  return { id: ref.id, message: query.empty ? "Data absensi berhasil disimpan!" : "Data absensi diperbarui!" };
}

async function requireDesktop(claims) {
  if (claims.client !== "desktop") fail(403, "Fitur ini hanya tersedia di aplikasi desktop.", "wrong_client");
}
async function requireRemote(claims) {
  if (claims.client !== "remote") fail(403, "Fitur ini hanya tersedia di perangkat remote.", "wrong_client");
}

async function createPairing(claims) {
  const pairingToken = randomToken(32);
  const sessionId = crypto.randomUUID();
  const expiresAt = admin.firestore.Timestamp.fromMillis(Date.now() + 3 * 60 * 1000);
  await db.collection("remote_pairings").doc(sha256(pairingToken)).set({
    uid: claims.uid, nip: claims.nip, session_id: sessionId,
    expires_at: expiresAt, used: false, created_at: now(),
  });
  const profile = (await getUser(claims.uid, claims)).data;
  await db.collection("remote_sessions").doc(sessionId).set({
    uid: claims.uid, nip: claims.nip, status: "waiting",
    nama_guru: cleanString(profile.nama_lengkap || profile.nama, 150) || "Guru",
    jabatan: cleanString(profile.jabatan, 100) || "Guru Pengajar",
    mapel: cleanString(profile.mapel, 100) || "-",
    connected_device: "-", custom_name: "", command: "none", last_command: "none",
    created_at: now(), last_update: now(),
    expires_at: admin.firestore.Timestamp.fromMillis(Date.now() + 12 * 60 * 60 * 1000),
  });
  return { sessionId, pairUrl: HOSTING_ORIGIN + "/#pair=" + encodeURIComponent(pairingToken), expiresIn: 180 };
}

async function redeemPairing(pairingToken, deviceName) {
  if (typeof pairingToken !== "string" || pairingToken.length < 30 || pairingToken.length > 200) fail(400, "Kode pairing tidak valid.", "invalid_pairing");
  const ref = db.collection("remote_pairings").doc(sha256(pairingToken));
  let pair;
  await db.runTransaction(async (tx) => {
    const snap = await tx.get(ref);
    if (!snap.exists) fail(401, "Kode pairing tidak ditemukan atau sudah digunakan.", "pairing_unavailable");
    pair = snap.data();
    if (pair.used || pair.expires_at.toMillis() < Date.now()) fail(401, "Kode pairing kedaluwarsa atau sudah digunakan.", "pairing_expired");
    tx.update(ref, { used: true, used_at: now() });
  });
  const sessionRef = db.collection("remote_sessions").doc(pair.session_id);
  const sessionSnap = await sessionRef.get();
  if (!sessionSnap.exists || sessionSnap.data().uid !== pair.uid || sessionSnap.data().status !== "waiting") fail(401, "Sesi pairing tidak lagi tersedia.", "session_unavailable");
  const userSnap = await db.collection("users").doc(pair.uid).get();
  if (!userSnap.exists) fail(401, "Akun tidak ditemukan.", "account_missing");
  const user = userSnap.data();
  await sessionRef.update({
    status: "connected", connected_device: cleanString(deviceName, 60) || "Perangkat",
    custom_name: cleanString(deviceName, 60) || "Perangkat", last_update: now(),
  });
  const deviceUid = "remote_" + pair.session_id;
  const claims = {
    nip: pair.nip,
    role: user.role || "guru",
    client: "remote",
    ownerUid: pair.uid,
    sid: pair.session_id,
  };

  // Each remote device gets its own Firebase Auth identity. Persistent custom
  // claims keep this device bound to one owner/session across ID-token refreshes.
  await auth.createUser({ uid: deviceUid, disabled: false });
  try {
    await auth.setCustomUserClaims(deviceUid, claims);
    await sessionRef.update({
      status: "connected",
      device_uid: deviceUid,
      connected_device: cleanString(deviceName, 60) || "Perangkat",
      custom_name: cleanString(deviceName, 60) || "Perangkat",
      last_update: now(),
    });
    const identity = await issueIdentityToken(deviceUid);
    return { ...identity, sessionId: pair.session_id, profile: publicProfile(user, pair.uid) };
  } catch (error) {
    await sessionRef.update({ status: "disconnected", last_update: now() }).catch(() => {});
    await auth.deleteUser(deviceUid).catch(() => {});
    throw error;
  }
}

async function handleAction(action, body, claims, req) {
  switch (action) {
    case "auth.register": {
      const name = cleanString(body.nama_lengkap, 150);
      const nip = cleanString(body.nip, 32);
      const password = typeof body.password === "string" ? body.password : "";
      const suppliedCode = typeof body.registration_code === "string" ? body.registration_code : "";
      const configuredCode = REGISTRATION_CODE.value();
      const mapel = cleanString(body.mapel, 100);
      const suppliedBuffer = Buffer.from(suppliedCode, "utf8");
      const configuredBuffer = Buffer.from(configuredCode || "", "utf8");
      const codeValid = configuredBuffer.length >= 16 &&
        suppliedBuffer.length === configuredBuffer.length &&
        crypto.timingSafeEqual(suppliedBuffer, configuredBuffer);
      if (!codeValid) fail(403, "Kode pendaftaran tidak valid.", "invalid_registration_code");
      if (!name || !/^[0-9]{5,32}$/.test(nip) || password.length < 10 || password.length > 128) {
        fail(400, "Nama, NIP 5–32 digit, dan password 10–128 karakter wajib valid.", "invalid_registration");
      }
      await applyRateLimit("register:" + req.ip, 5, 60 * 60 * 1000);
      const nipKey = sha256(nip);
      const registryRef = db.collection("nip_registry").doc(nipKey);
      const userRef = db.collection("users").doc();
      const uid = userRef.id;
      const registrySnap = await registryRef.get();
      if (registrySnap.exists) fail(409, "NIP ini sudah terdaftar.", "nip_registered");
      const legacy = await db.collection("users").where("nip", "==", nip).limit(1).get();
      if (!legacy.empty) fail(409, "NIP ini sudah terdaftar.", "nip_registered");
      await auth.createUser({ uid, disabled: false });
      try {
        await db.runTransaction(async (tx) => {
          const current = await tx.get(registryRef);
          if (current.exists) fail(409, "NIP ini sudah terdaftar.", "nip_registered");
          tx.create(registryRef, { uid, created_at: now() });
          tx.create(userRef, {
            uid, nip, nama_lengkap: name, mapel, role: "guru",
            password: hashPassword(password), created_at: now(),
          });
        });
      } catch (error) {
        await auth.deleteUser(uid).catch(() => {});
        throw error;
      }
      return { success: true, message: "Pendaftaran berhasil. Silakan masuk." };
    }
    case "auth.login": {
      const nip = cleanString(body.nip, 32);
      const password = typeof body.password === "string" ? body.password : "";
      if (!nip || !password || password.length > 128) fail(400, "NIP dan password wajib diisi.", "invalid_credentials");
      await applyRateLimit("login:" + req.ip + ":" + nip, 8);
      const matches = await db.collection("users").where("nip", "==", nip).limit(2).get();
      if (matches.size !== 1) fail(401, "NIP atau kata sandi salah.", "invalid_credentials");
      const userDoc = matches.docs[0];
      const user = userDoc.data();
      const verified = verifyPassword(password, user.password || "");
      if (!verified.valid) fail(401, "NIP atau kata sandi salah.", "invalid_credentials");
      if (verified.legacy) await userDoc.ref.update({ password: hashPassword(password) });
      const role = cleanString(user.role, 30) || "guru";
      await ensureAuthUser(userDoc.id, nip, role);
      const identity = await issueIdentityToken(userDoc.id);
      return { ...identity, profile: publicProfile(user, userDoc.id) };
    }
    case "remote.redeem":
      return await redeemPairing(cleanString(body.pairingToken, 200), cleanString(body.deviceName, 60));
    case "auth.refresh": {
      const cookieToken = (req.get("cookie") || "").split(";").map((item) => item.trim())
        .find((item) => item.startsWith("gp_refresh="));
      const refreshToken = cleanString(body.refreshToken || (cookieToken ? decodeURIComponent(cookieToken.slice("gp_refresh=".length)) : ""), 4096);
      if (!refreshToken) fail(400, "Refresh token wajib diisi.", "invalid_refresh_token");
      const refreshed = await refreshIdentityToken(refreshToken);
      const decoded = await auth.verifyIdToken(refreshed.idToken, true);
      if (decoded.client === "remote") {
        const sid = cleanString(decoded.sid, 128);
        const ownerUid = cleanString(decoded.ownerUid, 128);
        const session = await db.collection("remote_sessions").doc(sid).get();
        const sessionData = session.exists ? session.data() : null;
        if (!sessionData || sessionData.uid !== ownerUid || sessionData.device_uid !== decoded.uid ||
            sessionData.status !== "connected" ||
            (sessionData.expires_at && sessionData.expires_at.toMillis() < Date.now())) {
          fail(401, "Sesi perangkat telah dihentikan atau kedaluwarsa.", "remote_session_ended");
        }
        await getUser(ownerUid, decoded);
      } else {
        await getUser(decoded.uid, decoded);
      }
      return refreshed;
    }
    default:
      break;
  }

  if (!claims) fail(401, "Autentikasi diperlukan.", "unauthenticated");

  switch (action) {
    case "profile.get":
      return publicProfile((await getUser(claims.uid, claims)).data, claims.uid);
    case "profile.update": {
      await requireDesktop(claims);
      const allowed = ["nama_lengkap", "mapel", "jabatan", "foto_base64"];
      const update = {};
      for (const key of allowed) {
        if (Object.prototype.hasOwnProperty.call(body.data || {}, key)) {
          const value = body.data[key];
          if (key === "foto_base64" && (typeof value !== "string" ||
              value.length > 700000 ||
              !/^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$/.test(value))) {
            fail(400, "Foto harus berupa JPEG, PNG, atau WebP dengan ukuran yang diizinkan.", "invalid_photo");
          }
          update[key] = typeof value === "string" ? value.slice(0, key === "foto_base64" ? 700000 : 200) : value;
        }
      }
      if (!Object.keys(update).length) fail(400, "Tidak ada perubahan profil.", "empty_update");
      const user = await getUser(claims.uid, claims);
      await user.ref.update(update);
      return { success: true, profile: publicProfile({ ...user.data, ...update }, claims.uid) };
    }
    case "profile.password": {
      await requireDesktop(claims);
      const oldPassword = typeof body.currentPassword === "string" ? body.currentPassword : "";
      const newPassword = typeof body.newPassword === "string" ? body.newPassword : "";
      if (newPassword.length < 10 || newPassword.length > 128) fail(400, "Password baru minimal 10 karakter.", "weak_password");
      const user = await getUser(claims.uid, claims);
      if (!verifyPassword(oldPassword, user.data.password || "").valid) fail(401, "Password saat ini tidak cocok.", "invalid_current_password");
      await user.ref.update({ password: hashPassword(newPassword), password_changed_at: now() });
      await auth.revokeRefreshTokens(claims.uid);
      return { success: true, reauthenticate: true };
    }
    case "class.create": {
      await requireDesktop(claims);
      const name = cleanString(body.data && body.data.nama_kelas, 150);
      const subject = cleanString(body.data && body.data.mata_pelajaran, 120);
      if (!name || !subject) fail(400, "Nama kelas dan mata pelajaran wajib diisi.", "invalid_class");
      const data = {
        nama_kelas: name, mata_pelajaran: subject,
        semester: ["Ganjil", "Genap"].includes(body.data.semester) ? body.data.semester : "Ganjil",
        jadwal: cleanString(body.data.jadwal, 200),
        nip_guru: claims.nip, uid: claims.uid, created_at: now(),
      };
      const ref = await db.collection("kelas").add(data);
      return { success: true, id: ref.id, message: "Kelas " + name + " berhasil dibuat!" };
    }
    case "class.list":
      await requireDesktop(claims);
      return await listClasses(claims);
    case "class.delete": {
      await requireDesktop(claims);
      const owned = await ownedClass(body.classId, claims);
      const studentSnap = await owned.ref.collection("siswa").get();
      for (let i = 0; i < studentSnap.docs.length; i += 400) {
        const batch = db.batch();
        studentSnap.docs.slice(i, i + 400).forEach((doc) => batch.delete(doc.ref));
        await batch.commit();
      }
      const attendance = await db.collection("absensi").where("id_kelas", "==", owned.ref.id).get();
      for (let i = 0; i < attendance.docs.length; i += 400) {
        const batch = db.batch();
        attendance.docs.slice(i, i + 400).forEach((doc) => batch.delete(doc.ref));
        await batch.commit();
      }
      await owned.ref.delete();
      return { success: true };
    }
    case "students.import": {
      await requireDesktop(claims);
      const owned = await ownedClass(body.classId, claims);
      if (!Array.isArray(body.students) || body.students.length > 2000) fail(400, "Data siswa tidak valid (maksimal 2.000).", "invalid_students");
      const rows = body.students.map((row) => ({
        nis: cleanString(String(row.nis || ""), 40),
        nama: cleanString(row.nama, 150),
        gender: cleanString(row.gender, 20),
      })).filter((row) => row.nis && row.nama);
      for (let i = 0; i < rows.length; i += 400) {
        const batch = db.batch();
        rows.slice(i, i + 400).forEach((row) => batch.set(owned.ref.collection("siswa").doc(row.nis), row));
        await batch.commit();
      }
      return { success: true, count: rows.length };
    }
    case "students.list":
      await requireDesktop(claims);
      return await listStudents(body.classId, claims);
    case "students.count": {
      await requireDesktop(claims);
      const owned = await ownedClass(body.classId, claims);
      const snapshot = await owned.ref.collection("siswa").count().get();
      return { count: snapshot.data().count || 0 };
    }
    case "attendance.get": {
      await requireDesktop(claims);
      await ownedClass(body.classId, claims);
      const snap = await db.collection("absensi").where("id_kelas", "==", body.classId).where("pertemuan", "==", cleanString(body.pertemuan, 80)).limit(1).get();
      return snap.empty ? null : { id: snap.docs[0].id, ...snap.docs[0].data() };
    }
    case "attendance.list": {
      await requireDesktop(claims);
      await ownedClass(body.classId, claims);
      const snap = await db.collection("absensi").where("id_kelas", "==", body.classId).get();
      return snap.docs.map((doc) => ({ id: doc.id, ...doc.data() })).sort((a, b) => String(a.pertemuan || "").localeCompare(String(b.pertemuan || ""), "id", { numeric: true }));
    }
    case "attendance.save":
      await requireDesktop(claims);
      return await saveAttendance(body.data || {}, claims);
    case "remote.createPairing":
      await requireDesktop(claims);
      return await createPairing(claims);
    case "remote.sessions.list": {
      await requireDesktop(claims);
      const snap = await db.collection("remote_sessions").where("nip", "==", claims.nip).get();
      const visible = snap.docs.filter((doc) => !doc.data().uid || doc.data().uid === claims.uid);
      const legacy = visible.filter((doc) => !doc.data().uid);
      for (let i = 0; i < legacy.length; i += 400) {
        const batch = db.batch();
        legacy.slice(i, i + 400).forEach((doc) => batch.update(doc.ref, { uid: claims.uid, migrated_owner_at: now() }));
        await batch.commit();
      }
      return visible.map((doc) => ({ id: doc.id, ...doc.data(), uid: claims.uid }));
    }
    case "remote.session.get": {
      await requireDesktop(claims);
      const ref = db.collection("remote_sessions").doc(cleanString(body.sessionId, 128));
      const snap = await ref.get();
      if (!snap.exists || ((snap.data().uid ? snap.data().uid !== (claims.ownerUid || claims.uid) : snap.data().nip !== claims.nip))) return null;
      return { id: snap.id, ...snap.data() };
    }
    case "remote.session.update": {
      await requireDesktop(claims);
      const ref = db.collection("remote_sessions").doc(cleanString(body.sessionId, 128));
      const snap = await ref.get();
      if (!snap.exists || ((snap.data().uid ? snap.data().uid !== (claims.ownerUid || claims.uid) : snap.data().nip !== claims.nip))) fail(404, "Sesi tidak ditemukan.", "session_not_found");
      const changes = {};
      if (typeof body.custom_name === "string") changes.custom_name = cleanString(body.custom_name, 60);
      if (["disconnected_by_host", "disconnected"].includes(body.status)) changes.status = body.status;
      if (body.last_command === "none") changes.last_command = "none";
      if (body.command === "none") changes.command = "none";
      changes.last_update = now();
      await ref.update(changes);
      return { success: true };
    }
    case "remote.session.delete": {
      await requireDesktop(claims);
      const ref = db.collection("remote_sessions").doc(cleanString(body.sessionId, 128));
      const snap = await ref.get();
      if (!snap.exists || ((snap.data().uid ? snap.data().uid !== (claims.ownerUid || claims.uid) : snap.data().nip !== claims.nip))) fail(404, "Sesi tidak ditemukan.", "session_not_found");
      await ref.delete();
      return { success: true };
    }
    case "remote.pollCommands": {
      await requireDesktop(claims);
      const snap = await db.collection("remote_sessions").where("nip", "==", claims.nip).get();
      const items = [];
      for (const doc of snap.docs) {
        const data = doc.data();
        if (data.uid && data.uid !== claims.uid) continue;
        if (data.last_command === "refresh_ui" || String(data.last_command || "").startsWith("refresh_ui_")) {
          items.push({ id: doc.id, type: "refresh" });
          await doc.ref.update({ last_command: "none" });
        }
        if (data.command === "buka_dashboard" || data.command === "buka_kelas") {
          items.push({ id: doc.id, type: "navigate", page: data.command === "buka_dashboard" ? 0 : 1 });
          await doc.ref.update({ command: "none" });
        }
      }
      return items;
    }
    case "remote.session": {
      await requireRemote(claims);
      const session = await db.collection("remote_sessions").doc(claims.sid).get();
      if (!session.exists || session.data().uid !== claims.ownerUid || session.data().device_uid !== claims.uid) {
        fail(401, "Sesi perangkat tidak tersedia.", "remote_session_ended");
      }
      return { id: session.id, ...session.data() };
    }
    case "remote.heartbeat":
      await requireRemote(claims);
      await db.collection("remote_sessions").doc(claims.sid).update({ last_update: now() });
      return { success: true };
    case "remote.logout": {
      await requireRemote(claims);
      await db.collection("remote_sessions").doc(claims.sid).update({ status: "disconnected", last_update: now() });
      await auth.revokeRefreshTokens(claims.uid).catch(() => {});
      await auth.deleteUser(claims.uid).catch(() => {});
      return { success: true };
    }
    case "remote.classes": {
      await requireRemote(claims);
      const classes = await listClasses(claims);
      return await Promise.all(classes.map(async (item) => {
        const count = await db.collection("kelas").doc(item.id).collection("siswa").count().get();
        return { ...item, jumlah_siswa: count.data().count || 0 };
      }));
    }
    case "remote.students":
      await requireRemote(claims);
      return await listStudents(body.classId, claims);
    case "remote.attendance.get": {
      await requireRemote(claims);
      await ownedClass(body.classId, claims);
      const snap = await db.collection("absensi").where("id_kelas", "==", body.classId).where("pertemuan", "==", cleanString(body.pertemuan, 80)).limit(1).get();
      return snap.empty ? null : { id: snap.docs[0].id, ...snap.docs[0].data() };
    }
    case "remote.attendance.save": {
      await requireRemote(claims);
      const result = await saveAttendance({ ...(body.data || {}), sumber: "Mobile" }, claims);
      await db.collection("remote_sessions").doc(claims.sid).update({ last_command: "refresh_ui", last_update: now() });
      return result;
    }
    case "remote.profile": {
      await requireRemote(claims);
      const ownerUid = claims.ownerUid || claims.uid;
      return publicProfile((await getUser(ownerUid, claims)).data, ownerUid);
    }
    default:
      fail(404, "Aksi API tidak dikenal.", "unknown_action");
  }
}

exports.api = onRequest({
  region: REGION, timeoutSeconds: 60, memory: "512MiB", secrets: [API_KEY, REGISTRATION_CODE], cors: false,
}, async (req, res) => {
  res.set("Cache-Control", "no-store, max-age=0");
  res.set("Pragma", "no-cache");
  res.set("X-Content-Type-Options", "nosniff");
  res.set("Referrer-Policy", "no-referrer");
  const origin = req.get("origin");
  if (origin && ALLOWED_ORIGINS.has(origin)) {
    res.set("Access-Control-Allow-Origin", origin);
    res.set("Vary", "Origin");
    res.set("Access-Control-Allow-Headers", "Content-Type, Authorization");
    res.set("Access-Control-Allow-Methods", "POST, OPTIONS");
    res.set("Access-Control-Max-Age", "3600");
  } else if (origin) {
    return res.status(403).json({ error: "Origin tidak diizinkan.", code: "cors_denied" });
  }
  if (req.method === "OPTIONS") return res.status(204).send("");
  if (req.method !== "POST") return res.status(405).json({ error: "Method tidak diizinkan.", code: "method_not_allowed" });
  if (!req.is("application/json")) return res.status(415).json({ error: "Gunakan application/json.", code: "invalid_content_type" });
  try {
    const body = req.body || {};
    const action = cleanString(body.action, 80);
    if (!action) fail(400, "Aksi API wajib diisi.", "missing_action");
    let claims = null;
    if (!["auth.login", "auth.register", "auth.refresh", "remote.redeem"].includes(action)) claims = await bearerClaims(req);
    const result = await handleAction(action, body, claims, req);
    if (action === "remote.redeem" && result && result.refreshToken) {
      res.set("Set-Cookie", "gp_refresh=" + encodeURIComponent(result.refreshToken) + "; HttpOnly; Secure; SameSite=Strict; Path=/api; Max-Age=43200");
      const { refreshToken, ...safeResult } = result;
      return res.status(200).json({ data: safeResult });
    }
    if (action === "auth.refresh" && result && result.refreshToken) {
      const cookieRefresh = (req.get("cookie") || "").split(";")
        .some((item) => item.trim().startsWith("gp_refresh="));
      if (cookieRefresh || req.get("origin")) {
        res.set("Set-Cookie", "gp_refresh=" + encodeURIComponent(result.refreshToken) + "; HttpOnly; Secure; SameSite=Strict; Path=/api; Max-Age=43200");
        const { refreshToken, ...safeResult } = result;
        return res.status(200).json({ data: safeResult });
      }
    }
    if (action === "remote.logout") {
      res.set("Set-Cookie", "gp_refresh=; HttpOnly; Secure; SameSite=Strict; Path=/api; Max-Age=0");
    }
    return res.status(200).json({ data: serializeForClient(result) });
  } catch (error) {
    const status = Number(error.status) || 500;
    if (status >= 500) console.error("GuruPro API error:", error);
    return res.status(status).json({
      error: status >= 500 ? "Terjadi kesalahan pada server." : error.message,
      code: error.code || "internal_error",
    });
  }
});
