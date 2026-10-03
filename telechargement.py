import asyncio
import re
import traceback
from pathlib import Path
from urllib.parse import urlparse
from acces import GestionAcces
from playwright.async_api import async_playwright, Page, Browser, BrowserContext, TimeoutError as PlaywrightTimeoutError

# --- Constantes ---
_HEADLESS = False #False navigateur affiché, True navi. caché

_JS_REMOVE_CSS = """() => {
    const s = document.getElementById('manga-scraper-pdf-css');
    if (s) s.remove();
    document.body.style.removeProperty('background-color');
    document.documentElement.style.removeProperty('background-color');
    document.querySelectorAll('div, main, section, center').forEach(el => {
        el.style.removeProperty('width');
        el.style.removeProperty('max-width');
        el.style.removeProperty('margin');
        el.style.removeProperty('padding');
        el.style.removeProperty('background');
    });
}"""

_SEL_CHAPITRE_SELECT = (
    'select[name*="chapter" i]', 'select[id*="chapter" i]', 'select[class*="chapter" i]',
    'select[name*="chapitre" i]', 'select[id*="chapitre" i]', 'select[class*="chapitre" i]',
    'select[name*="episode" i]', 'select[id*="episode" i]',
    'select',  # fallback
)

_SEL_CHAPITRE_LIEN = (
    'a[href*="chapter"]', 'button[class*="chapter"]',
    'div[class*="chapter"]', 'a[href*="chapitre"]',
)

_SEL_LONG_STRIP = (
    'button:has-text("Long Strip")', 'a:has-text("Long Strip")',
    'button:has-text("Webtoon")', 'a:has-text("Webtoon")',
    'button:has-text("Vertical")', 'a:has-text("Vertical")',
    'button:has-text("Scroll")', 'a:has-text("Scroll")',
    'button:has-text("All Pages")', 'a:has-text("All Pages")',
    'button:has-text("Toutes les pages")', 'a:has-text("Toutes les pages")',
    '[class*="long-strip"]', '[id*="long-strip"]',
    '[class*="longstrip"]', '[id*="longstrip"]',
    '[class*="webtoon"]', '[id*="webtoon"]',
    '[class*="vertical"]', '[id*="vertical"]',
    '[class*="scroll-mode"]', '[id*="scroll-mode"]',
    '[class*="reader-mode"]', '[id*="reader-mode"]',
    'button[title*="Long Strip" i]', 'a[title*="Long Strip" i]',
    'button[aria-label*="Long Strip" i]', 'a[aria-label*="Long Strip" i]',
    'button[title*="Webtoon" i]', 'a[title*="Webtoon" i]',
    '.settings button', '.menu button',
    '[class*="settings"] button', '[class*="menu"] button',
)

_SEL_MENUS = (
    'button[class*="menu"]', 'button[class*="settings"]', 'button[class*="options"]',
    '[class*="menu-toggle"]', 'button:has-text("☰")', 'button:has-text("⋮")',
    'button:has-text("Settings")', 'button:has-text("Options")',
)

_LS_KEYWORDS = ('long', 'strip', 'webtoon', 'vertical', 'scroll', 'all', 'toutes')

_JS_FORCE_LAZY = """() => {
    document.querySelectorAll('img[data-src], img[data-lazy-src], img[loading="lazy"]').forEach(img => {
        if (img.dataset.src) img.src = img.dataset.src;
        if (img.dataset.lazySrc) img.src = img.dataset.lazySrc;
        img.loading = 'eager';
    });
}"""

_JS_IMAGE_STATS = """() => {
    const imgs = document.querySelectorAll('img');
    let ok = 0;
    imgs.forEach(img => { if (img.complete && img.naturalHeight > 0) ok++; });
    return {total: imgs.length, ok};
}"""

_JS_IMG_COUNT_VISIBLE = """() =>
    [...document.querySelectorAll('img')]
        .filter(img => { const r = img.getBoundingClientRect(); return r.width > 200 && r.height > 200; })
        .length
"""

_BROWSER_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--no-sandbox', '--disable-setuid-sandbox',
    '--window-size=1920,1080', '--disable-popup-blocking',
]

_ANTI_DETECTION_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
    Object.defineProperty(navigator, 'languages', {get: () => ['fr-FR', 'fr']});
    window.chrome = {runtime: {}};
    window.open = () => null;
"""

_RE_CHAPITRE = re.compile(r'\b(chapitres?|chapters?|chap|ch|c)([-_/])(\d+)', re.IGNORECASE)

_JS_INJECT_CSS = """() => {
    // 1. Fond blanc pur partout
    document.body.style.setProperty('background-color', 'white', 'important');
    document.documentElement.style.setProperty('background-color', 'white', 'important');

    // 2. LE MANTEAU D'INVISIBILITÉ (Sans casser le site)
    const style = document.createElement('style');
    style.id = 'manga-scraper-pdf-css';
    style.textContent = `
        /* Rend TOUT le texte transparent et minuscule (règle le bug "VF" et "SCANS") */
        body, h1, h2, h3, h4, p, span, a, div {
            color: transparent !important;
            font-size: 0px !important;
            line-height: 0px !important;
        }
        
        /* Cache les menus et boutons sans les supprimer du code */
        header, footer, nav, aside, .comments, #disqus_thread, select, button, iframe, .reader-controls {
            display: none !important;
        }
        
        /* Le format parfait pour les images manga */
        body, html { margin: 0 !important; padding: 0 !important; background: white !important; }
        img {
            width: 100% !important;
            max-width: 100% !important;
            height: auto !important;
            display: block !important;
            margin: 0 auto !important;
            break-inside: avoid !important;
            page-break-inside: avoid !important;
        }
    `;
    document.head.appendChild(style);

    // 3. Forcer TOUS les conteneurs à prendre 100% (Règle le bug d'alignement Scan-VF)
    document.querySelectorAll('div, main, section, center').forEach(el => {
        el.style.setProperty('width', '100%', 'important');
        el.style.setProperty('max-width', '100%', 'important');
        el.style.setProperty('margin', '0', 'important');
        el.style.setProperty('padding', '0', 'important');
        el.style.setProperty('background', 'white', 'important');
    });

    // 4. Cacher les drapeaux et logos (Images de moins de 300px)
    document.querySelectorAll('img').forEach(img => {
        if (img.clientWidth < 300 && img.naturalWidth < 300) {
            img.style.setProperty('display', 'none', 'important');
        }
    });
}"""


class GestionTelechargement:
    def __init__(self):
        self.images_chargees = 0
        self.acces = GestionAcces()

    # ------------------------------------------------------------------ #
    # Sélection de chapitre                                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extraire_nombres(texte: str) -> list[float]:
        return [float(n) for n in re.findall(r'\d+(?:\.\d+)?', texte)]
    
    @staticmethod
    def _construire_chemin(url: str, numero_chapitre: int = None) -> Path:
        """Construit le chemin : Pictures/MangaScraper/site/manga/fichier.pdf"""
        parsed = urlparse(url)

        # Nom du site : www.scan-vf.net → Scan-Vf
        site = parsed.netloc.replace('www.', '').rsplit('.', 1)[0].title()

        # Nom du manga : premier segment d'URL utile
        mots_a_ignorer = {'catalogue', 'scan', 'manga', 'chapitre', 'chapter', 'scans', 'vf', 'vostfr', 'v1', 'v2', 'v3'}
        parties = [p for p in parsed.path.split('/') if p and p.lower() not in mots_a_ignorer and not p.isdigit()]
        nom_manga = parties[0].replace('-', ' ').title().replace(' ', '-') if parties else "Manga-Inconnu"

        # Numéro de chapitre : depuis l'URL si non fourni
        if not numero_chapitre:
            match = _RE_CHAPITRE.search(url)
            numero_chapitre = match.group(3) if match else "inconnu"

        dossier = Path.home() / "Pictures" / "MangaScraper" / site / nom_manga
        dossier.mkdir(parents=True, exist_ok=True)
        if isinstance(numero_chapitre, float):
            numero_str = f"{numero_chapitre:g}".replace('.', '-')
        else:
            numero_str = str(numero_chapitre).replace('.', '-')
        return dossier / f"{nom_manga}_Ch_{numero_str}.pdf"

    async def selectionner_chapitre(self, page: Page, numero: float) -> bool:
        print(f"🔍 Recherche du chapitre {numero}...")

        # 1. Numéro déjà dans l'URL → navigation directe
        url_courante = page.url
        
        match = _RE_CHAPITRE.search(url_courante)
        if match and int(match.group(3)) == numero:
            print(f"   ✓ Déjà sur le chapitre {numero}")
            return True

        nouvelle_url = _RE_CHAPITRE.sub(lambda m: f"{m.group(1)}{m.group(2)}{numero}", url_courante)
        
        if nouvelle_url != url_courante:
            print(f"   ✓ Navigation directe → chapitre {numero}")
            await page.goto(nouvelle_url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_load_state('networkidle', timeout=10000)
            return True

        # 2. Menu déroulant visible
        for sel in _SEL_CHAPITRE_SELECT:
            for select_elem in await page.query_selector_all(sel):
                if not await select_elem.is_visible():
                    continue
                options = await select_elem.query_selector_all('option')
                if len(options) < 2:
                    continue
                print(f"   → Menu trouvé ({len(options)} options)")
                for opt in options:
                    texte = await opt.inner_text()
                    if numero not in self._extraire_nombres(texte):
                        continue
                    print(f"   ✓ Chapitre trouvé : '{texte}'")
                    value = await opt.get_attribute('value')
                    if value:
                        await select_elem.select_option(value=value)
                    else:
                        await select_elem.select_option(label=texte)
                    await page.wait_for_load_state('networkidle', timeout=10000)
                    return True

        # 3. Liens / boutons
        print("   → Recherche dans les liens/boutons...")
        for sel in _SEL_CHAPITRE_LIEN:
            for elem in await page.query_selector_all(sel):
                texte = await elem.inner_text()
                if numero in self._extraire_nombres(texte) and await elem.is_visible():
                    print(f"   ✓ Lien trouvé : '{texte}'")
                    await elem.click()
                    await page.wait_for_load_state('networkidle', timeout=10000)
                    return True

        # 4. Fallback manuel
        print(f"   ⚠️  Chapitre {numero} non trouvé — sélectionne-le manuellement")
        input("   Appuie sur Entrée quand c'est fait...")
        await page.wait_for_load_state('networkidle', timeout=10000)
        return True

    # ------------------------------------------------------------------ #
    # Mode Long Strip                                                      #
    # ------------------------------------------------------------------ #

    async def _cliquer_long_strip(self, page: Page) -> bool:
        for sel in _SEL_LONG_STRIP:
            try:
                elem = await page.query_selector(sel)
                if not elem or not await elem.is_visible() or not await elem.is_enabled():
                    continue
                if any(mot in (await elem.inner_text()).lower() for mot in _LS_KEYWORDS):
                    await elem.click()
                    try:
                        await page.wait_for_function(_JS_IMG_COUNT_VISIBLE + " >= 1", timeout=5000)
                    except Exception:
                        pass
                    return True
            except Exception:
                continue
        return False

    async def activer_mode_long_strip(self, page: Page) -> bool:
        print("🔍 Recherche du mode Long Strip...")

        if await self._cliquer_long_strip(page):
            print("   ✓ Mode Long Strip activé !")
            return True

        print("   → Recherche dans les menus...")
        for sel_menu in _SEL_MENUS:
            try:
                menu = await page.query_selector(sel_menu)
                if not menu or not await menu.is_visible():
                    continue
                await menu.click()
                await asyncio.sleep(0.8)
                if await self._cliquer_long_strip(page):
                    print("   ✓ Mode Long Strip activé via menu !")
                    return True
                await menu.click()
                await asyncio.sleep(0.3)
            except Exception:
                continue

        print("   ℹ️  Pas de mode Long Strip détecté")
        return False

    # ------------------------------------------------------------------ #
    # Pagination et scroll                                                 #
    # ------------------------------------------------------------------ #

    async def detecter_mode_pagination(self, page: Page) -> str:
        try:
            nb = await page.evaluate(_JS_IMG_COUNT_VISIBLE)
            if nb < 3:
                print(f"   ⚠️  {nb} image(s) visible(s) → mode page-par-page")
                return "page-par-page"
        except Exception:
            pass
        return "scroll"

    async def scroll_complet(self, page: Page, stop_event=None):
        print("📜 Chargement des images...")

        derniere_hauteur = stable = 0
        while stable < 5:
            if stop_event and stop_event.is_set():
                print("   ⏹️  Scroll interrompu.")
                return
            hauteur = await page.evaluate("document.body.scrollHeight")
            stable = stable + 1 if hauteur == derniere_hauteur else 0
            derniere_hauteur = hauteur
            await page.evaluate(f"window.scrollTo(0, {hauteur})")
            await asyncio.sleep(0.4)
            await page.evaluate(_JS_FORCE_LAZY)

        for pos in range(derniere_hauteur - 500, -1, -500):
            if stop_event and stop_event.is_set():
                print("   ⏹️  Scroll interrompu.")
                return
            await page.evaluate(f"window.scrollTo(0, {max(pos, 0)})")
            await asyncio.sleep(0.15)

        try:
            await page.wait_for_function(
                "() => [...document.querySelectorAll('img')].every(img => img.complete)",
                timeout=5000,
            )
        except Exception:
            pass

        stats = await page.evaluate(_JS_IMAGE_STATS)
        self.images_chargees = stats['ok']
        print(f"   ✓ {stats['ok']}/{stats['total']} images chargées")

    # ------------------------------------------------------------------ #
    # Sous-fonctions de telecharger() — principe SOLID                    #
    # ------------------------------------------------------------------ #

    async def _initialiser_navigateur(self, playwright) -> tuple[Browser, BrowserContext, Page]:
        browser = await playwright.chromium.launch(headless=_HEADLESS, args=_BROWSER_ARGS)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            locale='fr-FR',
        )
        page = await context.new_page()
        await page.add_init_script(_ANTI_DETECTION_SCRIPT)
        await page.route("**/*", lambda route: self.acces.bloquer_navigation_externe(route, route.request))
        context.on("page", lambda new_page: new_page.close())
        return browser, context, page

    async def _charger_page(self, page: Page, url: str) -> bool:
        """Charge l'URL, gère redirections, Cloudflare et captchas.
        Retourne False si l'utilisateur veut annuler."""
        print("🌐 Connexion...")
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await asyncio.sleep(3)

        domaine_actuel = urlparse(page.url).netloc
        if domaine_actuel != self.acces.domaine_original:
            print(f"   ⚠️  Redirection → {domaine_actuel}")
            self.acces.domaine_original = domaine_actuel

        await self.acces.contourner_cloudflare_smart(page)

        if await self.acces.detecter_captcha(page):
            await self.acces.attendre_captcha(page)

        hauteur = await page.evaluate("document.body.scrollHeight")
        if hauteur < 800:
            print(f"\n⚠️  Page très courte ({hauteur}px) — URL : {page.url}")
            if input("   Continuer ? (o/n) : ").strip().lower() not in ('o', 'oui', 'y'):
                return False

        print("✅ Page accessible !\n")
        return True

    async def _preparer_lecture(self, page: Page, numero_chapitre: int | None):
        """Sélectionne le chapitre et active le mode scroll si nécessaire."""
        if numero_chapitre:
            await self.selectionner_chapitre(page, numero_chapitre)

        if await self.detecter_mode_pagination(page) == "page-par-page":
            await self.activer_mode_long_strip(page)
            
    async def _decouvrir_chapitres(self, page: Page, debut: float, fin: float) -> list[float]:
        """Lit le menu déroulant et retourne les numéros réels compris entre debut et fin."""
        for sel in _SEL_CHAPITRE_SELECT:
            for select_elem in await page.query_selector_all(sel):
                if not await select_elem.is_visible():
                    continue
                options = await select_elem.query_selector_all('option')
                if len(options) < 2:
                    continue
                numeros = set()
                for opt in options:
                    texte = await opt.inner_text()
                    nombres = self._extraire_nombres(texte)
                    if nombres:
                        numeros.add(nombres[0])
                trouves = sorted(n for n in numeros if debut <= n <= fin)
                if trouves:
                    return trouves
        return []

    async def _generer_pdf(self, page: Page, nom_fichier: Path, stop_event=None):
        await self.scroll_complet(page, stop_event)

        if stop_event and stop_event.is_set():
            return

        print("📄 Génération du PDF...")
        
        # On applique la magie visuelle juste avant d'imprimer
        await page.evaluate(_JS_INJECT_CSS)
        
        await page.evaluate("window.scrollTo(0, 0)")
        try:
            await page.wait_for_function("() => window.scrollY === 0", timeout=3000)
        except Exception:
            pass

        # Format sur-mesure (hauteur plafonnée à 14400px)
        hauteur_totale = await page.evaluate("document.body.scrollHeight")
        hauteur_pdf = min(hauteur_totale, 14400)

        self.acces.generation_pdf = True
        await page.pdf(
            path=str(nom_fichier),
            width="850px",
            height=f"{hauteur_pdf}px",
            print_background=True,
            prefer_css_page_size=False,
            display_header_footer=False,
            margin={'top': '0mm', 'right': '0mm', 'bottom': '0mm', 'left': '0mm'},
            scale=1.0,
        )
        self.acces.generation_pdf = False
        await page.evaluate(_JS_REMOVE_CSS)

    # ------------------------------------------------------------------ #
    # Point d'entrée principal                                            #
    # ------------------------------------------------------------------ #
    
    async def _avec_retry(self, coro_factory) -> bool:
        """Exécute une coroutine avec 3 tentatives sur timeout réseau."""
        for tentative in range(3):
            try:
                await coro_factory()
                return True
            except PlaywrightTimeoutError:
                if tentative < 2:
                    print(f"   ⚠️  Timeout, nouvel essai ({tentative + 2}/3)...")
                    await asyncio.sleep(3)
                else:
                    print("❌ Échec après 3 tentatives.")
            except Exception:
                print("\n❌ ERREUR :")
                traceback.print_exc()
                return False
        return False

    async def telecharger(self, url: str, numero_chapitre: int = None, stop_event=None):
        self.acces.domaine_original = urlparse(url).netloc
        nom_fichier = self._construire_chemin(url, numero_chapitre)
        
        if nom_fichier.exists():
            print(f"Déjà téléchargé : {nom_fichier.name}")
            return

        print(f"\n{'=' * 70}\n📚 SCRAPER MANGA UNIVERSEL\n{'=' * 70}")
        print(f"🔗 URL : {url}")
        if numero_chapitre:
            print(f"📖 Chapitre : {numero_chapitre}")
        print(f"🏠 Domaine : {self.acces.domaine_original}\n")

        async def _run():
            async with async_playwright() as p:
                browser, _, page = await self._initialiser_navigateur(p)
                try:
                    if not await self._charger_page(page, url):
                        return
                    if stop_event and stop_event.is_set():
                        return

                    await self._preparer_lecture(page, numero_chapitre)
                    await self._generer_pdf(page, nom_fichier, stop_event)

                    if stop_event and stop_event.is_set():
                        return

                    print(f"\n{'=' * 70}")
                    if nom_fichier.exists():
                        taille = nom_fichier.stat().st_size / 1024
                        print(f"✅ {nom_fichier.name}")
                        print(f"   📁 {nom_fichier.parent}")
                        print(f"   📊 {taille:.1f} Ko — {self.images_chargees} images")
                    else:
                        print("❌ Échec de génération du PDF")
                    print('=' * 70)
                finally:
                    await browser.close()

        await self._avec_retry(_run)

    async def telecharger_plusieurs(self, url: str, debut: float, fin: float, stop_event=None):
        self.acces.domaine_original = urlparse(url).netloc
        print(f"\n{'=' * 70}\n📚 CHAPITRES {debut:g} → {fin:g}\n{'=' * 70}\n")

        async def _run():
            async with async_playwright() as p:
                browser, _, page = await self._initialiser_navigateur(p)
                try:
                    if not await self._charger_page(page, url):
                        return

                    chapitres = await self._decouvrir_chapitres(page, debut, fin)
                    if chapitres:
                        print(f"   ✓ {len(chapitres)} chapitre(s) trouvé(s) via le menu : {chapitres}")
                    else:
                        chapitres = [float(n) for n in range(int(debut), int(fin) + 1)]
                        print(f"   ℹ️  Pas de menu détecté, plage entière {int(debut)}-{int(fin)} utilisée")

                    for numero in chapitres:
                        if stop_event and stop_event.is_set():
                            print("   ⏹️  Annulé.")
                            return

                        print(f"\n{'─' * 70}\n📖 Chapitre {numero:g}\n{'─' * 70}")
                        nom_fichier = self._construire_chemin(url, numero)

                        if nom_fichier.exists():
                            print(f"   ⏭️  Déjà téléchargé, passage au suivant...")
                            continue

                        try:
                            await self._preparer_lecture(page, numero)
                            await self._generer_pdf(page, nom_fichier, stop_event)
                        except Exception:
                            print(f"   ❌ Erreur chapitre {numero:g}, passage au suivant...")
                            traceback.print_exc()
                            continue

                        if stop_event and stop_event.is_set():
                            return
                        if nom_fichier.exists():
                            taille = nom_fichier.stat().st_size / 1024
                            print(f"✅ {nom_fichier.name} ({taille:.1f} Ko) — {self.images_chargees} images")
                        else:
                            print("❌ Échec PDF")
                finally:
                    await browser.close()
        await self._avec_retry(_run)
