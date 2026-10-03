import asyncio
import random
from urllib.parse import urlparse

# --- Constantes ---

BLOCKLIST = (
    'doubleclick.net', 'googlesyndication.com', 'googleadservices.com',
    'adservice', 'adsystem', 'advertising', 'adversal',
    'adf.ly', 'bc.vc', 'linkbucks', 'shorte.st', 'ouo.io',
    'linkvertise', 'link-to.net', 'ay.gy', 'chainfo.xyz',
    'popads', 'popcash', 'propellerads', 'exoclick', 'bidvertiser',
    'adsterra', 'mgid', 'revcontent', 'taboola', 'outbrain',
    'google-analytics', 'googletagmanager', 'facebook.com/tr',
    'analytics', 'tracking', 'tracker', 'metrics',
    '/ads/', '/ad.', '/banner', '/popup', '/redirect',
    'cdn.viglink', 'cdn.taboola', 'cdn.outbrain',
)

CDN_AUTORISES = ('imgur.com', 'cdn.', 'img.', 'image.', 'static.', 'media.')

CF_PATTERNS = (
    'checking your browser',
    'just a moment',
    'ddos protection by cloudflare',
)

CF_CHECKBOX_SELECTORS = (
    'input[type="checkbox"]',
    'input#challenge-stage',
    'label.ctp-checkbox-label input',
)


class GestionAcces:
    def __init__(self):
        self.domaine_original: str | None = None
        self.generation_pdf: bool = False

    def _domaine_autorise(self, netloc: str) -> bool:
        if not self.domaine_original:
            return True
        if any(cdn in netloc for cdn in CDN_AUTORISES):
            return True
        return self.domaine_original.split('.')[-2:] == netloc.split('.')[-2:]

    async def bloquer_navigation_externe(self, route, request):
        url = request.url

        if 'cloudflare.com' in url or 'cf-' in url or self.generation_pdf:
            await route.continue_()
            return

        if any(p in url.lower() for p in BLOCKLIST):
            await route.abort()
            return

        netloc = urlparse(url).netloc
        if not self._domaine_autorise(netloc):
            print(f"   🚫 Bloqué : {netloc}")
            await route.abort()
            return

        if request.resource_type == 'document' and request.frame.parent_frame:
            await route.abort()
            return

        await route.continue_()

    async def _cloudflare_present(self, page) -> bool:
        try:
            texte = await page.evaluate("() => document.body.innerText.toLowerCase()")
            titre = (await page.title()).lower()
            return (
                any(p in texte for p in CF_PATTERNS)
                or ('cloudflare' in titre and ('wait' in titre or 'checking' in titre))
            )
        except Exception:
            return False

    async def _trouver_checkbox_cf(self, page):
        for _ in range(5):
            await asyncio.sleep(1)
            for frame in page.frames:
                for sel in CF_CHECKBOX_SELECTORS:
                    try:
                        for elem in await frame.query_selector_all(sel):
                            if await elem.is_visible() and await elem.is_enabled():
                                return elem
                    except Exception:
                        pass
        return None

    async def contourner_cloudflare_smart(self, page) -> bool:
        print("🛡️  Vérification Cloudflare...")
        await asyncio.sleep(2)

        if not await self._cloudflare_present(page):
            print("   ✓ Pas de Cloudflare")
            return True

        print("   → Challenge détecté !")

        checkbox = await self._trouver_checkbox_cf(page)
        if checkbox:
            try:
                box = await checkbox.bounding_box()
                if box:
                    await page.mouse.move(random.randint(100, 400), random.randint(100, 400))
                    await asyncio.sleep(random.uniform(0.3, 0.6))
                    await page.mouse.move(
                        box['x'] + box['width'] / 2 + random.randint(-3, 3),
                        box['y'] + box['height'] / 2 + random.randint(-3, 3),
                        steps=random.randint(20, 35),
                    )
                    await asyncio.sleep(random.uniform(0.4, 0.8))
                    await checkbox.click()
                    print("   ✓ Checkbox cliquée !")
            except Exception as e:
                print(f"   ⚠️  Erreur clic : {e}")
        else:
            print("   ℹ️  Pas de checkbox, attente automatique...")

        for i in range(30):
            await asyncio.sleep(1)
            if not await self._cloudflare_present(page):
                print(f"   ✅ Passé en {i + 1}s !")
                return True
            if i % 3 == 0:
                await page.mouse.move(random.randint(200, 600), random.randint(200, 500))
            if i % 5 == 0 and i:
                print(f"   ⏳ {i}s...")

        passed = not await self._cloudflare_present(page)
        print("   ✓ Finalement passé !" if passed else "   ⚠️  Timeout, on continue...")
        return passed

    async def detecter_captcha(self, page) -> bool:
        selecteurs = (
            'iframe[src*="recaptcha"]', 'iframe[src*="hcaptcha"]',
            '.g-recaptcha', '.h-captcha', '#captcha', '[class*="captcha"]',
        )
        for sel in selecteurs:
            try:
                elem = await page.query_selector(sel)
                if elem and await elem.is_visible():
                    return True
            except Exception:
                pass
        texte = await page.evaluate("() => document.body.innerText.toLowerCase()")
        return 'captcha' in texte or 'verify you are human' in texte

    async def attendre_captcha(self, page) -> bool:
        print("\n🤖 CAPTCHA DÉTECTÉ ! Résous-le dans le navigateur (max 5 min)...")
        for i in range(300):
            await asyncio.sleep(1)
            if not await self.detecter_captcha(page):
                print("✅ Captcha résolu !")
                await asyncio.sleep(2)
                return True
            if i % 10 == 0 and i:
                print(f"   ⏳ {i}s...")
        print("⚠️  Timeout, on continue...")
        return False
