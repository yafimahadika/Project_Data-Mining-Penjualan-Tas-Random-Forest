const appShell = document.querySelector(".app-shell");
const menuButton = document.querySelector(".menu-button");
const sidebarState = localStorage.getItem("sidebar-collapsed");

if (appShell && sidebarState === "true") {
    appShell.classList.add("sidebar-collapsed");
    menuButton?.setAttribute("aria-expanded", "false");
}

if (appShell && menuButton) {
    menuButton.addEventListener("click", () => {
        const isCollapsed = appShell.classList.toggle("sidebar-collapsed");
        menuButton.setAttribute("aria-expanded", String(!isCollapsed));
        localStorage.setItem("sidebar-collapsed", String(isCollapsed));
    });
}

const flashModalElement = document.getElementById("appFlashModal");
if (flashModalElement && window.bootstrap) {
    const flashModal = new bootstrap.Modal(flashModalElement);
    flashModal.show();
}

const confirmModalElement = document.getElementById("appConfirmModal");
const confirmTitle = document.getElementById("appConfirmTitle");
const confirmMessage = document.getElementById("appConfirmMessage");
const confirmSubmit = document.getElementById("appConfirmSubmit");
let pendingConfirmForm = null;

if (confirmModalElement && confirmSubmit && window.bootstrap) {
    const confirmModal = new bootstrap.Modal(confirmModalElement);

    document.querySelectorAll("form[data-confirm-title]").forEach((form) => {
        form.addEventListener("submit", (event) => {
            if (form.dataset.confirmed === "true") {
                return;
            }

            event.preventDefault();
            pendingConfirmForm = form;
            if (confirmTitle) {
                confirmTitle.textContent = form.dataset.confirmTitle || "Hapus data?";
            }
            if (confirmMessage) {
                confirmMessage.textContent = form.dataset.confirmMessage || "Data yang sudah dihapus tidak dapat dikembalikan.";
            }
            confirmModal.show();
        });
    });

    confirmSubmit.addEventListener("click", () => {
        if (!pendingConfirmForm) {
            return;
        }
        pendingConfirmForm.dataset.confirmed = "true";
        confirmModal.hide();
        pendingConfirmForm.submit();
    });

    confirmModalElement.addEventListener("hidden.bs.modal", () => {
        pendingConfirmForm = null;
    });
}

const datasetSelectAll = document.getElementById("datasetSelectAll");
const datasetRowChecks = Array.from(document.querySelectorAll(".dataset-row-check"));
const datasetBulkDeleteForm = document.getElementById("datasetBulkDeleteForm");
const datasetSelectedIds = document.getElementById("datasetSelectedIds");
const datasetBulkDeleteButton = datasetBulkDeleteForm?.querySelector("button[type='submit']");

const updateDatasetSelection = () => {
    const selected = datasetRowChecks.filter((checkbox) => checkbox.checked);
    if (datasetSelectedIds) {
        datasetSelectedIds.value = selected.map((checkbox) => checkbox.value).join(",");
    }
    if (datasetBulkDeleteButton) {
        datasetBulkDeleteButton.disabled = selected.length === 0;
    }
    if (datasetBulkDeleteForm) {
        datasetBulkDeleteForm.classList.toggle("is-hidden", selected.length === 0);
    }
    if (datasetSelectAll) {
        datasetSelectAll.checked = selected.length > 0 && selected.length === datasetRowChecks.length;
        datasetSelectAll.indeterminate = selected.length > 0 && selected.length < datasetRowChecks.length;
    }
};

if (datasetSelectAll && datasetRowChecks.length > 0) {
    datasetSelectAll.addEventListener("change", () => {
        datasetRowChecks.forEach((checkbox) => {
            checkbox.checked = datasetSelectAll.checked;
        });
        updateDatasetSelection();
    });
}

datasetRowChecks.forEach((checkbox) => {
    checkbox.addEventListener("change", updateDatasetSelection);
});

if (datasetBulkDeleteForm) {
    datasetBulkDeleteForm.addEventListener(
        "submit",
        (event) => {
            updateDatasetSelection();
            if (!datasetSelectedIds?.value) {
                event.preventDefault();
            }
        },
        true
    );
}

updateDatasetSelection();

const datasetUploadForm = document.getElementById("datasetUploadForm");
const datasetFile = document.getElementById("datasetFile");
const datasetUploadLabel = document.getElementById("datasetUploadLabel");
const datasetUploadStatus = document.getElementById("datasetUploadStatus");

datasetFile?.addEventListener("change", () => {
    const file = datasetFile.files[0];
    if (datasetUploadStatus) {
        datasetUploadStatus.textContent = file
            ? `${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB) siap diupload.`
            : "Pilih file .xlsx hasil ekspor pesanan Shopee, lalu klik tombol upload.";
    }
});

datasetUploadForm?.addEventListener("submit", (event) => {
    if (datasetUploadForm.dataset.uploading === "true") {
        event.preventDefault();
        return;
    }
    datasetUploadForm.dataset.uploading = "true";
    datasetUploadForm.setAttribute("aria-busy", "true");
    const button = datasetUploadForm.querySelector("button[type='submit']");
    if (button) {
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span>';
    }
    if (datasetUploadLabel) datasetUploadLabel.textContent = "Memproses...";
    if (datasetUploadStatus) {
        datasetUploadStatus.textContent = "Dataset sedang diupload dan diproses. Tunggu sampai hasilnya tampil.";
    }
});
