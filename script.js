document.addEventListener("DOMContentLoaded", function () {
  const leadForm = document.getElementById("lead-form");
  const formMessage = document.getElementById("form-message");

  leadForm.addEventListener("submit", function (e) {
    e.preventDefault();

    const formData = {
      name: document.getElementById("name").value,
      email: document.getElementById("email").value,
      phone: document.getElementById("phone").value,
      projectType: document.getElementById("project-type").value,
      message: document.getElementById("message").value,
      timestamp: new Date().toISOString(),
    };

    console.log("Lead Form Submission:", formData);

    formMessage.style.color = "#28a745";
    formMessage.textContent =
      "Thank you! We've received your quote request and will contact you within 24 hours.";

    leadForm.reset();

    setTimeout(() => {
      formMessage.textContent = "";
    }, 8000);
  });

  const ctaButtons = document.querySelectorAll('a[href="#contact-form"]');
  ctaButtons.forEach((button) => {
    button.addEventListener("click", function (e) {
      e.preventDefault();
      const formSection = document.getElementById("contact-form");
      const yOffset = -80;
      const y =
        formSection.getBoundingClientRect().top + window.pageYOffset + yOffset;

      window.scrollTo({ top: y, behavior: "smooth" });

      setTimeout(() => {
        document.getElementById("name").focus();
      }, 600);
    });
  });

  const phoneInput = document.getElementById("phone");
  phoneInput.addEventListener("input", function (e) {
    let value = e.target.value.replace(/\D/g, "");
    if (value.length >= 10) {
      value = value.substring(0, 10);
      const formatted = `(${value.substring(0, 3)}) ${value.substring(
        3,
        6
      )}-${value.substring(6, 10)}`;
      e.target.value = formatted;
    }
  });
});
