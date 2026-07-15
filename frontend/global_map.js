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
    // This allows the "Live Puzzle Rendering" effect where tiles appear as they are downloaded.
    const sentinelLayer = L.tileLayer('/static/hd_map/{z}/{x}/{y}.jpg', {
        attribution: 'Local Sentinel-2 Cloudless Cache',
        maxZoom: 14,
        tileSize: 256,
        // If the tile hasn't been downloaded yet (puzzle piece missing), show a transparent blank tile
        errorTileUrl: 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
    });

    sentinelLayer.addTo(map);

    // Optional labels overlay
    const labelsLayer = L.tileLayer('https://tiles.maps.eox.at/wmts/1.0.0/overlay_base_bright_3857/default/g/{z}/{y}/{x}.png', {
        attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 14
    });
    labelsLayer.addTo(map);
});
