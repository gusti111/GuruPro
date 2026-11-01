/* GuruPro remote PWA: protected data is accessed only through the authenticated API. */
(() => {
  "use strict";
  const API_URL = "/api";
  let idToken = null, sessionId = null, profile = null;
  let activeClass = null, activeClassName = "", currentMeeting = 1;
  let existingAttendanceId = null, deferredPrompt = null, heartbeatTimer = null;
  let isFetchingClasses = false;
  const $ = (id) => document.getElementById(id);
  const setText = (id, value) => { const el = $(id); if (el) el.textContent = value == null ? "" : String(value); };
  const esc = (value) => String(value == null ? "" : value).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

  async function request(action, payload = {}, authRequired = true, retry = true) {
    const headers = { "Content-Type": "application/json", "Accept": "application/json" };
    if (authRequired && idToken) headers.Authorization = "Bearer " + idToken;
    const response = await fetch(API_URL, {
      method: "POST", headers, credentials: "same-origin", cache: "no-store",
      body: JSON.stringify(Object.assign({ action }, payload))
    });
    const result = await response.json().catch(() => ({}));
    if (response.status === 401 && retry && authRequired) {
      await refreshSession();
      return request(action, payload, authRequired, false);
    }
    if (!response.ok || !Object.prototype.hasOwnProperty.call(result, "data")) {
      const error = new Error(result.error || "Permintaan gagal.");
      error.status = response.status;
      error.code = result.code || "request_failed";
      throw error;
    }
    return result.data;
  }

  async function refreshSession() {
    const response = await fetch(API_URL, {
      method: "POST", headers: { "Content-Type": "application/json", "Accept": "application/json" },
      credentials: "same-origin", cache: "no-store",
      body: JSON.stringify({ action: "auth.refresh" })
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.data || !result.data.idToken) {
      idToken = null;
      throw new Error(result.error || "Sesi tidak tersedia. Silakan scan QR terbaru.");
    }
    idToken = result.data.idToken;
    return idToken;
  }

  function toast(message) {
    const el = $("toast");
    if (!el) return;
    el.textContent = message;
    el.classList.add("show");
    window.setTimeout(() => el.classList.remove("show"), 3000);
  }

  function nav(id) {
    document.querySelectorAll(".page").forEach((page) => page.classList.remove("active"));
    if ($(id)) $(id).classList.add("active");
    document.querySelectorAll(".nav-i").forEach((item) => item.classList.remove("active"));
    if (id.indexOf("home") >= 0 && $("n-home")) $("n-home").classList.add("active");
    if (id.indexOf("kelas") >= 0 && $("n-kelas")) $("n-kelas").classList.add("active");
    if (id.indexOf("profil") >= 0 && $("n-profil")) $("n-profil").classList.add("active");
    window.scrollTo(0, 0);
  }
  window.nav = nav;

  function initClock() {
    const tick = () => {
      if ($("clock")) $("clock").textContent = new Date().toLocaleTimeString("id-ID", {
        hour12: false, hour: "2-digit", minute: "2-digit"
      });
    };
    tick();
    window.setInterval(tick, 1000);
  }

  function hideLoader() {
    const loader = $("initial-loader");
    if (loader) {
      loader.style.opacity = "0";
      window.setTimeout(() => loader.remove(), 500);
    }
  }

  function disconnected(message) {
    if (heartbeatTimer) window.clearInterval(heartbeatTimer);
    heartbeatTimer = null;
    idToken = null;
    sessionId = null;
    if ($("ov")) $("ov").style.display = "flex";
    const paragraph = $("ov") && $("ov").querySelector("p");
    if (paragraph && message) paragraph.textContent = message;
  }

  function renderProfile(user, session) {
    profile = user || profile || {};
    const name = profile.nama_lengkap || session.nama_guru || "Guru";
    setText("w-name", "Halo, " + name.split(" ")[0] + "!");
    setText("w-job", profile.jabatan || session.jabatan || "Guru");
    setText("device-name", session.custom_name || session.connected_device || "Perangkat");
    setText("p-name", name);
    setText("p-job", profile.jabatan || session.jabatan || "Guru");
    setText("p-nip", profile.nip || session.nip || "-");
    setText("p-sid", sessionId ? sessionId.slice(0, 8) + "…" : "-");
    const photo = profile.foto_base64;
    if (photo && typeof photo === "string" && /^data:image\/(jpeg|png|webp);base64,/.test(photo) && photo.length < 700000) {
      $("p-img").src = photo;
    } else if ($("p-img")) {
      $("p-img").removeAttribute("src");
    }
  }

  async function initializeSession() {
    const pairingToken = new URLSearchParams(window.location.hash.slice(1)).get("pair");
    if (pairingToken) {
      window.history.replaceState({}, document.title, window.location.pathname);
      const ua = navigator.userAgent;
      const deviceName = /Android/i.test(ua) ? "Android" : (/iPhone|iPad/i.test(ua) ? "iPhone/iPad" : "Browser");
      const pairing = await request("remote.redeem", { pairingToken: pairingToken, deviceName: deviceName }, false);
      idToken = pairing.idToken;
      sessionId = pairing.sessionId;
      profile = pairing.profile;
    } else {
      await refreshSession();
    }
    if (!idToken) throw new Error("Sesi tidak ditemukan. Scan QR pairing terbaru.");
    const session = await request("remote.session");
    if (!session || session.status !== "connected") throw new Error("Sesi perangkat sudah berakhir.");
    if (!profile) profile = await request("remote.profile");
    renderProfile(profile, session);
    await loadClasses();
    if (heartbeatTimer) window.clearInterval(heartbeatTimer);
    heartbeatTimer = window.setInterval(async () => {
      try {
        await request("remote.heartbeat");
        const current = await request("remote.session");
        if (!current || current.status !== "connected") disconnected("Sesi dihentikan dari komputer.");
      } catch (error) {
        disconnected(error.message);
      }
    }, 30000);
  }

  async function loadClasses() {
    if (isFetchingClasses) return;
    isFetchingClasses = true;
    try {
      const result = await request("remote.classes");
      const classes = Array.isArray(result) ? result : [];
      setText("t-kelas", classes.length);
      setText("s-t-k", classes.length);
      setText("s-t-s", classes.reduce((sum, item) => sum + Number(item.jumlah_siswa || 0), 0));
      const list = $("cls-list"), quick = $("quick-list");
      if (!classes.length) {
        list.innerHTML = '<p style="text-align:center;color:#94A3B8;margin-top:50px">Belum ada kelas</p>';
        quick.innerHTML = '<p style="color:#94A3B8;font-size:13px;">Belum ada kelas untuk ditampilkan.</p>';
        return;
      }
      list.innerHTML = classes.map((item) => {
        return '<button type="button" class="class-item js-open-class" data-id="' + esc(item.id) +
          '" data-name="' + esc(item.nama_kelas) + '" style="text-align:left;width:100%;cursor:pointer">' +
          '<div class="class-head"><div><h4 style="font-size:18px;font-weight:800;color:#0F172A;margin-bottom:5px;">' +
          esc(item.nama_kelas) + '</h4><p style="font-size:14px;color:#64748B;">' +
          esc(item.mata_pelajaran || "Umum") + '</p></div><span class="btn-arr"><i class="ri-arrow-right-s-line"></i></span></div>' +
          '<div class="class-meta" style="border-top:1px dashed #E2E8F0;margin-top:15px;padding-top:10px;">' +
          '<span class="meta-tag"><i class="ri-user-line"></i> ' + Number(item.jumlah_siswa || 0) + ' Siswa</span>' +
          '<span class="meta-tag active">Aktif</span></div></button>';
      }).join("");
      quick.innerHTML = classes.slice(0, 3).map((item) => {
        return '<button type="button" class="js-open-class" data-id="' + esc(item.id) +
          '" data-name="' + esc(item.nama_kelas) +
          '" style="width:100%;background:white;padding:18px;border-radius:16px;margin-bottom:10px;border:1px solid #E2E8F0;display:flex;justify-content:space-between;align-items:center;text-align:left;cursor:pointer">' +
          '<span><strong style="display:block;color:#0F172A;">' + esc(item.nama_kelas) +
          '</strong><small style="color:#64748B;">' + Number(item.jumlah_siswa || 0) +
          ' Siswa</small></span><i class="ri-arrow-right-s-line" style="color:#94A3B8;font-size:20px;"></i></button>';
      }).join("");
      document.querySelectorAll(".js-open-class").forEach((button) =>
        button.addEventListener("click", () => openClass(button.dataset.id, button.dataset.name)));
    } catch (error) {
      toast(error.message);
    } finally {
      isFetchingClasses = false;
    }
  }

  async function openClass(id, name) {
    activeClass = id;
    activeClassName = name;
    currentMeeting = 1;
    setText("abs-title", name);
    setText("meet-val", currentMeeting);
    nav("p-absen");
    await loadAttendance();
  }
  window.openA = openClass;

  function changeMeeting(delta) {
    if (currentMeeting + delta < 1 || currentMeeting + delta > 16) return;
    currentMeeting += delta;
    setText("meet-val", currentMeeting);
    loadAttendance();
  }
  window.chMeet = changeMeeting;

  function renderStudent(student, index, oldData) {
    const old = oldData.find((item) => String(item.nis) === String(student.nis));
    const status = old && old.status ? old.status : "Hadir";
    const score = old && Number.isFinite(Number(old.nilai)) ? Number(old.nilai) : 75;
    const options = [["Hadir", "H"], ["Sakit", "S"], ["Izin", "I"], ["Alpa", "A"]];
    const inputHtml = options.map((option) => {
      const id = "stu-" + index + "-" + option[1];
      return '<div class="radio-box"><input type="radio" name="status-' + index + '" id="' + id +
        '" value="' + option[0] + '"' + (status === option[0] ? " checked" : "") +
        '><label for="' + id + '">' + option[1] + '</label></div>';
    }).join("");
    return '<div class="st-item" data-nis="' + esc(student.nis) + '" data-name="' + esc(student.nama) + '">' +
      '<div class="st-head"><div><strong style="font-size:16px;color:#0F172A;">' + esc(student.nama) +
      '</strong><br><small style="background:#F1F5F9;padding:2px 8px;border-radius:4px;color:#64748B;">' +
      esc(student.nis) + '</small></div></div><div class="st-act">' + inputHtml +
      '</div><div class="score-inp"><span>Nilai</span><input class="js-score" type="number" min="0" max="100" value="' +
      score + '"' + (status !== "Hadir" ? " disabled" : "") + '></div></div>';
  }

  async function loadAttendance() {
    const container = $("stu-list");
    container.innerHTML = '<div style="text-align:center;padding:50px;color:#94A3B8;">Loading...</div>';
    const meeting = "Pertemuan Ke-" + currentMeeting;
    existingAttendanceId = null;
    try {
      const values = await Promise.all([
        request("remote.attendance.get", { classId: activeClass, pertemuan: meeting }),
        request("remote.students", { classId: activeClass })
      ]);
      const attendance = values[0];
      const roster = Array.isArray(values[1]) ? values[1] : [];
      existingAttendanceId = attendance && attendance.id ? attendance.id : null;
      $("i-materi").value = attendance && attendance.materi ? attendance.materi : "";
      $("i-catatan").value = attendance && attendance.catatan_jurnal ? attendance.catatan_jurnal : "";
      const button = $("btn-save");
      button.innerHTML = existingAttendanceId ? "UPDATE ABSENSI" : '<i class="ri-save-3-line"></i> SIMPAN ABSENSI';
      button.style.background = existingAttendanceId ? "#2563EB" : "#0F172A";
      if (!roster.length) {
        container.innerHTML = '<p style="text-align:center;color:#94A3B8;padding:40px">Belum ada siswa di kelas ini.</p>';
        return;
      }
      const oldData = attendance ? (attendance.data_siswa || attendance.detail || []) : [];
      container.innerHTML = roster.map((student, index) => renderStudent(student, index, oldData)).join("");
      container.querySelectorAll(".st-item").forEach((row) => {
        row.querySelectorAll('input[type="radio"]').forEach((input) => input.addEventListener("change", () => {
          const score = row.querySelector(".js-score");
          const active = row.querySelector('input[type="radio"]:checked').value === "Hadir";
          score.disabled = !active;
          if (!active) score.value = 0;
          else if (Number(score.value) === 0) score.value = 75;
        }));
      });
    } catch (error) {
      container.innerHTML = '<p style="color:#DC2626;padding:30px;text-align:center;">' + esc(error.message) + '</p>';
    }
  }

  async function saveAttendance() {
    const material = $("i-materi").value.trim();
    if (!material) { toast("Isi materi terlebih dahulu."); return; }
    const button = $("btn-save");
    button.disabled = true;
    button.textContent = "Menyimpan...";
    try {
      const dataStudents = [];
      let invalid = false;
      document.querySelectorAll(".st-item").forEach((row) => {
        const selected = row.querySelector('input[type="radio"]:checked');
        const score = Number.parseInt(row.querySelector(".js-score").value, 10) || 0;
        if (!selected || score < 0 || score > 100) invalid = true;
        dataStudents.push({
          nis: row.dataset.nis, nama: row.dataset.name,
          status: selected ? selected.value : "Alpa",
          nilai: selected && selected.value === "Hadir" ? score : 0
        });
      });
      if (invalid) throw new Error("Status dan nilai siswa harus valid (0–100).");
      const result = await request("remote.attendance.save", { data: {
        id_kelas: activeClass, nama_kelas: activeClassName,
        pertemuan: "Pertemuan Ke-" + currentMeeting, materi: material,
        catatan_jurnal: $("i-catatan").value.trim(), data_siswa: dataStudents, sumber: "Mobile"
      }});
      toast(result.message || "Absensi tersimpan.");
      nav("p-home");
    } catch (error) {
      toast(error.message);
    } finally {
      button.disabled = false;
      button.innerHTML = existingAttendanceId ? "UPDATE ABSENSI" : '<i class="ri-save-3-line"></i> SIMPAN ABSENSI';
    }
  }
  window.save = saveAttendance;

  async function logout(force) {
    if (!force && !window.confirm("Putuskan koneksi perangkat ini?")) return;
    try { if (idToken) await request("remote.logout"); }
    catch (error) { console.warn("Remote logout:", error.message); }
    disconnected("Sesi telah diputus. Scan QR baru untuk menghubungkan kembali.");
  }
  window.logout = logout;

  function resetApp() {
    window.location.replace(window.location.pathname);
  }
  window.resetApp = resetApp;

  async function installPWA() {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    $("install-btn-container").style.display = "none";
  }
  window.installPWA = installPWA;

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;
    $("install-btn-container").style.display = "block";
  });

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("./service-worker.js").catch((error) =>
        console.warn("Service worker unavailable:", error));
    });
  }

  document.addEventListener("DOMContentLoaded", async () => {
    initClock();
    try { await initializeSession(); }
    catch (error) {
      console.warn("GuruPro remote:", error.message);
      disconnected(error.message);
    } finally { hideLoader(); }
  });
})();