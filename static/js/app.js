// ========================================
// House of Hamill Food Drive - JavaScript
// ========================================

// Global state
let map;
let markers = [];
let shows = [];

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
        shows = await response.json();
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
function renderShows(shows) {
    const container = document.getElementById('shows-list');

    if (shows.length === 0) {
        container.innerHTML = `
            <div class="loading-spinner">
                No upcoming shows at this time. Check back soon!
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

        return `
            <div class="show-card ${statusClass}" data-show-id="${show.id}">
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

        // Format pantries for popup
        let pantriesHtml = '';
        if (show.pantries && show.pantries.length > 0) {
            pantriesHtml = `
                <div style="margin-top: 10px; text-align: left; border-top: 1px solid #eee; padding-top: 10px;">
                    <strong style="font-size: 11px; color: #666;">DONATION PARTNERS:</strong>
                    <ul style="margin: 5px 0; padding-left: 15px; font-size: 12px;">
                        ${show.pantries.slice(0, 2).map(p => `
                            <li style="margin-bottom: 5px;">
                                <strong>${escapeHtml(p.name)}</strong>
                                ${p.hours ? `<br><em style="color: #888; font-size: 11px;">${escapeHtml(p.hours)}</em>` : ''}
                            </li>
                        `).join('')}
                    </ul>
                </div>
            `;
        }

        const popupContent = `
            <div style="text-align: center; min-width: 200px; max-width: 280px;">
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
                ${pantriesHtml}
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
