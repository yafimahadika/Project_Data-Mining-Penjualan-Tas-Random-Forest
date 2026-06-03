const dashboardData = window.dashboardData || {};

const chartPalette = {
    purple: "#5427d8",
    violet: "#7c3aed",
    cyan: "#35aee2",
    green: "#20c985",
    lime: "#8bcf3f",
    red: "#ef476f",
    ink: "#20263a",
    muted: "#9aa3b2"
};

Chart.defaults.font.family = "'Segoe UI', Arial, sans-serif";
Chart.defaults.color = "#717a8c";

const formatRupiah = (value) => {
    return new Intl.NumberFormat("id-ID", {
        style: "currency",
        currency: "IDR",
        maximumFractionDigits: 0
    }).format(value);
};

const hasValues = (dataset) => Array.isArray(dataset?.values) && dataset.values.length > 0;

const makeGradient = (chart, colorStart, colorEnd) => {
    const {ctx, chartArea} = chart;
    if (!chartArea) return colorStart;
    const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
    gradient.addColorStop(0, colorStart);
    gradient.addColorStop(1, colorEnd);
    return gradient;
};

const monthlyCanvas = document.getElementById("monthlySalesChart");
if (monthlyCanvas && hasValues(dashboardData.monthlySales)) {
    new Chart(monthlyCanvas, {
        type: "line",
        data: {
            labels: dashboardData.monthlySales.labels,
            datasets: [{
                label: "Total Penjualan",
                data: dashboardData.monthlySales.values,
                borderColor: chartPalette.purple,
                backgroundColor: (context) => makeGradient(
                    context.chart,
                    "rgba(84, 39, 216, 0.22)",
                    "rgba(84, 39, 216, 0.02)"
                ),
                borderWidth: 4,
                fill: true,
                tension: 0.42,
                pointRadius: 5,
                pointHoverRadius: 7,
                pointBackgroundColor: "#ffffff",
                pointBorderColor: chartPalette.purple,
                pointBorderWidth: 3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 1200, easing: "easeOutQuart" },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (context) => formatRupiah(context.parsed.y)
                    }
                }
            },
            scales: {
                x: { grid: { display: false } },
                y: {
                    beginAtZero: true,
                    grid: { color: "rgba(148, 163, 184, 0.16)" },
                    ticks: { callback: (value) => formatRupiah(value) }
                }
            }
        }
    });
}

const segmentCanvas = document.getElementById("segmentChart");
if (segmentCanvas && hasValues(dashboardData.segments)) {
    new Chart(segmentCanvas, {
        type: "doughnut",
        data: {
            labels: dashboardData.segments.labels,
            datasets: [{
                data: dashboardData.segments.values,
                backgroundColor: [
                    chartPalette.purple,
                    chartPalette.green,
                    chartPalette.cyan,
                    chartPalette.lime,
                    chartPalette.red
                ],
                borderColor: "#ffffff",
                borderWidth: 5,
                hoverOffset: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "68%",
            animation: { animateRotate: true, duration: 1000 },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

const channelCanvas = document.getElementById("channelChart");
if (channelCanvas && hasValues(dashboardData.channels)) {
    new Chart(channelCanvas, {
        type: "bar",
        data: {
            labels: dashboardData.channels.labels,
            datasets: [{
                label: "Jumlah Transaksi",
                data: dashboardData.channels.values,
                backgroundColor: [chartPalette.purple, chartPalette.cyan, chartPalette.green],
                borderRadius: 12,
                maxBarThickness: 44
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 900, easing: "easeOutCubic" },
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false } },
                y: {
                    beginAtZero: true,
                    grid: { color: "rgba(148, 163, 184, 0.16)" },
                    ticks: { precision: 0 }
                }
            }
        }
    });
}

const categoryCanvas = document.getElementById("categoryChart");
if (categoryCanvas && hasValues(dashboardData.categories)) {
    new Chart(categoryCanvas, {
        type: "bar",
        data: {
            labels: dashboardData.categories.labels,
            datasets: [{
                label: "Jumlah Produk",
                data: dashboardData.categories.values,
                backgroundColor: chartPalette.green,
                borderRadius: 12,
                maxBarThickness: 36
            }]
        },
        options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 900, easing: "easeOutCubic" },
            plugins: { legend: { display: false } },
            scales: {
                x: {
                    beginAtZero: true,
                    grid: { color: "rgba(148, 163, 184, 0.16)" },
                    ticks: { precision: 0 }
                },
                y: { grid: { display: false } }
            }
        }
    });
}
