// Tabs wechseln
function openTab(tabName) {
    document.querySelectorAll(".tab-content").forEach(tab => tab.style.display = "none");
    document.getElementById(tabName).style.display = "block";
}

// Download starten
function startDownload() {
    fetch("/start_download")
        .then(res => res.json())
        .then(data => {
            document.getElementById("download-status").innerText = "Status: Download gestartet!";
        });
}

// Datenbank laden
function loadDatabase() {
    fetch("/database")
        .then(res => res.json())
        .then(data => {
            const tbody = document.querySelector("#db-table tbody");
            tbody.innerHTML = "";
            data.forEach(row => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td>${row.id}</td>
                    <td>${row.title}</td>
                    <td><a href="${row.url}" target="_blank">${row.url}</a></td>
                    <td>${row.complete ? "✅" : "❌"}</td>
                    <td>${row.deutsch_komplett ? "✅" : "❌"}</td>
                    <td>${row.fehlende}</td>
                `;
                tbody.appendChild(tr);
            });
        });
}

// Live Logs laden
function loadLogs() {
    fetch("/logs")
        .then(res => res.json())
        .then(data => {
            const logOutput = document.getElementById("log-output");
            logOutput.innerText = data.join("\n");
            logOutput.scrollTop = logOutput.scrollHeight;
        });
}

// Intervall für Logs und DB
setInterval(loadLogs, 2000);
setInterval(loadDatabase, 5000);
