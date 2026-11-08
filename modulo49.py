"""Modulo49 : modélisation de suites de nombres (1 à N-1) et prédiction MOD N, N au choix."""

import os
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

import moteur

TITRE = "Modulo49 – Modélisation et prédiction MOD N"


class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(TITRE)
        self.geometry("1180x780")
        self.minsize(900, 600)
        self.analyse = None
        self.fichier = None
        self.cible = None          # résultat de la recherche de la valeur cible
        self.fenetre_vue = None    # nombre de valeurs (k) surligné sur le graphique
        self._construire()

    # ------------------------------------------------------------------ interface
    def _construire(self):
        haut = ttk.Frame(self, padding=8)
        haut.pack(fill="x")
        ttk.Button(haut, text="Charger un CSV…", command=self.charger).pack(side="left")
        ttk.Label(haut, text="Modulo N :").pack(side="left", padx=(12, 2))
        self.var_n = tk.StringVar(value=str(moteur.MODULO_DEFAUT))
        champ_n = ttk.Spinbox(haut, from_=moteur.MODULO_MIN, to=moteur.MODULO_MAX, width=7,
                              textvariable=self.var_n, command=self.recalculer)
        champ_n.pack(side="left")
        champ_n.bind("<Return>", lambda e: self.recalculer())
        self.lbl_intervalle = ttk.Label(haut, text="(valeurs admises : 1 à 49, le 0 devient 1)")
        self.lbl_intervalle.pack(side="left", padx=(4, 0))
        ttk.Button(haut, text="Recalculer", command=self.recalculer).pack(side="left", padx=8)
        ttk.Button(haut, text="Plusieurs colonnes…",
                   command=lambda: self.ouvrir_multi()).pack(side="left")
        self.lbl_fichier = ttk.Label(haut, text="Aucun fichier (nombres en colonne A)")
        self.lbl_fichier.pack(side="left", padx=10)

        corps = ttk.PanedWindow(self, orient="horizontal")
        corps.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        gauche = ttk.Frame(corps, padding=4)
        corps.add(gauche, weight=1)

        cadre_pred = ttk.LabelFrame(gauche, text="Prochain nombre prédit", padding=8)
        cadre_pred.pack(fill="x")
        self.lbl_pred = tk.Label(cadre_pred, text="–", font=("Segoe UI", 44, "bold"), fg="#1f5fbf")
        self.lbl_pred.pack()
        self.lbl_modele = ttk.Label(cadre_pred, text="", wraplength=320, justify="center")
        self.lbl_modele.pack()

        self.onglets = ttk.Notebook(gauche)
        self.onglets.pack(fill="both", expand=True, pady=8)
        cadre_mod = ttk.Frame(self.onglets, padding=4)
        self.onglets.add(cadre_mod, text="Modèles comparés")
        colonnes = ("modele", "brut", "pred", "erreur")
        self.table = ttk.Treeview(cadre_mod, columns=colonnes, show="headings", height=7)
        for col, titre, larg in zip(colonnes,
                                    ("Modèle", "Brut", "MOD N", "Écart"),
                                    (200, 65, 55, 55)):
            self.table.heading(col, text=titre)
            self.table.column(col, width=larg, anchor="w" if col == "modele" else "center")
        self.table.pack(fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", lambda e: self.dessiner())

        cadre_cible = ttk.Frame(self.onglets, padding=4)
        self.onglets.add(cadre_cible, text="Valeur cible")
        ligne = ttk.Frame(cadre_cible)
        ligne.pack(fill="x")
        ttk.Label(ligne, text="Prédiction future (cible) :").pack(side="left")
        self.var_cible = tk.StringVar()
        champ = ttk.Entry(ligne, textvariable=self.var_cible, width=7)
        champ.pack(side="left", padx=4)
        champ.bind("<Return>", lambda e: self.verifier_cible())
        ttk.Button(ligne, text="Vérifier", command=self.verifier_cible).pack(side="left")
        ttk.Button(ligne, text="Récapitulatif…", command=self.ouvrir_recap).pack(side="left", padx=4)
        self.lbl_cible = ttk.Label(cadre_cible, text="Indiquez une valeur cible puis « Vérifier ».",
                                   wraplength=390, justify="left")
        self.lbl_cible.pack(fill="x", pady=4)
        colonnes = ("modele", "confirme", "valeurs", "proche")
        self.table_cible = ttk.Treeview(cadre_cible, columns=colonnes, show="headings", height=7)
        for col, titre, larg in zip(colonnes,
                                    ("Modèle", "Confirme", "Nb valeurs", "Plus proche"),
                                    (162, 62, 76, 80)):
            self.table_cible.heading(col, text=titre)
            self.table_cible.column(col, width=larg, anchor="w" if col == "modele" else "center")
        self.table_cible.tag_configure("oui", foreground="#1a7f37")
        self.table_cible.pack(fill="both", expand=True)
        self.table_cible.bind("<<TreeviewSelect>>", lambda e: self._choisir_ligne_cible())

        cadre_saisie = ttk.LabelFrame(gauche, text="Données (modifiables, une valeur par ligne)", padding=4)
        cadre_saisie.pack(fill="both", expand=True)
        self.txt = tk.Text(cadre_saisie, width=12, height=6)
        self.txt.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(cadre_saisie, command=self.txt.yview)
        sb.pack(side="right", fill="y")
        self.txt.configure(yscrollcommand=sb.set)

        ttk.Label(gauche, wraplength=330, foreground="#777", justify="left",
                  text="Écart : erreur moyenne du modèle testé pas à pas sur l'historique. "
                       "Sur des tirages aléatoires, aucun modèle ne fait mieux que le hasard."
                  ).pack(fill="x", pady=(6, 0))

        droite = ttk.Frame(corps)
        corps.add(droite, weight=3)
        self.fig = Figure(figsize=(7, 6), dpi=100)
        self.ax_brut = self.fig.add_subplot(211)
        self.ax_deplie = self.fig.add_subplot(212)
        self.canvas = FigureCanvasTkAgg(self.fig, master=droite)
        NavigationToolbar2Tk(self.canvas, droite).update()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.dessiner()

    # ------------------------------------------------------------------ actions
    def charger(self):
        chemin = filedialog.askopenfilename(
            title="Choisir le fichier CSV",
            filetypes=[("Fichiers CSV", "*.csv"), ("Fichiers texte", "*.txt"), ("Tous", "*.*")])
        if not chemin:
            return
        try:
            valeurs, avert = moteur.lire_csv(chemin)
        except OSError as e:
            messagebox.showerror(TITRE, f"Impossible de lire le fichier :\n{e}")
            return
        self.fichier = chemin
        self.lbl_fichier.config(text=f"{os.path.basename(chemin)} – {len(valeurs)} nombres lus")
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", "\n".join(map(str, valeurs)))
        if avert:
            extrait = "\n".join(avert[:15]) + ("\n…" if len(avert) > 15 else "")
            messagebox.showwarning(TITRE, f"{len(avert)} ligne(s) ignorée(s) :\n\n{extrait}")
        self.recalculer()
        try:
            colonnes, _ = moteur.lire_csv_colonnes(chemin)
        except OSError:
            return
        if len(colonnes) > 1 and messagebox.askyesno(
                TITRE, f"Le fichier contient {len(colonnes)} colonnes de nombres.\n\n"
                       f"Lancer le calcul sur toutes les colonnes en même temps ?"):
            self.ouvrir_multi(chemin)

    def ouvrir_multi(self, chemin=None):
        n = self._modulo()
        if n is not None:
            FenetreMulti(self, n, chemin)

    def charger_valeurs(self, nom, valeurs, cible=None):
        """Affiche une colonne dans la vue principale (depuis la fenêtre multi-colonnes)."""
        self.lbl_fichier.config(text=f"Colonne {nom} – {len(valeurs)} nombres")
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", "\n".join(map(str, valeurs)))
        self.var_cible.set("" if cible is None else str(cible))
        self.cible = None
        self.recalculer()
        self.lift()

    def _modulo(self):
        try:
            n = moteur.verifier_modulo(self.var_n.get())
        except ValueError:
            messagebox.showerror(TITRE, f"Le modulo N doit être un entier entre "
                                        f"{moteur.MODULO_MIN} et {moteur.MODULO_MAX}.")
            return None
        self.lbl_intervalle.config(text=f"(valeurs admises : 1 à {n - 1}, le 0 devient 1)")
        self.title(f"Modulo49 – Modélisation et prédiction MOD {n}")
        return n

    def recalculer(self):
        n = self._modulo()
        if n is None:
            return
        if not self.txt.get("1.0", "end").strip():
            return
        valeurs = []
        for i, ligne in enumerate(self.txt.get("1.0", "end").split(), start=1):
            try:
                v = int(ligne)
            except ValueError:
                messagebox.showerror(TITRE, f"Valeur {i} invalide : « {ligne} »")
                return
            if v < 1:
                messagebox.showerror(TITRE, f"Valeur {i} invalide : {v} (0 et négatifs non admis)")
                return
            valeurs.append(v)
        try:
            self.analyse = moteur.analyser(valeurs, n)
        except ValueError as e:
            messagebox.showerror(TITRE, str(e))
            return
        self.table.delete(*self.table.get_children())
        meilleur = self.analyse["meilleur"]
        for i, m in enumerate(self.analyse["modeles"]):
            err = "–" if m["nb_tests"] == 0 else f"{m['erreur']:.2f}"
            self.table.insert("", "end", iid=str(i), values=(
                ("★ " if m is meilleur else "") + m["nom"],
                f"{m['prediction_brute']:.2f}", m["prediction"], err))
            if m is meilleur:
                self.table.selection_set(str(i))
        self.lbl_pred.config(text=str(meilleur["prediction"]))
        self.lbl_modele.config(
            text=f"Modèle retenu : {meilleur['nom']}\n"
                 f"valeur brute {meilleur['prediction_brute']:.2f} → MOD {n} → {meilleur['prediction']}")
        if self.var_cible.get().strip():
            self.verifier_cible(silencieux=True)
        else:
            self.dessiner()

    def verifier_cible(self, silencieux=False):
        """Indique quels modèles retrouvent la valeur cible, et avec combien de valeurs."""
        if not self.analyse:
            if not silencieux:
                messagebox.showinfo(TITRE, "Chargez d'abord une suite de nombres.")
            return
        n = self.analyse["n"]
        try:
            cible = int(self.var_cible.get())
            resultats = moteur.chercher_cible(self.analyse["valeurs"], cible, n)
        except ValueError as e:
            self.cible = None
            if not silencieux:
                messagebox.showerror(TITRE, str(e) if "cible" in str(e) else
                                     f"La valeur cible doit être un entier entre 1 et {n - 1}.")
            self.dessiner()
            return
        self.cible = {"valeur": cible, "resultats": resultats}
        self.fenetre_vue = None
        self.table_cible.delete(*self.table_cible.get_children())
        total = len(self.analyse["valeurs"])
        for i, r in enumerate(resultats):
            if r["confirme"]:
                valeurs = moteur.resumer_fenetres(r["fenetres"])
                proche = "–"
            else:
                ecart, k, pred = r["plus_proche"] if r["plus_proche"] else (None, None, None)
                valeurs = "aucune"
                proche = f"{pred} (k={k})" if pred is not None else "–"
            self.table_cible.insert("", "end", iid=str(i), tags=("oui",) if r["confirme"] else (),
                                    values=(r["nom"], "oui ✔" if r["confirme"] else "non",
                                            valeurs, proche))
        nb = sum(r["confirme"] for r in resultats)
        self.lbl_cible.config(text=(
            f"{nb} modèle(s) sur {len(resultats)} confirment la cible {cible}. "
            f"« Nb de valeurs » = combien des dernières valeurs de la suite (la dernière, "
            f"{self.analyse['valeurs'][-1]}, toujours incluse ; {total} au total) il faut "
            f"prendre pour que le modèle prédise {cible}. Cliquez une ligne pour voir la "
            f"fenêtre sur le graphique."))
        if not silencieux:
            self.onglets.select(1)
        self.dessiner()

    def ouvrir_recap(self):
        if not self.cible:
            self.verifier_cible()
        if self.cible:
            FenetreRecap(self, self.analyse["valeurs"], self.analyse["n"],
                         self.cible["valeur"], self.cible["resultats"])

    def _choisir_ligne_cible(self):
        sel = self.table_cible.selection()
        if not sel or not self.cible:
            return
        r = self.cible["resultats"][int(sel[0])]
        if r["confirme"]:
            self.fenetre_vue = r["fenetres"][0]
        elif r["plus_proche"]:
            self.fenetre_vue = r["plus_proche"][1]
        else:
            self.fenetre_vue = None
        self.dessiner()

    def _modele_selectionne(self):
        if not self.analyse:
            return None
        sel = self.table.selection()
        if sel:
            return self.analyse["modeles"][int(sel[0])]
        return self.analyse["meilleur"]

    # ------------------------------------------------------------------ graphique
    def dessiner(self):
        for ax in (self.ax_brut, self.ax_deplie):
            ax.clear()
            ax.grid(alpha=0.3)
        n = self.analyse["n"] if self.analyse else moteur.MODULO_DEFAUT
        self.ax_brut.set_title(f"Suite observée (1 à {n - 1}) et prédiction MOD {n}")
        self.ax_brut.set_ylim(0, n)
        self.ax_deplie.set_title("Fonction d'évolution (suite dépliée) et modèle ajusté")
        self.ax_deplie.set_xlabel("Rang n")
        modele = self._modele_selectionne()
        if modele:
            vals = self.analyse["valeurs"]
            n = len(vals)
            x = range(n)
            self.ax_brut.plot(x, vals, "o-", color="#1f5fbf", ms=4, lw=1, label="Observé")
            self.ax_brut.plot([n], [modele["prediction"]], "*", color="#d6402b", ms=16,
                              label=f"Prédit : {modele['prediction']}")
            if self.cible:
                self.ax_brut.plot([n], [self.cible["valeur"]], "D", color="#1a7f37", ms=10,
                                  mfc="none", mew=2, label=f"Cible : {self.cible['valeur']}")
            if self.fenetre_vue:
                self.ax_brut.axvspan(n - self.fenetre_vue - 0.3, n - 0.7, color="#1a7f37",
                                     alpha=0.12, label=f"{self.fenetre_vue} dernières valeurs")
            self.ax_brut.legend(loc="upper left", fontsize=8)

            y = self.analyse["deplie"]
            self.ax_deplie.plot(x, y, "o-", color="#1f5fbf", ms=4, lw=1, label="Dépliée")
            self.ax_deplie.plot(x, modele["ajustement"], "--", color="#e08a00", lw=2,
                                label=modele["nom"])
            self.ax_deplie.plot([n], [modele["prediction_brute"]], "*", color="#d6402b", ms=16,
                                label=f"Prévision brute : {modele['prediction_brute']:.2f}")
            self.ax_deplie.margins(y=0.12)
            self.ax_deplie.legend(loc="best")
        self.fig.tight_layout()
        self.canvas.draw_idle()


class FenetreRecap(tk.Toplevel):
    """Récapitulatif des points communs entre modèles pour la valeur cible, exportable."""

    VERT, GRIS, ORANGE = "#1a7f37", "#c9cdd2", "#e08a00"

    def __init__(self, parent, valeurs, n, cible, resultats):
        super().__init__(parent)
        self.valeurs, self.n, self.cible, self.resultats = valeurs, n, cible, resultats
        self.total = len(valeurs)
        self.recap = moteur.recapituler(resultats, self.total)
        self.title(f"Récapitulatif – cible {cible} (MOD {n})")
        self.geometry("1080x760")
        self._construire()

    def _construire(self):
        rc = self.recap
        haut = ttk.Frame(self, padding=8)
        haut.pack(fill="x")
        accord = (f"{rc['accord_max']} modèle(s) d'accord pour k = "
                  f"{moteur.resumer_fenetres(rc['k_accord_max'])}" if rc["accord_max"]
                  else "aucun modèle ne confirme la cible")
        communs = moteur.resumer_fenetres(rc["k_communs_a_tous"]) or "aucun"
        ttk.Label(haut, justify="left", text=(
            f"Cible {self.cible} · {rc['nb_confirmants']} modèle(s) sur {len(self.resultats)} la "
            f"confirment · {self.total} valeurs, dernière = {self.valeurs[-1]} (toujours incluse)\n"
            f"Point commun : {accord}. k communs à tous les modèles qui confirment : {communs}."
        )).pack(anchor="w")
        boutons = ttk.Frame(haut)
        boutons.pack(anchor="w", pady=(6, 0))
        ttk.Button(boutons, text="Exporter le tableau (CSV/Excel)…",
                   command=self.exporter_tableau).pack(side="left", padx=3)
        ttk.Button(boutons, text="Exporter le graphique (PNG/PDF)…",
                   command=self.exporter_graphique).pack(side="left", padx=3)

        colonnes = ("modele", "confirme", "nb", "kmin", "kmax", "etendue", "plages", "proche")
        table = ttk.Treeview(self, columns=colonnes, show="headings", height=len(self.resultats))
        titres = ("Modèle", "Confirme", "Nb de k", "k min", "k max", "Étendue", "Plages de k",
                  "Plus proche")
        for col, titre, larg in zip(colonnes, titres, (170, 70, 60, 55, 55, 65, 150, 110)):
            table.heading(col, text=titre)
            table.column(col, width=larg, anchor="w" if col in ("modele", "plages") else "center")
        table.tag_configure("oui", foreground=self.VERT)
        for r in self.resultats:
            f = r["fenetres"]
            p = r["plus_proche"]
            table.insert("", "end", tags=("oui",) if f else (), values=(
                r["nom"], "oui ✔" if f else "non", len(f),
                f[0] if f else "–", f[-1] if f else "–", f[-1] - f[0] + 1 if f else "–",
                moteur.resumer_fenetres(f) or "aucune",
                "–" if f or not p else f"{p[2]} (k={p[1]})"))
        table.pack(fill="x", padx=8)

        self.fig = Figure(figsize=(10, 5.6), dpi=100)
        self._dessiner()
        canvas = FigureCanvasTkAgg(self.fig, master=self)
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)
        canvas.draw()

    def _dessiner(self):
        rc = self.recap
        ks = [x["k"] for x in rc["par_k"]]
        nbs = [x["nb"] for x in rc["par_k"]]
        ax1, ax2 = self.fig.subplots(2, 1, sharex=True,
                                     gridspec_kw={"height_ratios": [1, 1.25]})
        couleurs = [self.VERT if nb == rc["accord_max"] and nb > 0 else "#7fb08b" for nb in nbs]
        barres = ax1.bar(ks, nbs, color=couleurs, width=0.75)
        ax1.bar_label(barres, labels=[str(v) if v else "" for v in nbs], fontsize=8)
        ax1.set_ylabel("Modèles qui\nconfirment")
        ax1.set_ylim(0, len(self.resultats) + 0.8)
        ax1.set_title(f"Accord des modèles sur la cible {self.cible} selon le nombre de "
                      f"dernières valeurs utilisées (k)")
        ax1.grid(axis="y", alpha=0.3)
        ax1.spines[["top", "right"]].set_visible(False)

        noms = [r["nom"] for r in self.resultats]
        for i, r in enumerate(self.resultats):
            testes = sorted(r["predictions"])
            for k in testes:
                ok = k in r["fenetres"]
                ax2.barh(i, 0.9, left=k - 0.45, height=0.6,
                         color=self.VERT if ok else self.GRIS)
            if r["fenetres"]:
                f = r["fenetres"]
                ax2.text(max(testes) + 0.55, i, f"{f[0]}–{f[-1]}", va="center", fontsize=8,
                         color=self.VERT)
        for k in rc["k_communs_a_tous"]:
            ax2.axvspan(k - 0.5, k + 0.5, color=self.ORANGE, alpha=0.12, lw=0)
        ax2.set_yticks(range(len(noms)), noms, fontsize=8)
        ax2.invert_yaxis()
        ax2.set_xlabel("k = nombre de dernières valeurs de la suite (la dernière toujours incluse)")
        ax2.set_title("Étendue de la plage de k qui donne la cible (vert = confirme ; "
                      "zone orange = commune à tous)", fontsize=10)
        ax2.set_xticks(ks)
        ax2.set_xlim(min(ks) - 0.6, max(ks) + 1.6)
        ax2.spines[["top", "right"]].set_visible(False)
        self.fig.tight_layout()

    def exporter_tableau(self):
        chemin = filedialog.asksaveasfilename(
            parent=self, title="Exporter le récapitulatif", defaultextension=".csv",
            initialfile=f"recap_cible_{self.cible}_mod{self.n}.csv",
            filetypes=[("CSV (Excel)", "*.csv")])
        if chemin:
            try:
                moteur.exporter_csv(chemin, self.valeurs, self.n, self.cible, self.resultats)
            except OSError as e:
                messagebox.showerror(TITRE, f"Export impossible :\n{e}", parent=self)
                return
            messagebox.showinfo(TITRE, f"Tableau exporté :\n{chemin}", parent=self)

    def exporter_graphique(self):
        chemin = filedialog.asksaveasfilename(
            parent=self, title="Exporter le graphique", defaultextension=".png",
            initialfile=f"recap_cible_{self.cible}_mod{self.n}.png",
            filetypes=[("Image PNG", "*.png"), ("Document PDF", "*.pdf")])
        if chemin:
            try:
                self.fig.savefig(chemin, dpi=150, bbox_inches="tight")
            except OSError as e:
                messagebox.showerror(TITRE, f"Export impossible :\n{e}", parent=self)
                return
            messagebox.showinfo(TITRE, f"Graphique exporté :\n{chemin}", parent=self)


class FenetreMulti(tk.Toplevel):
    """Calcul sur toutes les colonnes d'un CSV, avec des modulos N saisis librement
    colonne par colonne, et export CSV des résultats."""

    ABREGES = ["Lin.", "Quad.", "Cub.", "Saut moy.", "Dern. saut", "Réc. 1", "Réc. 2"]
    LIMITE_AFFICHAGE = 5000      # lignes du détail affichées (l'export contient tout)
    LARGEURS = (230, 140, 330, 480)  # colonnes de la grille de réglage
    AIDE = "ex. 50  ·  37, 43, 50  ·  40-60  ·  30-35, 50, 61"

    def __init__(self, parent, n, chemin=None):
        super().__init__(parent)
        self.parent, self.n_defaut = parent, n
        self.colonnes, self.lignes_reglage = [], []
        self.synthese, self.details, self.complet, self.cible = [], [], True, None
        self.fichier = ""
        self._fil, self._resultat, self._suivi = None, None, None
        self._arret = threading.Event()
        self._progression = (0, 0)
        self.title("Modulo49 – Calcul sur plusieurs colonnes")
        self.geometry("1240x740")
        self.minsize(900, 560)
        self.protocol("WM_DELETE_WINDOW", self._fermer)
        self._construire()
        if chemin:
            self.charger(chemin)

    # ------------------------------------------------------------------ interface
    def _construire(self):
        haut = ttk.Frame(self, padding=8)
        haut.pack(fill="x")
        self.btn_charger = ttk.Button(haut, text="Charger un CSV…", command=self.charger)
        self.btn_charger.pack(side="left")
        ttk.Label(haut, text="Valeur cible (facultatif) :").pack(side="left", padx=(14, 2))
        self.var_cible = tk.StringVar(value=self.parent.var_cible.get())
        ttk.Entry(haut, textvariable=self.var_cible, width=7).pack(side="left")
        self.btn_calculer = ttk.Button(haut, text="Calculer toutes les colonnes",
                                       command=self.calculer)
        self.btn_calculer.pack(side="left", padx=(10, 4))
        self.btn_arreter = ttk.Button(haut, text="Arrêter", command=self._arret.set,
                                      state="disabled")
        self.btn_arreter.pack(side="left")
        self.btn_exporter = ttk.Button(haut, text="Exporter en CSV…", command=self.exporter)
        self.btn_exporter.pack(side="left", padx=10)
        self.lbl_info = ttk.Label(self, padding=(8, 0), justify="left",
                                  text="Chargez un CSV : chaque colonne (A, B, C…) est une suite "
                                       "calculée séparément, avec son propre modulo.")
        self.lbl_info.pack(fill="x")

        # --- réglage du modulo colonne par colonne
        cadre = ttk.LabelFrame(self, text="Modulo par colonne : saisissez librement les N à "
                                          "calculer (valeurs séparées par des virgules, "
                                          "a-b = tous les N de a à b)", padding=6)
        cadre.pack(fill="x", padx=8, pady=6)
        entete = ttk.Frame(cadre)
        entete.pack(fill="x")
        self._grille(entete)
        for j, titre in enumerate(("Colonne", "Valeurs", "N à calculer", "Calculs prévus")):
            ttk.Label(entete, text=titre, font=("Segoe UI", 9, "bold")).grid(
                row=0, column=j, sticky="w", padx=2)
        # ligne « toutes les colonnes » pour appliquer la même saisie partout
        self.tout = tk.StringVar(value=str(self.n_defaut))
        ttk.Label(entete, text="Toutes les colonnes :").grid(row=1, column=0, sticky="w", padx=2)
        ttk.Button(entete, text="Appliquer à toutes ↓", command=self._appliquer_a_toutes).grid(
            row=1, column=1, sticky="w", padx=2)
        ttk.Entry(entete, textvariable=self.tout, width=44).grid(row=1, column=2, sticky="w",
                                                                  padx=2)
        ttk.Label(entete, text=self.AIDE, foreground="#777").grid(row=1, column=3, sticky="w",
                                                                  padx=2)
        ttk.Separator(cadre).pack(fill="x", pady=4)

        zone = ttk.Frame(cadre)
        zone.pack(fill="x")
        self.canevas = tk.Canvas(zone, height=130, highlightthickness=0)
        sb = ttk.Scrollbar(zone, orient="vertical", command=self.canevas.yview)
        self.canevas.configure(yscrollcommand=sb.set)
        self.canevas.pack(side="left", fill="x", expand=True)
        sb.pack(side="right", fill="y")
        self.grille = ttk.Frame(self.canevas)
        self.canevas.create_window((0, 0), window=self.grille, anchor="nw")
        self.grille.bind("<Configure>", lambda e: self.canevas.configure(
            scrollregion=self.canevas.bbox("all")))
        self._grille(self.grille)

        # --- progression
        prog = ttk.Frame(self, padding=(8, 0))
        prog.pack(fill="x")
        self.barre = ttk.Progressbar(prog, mode="determinate", length=300)
        self.barre.pack(side="left")
        self.lbl_prog = ttk.Label(prog, text="")
        self.lbl_prog.pack(side="left", padx=8)

        # --- résultats
        self.onglets = ttk.Notebook(self)
        self.onglets.pack(fill="both", expand=True, padx=8, pady=6)
        self.table_synthese = self._table(self.onglets, "Synthèse par colonne")
        self.table_detail = self._table(self.onglets, "Détail par N")
        bas = ttk.Frame(self, padding=(8, 0, 8, 8))
        bas.pack(fill="x")
        ttk.Button(bas, text="Ouvrir la ligne sélectionnée dans la vue principale",
                   command=self.ouvrir_ligne).pack(side="left")
        ttk.Label(bas, foreground="#777", justify="left", text=(
            "  Double-clic = ouvrir. ★ = meilleur N de la colonne : plus forte réussite "
            "(prédictions exactes en validation pas à pas),\n  puis plus petit écart relatif "
            "(écart moyen / (N/2) : 0 % = parfait, environ 50 % = hasard).")).pack(side="left")

    def _grille(self, cadre):
        for j, largeur in enumerate(self.LARGEURS):
            cadre.columnconfigure(j, minsize=largeur)

    def _table(self, onglets, titre):
        cadre = ttk.Frame(onglets, padding=4)
        onglets.add(cadre, text=titre)
        table = ttk.Treeview(cadre, show="headings")
        sx = ttk.Scrollbar(cadre, orient="horizontal", command=table.xview)
        sy = ttk.Scrollbar(cadre, orient="vertical", command=table.yview)
        table.configure(xscrollcommand=sx.set, yscrollcommand=sy.set)
        table.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        cadre.rowconfigure(0, weight=1)
        cadre.columnconfigure(0, weight=1)
        table.tag_configure("oui", foreground="#1a7f37")
        table.tag_configure("meilleur", background="#e6f2ea")
        table.tag_configure("erreur", foreground="#b42318")
        table.bind("<Double-1>", lambda e: self.ouvrir_ligne())
        return table

    def _widgets_reglage(self, cadre, ligne, var, maxi):
        """Champ de saisie libre des N + calculs prévus, mis à jour à chaque frappe."""
        ttk.Entry(cadre, textvariable=var, width=44).grid(row=ligne, column=2, sticky="w",
                                                          padx=2, pady=1)
        info = tk.Label(cadre, anchor="w")
        info.grid(row=ligne, column=3, sticky="w", padx=2)

        def maj(*_):
            texte, rouge = self._prevision(var.get(), maxi)
            info.configure(text=texte, fg="#b42318" if rouge else "#1f2328")
            self._maj_total()
        var.trace_add("write", maj)
        maj()

    @staticmethod
    def _prevision(saisie, maxi):
        """Texte « calculs prévus » d'une ligne, et s'il signale un problème."""
        try:
            modulos = moteur.lire_modulos(saisie)
        except ValueError as e:
            return str(e), True
        calculables = [n for n in modulos if n > maxi]
        if not calculables:
            return f"aucun N calculable : il faut N ≥ {maxi + 1}", True
        liste = moteur.resumer_fenetres(calculables)
        if len(liste) > 60:
            liste = liste[:57].rsplit(",", 1)[0] + ", …"
        texte = f"{len(calculables)} calcul(s) : N = {liste}"
        if len(calculables) < len(modulos):
            texte += f"  ({len(modulos) - len(calculables)} N ≤ {maxi} ignoré(s))"
        return texte, False

    def _maj_total(self):
        if self._fil is not None or not self.lignes_reglage:
            return
        total = 0
        for (_, valeurs), var in zip(self.colonnes, self.lignes_reglage):
            try:
                total += sum(1 for n in moteur.lire_modulos(var.get()) if n > max(valeurs))
            except ValueError:
                pass
        self.lbl_prog.configure(text=f"{total} calcul(s) à faire au total.")

    def _appliquer_a_toutes(self):
        for var in self.lignes_reglage:
            var.set(self.tout.get())

    def _remplir_reglages(self):
        for w in self.grille.winfo_children():
            w.destroy()
        self.lignes_reglage = []
        for i, (nom, valeurs) in enumerate(self.colonnes):
            maxi = max(valeurs)
            n = self.n_defaut if self.n_defaut > maxi else maxi + 1
            var = tk.StringVar(value=str(n))
            ttk.Label(self.grille, text=nom).grid(row=i, column=0, sticky="w", padx=2)
            ttk.Label(self.grille, text=f"{len(valeurs)} val., max {maxi}").grid(
                row=i, column=1, sticky="w", padx=2)
            self.lignes_reglage.append(var)
            self._widgets_reglage(self.grille, i, var, maxi)
        self._maj_total()

    # ------------------------------------------------------------------ actions
    def charger(self, chemin=None):
        if self._fil is not None:
            return
        if not chemin:
            chemin = filedialog.askopenfilename(
                parent=self, title="Choisir le fichier CSV",
                filetypes=[("Fichiers CSV", "*.csv"), ("Fichiers texte", "*.txt"), ("Tous", "*.*")])
        if not chemin:
            return
        try:
            self.colonnes, avert = moteur.lire_csv_colonnes(chemin)
        except OSError as e:
            messagebox.showerror(TITRE, f"Impossible de lire le fichier :\n{e}", parent=self)
            return
        self.fichier = os.path.basename(chemin)
        self.synthese, self.details = [], []
        self._remplir_tables()
        self._remplir_reglages()
        self.lbl_info.configure(text=f"{self.fichier} : {len(self.colonnes)} colonne(s). Saisissez "
                                     f"les N de chaque colonne, puis « Calculer toutes les colonnes ».")
        if avert:
            extrait = "\n".join(avert[:15]) + ("\n…" if len(avert) > 15 else "")
            messagebox.showwarning(TITRE, f"{len(avert)} cellule(s) ignorée(s) :\n\n{extrait}",
                                   parent=self)

    def calculer(self):
        if self._fil is not None:
            return
        if not self.colonnes:
            messagebox.showinfo(TITRE, "Chargez d'abord un fichier CSV.", parent=self)
            return
        texte = self.var_cible.get().strip()
        cible = None
        if texte:
            try:
                cible = int(texte)
                if cible < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror(TITRE, "La valeur cible doit être un entier positif "
                                            "(elle doit aussi être inférieure à N).", parent=self)
                return
        reglages = []
        for (nom, _), var in zip(self.colonnes, self.lignes_reglage):
            try:
                moteur.lire_modulos(var.get())
            except ValueError as e:
                messagebox.showerror(TITRE, f"Colonne {nom} : saisie des N invalide.\n{e}",
                                     parent=self)
                return
            reglages.append(var.get())
        self.cible = cible
        self._arret.clear()
        self._progression = (0, 1)
        self._resultat = None
        self._debut = time.perf_counter()
        for b in (self.btn_calculer, self.btn_exporter, self.btn_charger):
            b.configure(state="disabled")
        self.btn_arreter.configure(state="normal")
        colonnes = list(self.colonnes)

        def rappel(fait, total):
            self._progression = (fait, total)
            return not self._arret.is_set()

        def travail():
            try:
                self._resultat = moteur.analyser_colonnes(colonnes, reglages, cible, rappel)
            except Exception as e:  # remonté à l'interface
                self._resultat = e

        self._fil = threading.Thread(target=travail, daemon=True)
        self._fil.start()
        self._suivre()

    def _suivre(self):
        fait, total = self._progression
        self.barre.configure(maximum=max(total, 1), value=fait)
        self.lbl_prog.configure(text=f"Calcul en cours : {fait} / {total} …")
        if self._fil.is_alive():
            self._suivi = self.after(100, self._suivre)
            return
        self._fil, self._suivi = None, None
        fait, total = self._progression
        self.barre.configure(maximum=max(total, 1), value=fait)
        for b in (self.btn_calculer, self.btn_exporter, self.btn_charger):
            b.configure(state="normal")
        self.btn_arreter.configure(state="disabled")
        if isinstance(self._resultat, Exception):
            messagebox.showerror(TITRE, f"Le calcul a échoué :\n{self._resultat}", parent=self)
            return
        self.synthese, self.details, self.complet = self._resultat
        duree = time.perf_counter() - self._debut
        nb = len(self.details)
        self.lbl_prog.configure(text=(
            f"Terminé : {nb} calcul(s) en {duree:.1f} s." if self.complet else
            f"Arrêté : résultats partiels ({nb} calcul(s) faits)."))
        self._remplir_tables()

    def _colonnes_table(self, table, colonnes):
        table.configure(columns=[c for c, _, _ in colonnes])
        for c, titre, largeur in colonnes:
            table.heading(c, text=titre)
            table.column(c, width=largeur, minwidth=40, stretch=False,
                         anchor="w" if c in ("colonne", "modele", "reglage", "remarque", "confirme_n")
                         else "center")

    def _remplir_tables(self):
        pc = lambda x: "–" if x is None else f"{x:.0f} %"
        noms = [nom for nom, _, _ in moteur.MODELES]
        c = self.cible
        # synthèse
        cols = [("colonne", "Colonne", 200), ("reglage", "N demandés", 160),
                ("testes", "N calculés", 105), ("ignores", "N ignorés", 85),
                ("meilleur", "Meilleur N", 80), ("pred", "Prédiction", 75),
                ("modele", "Modèle retenu", 172), ("reussite", "Réussite", 68),
                ("ecart", "Écart rel.", 70), ("freq", "Plus fréquente", 115)]
        if c is not None:
            cols += [("confirme_n", f"N où {c} est confirmée", 175),
                     ("accord", "Meilleur accord", 150)]
        cols += [("remarque", "Remarque", 330)]
        t = self.table_synthese
        self._colonnes_table(t, cols)
        t.delete(*t.get_children())
        for i, s in enumerate(self.synthese):
            debut = [s["colonne"], s["reglage"], moteur.resumer_fenetres(s["testes"]) or "–",
                     moteur.resumer_fenetres(s["ignores"]) or "–"]
            if s["erreur"]:
                t.insert("", "end", iid=str(i), tags=("erreur",),
                         values=debut + ["–"] * (len(cols) - len(debut) - 1) + [s["erreur"]])
                continue
            m = s["meilleure"]
            vals = debut + [m["n"], m["prediction"], m["modele"], pc(m["reussite"]),
                            pc(m["ecart_relatif"]),
                            f"{s['frequente']} ({s['nb_frequente']}/{len(s['testes'])} N)"]
            tags = ()
            if c is not None:
                vals += [moteur.resumer_fenetres(s["n_confirment"]) or "aucun",
                         f"{s['accord_max']}/{len(noms)} pour N = "
                         f"{moteur.resumer_fenetres(s['n_accord_max'])}" if s["accord_max"] else "–"]
                if s["n_confirment"]:
                    tags = ("oui",)
            t.insert("", "end", iid=str(i), tags=tags, values=vals + [""])
        # détail
        cols = [("colonne", "Colonne", 200), ("n", "N", 60), ("pred", "Prédiction", 75),
                ("modele", "Modèle retenu", 172), ("ecart", "Écart", 55),
                ("ecartr", "Écart rel.", 70), ("reussite", "Réussite", 68),
                ("majo", "Majoritaire", 85)]
        if c is not None:
            cols += [("confirment", f"Confirment {c}", 112), ("kaccord", "k accord max", 100)]
        cols += [(f"m{i}", abrege, 70) for i, abrege in enumerate(self.ABREGES[:len(noms)])]
        cols += [("remarque", "Remarque", 330)]
        t = self.table_detail
        self._colonnes_table(t, cols)
        t.delete(*t.get_children())
        for i, l in enumerate(self.details[:self.LIMITE_AFFICHAGE]):
            if l["erreur"]:
                t.insert("", "end", iid=str(i), tags=("erreur",),
                         values=[l["colonne"], l["n"]] + ["–"] * (len(cols) - 3) + [l["erreur"]])
                continue
            vals = [l["colonne"], ("★ " if l.get("est_meilleure") else "") + str(l["n"]),
                    l["prediction"], l["modele"],
                    "–" if l["ecart"] is None else f"{l['ecart']:.2f}",
                    pc(l["ecart_relatif"]), pc(l["reussite"]),
                    f"{l['majoritaire']} ({l['nb_majoritaire']}/{len(noms)})"]
            tags = ("meilleur",) if l.get("est_meilleure") else ()
            if c is not None:
                if l["nb_confirmants"] is None:
                    vals += ["hors 1 à N-1", "–"]
                else:
                    vals += [f"{l['nb_confirmants']}/{len(noms)}",
                             moteur.resumer_fenetres(l["k_accord_max"]) or "–"]
                    if l["nb_confirmants"]:
                        tags += ("oui",)
            vals += [l["predictions"].get(nom, "–") for nom in noms]
            t.insert("", "end", iid=str(i), tags=tags, values=vals + [""])
        if len(self.details) > self.LIMITE_AFFICHAGE:
            self.lbl_prog.configure(text=self.lbl_prog.cget("text") + (
                f" Détail : {self.LIMITE_AFFICHAGE} premières lignes affichées sur "
                f"{len(self.details)} ; l'export CSV contient tout."))
        if self.synthese:
            nb_ok = sum(1 for s in self.synthese if not s["erreur"])
            info = f"{self.fichier} : {nb_ok}/{len(self.synthese)} colonne(s) calculée(s)."
            if c is not None:
                nb = sum(1 for s in self.synthese if not s["erreur"] and s["n_confirment"])
                info += f" Cible {c} confirmée dans {nb} colonne(s) (en vert)."
            self.lbl_info.configure(text=info)

    def ouvrir_ligne(self):
        detail = self.onglets.index(self.onglets.select()) == 1
        table = self.table_detail if detail else self.table_synthese
        sel = table.selection()
        if not sel:
            messagebox.showinfo(TITRE, "Sélectionnez une ligne dans le tableau.", parent=self)
            return
        if detail:
            ligne = self.details[int(sel[0])]
        else:
            s = self.synthese[int(sel[0])]
            ligne = s["meilleure"] or s
        if ligne.get("erreur"):
            messagebox.showerror(TITRE, ligne["erreur"], parent=self)
            return
        self.parent.var_n.set(str(ligne["n"]))
        cible = self.cible if self.cible is not None and self.cible < ligne["n"] else None
        self.parent.charger_valeurs(f"{ligne['colonne']} (N = {ligne['n']})", ligne["valeurs"], cible)

    def exporter(self):
        if not self.synthese:
            messagebox.showinfo(TITRE, "Rien à exporter : chargez et calculez d'abord.", parent=self)
            return
        chemin = filedialog.asksaveasfilename(
            parent=self, title="Exporter les résultats", defaultextension=".csv",
            initialfile="resultats_colonnes.csv", filetypes=[("CSV (Excel)", "*.csv")])
        if not chemin:
            return
        try:
            moteur.exporter_colonnes_csv(chemin, self.synthese, self.details, self.cible,
                                         self.complet)
        except OSError as e:
            messagebox.showerror(TITRE, f"Export impossible :\n{e}", parent=self)
            return
        messagebox.showinfo(TITRE, f"Résultats exportés :\n{chemin}", parent=self)

    def _fermer(self):
        self._arret.set()
        if self._suivi is not None:
            self.after_cancel(self._suivi)
        self.destroy()


def main():
    app = Application()
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        valeurs, _ = moteur.lire_csv(sys.argv[1])
        app.txt.insert("1.0", "\n".join(map(str, valeurs)))
        app.lbl_fichier.config(text=f"{os.path.basename(sys.argv[1])} – {len(valeurs)} nombres lus")
        app.recalculer()
    app.mainloop()


if __name__ == "__main__":
    main()
