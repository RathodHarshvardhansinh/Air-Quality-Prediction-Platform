// =================================
// AUTO LOGIN CHECK
// =================================

const savedToken = localStorage.getItem("idToken");

if (savedToken) {

    window.location.href = "dashboard.html";

}
const loginForm = document.getElementById("loginForm");
const message = document.getElementById("message");
const loginButton = document.getElementById("loginButton");
const loginButtonText = document.getElementById("loginButtonText");

const passwordInput = document.getElementById("password");
const togglePassword = document.getElementById("togglePassword");


// ===============================
// SHOW / HIDE PASSWORD
// ===============================

togglePassword.addEventListener("click", function () {

    if (passwordInput.type === "password") {

        passwordInput.type = "text";
        togglePassword.textContent = "Hide";

    } else {

        passwordInput.type = "password";
        togglePassword.textContent = "Show";

    }

});


// ===============================
// LOGIN
// ===============================

loginForm.addEventListener("submit", async function (event) {

    event.preventDefault();

    const email = document
        .getElementById("email")
        .value
        .trim();

    const password = passwordInput.value;


    if (!email || !password) {

        message.textContent =
            "Please enter your email and password.";

        return;

    }


    loginButton.disabled = true;

    loginButtonText.textContent =
        "Signing in...";

    message.textContent = "";


    try {

        const response = await fetch(
            "http://127.0.0.1:5000/login",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    email: email,
                    password: password
                })
            }
        );


        const data = await response.json();


        if (!response.ok) {

            message.textContent =
                data.error || "Login failed.";

            return;

        }


        // Save authentication token
        localStorage.setItem(
            "idToken",
            data.idToken
        );


        // Save user email
        localStorage.setItem(
            "userEmail",
            data.email
        );


        message.textContent =
            "Login successful. Redirecting...";


        // Dashboard will be created next
        setTimeout(function () {

            window.location.href =
                "dashboard.html";

        }, 1000);


    } catch (error) {

        console.error(
            "Login error:",
            error
        );

        message.textContent =
            "Unable to connect to backend.";

    } finally {

        loginButton.disabled = false;

        loginButtonText.textContent =
            "Sign in";

    }

});