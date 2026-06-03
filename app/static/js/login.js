const loginForm = document.querySelector(".login-form");
const forgotButton = document.querySelector(".forgot-button");

if (loginForm) {
    loginForm.addEventListener("submit", (event) => {
        const username = loginForm.elements.username.value.trim();
        const password = loginForm.elements.password.value.trim();

        loginForm.classList.remove("is-shaking");

        if (!username || !password) {
            event.preventDefault();
            loginForm.classList.add("is-shaking");
        }
    });
}

if (forgotButton) {
    forgotButton.addEventListener("click", () => {
        forgotButton.textContent = "Hubungi admin";
    });
}
