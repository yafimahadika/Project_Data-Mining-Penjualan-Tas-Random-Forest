const evaluationData = window.evaluationData || {};

Chart.defaults.font.family = "'Segoe UI', Arial, sans-serif";
Chart.defaults.color = "#717a8c";

const metricCanvas = document.getElementById("evaluationMetricChart");
if (metricCanvas && Array.isArray(evaluationData.labels) && evaluationData.labels.length > 0) {
    new Chart(metricCanvas, {
        type: "line",
        data: {
            labels: evaluationData.labels,
            datasets: [
                {
                    label: "Akurasi",
                    data: evaluationData.accuracy,
                    borderColor: "#5427d8",
                    backgroundColor: "rgba(84, 39, 216, 0.12)",
                    borderWidth: 3,
                    tension: 0.38
                },
                {
                    label: "Precision",
                    data: evaluationData.precision,
                    borderColor: "#35aee2",
                    backgroundColor: "rgba(53, 174, 226, 0.1)",
                    borderWidth: 3,
                    tension: 0.38
                },
                {
                    label: "Recall",
                    data: evaluationData.recall,
                    borderColor: "#20c985",
                    backgroundColor: "rgba(32, 201, 133, 0.1)",
                    borderWidth: 3,
                    tension: 0.38
                },
                {
                    label: "F1-score",
                    data: evaluationData.f1,
                    borderColor: "#8bcf3f",
                    backgroundColor: "rgba(139, 207, 63, 0.1)",
                    borderWidth: 3,
                    tension: 0.38
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 900, easing: "easeOutCubic" },
            plugins: {
                legend: {
                    position: "bottom",
                    labels: { usePointStyle: true, boxWidth: 8 }
                },
                tooltip: {
                    callbacks: {
                        label: (context) => `${context.dataset.label}: ${context.parsed.y.toFixed(2)}%`
                    }
                }
            },
            scales: {
                x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true } },
                y: {
                    min: 0,
                    max: 100,
                    grid: { color: "rgba(148, 163, 184, 0.16)" },
                    ticks: { callback: (value) => `${value}%` }
                }
            }
        }
    });
}
