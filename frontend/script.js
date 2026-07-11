const API_URL = '/api/latest';
const REFRESH_INTERVAL = 60000; // Check for new data every 1 minute

let currentMode = 'true_color'; // 'true_color' or 'ir'
let currentData = null;

const imgElement = document.getElementById('satellite-img');
const loader = document.getElementById('loader');
const timestampDisplay = document.getElementById('timestamp-display');
const buttons = document.querySelectorAll('.btn');
const statusIndicator = document.querySelector('.status-indicator');
const systemStatus = document.getElementById('system-status');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    fetchLatestData();
    // Start polling
    setInterval(fetchLatestData, REFRESH_INTERVAL);
});

function setupEventListeners() {
    buttons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            // Remove active class from all
            buttons.forEach(b => b.classList.remove('active'));
            // Add active class to clicked
            const clickedBtn = e.currentTarget;
            clickedBtn.classList.add('active');
            
            // Set mode and update image
            currentMode = clickedBtn.dataset.mode;
            updateDisplay();
        });
    });
}

async function fetchLatestData() {
    try {
        const response = await fetch(API_URL);
        if (!response.ok) throw new Error('Network response was not ok');
        
        const data = await response.json();
        
        if (data.status === 'processing') {
            console.log('Backend is still processing initial data...');
            return;
        }

        // Check if data is new
        if (!currentData || currentData.timestamp !== data.timestamp) {
            console.log('New data received:', data);
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

    const imgUrl = currentData[currentMode];
    if (!imgUrl) return;

    // Show loader and hide image for transition
    imgElement.classList.add('hidden');
    loader.style.display = 'block';

    // Preload image
    const tempImg = new Image();
    tempImg.onload = () => {
        imgElement.src = imgUrl;
        // Small delay for smooth CSS transition
        setTimeout(() => {
            imgElement.classList.remove('hidden');
            loader.style.display = 'none';
        }, 100);
    };
    tempImg.onerror = () => {
        loader.style.display = 'none';
        console.error('Failed to load image:', imgUrl);
    };
    tempImg.src = imgUrl;
}
