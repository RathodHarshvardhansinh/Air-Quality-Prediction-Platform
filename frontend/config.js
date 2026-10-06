// Where the Flask backend lives.
// If you open the site through Flask (http://127.0.0.1:5000) the API is on the same origin.
// If you open the html files some other way (Live Server, double click) we point to Flask.
const API_BASE =
    window.location.port === "5000" && window.location.protocol.startsWith("http")
        ? window.location.origin
        : "http://127.0.0.1:5000";
