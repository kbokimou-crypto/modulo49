"""Modulo49 : modélisation de suites de nombres (1 à N-1) et prédiction MOD N, N au choix."""

import os
import sys
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
