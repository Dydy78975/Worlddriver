# JCStamps – Site vitrine : covering, flocage textile, vitrophanie

Statische Website (HTML/CSS/JS), auf Französisch. Kein Server und keine Installation nötig:
einfach `index.html` im Browser öffnen oder den Ordner bei einem Hoster hochladen
(z. B. Netlify, GitHub Pages, OVH, IONOS).

## Was noch angepasst werden muss (Platzhalter)

| Was | Wo |
|---|---|
|  Firmenname „JCStamps“ (bereits eingesetzt) | `index.html`, `mentions-legales.html` (Suchen & Ersetzen) |
| Telefon `+352 621 000 000` / `tel:+352621000000` | `index.html`, `mentions-legales.html` |
| E-Mail `contact@jcstamps.lu` (Vorschlag, existiert noch nicht) | `index.html`, `mentions-legales.html`, `script.js` (`EMAIL_CONTACT`) |
| Adresse, Öffnungszeiten | `index.html` (Abschnitt Contact) |
| Autorisation d’établissement, TVA, RCS, Name, Hoster (Luxemburg) | Fußzeile in `index.html`, `mentions-legales.html` |
| Fotos der Arbeiten | Abschnitt „Réalisations“ in `index.html` – Anleitung steht als Kommentar im Code |

## Dateien

- `index.html` – die Seite (Services, À propos, Réalisations, Méthode, Contact)
- `styles.css` – Design, passt sich an Handy/Tablet/PC an
- `script.js` – Handy-Menü und Kontaktformular (öffnet das E-Mail-Programm mit vorausgefüllter Anfrage)
- `mentions-legales.html` – Impressum (in Luxemburg Pflicht, Gesetz vom 14. August 2000 über den elektronischen Geschäftsverkehr)
