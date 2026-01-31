// ========================================
// House of Hamill Food Drive - JavaScript
// ========================================

// Global state
let map;
let markers = [];
let shows = [];
let allShows = []; // Keep original list for clearing search
let isFiltered = false;

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    fetchShows();
    fetchStats();
});

// Initialize Leaflet map
function initMap() {
    // Center on USA
    map = L.map('shows-map').setView([39.8283, -98.5795], 4);

    // Add tile layer (OpenStreetMap)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
}

// Fetch shows from API
async function fetchShows() {
    try {
        const response = await fetch('/api/shows');
        allShows = await response.json();
        shows = [...allShows];
        renderShows(shows);
        renderMapMarkers(shows);
    } catch (error) {
        console.error('Error fetching shows:', error);
        document.getElementById('shows-list').innerHTML = `
            <div class="loading-spinner">
                Unable to load shows. Please try again later.
            </div>
        `;
    }
}

// Geocode a location string using OpenStreetMap Nominatim
async function geocodeLocation(query) {
    try {
        const response = await fetch(
            `https://nominatim.openstreetmap.org/search?format=json&countrycodes=us&q=${encodeURIComponent(query)}`,
            { headers: { 'User-Agent': 'HouseOfHamillFoodDrive/1.0' } }
        );
        const results = await response.json();
        if (results.length > 0) {
            return {
                lat: parseFloat(results[0].lat),
                lon: parseFloat(results[0].lon),
                display_name: results[0].display_name
            };
        }
        return null;
    } catch (error) {
        console.error('Geocoding error:', error);
        return null;
    }
}

// Calculate distance between two points using Haversine formula (returns miles)
function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 3959; // Earth's radius in miles
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a =
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
        Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

// Search shows by location
async function searchShows() {
    const searchInput = document.getElementById('location-search');
    const query = searchInput.value.trim();

    if (!query) return;

    const searchBtn = document.getElementById('search-btn');
    searchBtn.textContent = 'Searching...';
    searchBtn.disabled = true;

    // First try to match venue or city names directly
    const textMatches = allShows.filter(show =>
        show.venue.toLowerCase().includes(query.toLowerCase()) ||
        show.city.toLowerCase().includes(query.toLowerCase()) ||
        (show.state && show.state.toLowerCase().includes(query.toLowerCase()))
    );

    // If we have exact venue/city matches, use those
    if (textMatches.length > 0 && textMatches.length <= 5) {
        displayFilteredShows(textMatches, query, null);
        searchBtn.textContent = 'Search';
        searchBtn.disabled = false;
        return;
    }

    // Otherwise, geocode the query and find nearest shows
    const location = await geocodeLocation(query);

    if (!location) {
        alert('Could not find that location. Please try a different city, zip code, or venue name.');
        searchBtn.textContent = 'Search';
        searchBtn.disabled = false;
        return;
    }

    // Calculate distance to each show
    const showsWithDistance = allShows
        .filter(show => show.latitude && show.longitude)
        .map(show => ({
            ...show,
            distance: calculateDistance(location.lat, location.lon, show.latitude, show.longitude)
        }))
        .sort((a, b) => a.distance - b.distance)
        .slice(0, 5); // Get 5 closest shows

    displayFilteredShows(showsWithDistance, query, location);
    searchBtn.textContent = 'Search';
    searchBtn.disabled = false;
}

// Display filtered shows
function displayFilteredShows(filteredShows, query, location) {
    shows = filteredShows;
    isFiltered = true;

    // Show clear button
    document.getElementById('clear-search-btn').style.display = 'inline-block';

    // Add search results info
    const container = document.getElementById('shows-list');
    const hasDistances = filteredShows.length > 0 && filteredShows[0].distance !== undefined;

    let infoHtml = `<div class="search-results-info">
        Showing ${filteredShows.length} show${filteredShows.length !== 1 ? 's' : ''}
        ${hasDistances ? 'nearest to' : 'matching'} "${escapeHtml(query)}"
    </div>`;

    renderShows(shows, hasDistances);
    container.insertAdjacentHTML('afterbegin', infoHtml);

    // Update map
    renderMapMarkers(shows);

    // Zoom map to show results
    if (filteredShows.length > 0) {
        const bounds = filteredShows
            .filter(s => s.latitude && s.longitude)
            .map(s => [s.latitude, s.longitude]);
        if (bounds.length > 0) {
            map.fitBounds(bounds, { padding: [50, 50], maxZoom: 8 });
        }
    }
}

// Clear search and show all shows
function clearSearch() {
    document.getElementById('location-search').value = '';
    document.getElementById('clear-search-btn').style.display = 'none';

    shows = [...allShows];
    isFiltered = false;

    renderShows(shows);
    renderMapMarkers(shows);
}

// Handle Enter key in search input
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('location-search');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                searchShows();
            }
        });
    }
});

// Fetch impact stats
async function fetchStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();

        document.getElementById('stat-pounds').textContent =
            stats.pounds_collected.toLocaleString() + '+';
        document.getElementById('stat-meals').textContent =
            stats.meals_provided.toLocaleString() + '+';
        document.getElementById('stat-shows').textContent =
            stats.shows_participated + '+';
        document.getElementById('stat-volunteers').textContent =
            stats.volunteers;
    } catch (error) {
        console.error('Error fetching stats:', error);
    }
}

// Render shows list
function renderShows(shows, showDistances = false) {
    const container = document.getElementById('shows-list');

    if (shows.length === 0) {
        container.innerHTML = `
            <div class="loading-spinner">
                ${isFiltered ? 'No shows found near that location.' : 'No upcoming shows at this time. Check back soon!'}
            </div>
        `;
        return;
    }

    container.innerHTML = shows.map(show => {
        const date = new Date(show.date);
        const formattedDate = date.toLocaleDateString('en-US', {
            weekday: 'long',
            month: 'long',
            day: 'numeric',
            year: 'numeric'
        });
        const formattedTime = date.toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit'
        });

        const location = [show.city, show.state || show.country]
            .filter(Boolean)
            .join(', ');

        const statusClass = show.has_volunteer ? 'has-volunteer' : 'needs-volunteer';
        const statusText = show.has_volunteer
            ? '❤️ Volunteer Secured'
            : '✋ Needs Volunteer';
        const buttonClass = show.has_volunteer ? 'secured' : 'active';
        const buttonText = show.has_volunteer
            ? 'Volunteer Secured ✓'
            : 'Volunteer for This Show';

        const distanceText = showDistances && show.distance !== undefined
            ? `<div class="show-distance">${Math.round(show.distance)} miles away</div>`
            : '';

        return `
            <div class="show-card ${statusClass}" data-show-id="${show.id}">
                ${distanceText}
                <div class="show-date">${formattedDate} • ${formattedTime}</div>
                <div class="show-venue">${escapeHtml(show.venue)}</div>
                <div class="show-location">${escapeHtml(location)}</div>
                <div class="show-status ${statusClass}">${statusText}</div>
                <button
                    class="volunteer-btn ${buttonClass}"
                    ${show.has_volunteer ? 'disabled' : ''}
                    onclick="openVolunteerModal(${show.id})"
                >
                    ${buttonText}
                </button>
            </div>
        `;
    }).join('');
}

// Render map markers
function renderMapMarkers(shows) {
    // Clear existing markers
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];

    const bounds = [];

    shows.forEach(show => {
        if (!show.latitude || !show.longitude) return;

        bounds.push([show.latitude, show.longitude]);

        // Create custom icon
        const iconHtml = show.has_volunteer
            ? '<div class="marker-has-volunteer">❤️</div>'
            : '<div class="marker-needs-volunteer"></div>';

        const icon = L.divIcon({
            html: iconHtml,
            className: 'custom-marker',
            iconSize: [30, 30],
            iconAnchor: [15, 15]
        });

        const marker = L.marker([show.latitude, show.longitude], { icon })
            .addTo(map);

        // Create popup content
        const date = new Date(show.date);
        const formattedDate = date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric'
        });

        const location = [show.city, show.state || show.country]
            .filter(Boolean)
            .join(', ');

        const popupContent = `
            <div style="text-align: center; min-width: 180px;">
                <strong style="font-size: 14px;">${escapeHtml(show.venue)}</strong><br>
                <span style="color: #666;">${escapeHtml(location)}</span><br>
                <span style="color: #8B4513; font-weight: 500;">${formattedDate}</span><br>
                <div style="margin-top: 10px;">
                    ${show.has_volunteer
                        ? '<span style="color: #dc3545;">❤️ Volunteer Secured</span>'
                        : `<button
                            onclick="openVolunteerModal(${show.id})"
                            style="
                                background: #8B4513;
                                color: white;
                                border: none;
                                padding: 8px 16px;
                                border-radius: 4px;
                                cursor: pointer;
                                font-weight: 500;
                            "
                        >Volunteer</button>`
                    }
                </div>
            </div>
        `;

        marker.bindPopup(popupContent);
        markers.push(marker);
    });

    // Fit map to show all markers
    if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [50, 50] });
    }
}

// Open volunteer modal
function openVolunteerModal(showId) {
    const show = shows.find(s => s.id === showId);
    if (!show || show.has_volunteer) return;

    const date = new Date(show.date);
    const formattedDate = date.toLocaleDateString('en-US', {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
        year: 'numeric'
    });

    const location = [show.city, show.state || show.country]
        .filter(Boolean)
        .join(', ');

    document.getElementById('show-id').value = showId;
    document.getElementById('modal-show-info').innerHTML = `
        <strong>${escapeHtml(show.venue)}</strong><br>
        ${escapeHtml(location)} • ${formattedDate}
    `;

    // Update pantry info in modal
    const pantryContainer = document.getElementById('modal-pantries');
    if (pantryContainer) {
        if (show.pantries && show.pantries.length > 0) {
            pantryContainer.innerHTML = `
                <h4>Local Food Banks for This Show:</h4>
                <ul>
                    ${show.pantries.map(p => `
                        <li>
                            <strong>${escapeHtml(p.name)}</strong>
                            ${p.address ? `<br><span class="pantry-address">${escapeHtml(p.address)}</span>` : ''}
                            ${p.phone ? `<br><span class="pantry-phone">${escapeHtml(p.phone)}</span>` : ''}
                            ${p.hours ? `<br><em class="pantry-hours">${escapeHtml(p.hours)}</em>` : ''}
                        </li>
                    `).join('')}
                </ul>
            `;
            pantryContainer.style.display = 'block';
        } else {
            pantryContainer.style.display = 'none';
        }
    }

    // Reset form
    document.getElementById('volunteer-form').reset();
    document.getElementById('volunteer-form').style.display = 'block';
    document.getElementById('form-success').style.display = 'none';

    // Show modal
    const modal = document.getElementById('volunteer-modal');
    modal.classList.add('active');

    // Focus first input
    setTimeout(() => {
        document.getElementById('volunteer-name').focus();
    }, 100);
}

// Close modal
function closeModal() {
    const modal = document.getElementById('volunteer-modal');
    modal.classList.remove('active');
}

// Close modal on outside click
document.getElementById('volunteer-modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'volunteer-modal') {
        closeModal();
    }
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
    }
});

// Submit volunteer form
async function submitVolunteerForm(event) {
    event.preventDefault();

    const form = event.target;
    const submitBtn = form.querySelector('.submit-btn');
    const originalText = submitBtn.textContent;

    // Disable button and show loading
    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting...';

    const data = {
        name: document.getElementById('volunteer-name').value.trim(),
        email: document.getElementById('volunteer-email').value.trim(),
        phone: document.getElementById('volunteer-phone').value.trim(),
        show_id: parseInt(document.getElementById('show-id').value)
    };

    try {
        const response = await fetch('/api/volunteer', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (response.ok) {
            // Show success message
            document.getElementById('volunteer-form').style.display = 'none';
            document.getElementById('form-success').style.display = 'block';

            // Update local state
            const showIndex = shows.findIndex(s => s.id === data.show_id);
            if (showIndex !== -1) {
                shows[showIndex].has_volunteer = true;
            }

            // Re-render shows and map
            renderShows(shows);
            renderMapMarkers(shows);

            // Update stats
            fetchStats();

            // Close modal after delay
            setTimeout(() => {
                closeModal();
            }, 3000);
        } else {
            alert(result.error || 'An error occurred. Please try again.');
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    } catch (error) {
        console.error('Error submitting form:', error);
        alert('An error occurred. Please try again.');
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
}

// Utility: Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            const navHeight = document.querySelector('.navbar').offsetHeight;
            const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - navHeight;
            window.scrollTo({
                top: targetPosition,
                behavior: 'smooth'
            });
        }
    });
});
