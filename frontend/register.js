const registerForm = document.getElementById("registerForm");

const nameInput = document.getElementById("name");
const emailInput = document.getElementById("email");
const passwordInput = document.getElementById("password");
const confirmPasswordInput = document.getElementById("confirmPassword");

const togglePassword = document.getElementById("togglePassword");
const toggleConfirmPassword = document.getElementById("toggleConfirmPassword");

const registerButton = document.getElementById("registerButton");
const registerButtonText = document.getElementById("registerButtonText");

const registerMessage = document.getElementById("registerMessage");


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
// SHOW / HIDE CONFIRM PASSWORD
// ===============================

toggleConfirmPassword.addEventListener("click", function () {

    if (confirmPasswordInput.type === "password") {
        confirmPasswordInput.type = "text";
        toggleConfirmPassword.textContent = "Hide";
    } else {
        confirmPasswordInput.type = "password";
        toggleConfirmPassword.textContent = "Show";
    }

});


// ===============================
// REGISTER
// ===============================

registerForm.addEventListener("submit", async function (event) {

    event.preventDefault();

    const name = nameInput.value.trim();
    const email = emailInput.value.trim();
    const password = passwordInput.value;
    const confirmPassword = confirmPasswordInput.value;


    // Clear previous message
    registerMessage.textContent = "";


    // ===============================
    // VALIDATION
    // ===============================

    if (!name || !email || !password || !confirmPassword) {

        registerMessage.textContent =
            "Please fill in all fields.";

        return;
    }


    if (password.length < 6) {

        registerMessage.textContent =
            "Password must be at least 6 characters.";

        return;
    }


    if (password !== confirmPassword) {

        registerMessage.textContent =
            "Passwords do not match.";

        return;
    }


    // ===============================
    // LOADING STATE
    // ===============================

    registerButton.disabled = true;

    registerButtonText.textContent =
        "Creating Account...";


    try {

        const response = await fetch(
            "http://127.0.0.1:5000/register",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    name: name,
                    email: email,
                    password: password
                })
            }
        );


        const data = await response.json();


        // ===============================
        // ERROR RESPONSE
        // ===============================

        if (!response.ok) {

            registerMessage.textContent =
                data.error || "Registration failed.";

            return;
        }


        // ===============================
        // SUCCESS
        // ===============================

        registerMessage.textContent =
            "Account created successfully! Redirecting to login...";


        setTimeout(function () {

            window.location.href =
                "index.html";

        }, 1500);


    } catch (error) {

        console.error(
            "Registration error:",
            error
        );

        registerMessage.textContent =
            "Unable to connect to backend.";

    } finally {

        registerButton.disabled = false;

        registerButtonText.textContent =
            "Create Account";

    }

});