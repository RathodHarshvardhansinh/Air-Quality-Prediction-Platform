// =====================================
// AUTHENTICATION CHECK
// =====================================

const idToken = localStorage.getItem("idToken");
const userEmail = localStorage.getItem("userEmail");

if (!idToken) {
    window.location.href = "index.html";
}


// =====================================
// LOAD USER INFORMATION
// =====================================

const userEmailElement =
    document.getElementById("userEmail");

const userNameElement =
    document.getElementById("userName");

const welcomeNameElement =
    document.getElementById("welcomeName");


if (userEmail) {

    const name =
        userEmail.split("@")[0];

    if (userEmailElement) {
        userEmailElement.textContent =
            userEmail;
    }

    if (userNameElement) {
        userNameElement.textContent =
            name;
    }

    if (welcomeNameElement) {
        welcomeNameElement.textContent =
            name;
    }

}


// =====================================
// LOGOUT
// =====================================

const logoutButton =
    document.getElementById("logoutButton");


if (logoutButton) {

    logoutButton.addEventListener(
        "click",
        function () {

            localStorage.removeItem("idToken");

            localStorage.removeItem("userEmail");

            window.location.href =
                "index.html";

        }
    );

}


// =====================================
// CITY SEARCH
// =====================================

const citySearch =
    document.getElementById("citySearch");

const searchCityButton =
    document.getElementById(
        "searchCityButton"
    );


// =====================================
// AQI ELEMENTS
// =====================================

const liveAqi =
    document.getElementById("liveAqi");

const aqiCity =
    document.getElementById("aqiCity");

const aqiStatus =
    document.getElementById("aqiStatus");

const aqiProgress =
    document.getElementById("aqiProgress");


// =====================================
// WEATHER ELEMENTS
// =====================================

const weatherTemperature =
    document.getElementById("temperature");

const weatherCity =
    document.getElementById("weatherCity");

const weatherHumidity =
    document.getElementById("humidity");

const weatherWind =
    document.getElementById("windSpeed");

const weatherPressure =
    document.getElementById("pressure");

    


// =====================================
// AQI STATUS
// =====================================

function getAQIStatus(aqi) {

    if (aqi <= 50) {
        return "Good";
    }

    if (aqi <= 100) {
        return "Moderate";
    }

    if (aqi <= 150) {
        return "Unhealthy for Sensitive Groups";
    }

    if (aqi <= 200) {
        return "Unhealthy";
    }

    if (aqi <= 300) {
        return "Very Unhealthy";
    }

    return "Hazardous";
}


// =====================================
// LOAD AQI
// =====================================

async function loadAQI(city) {

    if (!city) {
        return;
    }

    try {

        // Loading state

        liveAqi.textContent =
            "...";

        aqiStatus.textContent =
            "Loading AQI...";

        aqiCity.textContent =
            city;


        // API REQUEST

        const response =
            await fetch(
                `http://127.0.0.1:5000/aqi?city=${encodeURIComponent(city)}`
            );


        const data =
            await response.json();


        // API ERROR

        if (!response.ok) {

            throw new Error(
                data.error ||
                "Unable to fetch AQI"
            );

        }


        // =================================
        // UPDATE AQI
        // =================================

        aqiCity.textContent =
            data.city || city;

        liveAqi.textContent =
            data.aqi ?? "--";


        // =================================
        // AQI STATUS
        // =================================

        if (
            data.aqi !== null &&
            data.aqi !== undefined
        ) {

            aqiStatus.textContent =
                getAQIStatus(data.aqi);


            const progress =
                Math.min(
                    (data.aqi / 300) * 100,
                    100
                );


            aqiProgress.style.width =
                `${progress}%`;

        } else {

            aqiStatus.textContent =
                "AQI unavailable";

            aqiProgress.style.width =
                "0%";

        }


        // =================================
        // POLLUTANTS
        // =================================

        document.getElementById("pm25").textContent =
            data.pm25 ?? "--";

        document.getElementById("pm10").textContent =
            data.pm10 ?? "--";

        document.getElementById("no2").textContent =
            data.no2 ?? "--";

        document.getElementById("co").textContent =
            data.co ?? "--";

        document.getElementById("o3").textContent =
            data.o3 ?? "--";

        document.getElementById("so2").textContent =
            data.so2 ?? "--";


        console.log(
            "AQI loaded successfully:",
            data
        );


    } catch (error) {

        console.error(
            "AQI Error:",
            error
        );


        liveAqi.textContent =
            "--";

        aqiStatus.textContent =
            error.message ||
            "Unable to load AQI";

        aqiProgress.style.width =
            "0%";


        document.getElementById("pm25").textContent =
            "--";

        document.getElementById("pm10").textContent =
            "--";

        document.getElementById("no2").textContent =
            "--";

        document.getElementById("co").textContent =
            "--";

        document.getElementById("o3").textContent =
            "--";

        document.getElementById("so2").textContent =
            "--";

    }

}


// =====================================
// LOAD WEATHER
// =====================================

async function loadWeather(city) {

    if (!city) {
        return;
    }

    try {

        // Loading state

        weatherTemperature.textContent =
            "--°C";

        weatherCity.textContent =
            city;

        weatherHumidity.textContent =
            "--%";

        weatherWind.textContent =
            "--";

        weatherPressure.textContent =
            "--";


        // API REQUEST

        const response =
            await fetch(
                `http://127.0.0.1:5000/weather?city=${encodeURIComponent(city)}`
            );


        const data =
            await response.json();


        // API ERROR

        if (!response.ok) {

            throw new Error(
                data.error ||
                "Unable to fetch weather"
            );

        }


        // =================================
        // UPDATE WEATHER
        // =================================

        weatherTemperature.textContent =
            data.temperature !== null &&
            data.temperature !== undefined

                ? `${data.temperature}°C`

                : "--°C";


        weatherCity.textContent =
            data.city || city;


        weatherHumidity.textContent =
            data.humidity !== null &&
            data.humidity !== undefined

                ? `${data.humidity}%`

                : "--%";


        weatherWind.textContent =
            data.wind_speed !== null &&
            data.wind_speed !== undefined

                ? `${data.wind_speed} m/s`

                : "--";


        weatherPressure.textContent =
            data.pressure !== null &&
            data.pressure !== undefined

                ? `${data.pressure} hPa`

                : "--";


        console.log(
            "Weather loaded successfully:",
            data
        );


    } catch (error) {

        console.error(
            "Weather Error:",
            error
        );


        weatherTemperature.textContent =
            "--°C";

        weatherCity.textContent =
            city;

        weatherHumidity.textContent =
            "--%";

        weatherWind.textContent =
            "--";

        weatherPressure.textContent =
            "--";

    }

}


// =====================================
// LOAD CITY DATA
// AQI + WEATHER
// =====================================

function loadCityData(city) {

    if (!city) {
        return;
    }

    console.log(
        "Loading data for:",
        city
    );


    // Load AQI

    loadAQI(city);


    // Load Weather

    loadWeather(city);

}


// =====================================
// SEARCH BUTTON
// =====================================

if (searchCityButton) {

    searchCityButton.addEventListener(
        "click",
        function () {

            const city =
                citySearch.value.trim();


            if (!city) {

                citySearch.focus();

                return;

            }


            // Save last searched city

            localStorage.setItem(
                "lastCity",
                city
            );


            // Load AQI + Weather

            loadCityData(city);

        }
    );

}


// =====================================
// PRESS ENTER TO SEARCH
// =====================================

if (citySearch) {

    citySearch.addEventListener(
        "keydown",
        function (event) {

            if (
                event.key === "Enter"
            ) {

                event.preventDefault();

                searchCityButton.click();

            }

        }
    );

}


// =====================================
// AUTO DETECT USER LOCATION
// =====================================

function detectUserLocation() {

    if (!navigator.geolocation) {

        console.log(
            "Geolocation is not supported."
        );

        loadFallbackCity();

        return;

    }


    // Loading state

    citySearch.value =
        "Detecting location...";

    liveAqi.textContent =
        "...";

    aqiStatus.textContent =
        "Finding your location...";


    navigator.geolocation.getCurrentPosition(

        async function (position) {

            const latitude =
                position.coords.latitude;

            const longitude =
                position.coords.longitude;


            try {

                // Get nearby city

                const response =
                    await fetch(

                        `http://127.0.0.1:5000/location?latitude=${latitude}&longitude=${longitude}`

                    );


                const data =
                    await response.json();


                if (!response.ok) {

                    throw new Error(
                        data.error ||
                        "Unable to find location"
                    );

                }


                const detectedCity =
                    data.city;


                // Save detected city

                localStorage.setItem(
                    "lastCity",
                    detectedCity
                );


                // Show city

                citySearch.value =
                    detectedCity;


                // Load AQI + Weather

                loadCityData(
                    detectedCity
                );


            } catch (error) {

                console.error(
                    "Location detection error:",
                    error
                );


                loadFallbackCity();

            }

        },


        function (error) {

            console.log(
                "Location permission denied or unavailable:",
                error.message
            );


            loadFallbackCity();

        },


        {
            enableHighAccuracy: true,

            timeout: 10000,

            maximumAge: 300000

        }

    );

}


// =====================================
// FALLBACK CITY
// =====================================

function loadFallbackCity() {

    const lastCity =
        localStorage.getItem(
            "lastCity"
        );


    if (lastCity) {

        citySearch.value =
            lastCity;


        loadCityData(
            lastCity
        );


        return;

    }


    // First-time fallback

    const fallbackCity =
        "Ahmedabad";


    citySearch.value =
        fallbackCity;


    loadCityData(
        fallbackCity
    );

}


// =====================================
// START LOCATION DETECTION
// =====================================

detectUserLocation();