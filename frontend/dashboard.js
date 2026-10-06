// =====================================================
// AirSense dashboard
// =====================================================

// ---------- auth ----------
const idToken = localStorage.getItem("idToken");
const userEmail = localStorage.getItem("userEmail");
if (!idToken) {
    window.location.href = "index.html";
}

// ---------- tiny helpers ----------
const $ = (id) => document.getElementById(id);
const has = (v) => v !== null && v !== undefined && !Number.isNaN(v);

function toast(message, ms = 3500) {
    const el = $("toast");
    el.textContent = message;
    el.classList.add("show");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.remove("show"), ms);
}

function animateNumber(el, to, decimals = 0, duration = 900) {
    const from = parseFloat(el.dataset.value) || 0;
    el.dataset.value = to;
    const start = performance.now();
    function step(now) {
        const t = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - t, 3);
        el.textContent = (from + (to - from) * eased).toFixed(decimals);
        if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}

// ---------- settings ----------
const defaultSettings = { autoLocate: false, autoRefresh: true, notify: false };
let settings = { ...defaultSettings, ...JSON.parse(localStorage.getItem("airsense_settings") || "{}") };
const saveSettings = () => localStorage.setItem("airsense_settings", JSON.stringify(settings));

// =====================================================
// AQI LEVELS  (Indian NAQI / CPCB)
// =====================================================
const LEVELS = [
    { key: "good",         label: "Good",         max: 50,  range: "0 – 50",    color: "#2ecf8f" },
    { key: "satisfactory", label: "Satisfactory", max: 100, range: "51 – 100",  color: "#8fd14f" },
    { key: "moderate",     label: "Moderate",     max: 200, range: "101 – 200", color: "#f2c230" },
    { key: "poor",         label: "Poor",         max: 300, range: "201 – 300", color: "#f28a30" },
    { key: "verypoor",     label: "Very Poor",    max: 400, range: "301 – 400", color: "#e5484d" },
    { key: "severe",       label: "Severe",       max: 9999, range: "401 – 500", color: "#9b2c4a" },
];

function levelOf(aqi) {
    if (!has(aqi)) return { key: "none", label: "Unavailable", color: "#9aa8a3" };
    return LEVELS.find((l) => aqi <= l.max) || LEVELS[LEVELS.length - 1];
}

const ADVICE = {
    good: {
        icon: "🟢", title: "Good — air quality is safe",
        text: "Air quality is satisfactory and poses little or no risk.",
        tips: ["Great time for outdoor activity or exercise.", "No precautions needed."],
    },
    satisfactory: {
        icon: "🟡", title: "Satisfactory — minor concern",
        text: "Air is acceptable; a small risk exists for unusually sensitive people.",
        tips: ["Sensitive people should watch for mild symptoms.", "Normal outdoor activity is fine for most."],
    },
    moderate: {
        icon: "🟠", title: "Moderate — caution for sensitive groups",
        text: "Children, elderly and people with asthma or heart/lung disease may feel mild effects.",
        tips: ["Sensitive groups: reduce long outdoor exertion.", "Keep windows closed in peak traffic hours.", "Healthy adults can continue normally."],
    },
    poor: {
        icon: "🔴", title: "Poor — health effects possible",
        text: "Everyone may begin to feel effects; sensitive groups may feel more serious ones.",
        tips: ["Limit outdoor exertion, especially children & elderly.", "Wear an N95 mask outside.", "Use an air purifier indoors if you have one."],
        alert: "Pollution alert: air quality is Poor — avoid long outdoor exposure.",
    },
    verypoor: {
        icon: "🟣", title: "Very Poor — health warning",
        text: "The entire population is likely to be affected.",
        tips: ["Avoid outdoor physical activity.", "Keep doors & windows closed; run a purifier.", "People with lung/heart conditions should stay indoors."],
        alert: "Pollution alert: air quality is Very Poor — stay indoors where possible.",
    },
    severe: {
        icon: "⛔", title: "Severe — health emergency",
        text: "Serious risk of respiratory effects for everyone.",
        tips: ["Stay indoors with windows closed.", "Avoid all outdoor activity.", "Seek medical help if breathing is difficult."],
        alert: "Severe pollution alert: air is hazardous — stay indoors.",
    },
};

// =====================================================
// USER + GREETING
// =====================================================
function setUserName(name) {
    const clean = (name || "").trim();
    if (!clean) return;
    $("userName").textContent = clean;
    $("welcomeName").textContent = clean.split(" ")[0];
    $("userAvatar").textContent = clean[0].toUpperCase();
}

(function initUser() {
    if (userEmail) {
        $("userEmail").textContent = userEmail;
        setUserName(localStorage.getItem("userName") || userEmail.split("@")[0]);
    }
    // Ask the backend for the real name saved at registration
    fetch(`${API_BASE}/profile`, { headers: { Authorization: `Bearer ${idToken}` } })
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
            if (d && d.user && d.user.name) {
                localStorage.setItem("userName", d.user.name);
                setUserName(d.user.name);
            }
        })
        .catch(() => {});
})();

function greetingFor(date) {
    const h = date.getHours();
    if (h >= 5 && h < 12) return "Good morning";
    if (h >= 12 && h < 17) return "Good afternoon";
    if (h >= 17 && h < 21) return "Good evening";
    return "Good night";
}

function tickClock() {
    const now = new Date();
    $("greetingText").textContent = greetingFor(now);
    $("clockText").textContent =
        "· " + now.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" }) +
        ", " + now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
tickClock();
setInterval(tickClock, 30000);

// logout
$("logoutButton").addEventListener("click", () => {
    ["idToken", "userEmail", "userName", "airsense_place", "lastCity"].forEach((k) => localStorage.removeItem(k));
    window.location.href = "index.html";
});

// =====================================================
// NAVIGATION (sidebar views)
// =====================================================
const VIEWS = ["dashboard", "air", "weather", "traffic", "settings"];

function showView(name) {
    if (!VIEWS.includes(name)) name = "dashboard";
    VIEWS.forEach((v) => $("view-" + v).classList.toggle("active", v === name));
    document.querySelectorAll(".nav-item[data-view]").forEach((a) =>
        a.classList.toggle("active", a.dataset.view === name)
    );
    window.scrollTo({ top: 0, behavior: "smooth" });
}

window.addEventListener("hashchange", () => showView(location.hash.replace("#", "")));
showView(location.hash.replace("#", "") || "dashboard");

// =====================================================
// STATE
// =====================================================
const state = { place: null, env: null, predictions: null, selected: "1h", requestId: 0, loadedOnce: false };

function setStatus(kind, text) {
    const pill = $("statusPill");
    pill.className = "last-updated" + (kind ? " " + kind : "");
    $("statusText").textContent = text;
}

// =====================================================
// RENDER: AQI
// =====================================================
const POLLUTANTS = [
    { id: "pm25", key: "PM2.5", label: "PM2.5", unit: "µg/m³" },
    { id: "pm10", key: "PM10", label: "PM10", unit: "µg/m³" },
    { id: "no2", key: "NO2", label: "NO₂", unit: "µg/m³" },
    { id: "co", key: "CO", label: "CO", unit: "mg/m³" },
    { id: "o3", key: "O3", label: "O₃", unit: "µg/m³" },
    { id: "so2", key: "SO2", label: "SO₂", unit: "µg/m³" },
];

function pollutantTiles(data) {
    return POLLUTANTS.map((p) => {
        const value = data ? data[p.id] : null;
        const sub = data && data.sub_indices ? data.sub_indices[p.key] : null;
        const lvl = levelOf(has(sub) ? sub : null);
        const width = has(sub) ? Math.min((sub / 300) * 100, 100) : 0;
        return `
            <div class="pollutant" data-level="${lvl.key}">
                <span>${p.label}</span>
                <strong>${has(value) ? value : "--"}</strong>
                <small>${p.unit}</small>
                <div class="bar"><i data-w="${width}"></i></div>
            </div>`;
    }).join("");
}

function fillBars(root) {
    requestAnimationFrame(() => root.querySelectorAll(".bar i").forEach((b) => (b.style.width = b.dataset.w + "%")));
}

function renderAQI(data, errorMsg) {
    const hero = $("heroCard");
    $("liveAqi").classList.remove("skeleton");

    $("aqiCity").textContent = state.place ? state.place.name : "--";

    const aqi = data ? data.aqi : null;
    const lvl = levelOf(aqi);

    ["heroCard", "advisoryCard"].forEach((id) => ($(id).dataset.level = lvl.key));

    if (has(aqi)) {
        animateNumber($("liveAqi"), aqi, 0);
        $("ringFill").style.strokeDashoffset = 440 * (1 - Math.min(aqi / 500, 1));
        $("aqiMarker").style.left = `calc(${Math.min(aqi / 500, 1) * 100}% - 2px)`;
        $("aqiStatus").textContent = data.status || data.category || lvl.label;
        const prom = data.prominent_pollutant ? `Main pollutant: ${data.prominent_pollutant}.` : "";
        $("aqiHint").textContent = `${ADVICE[lvl.key].text} ${prom}`;
        const dist = has(data.station_distance_km) && data.station_distance_km > 0 ? ` · ${data.station_distance_km} km away` : "";
        $("aqiSource").textContent = `Source: ${data.source || "—"}${data.station ? " · " + data.station : ""}${dist}`;
    } else {
        $("liveAqi").textContent = "--";
        $("ringFill").style.strokeDashoffset = 440;
        $("aqiMarker").style.left = "0";
        $("aqiStatus").textContent = "AQI unavailable";
        $("aqiHint").textContent = errorMsg || "Could not read air quality for this location right now.";
        $("aqiSource").textContent = "";
    }

    $("aqiUpdated").textContent = "Updated " + new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    // pollutant tiles (dashboard + air-quality page)
    $("pollutantsGrid").innerHTML = pollutantTiles(data);
    $("pollutantsGridAir").innerHTML = pollutantTiles(data);
    fillBars($("pollutantsGrid"));
    fillBars($("pollutantsGridAir"));
    $("airSourceNote").textContent = data
        ? `Bars show each pollutant's own sub-index (CPCB). ${data.station ? "Station: " + data.station + "." : ""}`
        : "";

    // legend
    $("aqiLegend").innerHTML = LEVELS.map((l) => `
        <div class="legend-row ${has(aqi) && l.key === lvl.key ? "current" : ""}">
            <i style="background:${l.color}"></i>${l.label}<span>${l.range}</span>
        </div>`).join("");

    renderAdvisory(aqi, lvl);
}

function renderAdvisory(aqi, lvl) {
    const banner = $("pollutionAlertBanner");
    if (!has(aqi)) {
        $("advisoryIcon").textContent = "⚪";
        $("advisoryTitle").textContent = "Advisory unavailable";
        $("advisoryText").textContent = "Could not determine a health advisory — AQI data is unavailable.";
        $("advisoryTips").innerHTML = "";
        banner.style.display = "none";
        return;
    }
    const a = ADVICE[lvl.key];
    $("advisoryIcon").textContent = a.icon;
    $("advisoryTitle").textContent = a.title;
    $("advisoryText").textContent = a.text;
    $("advisoryTips").innerHTML = a.tips.map((t) => `<li>${t}</li>`).join("");

    if (a.alert) {
        banner.style.display = "flex";
        $("pollutionAlertText").textContent = a.alert;
        // one notification per place/level, not on every refresh
        const sig = `${state.place && state.place.name}:${lvl.key}`;
        if (settings.notify && "Notification" in window && Notification.permission === "granted" &&
            sessionStorage.getItem("airsense_notified") !== sig) {
            sessionStorage.setItem("airsense_notified", sig);
            try { new Notification("AirSense pollution alert", { body: a.alert }); } catch (e) { /* ignore */ }
        }
    } else {
        banner.style.display = "none";
    }
}

// =====================================================
// RENDER: WEATHER
// =====================================================
function weatherDisplay(description) {
    const c = (description || "").toLowerCase();
    const night = new Date().getHours() >= 19 || new Date().getHours() < 6;
    if (!c) return { icon: "🌤️", text: "Weather unavailable" };
    if (c.includes("thunder")) return { icon: "⛈️", text: "Thunderstorm" };
    if (c.includes("rain") || c.includes("drizzle") || c.includes("shower")) return { icon: "🌧️", text: "Rainy" };
    if (c.includes("snow")) return { icon: "❄️", text: "Snow" };
    if (c.includes("mist") || c.includes("fog") || c.includes("haze") || c.includes("smoke") || c.includes("dust")) return { icon: "🌫️", text: "Hazy" };
    if (c.includes("cloud") || c.includes("overcast")) return { icon: night ? "☁️" : "⛅", text: "Cloudy" };
    if (c.includes("clear") || c.includes("sun")) return night ? { icon: "🌙", text: "Clear night" } : { icon: "☀️", text: "Sunny" };
    return { icon: "🌤️", text: description };
}

function renderWeather(w) {
    const d = weatherDisplay(w && w.description);
    const temp = w && has(w.temperature) ? `${Math.round(w.temperature * 10) / 10}°C` : "--°C";
    const hum = w && has(w.humidity) ? `${w.humidity}%` : "--%";
    const wind = w && has(w.wind_speed) ? `${w.wind_speed} m/s` : "--";
    const press = w && has(w.pressure) ? `${w.pressure} hPa` : "--";
    const vis = w && has(w.visibility) ? `${(w.visibility / 1000).toFixed(1)} km` : "--";

    $("temperature").textContent = temp;
    $("weatherIcon").textContent = d.icon;
    $("weatherDescription").textContent = w ? d.text : "Weather unavailable";
    $("humidity").textContent = hum;
    $("windSpeed").textContent = wind;
    $("pressure").textContent = press;

    $("wxCity").textContent = state.place ? state.place.name : "Weather";
    $("wxIcon").textContent = d.icon;
    $("wxTemp").textContent = temp;
    $("wxDesc").textContent = w ? (w.description || d.text) : "Weather unavailable";
    $("wxSource").textContent = w && w.source ? `Source: ${w.source}` : "";
    $("wxTiles").innerHTML = [
        ["💧 Humidity", hum], ["💨 Wind speed", wind], ["◉ Pressure", press], ["👁 Visibility", vis],
    ].map(([k, v]) => `<div class="tile"><span>${k}</span><strong>${v}</strong></div>`).join("");
}

// =====================================================
// RENDER: TRAFFIC
// =====================================================
function trafficInfo(t) {
    const ratio = t.current_speed / t.free_flow_speed;
    if (t.road_closure) return { status: "Road closed", road: "Closed", best: "Avoid", color: "#e5484d", level: "verypoor", ratio: 0 };
    if (ratio >= 0.85) return { status: "Light", road: "Smooth flow", best: "Now ✅", color: "#2ecf8f", level: "good", ratio };
    if (ratio >= 0.6) return { status: "Moderate", road: "Busy", best: "Good time", color: "#f2c230", level: "moderate", ratio };
    return { status: "Heavy", road: "Congested", best: "Avoid peak", color: "#e5484d", level: "verypoor", ratio };
}

function formatDelay(t) {
    if (!has(t.current_travel_time) || !has(t.free_flow_travel_time)) return "--";
    const sec = Math.max(0, t.current_travel_time - t.free_flow_travel_time);
    if (sec < 60) return `${Math.round(sec)} sec`;
    return `${Math.round(sec / 60)} min`;
}

function renderTraffic(t, errorMsg) {
    const ok = t && has(t.current_speed) && has(t.free_flow_speed) && t.free_flow_speed > 0;

    if (!ok) {
        const msg = errorMsg || "No live traffic data for this location";
        $("trafficStatus").textContent = "No data";
        $("trafficCircle").style.cssText = "background:#9aa8a3;box-shadow:0 0 0 6px rgba(154,168,163,.18)";
        $("currentSpeed").textContent = "-- km/h";
        $("roadCondition").textContent = "--";
        $("travelDelay").textContent = "--";
        $("bestTime").textContent = "--";
        $("tfStatus").textContent = "Traffic";
        $("tfSpeed").textContent = "-- km/h";
        $("tfBar").style.width = "0%";
        $("tfFree").textContent = "Free flow --";
        $("tfNote").textContent = msg + ". Traffic coverage is best on main roads of larger towns.";
        $("tfTiles").innerHTML = "";
        $("trafficBigCard").dataset.level = "none";
        return;
    }

    const info = trafficInfo(t);
    const speed = `${Math.round(t.current_speed)} km/h`;
    const delay = formatDelay(t);

    $("trafficStatus").textContent = info.status;
    $("trafficCircle").style.cssText = `background:${info.color};box-shadow:0 0 0 6px ${info.color}33`;
    $("currentSpeed").textContent = speed;
    $("roadCondition").textContent = info.road;
    $("travelDelay").textContent = delay;
    $("bestTime").textContent = info.best;

    $("trafficBigCard").dataset.level = info.level;
    $("tfStatus").textContent = `${info.status} traffic`;
    $("tfSpeed").textContent = speed;
    $("tfBar").style.width = `${Math.min((t.current_speed / t.free_flow_speed) * 100, 100)}%`;
    $("tfFree").textContent = `Free flow ${Math.round(t.free_flow_speed)} km/h`;
    $("tfNote").textContent = t.source ? `Showing: ${t.source}.` : "Live data from TomTom.";
    $("tfTiles").innerHTML = [
        ["Current speed", speed],
        ["Free-flow speed", `${Math.round(t.free_flow_speed)} km/h`],
        ["Road condition", info.road],
        ["Congestion", `${Math.max(0, Math.round((1 - info.ratio) * 100))}%`],
        ["Travel delay", delay],
        ["Best time", info.best],
    ].map(([k, v]) => `<div class="tile"><span>${k}</span><strong>${v}</strong></div>`).join("");
}

// =====================================================
// FORECAST
// =====================================================
function showPrediction(type) {
    state.selected = type;
    $("prediction1hButton").classList.toggle("active", type === "1h");
    $("prediction6hButton").classList.toggle("active", type === "6h");

    const p = state.predictions;
    const value = p ? (type === "1h" ? p.prediction_1h : p.prediction_6h) : null;
    const lvl = levelOf(value);
    $("forecastCard").dataset.level = lvl.key;

    if (has(value)) {
        animateNumber($("predictionValue"), value, 0);
        $("predictionValueStatus").textContent = lvl.label;
        const now = state.env && state.env.air_quality ? state.env.air_quality.aqi : null;
        if (has(now)) {
            const diff = Math.round(value - now);
            $("predictionDelta").textContent =
                diff === 0 ? "Same as right now" : `${diff > 0 ? "▲" : "▼"} ${Math.abs(diff)} ${diff > 0 ? "higher" : "lower"} than now`;
        } else {
            $("predictionDelta").textContent = "";
        }
    } else {
        $("predictionValue").textContent = "--";
        $("predictionValueStatus").textContent = "Prediction unavailable";
        $("predictionDelta").textContent = state.predictionError || "";
    }
}

async function loadPredictions(cityName, requestId) {
    state.predictions = null;
    state.predictionError = "";
    $("predictionCity").textContent = cityName;
    $("predictionValueStatus").textContent = "Loading...";
    try {
        const r = await fetch(`${API_BASE}/predict?city=${encodeURIComponent(cityName)}`);
        const d = await r.json();
        if (requestId !== state.requestId) return;
        if (!r.ok) throw new Error(d.error || "Prediction unavailable");
        state.predictions = d;
    } catch (e) {
        if (requestId !== state.requestId) return;
        state.predictionError = e.message;
    }
    showPrediction(state.selected);
}

$("prediction1hButton").addEventListener("click", () => showPrediction("1h"));
$("prediction6hButton").addEventListener("click", () => showPrediction("6h"));

// =====================================================
// LOAD EVERYTHING FOR A PLACE
// query = { lat, lon, city? }  or  { city }
// =====================================================
async function loadEnvironment(query, { silent = false } = {}) {
    const requestId = ++state.requestId;

    if (!silent) {
        $("liveAqi").classList.add("skeleton");
        $("aqiStatus").textContent = "Loading...";
        setStatus("", "Loading live data...");
    }

    const params = new URLSearchParams();
    if (has(query.lat) && has(query.lon)) {
        params.set("lat", query.lat);
        params.set("lon", query.lon);
    }
    if (query.city) params.set("city", query.city);

    let env;
    try {
        const r = await fetch(`${API_BASE}/environment?${params}`);
        env = await r.json();
        if (requestId !== state.requestId) return;
        if (!r.ok) {
            $("liveAqi").classList.remove("skeleton");
            toast(env.error || "Could not load data");
            setStatus("stale", "Not found");
            if (!state.loadedOnce) $("aqiStatus").textContent = "Search a city to begin";
            return;
        }
    } catch (e) {
        if (requestId !== state.requestId) return;
        console.error("Backend error:", e);
        $("liveAqi").classList.remove("skeleton");
        setStatus("offline", "Backend offline");
        toast("Cannot reach the AirSense server. Start it with:  python backend/app.py", 6000);
        return;
    }

    state.env = env;
    state.place = env.location;
    state.loadedOnce = true;
    savePlace(env.location);
    rememberViewed(env.location.name);
    updatePlaceUi();

    const err = env.errors || {};
    renderAQI(env.air_quality, err.air_quality);
    renderWeather(env.weather);
    renderTraffic(env.traffic, err.traffic);

    const failed = Object.keys(err).length;
    setStatus(
        failed ? "stale" : "",
        failed ? `Partial data · ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
               : `Live · ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
    );

    loadPredictions(env.location.name, requestId);
}

// =====================================================
// PLACE HANDLING
// =====================================================
function savePlace(p) {
    localStorage.setItem("airsense_place", JSON.stringify({ name: p.name, latitude: p.latitude, longitude: p.longitude }));
}
function loadSavedPlace() {
    try { return JSON.parse(localStorage.getItem("airsense_place")); } catch (e) { return null; }
}

function updatePlaceUi() {
    const p = state.place;
    if (!p) return;
    $("placeLabel").textContent = p.state ? `${p.name}, ${p.state}` : p.name;
    $("citySearch").value = p.name;
    $("historyLink").href = `history.html?city=${encodeURIComponent(p.name)}`;
    $("analyticsHistoryLink").href = `history.html?city=${encodeURIComponent(p.name)}`;
    $("savedPlaceText").textContent = p.name;
}

function rememberViewed(city) {
    let list = [];
    try { list = JSON.parse(localStorage.getItem("airSenseRecentlyViewed")) || []; } catch (e) { /* ignore */ }
    list = list.filter((x) => x.city.toLowerCase() !== city.toLowerCase());
    list.unshift({ city, time: new Date().toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) });
    localStorage.setItem("airSenseRecentlyViewed", JSON.stringify(list.slice(0, 8)));
}

// ---------- GPS ----------
function getGPS() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) return reject(new Error("Geolocation not supported"));
        navigator.geolocation.getCurrentPosition(resolve, reject, {
            enableHighAccuracy: false,   // network/wifi fix is enough for a city & much faster
            timeout: 12000,
            maximumAge: 60000,
        });
    });
}

async function ipLocation() {
    // last-resort: approximate location from the internet connection
    try {
        const r = await fetch("https://ipwho.is/");
        const d = await r.json();
        if (d && d.success && has(d.latitude)) return { lat: d.latitude, lon: d.longitude, city: d.city };
    } catch (e) { /* ignore */ }
    return null;
}

async function detectLocation({ manual = false } = {}) {
    $("placeLabel").textContent = "Detecting your location...";
    setStatus("", "Locating...");

    try {
        const pos = await getGPS();
        // Let the backend name the place from the GPS fix; /environment does it for us
        await loadEnvironment({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        return;
    } catch (e) {
        console.warn("GPS failed:", e.message);
        if (manual) toast("Location permission is blocked. Allow it in the browser address bar, or search a city.", 5000);
    }

    const ip = await ipLocation();
    if (ip) {
        toast("Using approximate location (GPS not available).");
        await loadEnvironment({ lat: ip.lat, lon: ip.lon, city: ip.city });
        return;
    }

    const saved = loadSavedPlace();
    if (saved) {
        toast(`Showing your last location: ${saved.name}`);
        await loadEnvironment({ lat: saved.latitude, lon: saved.longitude, city: saved.name });
        return;
    }

    $("placeLabel").textContent = "Location unavailable";
    setStatus("stale", "Search a city");
    $("liveAqi").classList.remove("skeleton");
    $("aqiStatus").textContent = "Search a city to begin";
    toast("Could not detect your location — type a city in the search box.");
}

// ---------- search ----------
$("searchCityButton").addEventListener("click", () => {
    const city = $("citySearch").value.trim();
    if (!city) { $("citySearch").focus(); return; }
    loadEnvironment({ city });
});
$("citySearch").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); $("searchCityButton").click(); }
});
$("citySearch").addEventListener("focus", (e) => e.target.select());
$("useLocationButton").addEventListener("click", () => detectLocation({ manual: true }));

// =====================================================
// SETTINGS PAGE
// =====================================================
$("setAutoLocate").checked = settings.autoLocate;
$("setAutoRefresh").checked = settings.autoRefresh;
$("setNotify").checked = settings.notify;

$("setAutoLocate").addEventListener("change", (e) => { settings.autoLocate = e.target.checked; saveSettings(); });
$("setAutoRefresh").addEventListener("change", (e) => { settings.autoRefresh = e.target.checked; saveSettings(); });
$("setNotify").addEventListener("change", async (e) => {
    settings.notify = e.target.checked;
    if (settings.notify && "Notification" in window && Notification.permission === "default") {
        const result = await Notification.requestPermission();
        if (result !== "granted") { settings.notify = false; e.target.checked = false; toast("Notifications were blocked by the browser."); }
    }
    saveSettings();
});
$("clearPlaceButton").addEventListener("click", () => {
    localStorage.removeItem("airsense_place");
    toast("Saved location cleared.");
});

// =====================================================
// ANALYTICS OVERLAY
// =====================================================
let analyticsChart = null;

async function openAnalytics() {
    const overlay = $("analyticsOverlay");
    overlay.classList.add("active");
    document.body.style.overflow = "hidden";

    const env = state.env || {};
    const aqi = env.air_quality && env.air_quality.aqi;
    $("analyticsSub").textContent = state.place ? `${state.place.name} · last 24 hours` : "AI powered air intelligence";
    $("analyticsAQI").textContent = has(aqi) ? aqi : "--";
    $("analyticsAQIStatus").textContent = levelOf(aqi).label;
    $("analyticsTemp").textContent = env.weather && has(env.weather.temperature) ? `${Math.round(env.weather.temperature)}°C` : "--";
    $("analyticsHumidity").textContent = env.weather && has(env.weather.humidity) ? `${env.weather.humidity}%` : "--";
    $("analyticsTraffic").textContent = env.traffic && has(env.traffic.current_speed) ? `${Math.round(env.traffic.current_speed)} km/h` : "--";

    const note = $("analyticsChartNote");
    note.textContent = "";
    if (!state.place) return;

    try {
        const r = await fetch(`${API_BASE}/history/24h?city=${encodeURIComponent(state.place.name)}`);
        const d = await r.json();
        if (!r.ok) throw new Error(d.error);
        if (!d.records.length) {
            note.textContent = "No saved history for this place yet. Every visit saves a reading, so the chart will fill up over time.";
            if (analyticsChart) { analyticsChart.destroy(); analyticsChart = null; }
            return;
        }
        if (typeof Chart === "undefined") { note.textContent = "Chart library could not load (check internet)."; return; }
        if (analyticsChart) analyticsChart.destroy();
        analyticsChart = new Chart($("analyticsChart"), {
            type: "line",
            data: {
                labels: d.records.map((x) => new Date(x.timestamp.replace(" ", "T")).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })),
                datasets: [{
                    label: "AQI", data: d.records.map((x) => x.aqi),
                    borderColor: "#35d39a", backgroundColor: "rgba(53,211,154,.15)",
                    fill: true, tension: 0.4, borderWidth: 3, pointRadius: 2,
                }],
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } }, y: { beginAtZero: true } },
            },
        });
        note.textContent = `Latest saved reading: ${d.latest}`;
    } catch (e) {
        note.textContent = "Could not load history.";
    }
}

function closeAnalytics() {
    $("analyticsOverlay").classList.remove("active");
    document.body.style.overflow = "";
}

$("openAnalytics").addEventListener("click", openAnalytics);
$("closeAnalytics").addEventListener("click", closeAnalytics);
$("analyticsOverlay").addEventListener("click", (e) => { if (e.target === $("analyticsOverlay")) closeAnalytics(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeAnalytics(); });

// =====================================================
// START
// =====================================================
(async function start() {
    const saved = loadSavedPlace();
    if (settings.autoLocate) {
        await detectLocation();
    } else if (saved) {
        await loadEnvironment({ lat: saved.latitude, lon: saved.longitude, city: saved.name });
    } else {
        await detectLocation();
    }
})();

// auto refresh every 5 minutes
setInterval(() => {
    if (!settings.autoRefresh || document.hidden || !state.place) return;
    loadEnvironment({ lat: state.place.latitude, lon: state.place.longitude, city: state.place.name }, { silent: true });
}, 5 * 60 * 1000);

// refresh when the tab becomes visible again after a long time
let hiddenAt = 0;
document.addEventListener("visibilitychange", () => {
    if (document.hidden) { hiddenAt = Date.now(); return; }
    if (settings.autoRefresh && state.place && Date.now() - hiddenAt > 10 * 60 * 1000) {
        loadEnvironment({ lat: state.place.latitude, lon: state.place.longitude, city: state.place.name }, { silent: true });
    }
});
