# Manga Scraper Universel

Scraper de manga/webtoon en ligne de commande et en interface graphique, basé sur **Playwright**. Il transforme n'importe quel chapitre lu en ligne en un **PDF propre et lisible**, en gérant automatiquement les publicités, les protections Cloudflare, les captchas et les différents modes de lecture des sites de scan.

> Projet personnel à but éducatif — aucune affiliation avec les sites de scan mentionnés.

---

## ✨ Fonctionnalités

- **Universel par conception** — ne dépend d'aucun site en particulier : détection de chapitre par URL, par menu déroulant ou par liens, sans patch spécifique à un site
- **Contournement intelligent** — blocage des publicités/trackers, détection et passage de Cloudflare, attente de résolution de captcha
- **Mode de lecture automatique** — détecte si un site affiche le manga page par page et bascule lui-même sur le mode "page continue" quand il existe
- **Sélection de chapitre flexible** — un chapitre unique, une plage (`10` à `20`), ou des numéros décimaux (`262.5`)
- **Découverte de chapitres** — lit le vrai menu déroulant du site pour ne télécharger que les chapitres qui existent réellement dans une plage donnée
- **PDF soigné** — mise en forme CSS injectée avant impression (marges supprimées, images non coupées entre deux pages)
- **Rangement automatique** — classement des PDF par site et par manga, sans intervention
- **Reprise intelligente** — un chapitre déjà téléchargé n'est jamais retéléchargé ; un chapitre en échec est ignoré sans bloquer les suivants
- **Nouvelles tentatives automatiques** — un problème réseau ponctuel relance l'opération sans tout recommencer
- **Interface graphique** (Tkinter) — logs en direct, annulation en cours de téléchargement, thread-safe
- **Interface en ligne de commande** — utilisable en script ou en automatisation

---

## Aperçu

| Interface graphique | Mode CLI |
|---|---|
| Saisie d'URL, plage de chapitres, logs en direct | Téléchargement rapide en une commande |

---

## Prérequis

- Python 3.10 ou supérieur
- [Playwright](https://playwright.dev/python/) pour Python
- Google Chrome d'installer

---

## Installation

```bash
# Cloner le dépôt
git clone <url-du-depot>
cd manga-scraper

# Installer les dépendances
pip install playwright

# Installer le navigateur Chromium requis par Playwright
playwright install chromium
```

---

## Utilisation

### Interface graphique

```bash
python gui.py
```

1. Colle l'URL du chapitre à télécharger
2. Coche **Plusieurs chapitres** pour indiquer une plage (début/fin) si le numéro du chapitre n'apparait pas déjà dans le lien
3. Clique sur **Lancer**
4. Le fichier `.pdf` est automatiquement rangé dans `Pictures/MangaScraper/<site>/<manga>/`

### Ligne de commande

```bash
python main.py
```

Formats acceptés :

```
URL                     → télécharge le lien tel quel
URL chapitre            → télécharge un chapitre précis (ex: 12 ou 262.5)
URL début fin           → télécharge une plage de chapitres
```

Exemple :
```
Lien (q pour quitter) : https://exemple.com/manga/chapitre-1 10 20
```

---

## Structure du projet

```
.
├── gui.py              # Interface graphique Tkinter
├── main.py             # Interface en ligne de commande
├── telechargement.py   # Cœur du scraper : navigation, PDF, détection de chapitre
├── acces.py            # Blocage pubs, contournement Cloudflare, captcha
└── README.md
```

| Fichier | Rôle |
|---|---|
| `GestionAcces` (`acces.py`) | Filtrage réseau (publicités, trackers), détection et contournement de Cloudflare, détection de captcha |
| `GestionTelechargement` (`telechargement.py`) | Pilotage du navigateur, sélection de chapitre, détection du mode de lecture, génération du PDF, logique de reprise/retry |
| `MangaScraperGUI` (`gui.py`) | Interface graphique, communication thread-safe avec le scraper via file d'attente |

---

## Comment ça fonctionne

1. **Chargement de la page** — navigation avec un navigateur furtif (anti-détection), filtrage des ressources indésirables en temps réel
2. **Passage des protections** — attente et résolution automatique du challenge Cloudflare si présent, pause pour résolution manuelle d'un captcha si nécessaire
3. **Sélection du chapitre** — par remplacement direct dans l'URL si le numéro y figure, sinon recherche dans un menu déroulant ou dans les liens de la page
4. **Mise en page** — détection automatique du mode d'affichage (page par page vs page continue) et activation du mode continu si le site le propose
5. **Génération du PDF** — défilement complet de la page pour charger toutes les images, injection d'un style qui nettoie la mise en page, export en PDF à la taille réelle du contenu

---

## Limites connues

- Certains sites sans mode "page continue" ni menu déroulant nécessitent une sélection manuelle du chapitre
- Les protections anti-bot les plus strictes (Cloudflare Turnstile avancé) ne sont pas garanties d'être contournées à 100 %
- La découverte automatique de chapitres (plages avec numéros décimaux) nécessite que le site expose un menu déroulant natif

---

## Pistes d'amélioration

- [ ] Support de plusieurs liens en une seule file d'attente
- [ ] Génération PDF par recomposition d'images pour les très longs webtoons (au-delà des limites de pagination navigateur)
- [ ] Contournement Cloudflare renforcé pour les sites les plus protégés

---

## Licence

Projet personnel — usage privé.
