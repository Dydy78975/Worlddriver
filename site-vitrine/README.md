# JCStamps – Site vitrine : covering, flocage textile, vitrophanie

Statische Website (HTML/CSS/JS), auf Französisch. Kein Server und keine Installation nötig:
einfach `index.html` im Browser öffnen oder den Ordner bei einem Hoster hochladen
(z. B. Netlify, GitHub Pages, OVH, IONOS).

## Was noch angepasst werden muss (Platzhalter)

| Was | Wo |
|---|---|
|  Firmenname „JCStamps“ (bereits eingesetzt) | `index.html`, `mentions-legales.html` (Suchen & Ersetzen) |
| Telefon `06 00 00 00 00` / `tel:+33600000000` | `index.html`, `mentions-legales.html` |
| E-Mail `contact@jcstamps.fr` (Vorschlag, existiert noch nicht) | `index.html`, `mentions-legales.html`, `script.js` (`EMAIL_CONTACT`) |
| Adresse, Öffnungszeiten | `index.html` (Abschnitt Contact) |
| SIRET, Name, Hoster | Fußzeile in `index.html`, `mentions-legales.html` |
| Fotos der Arbeiten | Abschnitt „Réalisations“ in `index.html` – Anleitung steht als Kommentar im Code |

## Dateien

- `index.html` – die Seite (Services, À propos, Réalisations, Méthode, Contact)
- `styles.css` – Design, passt sich an Handy/Tablet/PC an
- `script.js` – Handy-Menü und Kontaktformular (öffnet das E-Mail-Programm mit vorausgefüllter Anfrage)
- `mentions-legales.html` – Impressum (in Frankreich Pflicht)
