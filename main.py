"""
Point d'entrée CLI (optionnel).
Pour l'interface graphique, lance gui.py directement
ou compile avec : pyinstaller --onefile --noconsole gui.py
"""
import asyncio

from telechargement import GestionTelechargement


async def main():
    print("📚 Manga Scraper — Mode CLI")
    #print("💡 Format : URL  ou  URL numéro_chapitre\n")
    print("💡 Format : URL  |  URL chapitre  |  URL début fin\n")

    while True:
        entree = input("🔗 Lien (q pour quitter) : ").strip()

        if entree.lower() in ("q", "quit", "exit"):
            print("👋 Au revoir !")
            break

        if not entree:
            continue

        parties = entree.split()
        url = parties[0]

        if not url.startswith("http"):
            print("❌ URL invalide.")
            continue

#         numero = None
#         if len(parties) > 1:
#             try:
#                 numero = int(parties[1])
#             except ValueError:
#                 print("⚠️  Le numéro de chapitre doit être un entier.")
#                 continue
# 
#         await GestionTelechargement().telecharger(url, numero)
#         print()
        debut = fin = None
        try:
            if len(parties) == 2:
                debut = fin = float(parties[1])
            elif len(parties) >= 3:
                debut, fin = float(parties[1]), float(parties[2])
                if debut > fin:
                    print("⚠️  Le chapitre de début doit être inférieur à la fin.")
                    continue
        except ValueError:
            print("⚠️  Les numéros de chapitre doivent être des nombres.")
            continue

        if debut is None:
            await GestionTelechargement().telecharger(url)
        else:
            await GestionTelechargement().telecharger_plusieurs(url, debut, fin)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Arrêt.")
