document.addEventListener('DOMContentLoaded', () => {
    // Tab switching logic
    const tabs = document.querySelectorAll('.nav-tab');
    const views = document.querySelectorAll('.view-section');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active class from all tabs and views
            tabs.forEach(t => t.classList.remove('active'));
            views.forEach(v => v.classList.remove('active'));

            // Add active class to clicked tab and corresponding view
            tab.classList.add('active');
            const targetId = tab.getAttribute('data-target');
            document.getElementById(targetId).classList.add('active');

            // If switching to map view, invalidate map size to fix rendering issues
            if (targetId === 'map-view' && window.globalLeafletMap) {
                setTimeout(() => {
                    window.globalLeafletMap.invalidateSize();
                }, 100);
            }
        });
    });

    // Initialize Leaflet Map
    // Copernicus Sentinel-2 cloudless layer provided by EOX IT Services GmbH
    const map = L.map('leaflet-map', {
        center: [23.5, 121], // Center on Taiwan by default
        zoom: 6,
        minZoom: 2,
        maxZoom: 14 // EOX layer supports up to 14
    });
    
    window.globalLeafletMap = map;

    // We use the LOCAL Cache!
    const sentinelLayer = L.tileLayer('/api/tile/{z}/{x}/{y}', {
        attribution: 'Local Sentinel-2 Cloudless Cache',
        maxZoom: 14,
        tileSize: 256,
        // If the tile hasn't been downloaded yet (puzzle piece missing), show a transparent blank tile
        errorTileUrl: 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
    });

    sentinelLayer.addTo(map);

    // Dynamic Zoom Level Update
    const zoomEl = document.getElementById('map-zoom-level');
    if (zoomEl) {
        zoomEl.textContent = map.getZoom();
        map.on('zoomend', () => {
            zoomEl.textContent = map.getZoom();
        });
    }

    // Dynamic System Info Update
    const sysInfoEl = document.getElementById('map-sys-info');
    if (sysInfoEl) {
        const fetchSysInfo = async () => {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                sysInfoEl.textContent = `CPU ${data.cpu.usage_percent}% | RAM ${data.memory.usage_percent}% | Dwn ${data.network.recv_kbps.toFixed(1)} KB/s`;
            } catch (e) {
                sysInfoEl.textContent = '連線異常';
            }
        };
        fetchSysInfo();
        setInterval(fetchSysInfo, 2000);
    }
});
