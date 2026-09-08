// Firebase App
import {
    initializeApp
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";

import {
    getAuth,
    sendPasswordResetEmail
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";


// =================================
// FIREBASE CONFIG
// =================================

// IMPORTANT:
// Yahan apne Firebase Web App ki PUBLIC configuration paste karo.
// Firebase Console → Project Settings → Your Apps → Web App

const firebaseConfig = {
  apiKey: "AIzaSyDFu5duHLbGuA52KFdWCWTKbkvEjql3avg",
  authDomain: "airqualitypredictionplatform.firebaseapp.com",
  projectId: "airqualitypredictionplatform",
  storageBucket: "airqualitypredictionplatform.firebasestorage.app",
  messagingSenderId: "835488755303",
  appId: "1:835488755303:web:9b5823cd4eb815cbb4eec2"
};


// Initialize Firebase
const app = initializeApp(firebaseConfig);

const auth = getAuth(app);


// =================================
// ELEMENTS
// =================================

const forgotPasswordForm =
    document.getElementById("forgotPasswordForm");

const emailInput =
    document.getElementById("email");

const resetButton =
    document.getElementById("resetButton");

const resetButtonText =
    document.getElementById("resetButtonText");

const resetMessage =
    document.getElementById("resetMessage");


// =================================
// FORGOT PASSWORD
// =================================

forgotPasswordForm.addEventListener(
    "submit",
    async function (event) {

        event.preventDefault();

        const email =
            emailInput.value.trim();


        if (!email) {

            resetMessage.textContent =
                "Please enter your email address.";

            return;
        }


        resetButton.disabled = true;

        resetButtonText.textContent =
            "Sending...";

        resetMessage.textContent =
            "";


        try {

            await sendPasswordResetEmail(
                auth,
                email
            );


            resetMessage.textContent =
                "Password reset email sent. Please check your inbox.";


            emailInput.value = "";


        } catch (error) {

            console.error(
                "Password reset error:",
                error
            );


            if (
                error.code ===
                "auth/invalid-email"
            ) {

                resetMessage.textContent =
                    "Please enter a valid email address.";

            } else {

                resetMessage.textContent =
                    "Unable to send password reset email. Please try again.";

            }

        } finally {

            resetButton.disabled = false;

            resetButtonText.textContent =
                "Send Reset Link";

        }

    }
);