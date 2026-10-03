import asyncio
import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
from telechargement import GestionTelechargement
import queue

# --- Couleurs ---
BG      = "#1e1e1e"
BG2     = "#2a2a2a"
ACCENT  = "#9b59b6"
FG      = "#f0f0f0"
FG_DIM  = "#888888"
DANGER  = "#c0392b"


class StdoutVersConsole:
    """Redirige stdout vers la queue — thread-safe."""

    def __init__(self, q: queue.Queue):
        self._queue = q

    def write(self, texte: str):
        if texte:
            self._queue.put(texte)

    def flush(self):
        pass


class MangaScraperGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Manga Scraper v7")
        self.root.geometry("720x580")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.url_var    = tk.StringVar()
        self.multi_var  = tk.BooleanVar(value=False)
        self.start_var  = tk.StringVar()
        self.end_var    = tk.StringVar()
        self.is_running = False
        self._queue      = queue.Queue()
        self._stop_event = threading.Event()
        self._build()
        self._polling()
        sys.stdout = StdoutVersConsole(self._queue)

    def _polling(self):
        """Lit la queue depuis le thread principal toutes les 50ms — thread-safe."""
        try:
            while True:
                msg = self._queue.get_nowait()
                self.console.insert(tk.END, msg)
                self.console.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(50, self._polling)

    # ------------------------------------------------------------------ #
    # Construction de l'UI                                               #
    # ------------------------------------------------------------------ #

    def _lbl(self, parent, texte, dim=False, **kw):
        return tk.Label(parent, text=texte, bg=kw.pop("bg", BG),
                        fg=FG_DIM if dim else FG,
                        font=("Segoe UI", 9), **kw)

    def _entry(self, parent, var, **kw):
        return tk.Entry(parent, textvariable=var,
                        bg=BG2, fg=FG, insertbackground=FG,
                        relief=tk.FLAT, font=("Segoe UI", 10),
                        highlightthickness=1, highlightbackground="#444",
                        highlightcolor=ACCENT, **kw)

    def _btn(self, parent, texte, cmd, bg=BG2, bold=False):
        return tk.Button(parent, text=texte, command=cmd,
                         bg=bg, fg=FG, activebackground=bg, activeforeground=FG,
                         font=("Segoe UI", 10, "bold" if bold else "normal"),
                         relief=tk.FLAT, cursor="hand2", padx=12, pady=8)

    def _build(self):
        pad = dict(padx=20, pady=8)

        # --- En-tête ---
        header = tk.Frame(self.root, bg=ACCENT, pady=12)
        header.pack(fill=tk.X)
        tk.Label(header, text="📚  Manga Scraper Universel",
                 bg=ACCENT, fg=FG, font=("Segoe UI", 15, "bold")).pack()
        tk.Label(header, text="Téléchargement de mangas en PDF",
                 bg=ACCENT, fg="#ddd", font=("Segoe UI", 9)).pack()

        # --- URL ---
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill=tk.BOTH, expand=True, padx=20, pady=12)

        self._lbl(body, "URL du manga").pack(anchor=tk.W)
        self._entry(body, self.url_var).pack(fill=tk.X, ipady=6, pady=(2, 10))

        # --- Chapitres multiples ---
        tk.Checkbutton(body, text="Plusieurs chapitres",
                       variable=self.multi_var, command=self._toggle_range,
                       bg=BG, fg=FG, selectcolor=BG2, activebackground=BG,
                       font=("Segoe UI", 9)).pack(anchor=tk.W)

        self.range_frame = tk.Frame(body, bg=BG)

        row = tk.Frame(self.range_frame, bg=BG)
        row.pack(fill=tk.X, pady=(6, 0))

        for label, var in (("Chapitre début", self.start_var), ("Chapitre fin", self.end_var)):
            col = tk.Frame(row, bg=BG)
            col.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 10))
            self._lbl(col, label, dim=True).pack(anchor=tk.W)
            self._entry(col, var, width=10).pack(fill=tk.X, ipady=5, pady=(2, 0))

        # --- Console ---
        self._lbl(body, "Logs", dim=True).pack(anchor=tk.W, pady=(14, 2))
        self.console = scrolledtext.ScrolledText(
            body, bg="#111", fg="#ccc", font=("Consolas", 9),
            insertbackground=FG, relief=tk.FLAT, height=14,
        )
        self.console.pack(fill=tk.BOTH, expand=True)

        # --- Boutons ---
        btns = tk.Frame(body, bg=BG)
        btns.pack(fill=tk.X, pady=(12, 0))

        self.btn_reset  = self._btn(btns, "Réinitialiser", self._reset)
        self.btn_reset.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        self.btn_start = self._btn(btns, "Lancer", self._lancer, bg=ACCENT, bold=True)
        self.btn_start.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._log("Prêt.\n")

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _toggle_range(self):
        if self.multi_var.get():
            self.range_frame.pack(fill=tk.X, pady=(4, 0))
        else:
            self.range_frame.pack_forget()

    def _log(self, msg: str):
        self._queue.put(msg + "\n")

    def _set_running(self, running: bool):
        self.is_running = running
        state = tk.DISABLED if running else tk.NORMAL
        color = "#555" if running else ACCENT
        self.btn_start.config(state=state, bg=color)

    def _valider(self) -> bool:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Erreur", "URL manquante.")
            return False
        if not url.startswith("http"):
            messagebox.showerror("Erreur", "L'URL doit commencer par http:// ou https://")
            return False
        if self.multi_var.get():
            try:
                s, e = float(self.start_var.get()), float(self.end_var.get())
                if s < 1 or s > e:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Erreur", "Plage de chapitres invalide.")
                return False
        return True

    def _reset(self):
        if self.is_running:
            if not messagebox.askyesno("Confirmation", "Un téléchargement est en cours. Arrêter ?"):
                return
            self._stop_event.set()
        for var in (self.url_var, self.start_var, self.end_var):
            var.set("")
        self.multi_var.set(False)
        self._toggle_range()
        self.console.delete("1.0", tk.END)
        self._log("Prêt.\n")

    # ------------------------------------------------------------------ #
    # Scraping                                                             #
    # ------------------------------------------------------------------ #

    def _lancer(self):
        if not self._valider():
            return
        self._set_running(True)
        threading.Thread(target=self._run_thread, daemon=True).start()

    def _run_async(self, coro):
        """Lance une coroutine dans un event loop dédié au thread courant.
        Nécessaire sur Windows avec PyInstaller : asyncio.run() peut planter
        si appelé depuis un thread non-principal.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(coro)
        finally:
            loop.close()

    def _run_thread(self):
        url = self.url_var.get().strip()
        self._stop_event.clear()
        try:
            if self.multi_var.get():
                start, end = float(self.start_var.get()), float(self.end_var.get())
                self._log(f"\n📚 Chapitres {start:g} → {end:g}\n")
                self._run_async(
                    GestionTelechargement().telecharger_plusieurs(
                        url, start, end, self._stop_event
                    )
                )
            else:
                self._log("\n📥 Téléchargement...\n")
                self._run_async(
                    GestionTelechargement().telecharger(url, stop_event=self._stop_event)
                )
            if not self._stop_event.is_set():
                self._log("\n✅ Terminé.")
            else:
                self._log("\n⏹️  Annulé.")
        except Exception as e:
            self._log(f"\n❌ Erreur : {e}")
            messagebox.showerror("Erreur", str(e))
        finally:
            self._set_running(False)


if __name__ == "__main__":
    root = tk.Tk()
    MangaScraperGUI(root)
    root.mainloop()
