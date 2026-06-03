const reportData = window.reportData || {};

Chart.defaults.font.family = "'Segoe UI', Arial, sans-serif";
Chart.defaults.color = "#717a8c";

const palette = ["#5427d8", "#20c985", "#35aee2", "#8bcf3f", "#ef476f", "#f59e0b"];

const hasValues = (item) => Array.isArray(item?.values) && item.values.length > 0;

const makeEmptyState = (canvas) => {
    const parent = canvas?.parentElement;
    if (parent) {
        parent.innerHTML = '<div class="empty-state">Belum ada data untuk grafik.</div>';
    }
};

const segmentCanvas = document.getElementById("reportSegmentChart");
if (segmentCanvas && hasValues(reportData.segments)) {
    new Chart(segmentCanvas, {
        type: "doughnut",
        data: {
            labels: reportData.segments.labels,
            datasets: [{
                data: reportData.segments.values,
                backgroundColor: palette,
                borderColor: "#ffffff",
                borderWidth: 5,
                hoverOffset: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "66%",
            plugins: {
                legend: {
                    position: "bottom",
                    labels: { usePointStyle: true, boxWidth: 8 }
                }
            }
        }
    });
} else {
    makeEmptyState(segmentCanvas);
}

const productCanvas = document.getElementById("reportProductChart");
if (productCanvas && hasValues(reportData.products)) {
    new Chart(productCanvas, {
        type: "bar",
        data: {
            labels: reportData.products.labels,
            datasets: [{
                label: "Qty Terjual",
                data: reportData.products.values,
                backgroundColor: "#20c985",
                borderRadius: 12,
                maxBarThickness: 34
            }]
        },
        options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { beginAtZero: true, grid: { color: "rgba(148, 163, 184, 0.16)" } },
                y: { grid: { display: false } }
            }
        }
    });
} else {
    makeEmptyState(productCanvas);
}

const paymentCanvas = document.getElementById("reportPaymentChart");
if (paymentCanvas && hasValues(reportData.payments)) {
    new Chart(paymentCanvas, {
        type: "bar",
        data: {
            labels: reportData.payments.labels,
            datasets: [{
                label: "Order",
                data: reportData.payments.values,
                backgroundColor: palette,
                borderRadius: 12,
                maxBarThickness: 44
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false } },
                y: { beginAtZero: true, grid: { color: "rgba(148, 163, 184, 0.16)" } }
            }
        }
    });
} else {
    makeEmptyState(paymentCanvas);
}
