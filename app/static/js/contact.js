document.addEventListener("DOMContentLoaded", () => {

    const form = document.getElementById("contactForm");
    const errorDiv = document.getElementById("formError");
    const resultDiv = document.getElementById("submissionResult");

    form.addEventListener("submit", async (event) => {

        event.preventDefault();

        errorDiv.textContent = "";
        resultDiv.textContent = "";

        const name = document.getElementById("name").value.trim();
        const email = document.getElementById("email").value.trim();
        const phone = document.getElementById("phone").value.trim();
        const department = document.getElementById("department").value;
        const message = document.getElementById("message").value.trim();

        //
        // Basic Validation
        //

        const namePattern = /^[a-zA-Z\s.'-]+$/;
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        const phonePattern = /^[0-9()+\-\s]+$/;

        if (!name) {
            return showError("Name is required.");
        }

        if (!namePattern.test(name)) {
            return showError("Name contains invalid characters.");
        }

        if (!email && !phone) {
            return showError(
                "Provide either an email address or phone number."
            );
        }

        if (email && !emailPattern.test(email)) {
            return showError(
                "Please enter a valid email address."
            );
        }

        if (phone && !phonePattern.test(phone)) {
            return showError(
                "Please enter a valid phone number."
            );
        }

        if (!message) {
            return showError("Message is required.");
        }

        if (message.length < 10) {
            return showError(
                "Message must be at least 10 characters."
            );
        }

        //
        // Payload
        //

        const payload = {
            name,
            email: email || null,
            phone: phone || null,
            department,
            message
        };

        try {

            const response = await fetch("/submit", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.detail || "Submission failed."
                );
            }

            resultDiv.innerHTML = `
                <p><strong>Request submitted successfully.</strong></p>
                <p>Run ID:</p>
                <code>${data.run_id}</code>
            `;

            form.reset();

        } catch (error) {

            showError(error.message);

        }

    });

    function showError(message) {
        errorDiv.textContent = message;
    }

});