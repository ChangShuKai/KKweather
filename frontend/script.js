const API_URL = '/api/latest';
const LOGS_URL = '/api/logs';
const REFRESH_INTERVAL = 60000; // Check for new data every 1 minute
const LOG_INTERVAL = 2000; // Check logs every 2 seconds

let currentMode = 'true_color'; // 'true_color' or 'ir'
let currentRegion = 'taiwan'; // 'global', 'asia', or 'taiwan'
let currentData = null;

const imgElement = document.getElementById('satellite-img');
const loader = document.getElementById('loader');
const timestampDisplay = document.getElementById('timestamp-display');
const modeButtons = document.querySelectorAll('.mode-btn');
const regionButtons = document.querySelectorAll('.region-btn');
const statusIndicator = document.querySelector('.status-indicator');
const systemStatus = document.getElementById('system-status');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    fetchLatestData();
    fetchLogs();
    // Start polling
    setInterval(fetchLatestData, REFRESH_INTERVAL);
    setInterval(fetchLogs, LOG_INTERVAL);
});

function setupEventListeners() {
    modeButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            modeButtons.forEach(b => b.classList.remove('active'));
            const clickedBtn = e.currentTarget;
            clickedBtn.classList.add('active');
            currentMode = clickedBtn.dataset.mode;
            updateDisplay();
        });
    });

    regionButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            regionButtons.forEach(b => b.classList.remove('active'));
            const clickedBtn = e.currentTarget;
            clickedBtn.classList.add('active');
            currentRegion = clickedBtn.dataset.region;
            updateDisplay();
        });
    });
}

async function fetchLatestData() {
    try {
        const urlWithCacheBuster = `${API_URL}?t=${Date.now()}`;
        const response = await fetch(urlWithCacheBuster);
        if (!response.ok) throw new Error('Network response was not ok');
        
        const data = await response.json();
        
        if (data.status === 'processing') {
            console.log('Backend is still processing initial data...');
            const loadingText = document.getElementById('loading-text');
            if (loadingText) loadingText.textContent = data.message || 'Initial satellite rendering in progress...';
            const loaderContainer = document.getElementById('loader-container');
            if (loaderContainer) loaderContainer.style.display = 'flex';
            imgElement.classList.add('hidden');
            return;
        }

        // Check if data is new or updated
        const isNewData = !currentData || 
                          currentData.timestamp !== data.timestamp || 
                          JSON.stringify(currentData) !== JSON.stringify(data);

        if (isNewData) {
            console.log('New data received/updated:', data);
            currentData = data;
            
            // Format timestamp for display (YYYYMMDD_HHMM to readable)
            const raw = data.timestamp; // e.g., 20260711_1600
            const year = raw.substring(0,4);
            const month = raw.substring(4,6);
            const day = raw.substring(6,8);
            const hour = raw.substring(9,11);
            const min = raw.substring(11,13);
            timestampDisplay.textContent = `${year}-${month}-${day} ${hour}:${min} (UTC)`;
            
            updateDisplay();
            
            // Update status indicator
            statusIndicator.classList.remove('offline');
            systemStatus.textContent = '連線中';
        }
    } catch (error) {
        console.error('Error fetching data:', error);
        statusIndicator.classList.add('offline');
        systemStatus.textContent = '離線';
    }
}

function updateDisplay() {
    if (!currentData) return;

    const imgUrl = currentData[currentMode]?.[currentRegion];
    const loaderContainer = document.getElementById('loader-container');
    const loadingText = document.getElementById('loading-text');

    if (!imgUrl) {
        // Specific region is not yet available
        if (loadingText) {
            const regionNames = { 'taiwan': '台灣', 'asia': '亞洲', 'global': '全球' };
            const regionName = regionNames[currentRegion] || '';
            loadingText.textContent = `${regionName}區域正在太空刻錄中...`;
        }
        if (loaderContainer) loaderContainer.style.display = 'flex';
        imgElement.classList.add('hidden');
        return;
    }

    // Show loader and hide image for transition
    imgElement.classList.add('hidden');
    if (loaderContainer) loaderContainer.style.display = 'flex';
    if (loadingText) loadingText.textContent = '載入中...';

    // Preload image
    const tempImg = new Image();
    tempImg.onload = () => {
        imgElement.src = imgUrl;
        // Small delay for smooth CSS transition
        setTimeout(() => {
            imgElement.classList.remove('hidden');
            if (loaderContainer) loaderContainer.style.display = 'none';
        }, 100);
    };
    tempImg.onerror = () => {
        if (loaderContainer) loaderContainer.style.display = 'none';
        if (loadingText) loadingText.textContent = '影像載入失敗，等待下一次更新...';
        imgElement.classList.remove('hidden');
        imgElement.alt = "Image failed to load";
        console.error('Failed to load image:', imgUrl);
    };
    tempImg.src = imgUrl;
}

// Log Fetching and Parsing
async function fetchLogs() {
    try {
        const urlWithCacheBuster = `${LOGS_URL}?t=${Date.now()}`;
        const response = await fetch(urlWithCacheBuster);
        if (!response.ok) return;
        const data = await response.json();
        
        const logContent = document.getElementById('live-log-content');
        if (logContent && data.logs) {
            logContent.innerHTML = '';
            
            // Highlight rules
            const highlights = ['Downloading', 'Starting scheduled job', 'Using', 'Loading True Color', 'completed successfully', 'failed', 'Processing'];
            
            data.logs.forEach(log => {
                const div = document.createElement('div');
                div.className = 'log-line';
                
                // Check if line should be highlighted
                const isHighlight = highlights.some(h => log.includes(h));
                if (isHighlight) {
                    div.classList.add('highlight');
                }
                
                div.textContent = log;
                logContent.appendChild(div);
            });
            
            // Auto scroll to bottom
            logContent.scrollTop = logContent.scrollHeight;
            
            // Dynamically update the loading text and percent
            const loaderContainer = document.getElementById('loader-container');
            const loadingText = document.getElementById('loading-text');
            const loadingPercent = document.getElementById('loading-percent');
            
            if (loaderContainer && loaderContainer.style.display !== 'none' && data.logs.length > 0) {
                const lastLog = data.logs[data.logs.length - 1];
                
                // Parse [Progress] XX% from any recent log
                let currentPercent = '0%';
                for (let i = data.logs.length - 1; i >= 0; i--) {
                    const match = data.logs[i].match(/\[Progress\]\s*(\d+)%/);
                    if (match) {
                        currentPercent = match[1] + '%';
                        break;
                    }
                }
                
                if (loadingPercent) {
                    loadingPercent.textContent = currentPercent;
                }
                
                // Only show the message part (without the [Progress] prefix)
                if (loadingText) {
                    loadingText.textContent = lastLog.replace(/\[Progress\]\s*\d+%\s*-\s*/, '');
                }
                
                // If we are processing, aggressively check for the latest image so it shows instantly
                fetchLatestData();
            }
        }
    } catch (error) {
        console.error('Error fetching logs:', error);
    }
}
