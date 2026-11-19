// Adresse e-mail qui reçoit les demandes du formulaire (à modifier)
const EMAIL_CONTACT = "contact@exemple.fr";

// Menu mobile
const toggle = document.querySelector(".nav-toggle");
const nav = document.querySelector(".nav");
toggle.addEventListener("click", () => {
  const open = nav.classList.toggle("open");
  toggle.setAttribute("aria-expanded", open);
  toggle.setAttribute("aria-label", open ? "Fermer le menu" : "Ouvrir le menu");
});
nav.querySelectorAll("a").forEach((a) =>
  a.addEventListener("click", () => {
    nav.classList.remove("open");
    toggle.setAttribute("aria-expanded", "false");
  })
);

// Année dans le pied de page
document.getElementById("year").textContent = new Date().getFullYear();

// Formulaire : ouvre le logiciel de messagerie avec la demande pré-remplie
const form = document.getElementById("contact-form");
const note = form.querySelector(".form__note");

form.addEventListener("submit", (e) => {
  e.preventDefault();
  let valid = true;
  form.querySelectorAll("[required]").forEach((field) => {
    const ok = field.value.trim() !== "" && field.checkValidity();
    field.classList.toggle("invalid", !ok);
    if (!ok) valid = false;
  });

  if (!valid) {
    note.textContent = "Merci de remplir les champs obligatoires (nom, e-mail valide, message).";
    note.className = "form__note err";
    return;
  }

  const d = Object.fromEntries(new FormData(form));
  const subject = `Demande de devis – ${d.service}`;
  const body =
    `Nom : ${d.nom}\nTéléphone : ${d.tel || "-"}\nE-mail : ${d.email}\n` +
    `Projet : ${d.service}\n\n${d.message}`;

  window.location.href =
    `mailto:${EMAIL_CONTACT}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

  note.textContent = "Merci ! Votre messagerie va s'ouvrir pour envoyer la demande.";
  note.className = "form__note ok";
});
