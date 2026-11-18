// app/static/assets/js/main.js
const API_BASE = "/api/v1/";

async function fetchComboboxData(url, query = "") {
  try {
    const fullUrl = query
      ? `${API_BASE}${url}?q=${encodeURIComponent(query)}`
      : `${API_BASE}${url}`;
    const res = await fetch(fullUrl);
    if (!res.ok) throw new Error("Network error");
    const data = await res.json();
    return Array.isArray(data)
      ? data.map((item) => ({
          id: item.id_perusahaan ?? item.id_pos ?? item.id,
          nama: item.nama_perusahaan || item.nama_pos || item.nama,
          kode: item.kode,
        }))
      : [];
  } catch (err) {
    console.error("Gagal load data:", err);
    return [];
  }
}

function createCombobox(input, url, onSelect) {
  const container = input.parentElement;
  let dropdown = container.querySelector(".combobox-dropdown");
  if (!dropdown) {
    dropdown = document.createElement("ul");
    dropdown.className =
      "combobox-dropdown position-absolute start-0 end-0 bg-white border rounded shadow-lg overflow-auto";
    dropdown.style.maxHeight = "12rem";
    dropdown.style.zIndex = "1050";
    dropdown.style.top = "100%";
    dropdown.style.marginTop = "0.125rem";
    container.style.position = "relative";
    container.appendChild(dropdown);
  }

  const toggleBtn = container.querySelector(".combobox-toggle");
  let debounceTimer;

  async function render(query = "") {
    const items = await fetchComboboxData(url, query);
    dropdown.innerHTML = "";
    if (items.length === 0) {
      dropdown.innerHTML =
        '<li class="px-3 py-2 text-muted small">Tidak ditemukan</li>';
    } else {
      items.forEach((item) => {
        const li = document.createElement("li");
        li.className = "px-3 py-2 cursor-pointer small";
        li.textContent = item.kode ? `${item.nama} (${item.kode})` : item.nama;
        li.onclick = () => {
          input.value = item.kode ? `${item.nama} (${item.kode})` : item.nama;
          input.dataset.id = item.id;
          if (onSelect) onSelect(item);
          dropdown.classList.remove("show");
        };
        li.onmouseenter = () => (li.style.backgroundColor = "#f8f9fa");
        li.onmouseleave = () => (li.style.backgroundColor = "");
        dropdown.appendChild(li);
      });
    }
    dropdown.classList.add("show");
  }

  input.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    const val = input.value.trim();
    if (!val) {
      dropdown.classList.remove("show");
      return;
    }
    debounceTimer = setTimeout(() => render(val), 300);
  });

  if (toggleBtn) {
    toggleBtn.onclick = () =>
      dropdown.classList.contains("show")
        ? dropdown.classList.remove("show")
        : render(input.value.trim());
  }

  document.addEventListener("click", (e) => {
    if (!container.contains(e.target)) dropdown.classList.remove("show");
  });
}

// DOM READY
document.addEventListener("DOMContentLoaded", () => {
  const alamatInput = document.getElementById("alamat");
  const statusSelect = document.getElementById("status");
  const regularFields = document.getElementById("regularFields");
  const lainnyaFields = document.getElementById("lainnyaFields");

  // Status change handler - SHOW/HIDE Lainnya fields
  if (statusSelect) {
    statusSelect.addEventListener("change", (e) => {
      if (e.target.value === "Lainnya") {
        regularFields?.classList.add("d-none");
        lainnyaFields?.classList.remove("d-none");
      } else {
        regularFields?.classList.remove("d-none");
        lainnyaFields?.classList.add("d-none");
      }
    });
  }

  // Combobox Perusahaan
  createCombobox(alamatInput, "api/mitra/all");

  // Init Combobox POS
  function initPosInputs() {
    document
      .querySelectorAll(".pos-input:not([data-init])")
      .forEach((input) => {
        createCombobox(input, "api/pos/destinations", (item) => {
          console.log(
            "POS berhasil dipilih:",
            item.nama_pos || item.nama,
            "ID:",
            item.id_pos || item.id,
          );
        });
        input.dataset.init = "true";
      });
  }

  initPosInputs();
  setTimeout(initPosInputs, 100);
  setTimeout(initPosInputs, 500);

  const observer = new MutationObserver(() => {
    initPosInputs();
  });
  observer.observe(document.getElementById("tujuanContainer"), {
    childList: true,
    subtree: true,
  });

  // POPUP TUJUAN HANDLER
  const popupOverlay = document.getElementById("popupOverlay");
  const popupForm = document.getElementById("popupForm");
  const addContainer = document.getElementById("addContainer");
  const cancelPopup = document.getElementById("cancelPopup");
  const tujuanContainer = document.getElementById("tujuanContainer");

  if (addContainer) {
    addContainer.addEventListener("click", () => {
      if (popupOverlay) {
        popupOverlay.classList.remove("d-none");
        popupOverlay.classList.add("d-flex");
      }
    });
  }

  if (cancelPopup) {
    cancelPopup.addEventListener("click", () => {
      if (popupOverlay) {
        popupOverlay.classList.add("d-none");
        popupOverlay.classList.remove("d-flex");
      }
      if (popupForm) popupForm.reset();
    });
  }

  if (popupForm) {
    popupForm.addEventListener("submit", (e) => {
      e.preventDefault();

      const popupPosInput = document.getElementById("popupPos");
      const pos = popupPosInput.value.trim();
      const posId = popupPosInput.dataset.id;
      const bertemu = document.getElementById("popupBertemu").value.trim();
      const bagian = document.getElementById("popupBagian").value.trim();
      const keperluan = document.getElementById("popupKeperluan").value.trim();

      if (!pos || !posId || !bertemu) {
        return alert(
          "POS dan Bertemu Dengan harus diisi & dipilih dari daftar!",
        );
      }

      const box = document.createElement("div");
      box.className = "border rounded p-3 mb-3 position-relative";

      const posInput = document.createElement("input");
      posInput.type = "text";
      posInput.className = "form-control form-control-sm pos-input mb-2";
      posInput.value = pos;
      posInput.dataset.id = posId;
      posInput.readOnly = true;

      const bertemuInput = Object.assign(document.createElement("input"), {
        type: "text",
        className: "form-control form-control-sm mb-2",
        value: bertemu,
        readOnly: true,
      });

      const bagianInput = Object.assign(document.createElement("input"), {
        type: "text",
        className: "form-control form-control-sm mb-2",
        value: bagian,
        readOnly: true,
      });

      const keperluanInput = Object.assign(document.createElement("input"), {
        type: "text",
        className: "form-control form-control-sm mb-3",
        value: keperluan,
        readOnly: true,
      });

      const labels = ["POS", "Bertemu Dengan", "Bagian", "Keperluan"];
      [posInput, bertemuInput, bagianInput, keperluanInput].forEach(
        (input, i) => {
          const wrapper = document.createElement("div");
          wrapper.className = "mb-2";
          wrapper.innerHTML = `<label class="form-label small fw-semibold">${labels[i]}</label>`;
          wrapper.appendChild(input);
          box.appendChild(wrapper);
        },
      );

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className =
        "btn btn-sm btn-danger position-absolute top-0 end-0 m-2";
      removeBtn.innerHTML = "&times;";
      removeBtn.onclick = () => box.remove();
      box.appendChild(removeBtn);

      tujuanContainer.appendChild(box);

      popupOverlay.classList.remove("d-flex");
      popupOverlay.classList.add("d-none");
      popupForm.reset();

      document.getElementById("removeContainer").classList.remove("d-none");
    });
  }

  if (popupOverlay) {
    popupOverlay.addEventListener("click", (e) => {
      if (e.target === popupOverlay) {
        popupOverlay.classList.add("d-none");
        popupOverlay.classList.remove("d-flex");
      }
    });
  }

  // ==========================================
  // SUBMIT FORM
  // ==========================================
  document.getElementById("visitorForm").onsubmit = async (e) => {
    e.preventDefault();

    const status = document.getElementById("status").value;

    // PERBAIKAN: Hanya status "Lainnya" yang tidak memerlukan tujuan spesifik
    const isLainnya = status === "Lainnya";

    let perusahaanId = null;
    let alamatValue = alamatInput.value.trim();

    // Validasi Perusahaan
    if (!isLainnya) {
      // Jika bukan Lainnya, cek apakah user memilih perusahaan dari dropdown (jika diperlukan)
      // (Logika ini bisa disesuaikan, apakah Tamu Umum wajib punya PT atau tidak)
      if (alamatInput.dataset.id) {
        perusahaanId = parseInt(alamatInput.dataset.id);
      }
    }

    const tujuanList = [];
    let ok = true;

    // PERBAIKAN: Ambil tujuan untuk SEMUA status selain "Lainnya"
    if (!isLainnya) {
      const allPosInputs = document.querySelectorAll(".pos-input");

      // Filter: Hanya ambil yang berada di dalam form utama (bukan di dalam pop-up)
      const formPosInputs = Array.from(allPosInputs).filter(
        (input) => !input.closest("#popupOverlay"),
      );

      if (formPosInputs.length === 0) {
        ok = false;
        alert("Tambahkan setidaknya satu tujuan kunjungan!");
      }

      formPosInputs.forEach((posInput) => {
        if (!posInput.dataset.id) {
          ok = false;
          alert("Silakan pilih POS tujuan dari daftar dropdown!");
          return;
        }

        const box = posInput.closest("div.border");
        if (!box) return;

        const allInputsInBox = box.querySelectorAll("input[type='text']");
        const bertemu = allInputsInBox[1] ? allInputsInBox[1].value.trim() : "";
        const bagian = allInputsInBox[2] ? allInputsInBox[2].value.trim() : "";
        const keperluan = allInputsInBox[3]
          ? allInputsInBox[3].value.trim()
          : "";

        tujuanList.push({
          pos_id: parseInt(posInput.dataset.id),
          bertemu_dengan: bertemu || null,
          bagian: bagian || null,
          keperluan: keperluan || null,
        });
      });
    }

    if (!ok) return;

    const basePayload = {
      nama: document.getElementById("nama").value.trim(),
      telepon: document.getElementById("telepon").value.trim(),
      status_kunjungan: status,
      jumlah: +document.getElementById("jumlah").value || 1,
      nama_lain: document.getElementById("nama_lain").value.trim() || null,
      alamat: alamatValue,
      jenis: document.getElementById("jenisKendaraan").value || null,
      nomor_polisi: document.getElementById("noKendaraan").value.trim() || null,
      ...(perusahaanId ? { perusahaan_id: perusahaanId } : {}),
      tujuan_kunjungan: isLainnya ? [] : tujuanList, // <-- Kirim tujuan jika bukan Lainnya
    };

    let payload, endpoint;

    if (isLainnya) {
      payload = {
        nama_lengkap: basePayload.nama,
        keterangan: document.getElementById("keterangan").value.trim(),
        status: basePayload.status_kunjungan,
        jenis: basePayload.jenis,
        nomor_polisi: basePayload.nomor_polisi,
      };
      endpoint = `${API_BASE}api/kunjungan/lainnya`;
    } else {
      payload = basePayload;
      endpoint = `${API_BASE}api/Registrasi/submit`;
    }

    // Debugging: Cek data yang dikirim di console
    console.log("Payload dikirim:", JSON.stringify(payload, null, 2));

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const error = await res.json();
        console.error("Detail Error Backend:", error);
        let errorMsg = error.detail;
        if (Array.isArray(errorMsg)) {
          errorMsg = errorMsg
            .map((e) => `${e.loc.join(".")}: ${e.msg}`)
            .join("\n");
        }
        throw new Error(errorMsg || "Gagal mendaftar");
      }

      const result = await res.json();
      alert(`✓ Check-in berhasil! Barcode: ${result.barcode}`);

      const params = new URLSearchParams({
        code: result.barcode || "BC-UNKNOWN",
        nama: (result.nama_lengkap || result.nama || "Pengunjung").trim(),
        status_kunjungan: status.trim(),
        kendaraan: (result.jenis || "").trim(),
        nomor: (result.nomor_polisi || "").trim(),
      });

      // Redirect ke halaman barcode
      window.location.href = `/static/barcode.html?${params.toString()}`;

      document.getElementById("visitorForm").reset();
      regularFields?.classList.remove("d-none");
      lainnyaFields?.classList.add("d-none");
    } catch (err) {
      console.error("Submit error:", err);
      alert(`❌ Error: ${err.message}`);
    }
  };
});
