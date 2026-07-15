// status.js - Logic for fetching and rendering real-time system metrics

const STATUS_API_URL = '/api/status';
const REFRESH_INTERVAL = 2000; // 2 seconds

// DOM Elements
const cpuValueEl = document.getElementById('cpu-value');
const cpuProgressEl = document.querySelector('.cpu-progress');
const cpuCoresEl = document.getElementById('cpu-cores');

const memValueEl = document.getElementById('mem-value');
const memProgressEl = document.querySelector('.mem-progress');
const memUsedEl = document.getElementById('mem-used');
const memTotalEl = document.getElementById('mem-total');
const memFreeEl = document.getElementById('mem-free');

const serverNameEl = document.getElementById('server-name');
const runtimePidEl = document.getElementById('runtime-pid');
const runtimeThreadsEl = document.getElementById('runtime-threads');

const statusBadgeEl = document.getElementById('server-status-badge');
const statusTextEl = document.getElementById('server-status-text');

// Gauge Constants (Radius = 80, Circumference = 2 * PI * 80)
const CIRCUMFERENCE = 502.65;

function setGaugeProgress(element, percent) {
    // Limit to 100% max for display purposes
    const validPercent = Math.min(Math.max(percent, 0), 100);
    const offset = CIRCUMFERENCE - (validPercent / 100) * CIRCUMFERENCE;
    element.style.strokeDashoffset = offset;
}

// Animate numbers
function animateValue(obj, start, end, duration) {
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        const currentVal = start + progress * (end - start);
        
        // Handle floating points vs integers
        if (Number.isInteger(end)) {
            obj.innerHTML = Math.floor(currentVal);
        } else {
            obj.innerHTML = currentVal.toFixed(1);
        }

        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}

let lastData = null;

async function fetchStatus() {
    try {
        const timestamp = Date.now();
        const response = await fetch(`${STATUS_API_URL}?t=${timestamp}`);
        if (!response.ok) throw new Error('Network error');
        
        const data = await response.json();
        updateDashboard(data);
        setConnectionStatus(true);
    } catch (error) {
        console.error('Failed to fetch status:', error);
        setConnectionStatus(false);
    }
}

function updateDashboard(data) {
    if (!data) return;

    // CPU Updates
    const cpuUsage = data.cpu.usage_percent;
    const oldCpu = lastData ? lastData.cpu.usage_percent : 0;
    if (cpuUsage !== oldCpu) {
        animateValue(cpuValueEl, oldCpu, cpuUsage, 800);
        setGaugeProgress(cpuProgressEl, cpuUsage);
    }
    cpuCoresEl.textContent = data.cpu.logical_cores;

    // Memory Updates
    const memUsage = data.memory.usage_percent;
    const oldMem = lastData ? lastData.memory.usage_percent : 0;
    if (memUsage !== oldMem) {
        animateValue(memValueEl, oldMem, memUsage, 800);
        setGaugeProgress(memProgressEl, memUsage);
    }
    memUsedEl.textContent = data.memory.used_mb.toFixed(1);
    memTotalEl.textContent = data.memory.total_mb.toFixed(1);
    memFreeEl.textContent = data.memory.free_mb.toFixed(1);

    // Info Updates
    serverNameEl.textContent = data.server_name;
    runtimePidEl.textContent = data.runtime.pid;
    runtimeThreadsEl.textContent = data.runtime.active_threads;

    // Network Updates
    if (data.network) {
        const netRecvEl = document.getElementById('net-recv');
        const netSentEl = document.getElementById('net-sent');
        if (netRecvEl && netSentEl) {
            const newRecv = data.network.recv_kbps || 0;
            const newSent = data.network.sent_kbps || 0;
            const oldRecv = lastData && lastData.network ? lastData.network.recv_kbps : 0;
            const oldSent = lastData && lastData.network ? lastData.network.sent_kbps : 0;
            
            animateValue(netRecvEl, oldRecv, newRecv, 800);
            animateValue(netSentEl, oldSent, newSent, 800);
        }
    }

    lastData = data;
}

function setConnectionStatus(isOnline) {
    if (isOnline) {
        statusBadgeEl.classList.remove('offline');
        statusTextEl.textContent = '連線中';
    } else {
        statusBadgeEl.classList.add('offline');
        statusTextEl.textContent = '離線 (Offline)';
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Initial fetch
    fetchStatus();
    // Setup polling
    setInterval(fetchStatus, REFRESH_INTERVAL);
});
