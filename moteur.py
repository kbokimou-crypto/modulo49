"""Moteur de modélisation et de prédiction pour les suites de nombres de 1 à N-1.

Principe
--------
Le modulo N est au choix (50 par défaut) ; les valeurs admises vont de 1 à N-1.

1. La suite brute est "dépliée" : chaque saut u(i) - u(i-1) est ramené modulo N
   dans l'intervalle ]-N/2, N/2], puis cumulé. On obtient ainsi une courbe
   continue qui représente la fonction d'évolution sans les retours à 1.
2. Plusieurs modèles sont ajustés sur cette courbe dépliée.
3. Chaque modèle est évalué par validation glissante (on le refait sur le début de la
   suite et on compare sa prédiction à la valeur réellement observée ensuite).
4. La prédiction est ramenée dans l'intervalle par MOD N. Le résultat 0 n'étant pas
   admis, un 0 est remplacé par 1 (on passe à la valeur suivante du cycle).
"""

import csv
import io
import warnings

import numpy as np

MODULO_DEFAUT = 50
MODULO_MIN, MODULO_MAX = 3, 100000


def verifier_modulo(n):
    n = int(n)
    if not MODULO_MIN <= n <= MODULO_MAX:
        raise ValueError(f"Le modulo N doit être compris entre {MODULO_MIN} et {MODULO_MAX}.")
    return n


def reduire(x, n=MODULO_DEFAUT):
    """Ramène un nombre réel dans 1..N-1 avec la règle MOD N (0 interdit -> 1)."""
    r = int(round(x)) % n
    return 1 if r == 0 else r


def ecart_circulaire(a, b, n=MODULO_DEFAUT):
    """Distance entre deux valeurs sur le cycle MOD N (0 à N/2)."""
    d = abs(int(a) - int(b)) % n
    return min(d, n - d)


def deplier(valeurs, n=MODULO_DEFAUT):
    """Transforme la suite brute en courbe continue (sauts ramenés dans ]-N/2, N/2])."""
    out = [float(valeurs[0])]
    for prec, cour in zip(valeurs, valeurs[1:]):
        saut = (cour - prec) % n
        if saut > n // 2:
            saut -= n
        out.append(out[-1] + saut)
    return np.array(out)


# --------------------------------------------------------------------------- modèles
# Chaque modèle reçoit la courbe dépliée y et renvoie (ajustement, prediction_suivante)
# où "ajustement" est un tableau de même longueur que y (NaN là où non défini).

def _poly(y, degre):
    x = np.arange(len(y))
    coef = np.polyfit(x, y, degre)
    return np.polyval(coef, x), float(np.polyval(coef, len(y)))


def modele_lineaire(y):
    return _poly(y, 1)


def modele_quadratique(y):
    return _poly(y, 2)


def modele_saut_moyen(y):
    sauts = np.diff(y)
    m = float(sauts.mean())
    ajust = y[0] + m * np.arange(len(y))
    return ajust, float(y[-1] + m)


def modele_dernier_saut(y):
    ajust = np.full(len(y), np.nan)
    ajust[2:] = y[1:-1] + (y[1:-1] - y[:-2])
    return ajust, float(y[-1] + (y[-1] - y[-2]))


def modele_recurrence(y):
    """Récurrence affine u(n+1) = a*u(n) + b, ajustée par moindres carrés."""
    a, b = np.polyfit(y[:-1], y[1:], 1)
    ajust = np.full(len(y), np.nan)
    ajust[1:] = a * y[:-1] + b
    return ajust, float(a * y[-1] + b)


def modele_cubique(y):
    return _poly(y, 3)


def modele_recurrence_ordre2(y):
    """Récurrence u(n+1) = a*u(n) + b*u(n-1) + c (type Fibonacci généralisé)."""
    A = np.column_stack([y[1:-1], y[:-2], np.ones(len(y) - 2)])
    (a, b, c), *_ = np.linalg.lstsq(A, y[2:], rcond=None)
    ajust = np.full(len(y), np.nan)
    ajust[2:] = a * y[1:-1] + b * y[:-2] + c
    return ajust, float(a * y[-1] + b * y[-2] + c)


# (nom, fonction, nombre minimum de valeurs)
# ordre 1 : u(n+1) = a·u(n) + b ; ordre 2 : u(n+1) = a·u(n) + b·u(n-1) + c
MODELES = [
    ("Régression linéaire", modele_lineaire, 2),
    ("Régression quadratique", modele_quadratique, 3),
    ("Régression cubique", modele_cubique, 4),
    ("Saut moyen", modele_saut_moyen, 2),
    ("Dernier saut répété", modele_dernier_saut, 2),
    ("Récurrence ordre 1", modele_recurrence, 3),
    ("Récurrence ordre 2", modele_recurrence_ordre2, 5),
]


def _predire(fonction, valeurs, n):
    """Prédiction brute d'un modèle sur une suite, ou None si le calcul échoue."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, p = fonction(deplier(valeurs, n))
    except (np.linalg.LinAlgError, ValueError):
        return None
    return p if np.isfinite(p) else None


def evaluer(fonction, valeurs, minimum, n=MODULO_DEFAUT):
    """Erreur moyenne (sur le cycle) des prédictions faites pas à pas sur l'historique."""
    erreurs = []
    debut = max(minimum, 3)
    for k in range(debut, len(valeurs)):
        p = _predire(fonction, valeurs[:k], n)
        if p is not None:
            erreurs.append(ecart_circulaire(reduire(p, n), valeurs[k], n))
    return (float(np.mean(erreurs)), len(erreurs)) if erreurs else (float("nan"), 0)


def analyser(valeurs, n=MODULO_DEFAUT):
    """Analyse complète. Renvoie un dict avec la courbe dépliée, les modèles et le meilleur."""
    if len(valeurs) < 3:
        raise ValueError("Il faut au moins 3 nombres pour modéliser la suite.")
    n = verifier_modulo(n)
    hors = [v for v in valeurs if not 1 <= v <= n - 1]
    if hors:
        raise ValueError(f"Avec N = {n}, les valeurs doivent être entre 1 et {n - 1}. "
                         f"Valeur(s) hors intervalle : {', '.join(map(str, sorted(set(hors))[:10]))}. "
                         f"Choisissez N ≥ {max(valeurs) + 1}.")
    y = deplier(valeurs, n)
    resultats = []
    for nom, fonction, minimum in MODELES:
        if len(valeurs) < minimum:
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                ajust, p = fonction(y)
        except (np.linalg.LinAlgError, ValueError):
            continue
        if not np.isfinite(p):
            continue
        erreur, nb = evaluer(fonction, valeurs, minimum, n)
        resultats.append({
            "nom": nom,
            "ajustement": ajust,
            "prediction_brute": p,
            "prediction": reduire(p, n),
            "erreur": erreur,
            "nb_tests": nb,
        })
    if not resultats:
        raise ValueError("Aucun modèle n'a pu être ajusté sur ces données.")
    testes = [r for r in resultats if r["nb_tests"] > 0]
    meilleur = min(testes, key=lambda r: r["erreur"]) if testes else resultats[0]
    return {"valeurs": list(valeurs), "n": n, "deplie": y, "modeles": resultats, "meilleur": meilleur}


# --------------------------------------------------------------------------- cible
def chercher_cible(valeurs, cible, n=MODULO_DEFAUT):
    """Pour chaque modèle, cherche avec combien de valeurs il prédit la cible.

    On garde toujours la dernière valeur de la suite et on prend les k dernières
    valeurs (k = taille minimale du modèle ... toute la suite). Pour chaque k, la
    prédiction MOD N est comparée à la cible.
    """
    n = verifier_modulo(n)
    cible = int(cible)
    if not 1 <= cible <= n - 1:
        raise ValueError(f"La valeur cible doit être entre 1 et {n - 1}.")
    total = len(valeurs)
    resultats = []
    for nom, fonction, minimum in MODELES:
        debut = max(minimum, 3)
        if total < debut:
            continue
        fenetres, plus_proche, predictions = [], None, {}
        for k in range(debut, total + 1):
            p = _predire(fonction, valeurs[-k:], n)
            if p is None:
                continue
            pred = reduire(p, n)
            predictions[k] = pred
            ecart = ecart_circulaire(pred, cible, n)
            if ecart == 0:
                fenetres.append(k)
            if plus_proche is None or ecart < plus_proche[0]:
                plus_proche = (ecart, k, pred)
        resultats.append({
            "nom": nom,
            "confirme": bool(fenetres),
            "fenetres": fenetres,
            "toute_la_suite": total in fenetres,
            "nb_testees": total - debut + 1,
            "plus_proche": plus_proche,  # (écart, k, prédiction)
            "predictions": predictions,  # {k: prédiction MOD N}
        })
    return resultats


def recapituler(resultats, total):
    """Points communs entre les modèles pour la cible.

    Renvoie, pour chaque nombre de valeurs k, les modèles qui confirment la cible,
    ainsi que la plage de k où l'accord entre modèles est maximal.
    """
    par_k = []
    for k in range(3, total + 1):
        modeles = [r["nom"] for r in resultats if k in r["fenetres"]]
        par_k.append({"k": k, "nb": len(modeles), "modeles": modeles})
    maxi = max((x["nb"] for x in par_k), default=0)
    meilleurs_k = [x["k"] for x in par_k if x["nb"] == maxi and maxi > 0]
    confirmants = [r for r in resultats if r["confirme"]]
    communs = set.intersection(*(set(r["fenetres"]) for r in confirmants)) if confirmants else set()
    return {
        "par_k": par_k,
        "accord_max": maxi,
        "k_accord_max": meilleurs_k,
        "k_communs_a_tous": sorted(communs),
        "nb_confirmants": len(confirmants),
    }


def exporter_csv(chemin, valeurs, n, cible, resultats):
    """Exporte le récapitulatif (séparateur ;, lisible directement par Excel)."""
    total = len(valeurs)
    recap = recapituler(resultats, total)
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Récapitulatif Modulo49"])
        w.writerow(["Modulo N", n])
        w.writerow(["Valeur cible", cible])
        w.writerow(["Nombre de valeurs dans la suite", total])
        w.writerow(["Dernière valeur (toujours incluse)", valeurs[-1]])
        w.writerow(["Modèles qui confirment", f"{recap['nb_confirmants']} sur {len(resultats)}"])
        w.writerow(["Accord maximal", f"{recap['accord_max']} modèle(s) pour k = "
                    + (resumer_fenetres(recap["k_accord_max"]) or "aucun")])
        w.writerow(["k communs à tous les modèles qui confirment",
                    resumer_fenetres(recap["k_communs_a_tous"]) or "aucun"])
        w.writerow([])
        w.writerow(["Modèle", "Confirme", "Nb de k qui confirment", "k min", "k max",
                    "Étendue de la plage (k max - k min + 1)", "Plages de k",
                    "Plus proche (si non)", "k du plus proche"])
        for r in resultats:
            f_ = r["fenetres"]
            proche = r["plus_proche"]
            w.writerow([r["nom"], "oui" if r["confirme"] else "non", len(f_),
                        f_[0] if f_ else "", f_[-1] if f_ else "",
                        f_[-1] - f_[0] + 1 if f_ else "", resumer_fenetres(f_) or "aucune",
                        "" if r["confirme"] or not proche else proche[2],
                        "" if r["confirme"] or not proche else proche[1]])
        w.writerow([])
        w.writerow(["k (nb de dernières valeurs)", "Rangs utilisés", "Valeurs utilisées",
                    "Nb de modèles qui confirment", "Modèles"])
        for x in recap["par_k"]:
            k = x["k"]
            w.writerow([k, f"{total - k} à {total - 1}",
                        " ".join(map(str, valeurs[-k:])) if k <= 30 else
                        " ".join(map(str, valeurs[-30:])) + " (30 dernières)",
                        x["nb"], ", ".join(x["modeles"])])
        w.writerow([])
        w.writerow(["Prédiction de chaque modèle selon k"])
        ks = [x["k"] for x in recap["par_k"]]
        w.writerow(["Modèle"] + [f"k={k}" for k in ks])
        for r in resultats:
            w.writerow([r["nom"]] + [r["predictions"].get(k, "") for k in ks])
    return recap


def resumer_fenetres(fenetres):
    """[3, 4, 5, 9, 10] -> '3 à 5, 9 à 10'."""
    plages, debut, prec = [], None, None
    for k in fenetres:
        if debut is None:
            debut = prec = k
        elif k == prec + 1:
            prec = k
        else:
            plages.append((debut, prec))
            debut = prec = k
    if debut is not None:
        plages.append((debut, prec))
    return ", ".join(str(a) if a == b else f"{a} à {b}" for a, b in plages)


# --------------------------------------------------------------------------- CSV
def lire_csv(chemin):
    """Lit les entiers positifs de la colonne A d'un CSV. Renvoie (valeurs, avertissements).

    La vérification par rapport au modulo N est faite au moment de l'analyse."""
    with open(chemin, "rb") as f:
        brut = f.read()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texte = brut.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    echantillon = texte[:4096]
    try:
        dialecte = csv.Sniffer().sniff(echantillon, delimiters=";,\t|")
        sep = dialecte.delimiter
    except csv.Error:
        sep = ";" if ";" in echantillon else ","

    valeurs, avertissements = [], []
    for num, ligne in enumerate(csv.reader(io.StringIO(texte), delimiter=sep), start=1):
        if not ligne or not ligne[0].strip():
            continue
        cellule = ligne[0].strip().replace(",", ".")
        try:
            v = float(cellule)
        except ValueError:
            if num == 1:
                continue  # ligne d'en-tête
            avertissements.append(f"Ligne {num} ignorée : « {ligne[0]} » n'est pas un nombre.")
            continue
        if v != int(v) or v < 1:
            avertissements.append(f"Ligne {num} ignorée : {ligne[0]} n'est pas un entier positif.")
            continue
        valeurs.append(int(v))
    return valeurs, avertissements
