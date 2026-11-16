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
import re
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
    v = np.asarray(valeurs, dtype=np.int64)
    sauts = np.diff(v) % n
    sauts[sauts > n // 2] -= n
    return float(v[0]) + np.concatenate(([0.0], np.cumsum(sauts, dtype=np.float64)))


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


def _predire(fonction, y):
    """Prédiction brute d'un modèle sur une courbe dépliée, ou None si le calcul échoue."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _, p = fonction(y)
    except (np.linalg.LinAlgError, ValueError):
        return None
    return p if np.isfinite(p) else None


def evaluer(fonction, valeurs, minimum, n=MODULO_DEFAUT):
    """Validation pas à pas sur l'historique.

    Renvoie (écart moyen sur le cycle, nombre de tests, nombre de prédictions exactes).
    Le dépliage d'un début de suite étant le début du dépliage complet, on ne déplie
    qu'une fois.
    """
    y = deplier(valeurs, n)
    erreurs = []
    debut = max(minimum, 3)
    for k in range(debut, len(valeurs)):
        p = _predire(fonction, y[:k])
        if p is not None:
            erreurs.append(ecart_circulaire(reduire(p, n), valeurs[k], n))
    if not erreurs:
        return float("nan"), 0, 0
    return float(np.mean(erreurs)), len(erreurs), erreurs.count(0)


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
        erreur, nb, exactes = evaluer(fonction, valeurs, minimum, n)
        resultats.append({
            "nom": nom,
            "ajustement": ajust,
            "prediction_brute": p,
            "prediction": reduire(p, n),
            "erreur": erreur,
            "nb_tests": nb,
            # part des prédictions exactes lors de la validation pas à pas (0 à 1)
            "reussite": exactes / nb if nb else float("nan"),
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
    y = deplier(valeurs, n)
    resultats = []
    for nom, fonction, minimum in MODELES:
        debut = max(minimum, 3)
        if total < debut:
            continue
        fenetres, plus_proche, predictions = [], None, {}
        for k in range(debut, total + 1):
            # dépliage des k dernières valeurs = fin du dépliage complet, recalée sur u(-k)
            p = _predire(fonction, y[-k:] - y[-k] + valeurs[-k])
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
def lettre_colonne(i):
    """0 -> A, 25 -> Z, 26 -> AA (comme dans Excel)."""
    lettres = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        lettres = chr(65 + r) + lettres
    return lettres


def _lire_lignes(chemin):
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
        sep = csv.Sniffer().sniff(echantillon, delimiters=";,\t|").delimiter
    except csv.Error:
        sep = ";" if ";" in echantillon else ","
    return list(csv.reader(io.StringIO(texte), delimiter=sep))


def _nombre(cellule):
    try:
        return float(cellule.strip().replace(",", "."))
    except ValueError:
        return None


def lire_csv_colonnes(chemin):
    """Lit toutes les colonnes d'un CSV.

    Renvoie (colonnes, avertissements) où colonnes est une liste de
    (nom, valeurs) : le nom est l'en-tête s'il y en a un, sinon la lettre (A, B…).
    Les cellules vides sont ignorées, ce qui permet des colonnes de longueurs différentes.
    """
    lignes = _lire_lignes(chemin)
    nb_col = max((len(l) for l in lignes), default=0)
    entete = lignes[0] if lignes else []
    a_entete = any(c.strip() and _nombre(c) is None for c in entete)
    colonnes, avertissements = [], []
    for j in range(nb_col):
        lettre = lettre_colonne(j)
        titre = entete[j].strip() if a_entete and j < len(entete) else ""
        nom = f"{lettre} – {titre}" if titre else lettre
        valeurs = []
        for num, ligne in enumerate(lignes, start=1):
            if (a_entete and num == 1) or j >= len(ligne) or not ligne[j].strip():
                continue
            v = _nombre(ligne[j])
            if v is None:
                avertissements.append(f"{lettre}{num} ignorée : « {ligne[j]} » n'est pas un nombre.")
            elif v != int(v) or v < 1:
                avertissements.append(f"{lettre}{num} ignorée : {ligne[j]} n'est pas un entier positif.")
            else:
                valeurs.append(int(v))
        if valeurs:
            colonnes.append((nom, valeurs))
    return colonnes, avertissements


def lire_csv(chemin):
    """Lit les entiers positifs de la colonne A d'un CSV. Renvoie (valeurs, avertissements).

    La vérification par rapport au modulo N est faite au moment de l'analyse."""
    colonnes, avertissements = lire_csv_colonnes(chemin)
    avertissements = [a for a in avertissements if a.startswith("A") and a[1].isdigit()]
    if colonnes and colonnes[0][0].split(" ")[0] == "A":
        return colonnes[0][1], avertissements
    return [], avertissements


# --------------------------------------------------------------------------- multi-colonnes
# Chaque colonne a sa propre liste de modulos N, saisie librement :
#   « 50 »  « 37, 43, 50 »  « 40-60 »  « 30-35 ; 50 61 »  « 40 à 45, 52 »

def lire_modulos(texte):
    """Lit une saisie libre de modulos et renvoie la liste des N, triée et sans doublons.

    Séparateurs : virgule, point-virgule ou espace. « a-b » (ou « a à b », « a..b »)
    désigne tous les N de a à b.
    """
    t = str(texte).replace("–", "-").replace("—", "-").replace("..", "-")
    t = re.sub(r"\s*(?:-|à|À)\s*", "-", t)
    morceaux = [m for m in re.split(r"[,;\s]+", t) if m]
    if not morceaux:
        raise ValueError("Aucune valeur de N : saisissez par exemple 50, ou 37, 43, 50, ou 40-60.")
    modulos = set()
    for m in morceaux:
        plage = re.fullmatch(r"(\d+)-(\d+)", m)
        if plage:
            a, b = sorted((int(plage.group(1)), int(plage.group(2))))
        elif m.isdigit():
            a = b = int(m)
        else:
            raise ValueError(f"« {m} » n'est pas compris : écrivez des entiers (ex. 50) "
                             f"ou des plages (ex. 40-60).")
        for n in (a, b):
            if not MODULO_MIN <= n <= MODULO_MAX:
                raise ValueError(f"N = {n} : le modulo doit être compris entre "
                                 f"{MODULO_MIN} et {MODULO_MAX}.")
        modulos.update(range(a, b + 1))
    return sorted(modulos)


def modulos_a_tester(reglage):
    """Liste des N à calculer : saisie libre (texte) ou liste d'entiers."""
    if isinstance(reglage, str):
        return lire_modulos(reglage)
    return lire_modulos(", ".join(str(n) for n in reglage))


def decrire_reglage(reglage):
    return resumer_fenetres(modulos_a_tester(reglage))


def _pourcent(x):
    return None if x is None or not np.isfinite(x) else 100.0 * x


def analyser_ligne(nom, valeurs, n, cible=None):
    """Calcul d'une colonne pour un modulo N donné : une ligne du tableau de détail."""
    ligne = {"colonne": nom, "n": n, "nb": len(valeurs), "valeurs": valeurs,
             "derniere": valeurs[-1] if valeurs else None, "erreur": None}
    try:
        a = analyser(valeurs, n)
    except ValueError as e:
        ligne["erreur"] = str(e)
        return ligne
    m = a["meilleur"]
    preds = {r["nom"]: r["prediction"] for r in a["modeles"]}
    compte = {}
    for p in preds.values():
        compte[p] = compte.get(p, 0) + 1
    majo = max(compte.items(), key=lambda kv: (kv[1], kv[0] == m["prediction"]))
    teste = m["nb_tests"] > 0
    ligne.update({
        "prediction": m["prediction"],
        "modele": m["nom"],
        "brut": m["prediction_brute"],
        "ecart": m["erreur"] if teste else None,
        # écart rapporté à l'écart maximal possible N/2 : 0 % = parfait, ~50 % = hasard
        "ecart_relatif": _pourcent(m["erreur"] / (n / 2)) if teste else None,
        "reussite": _pourcent(m["reussite"]) if teste else None,
        "predictions": preds,
        "majoritaire": majo[0],
        "nb_majoritaire": majo[1],
    })
    if cible is not None:
        if 1 <= cible <= n - 1:
            res = chercher_cible(valeurs, cible, n)
            rc = recapituler(res, len(valeurs))
            ligne.update({
                "nb_confirmants": rc["nb_confirmants"],
                "confirmants": [r["nom"] for r in res if r["confirme"]],
                "k_accord_max": rc["k_accord_max"],
                "k_communs": rc["k_communs_a_tous"],
            })
        else:
            ligne["nb_confirmants"] = None  # cible hors de 1..N-1 pour ce N
    return ligne


def _score(ligne):
    """Classement des N d'une colonne : meilleure réussite, puis plus petit écart relatif."""
    reussite = ligne["reussite"] if ligne["reussite"] is not None else -1.0
    ecart = ligne["ecart_relatif"] if ligne["ecart_relatif"] is not None else 101.0
    return (-reussite, ecart, ligne["n"])


def synthetiser(nom, valeurs, reglage, modulos, lignes, cible=None):
    """Résumé d'une colonne sur tous les N calculés."""
    ok = [l for l in lignes if not l["erreur"]]
    ignores = [n for n in modulos if valeurs and n <= max(valeurs)]
    s = {"colonne": nom, "nb": len(valeurs), "derniere": valeurs[-1] if valeurs else None,
         "valeurs": valeurs, "reglage": decrire_reglage(reglage), "modulos": modulos,
         "testes": [l["n"] for l in ok], "ignores": ignores, "erreur": None, "meilleure": None}
    if not ok:
        if len(valeurs) < 3:
            s["erreur"] = "Il faut au moins 3 nombres pour modéliser la suite."
        elif ignores and len(ignores) == len(modulos):
            s["erreur"] = f"Aucun N calculable : la valeur maximale est {max(valeurs)}, il faut N ≥ {max(valeurs) + 1}."
        else:
            s["erreur"] = lignes[0]["erreur"] if lignes else "Calcul interrompu."
        return s
    meilleure = min(ok, key=_score)
    meilleure["est_meilleure"] = True
    compte = {}
    for l in ok:
        compte[l["prediction"]] = compte.get(l["prediction"], 0) + 1
    freq = max(compte.items(), key=lambda kv: (kv[1], kv[0] == meilleure["prediction"]))
    s.update({"meilleure": meilleure, "frequente": freq[0], "nb_frequente": freq[1]})
    if cible is not None:
        avec = [l for l in ok if l.get("nb_confirmants")]
        maxi = max((l["nb_confirmants"] for l in avec), default=0)
        s.update({
            "n_confirment": [l["n"] for l in avec],
            "accord_max": maxi,
            "n_accord_max": [l["n"] for l in avec if l["nb_confirmants"] == maxi],
        })
    return s


def analyser_colonnes(colonnes, reglages, cible=None, rappel=None):
    """Calcule toutes les colonnes, chacune avec son propre réglage du modulo.

    colonnes : liste de (nom, valeurs) ; reglages : pour chaque colonne, la saisie libre
    des N à calculer (ex. « 37, 43, 50 » ou « 40-60 ») ou une liste d'entiers.
    rappel(fait, total) est appelé après chaque N ; s'il renvoie False le calcul s'arrête.
    Renvoie (synthese, details, complet). Les N trop petits pour les valeurs de la
    colonne (N ≤ valeur maximale) ne sont pas calculés et sont signalés dans la synthèse.
    """
    listes = [modulos_a_tester(r) for r in reglages]
    total = sum(len(l) for l in listes)
    fait, complet = 0, True
    synthese, details = [], []
    for (nom, valeurs), reglage, modulos in zip(colonnes, reglages, listes):
        if not complet:
            s = synthetiser(nom, valeurs, reglage, modulos, [], cible)
            s["erreur"] = "Non calculée : calcul arrêté avant cette colonne."
            synthese.append(s)
            continue
        lignes = []
        for n in modulos:
            if len(valeurs) >= 3 and n > max(valeurs):
                lignes.append(analyser_ligne(nom, valeurs, n, cible))
            fait += 1
            if rappel is not None and rappel(fait, total) is False:
                complet = False
                break
        details.extend(lignes)
        synthese.append(synthetiser(nom, valeurs, reglage, modulos, lignes, cible))
    return synthese, details, complet


def _nombre_fr(x, decimales=2):
    return "" if x is None else f"{x:.{decimales}f}".replace(".", ",")


def exporter_colonnes_csv(chemin, synthese, details, cible=None, complet=True):
    """Exporte la synthèse par colonne puis le détail par N (séparateur ;, pour Excel)."""
    noms_modeles = [nom for nom, _, _ in MODELES]
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Analyse multi-colonnes Modulo49"])
        w.writerow(["Valeur cible", cible if cible is not None else "aucune"])
        if not complet:
            w.writerow(["Attention", "calcul interrompu : résultats partiels"])
        w.writerow(["Réussite", "part des prédictions exactes en validation pas à pas"])
        w.writerow(["Écart relatif", "écart moyen / (N/2) : 0 % = parfait, environ 50 % = hasard"])
        w.writerow(["Meilleur N", "plus forte réussite, puis plus petit écart relatif"])
        w.writerow([])

        w.writerow(["SYNTHÈSE PAR COLONNE"])
        entete = ["Colonne", "Nb de valeurs", "Dernière valeur", "N demandés",
                  "Nb de N calculés", "N calculés", "N ignorés (trop petits)", "Meilleur N",
                  "Prédiction au meilleur N", "Modèle retenu", "Réussite (%)",
                  "Écart relatif (%)", "Prédiction la plus fréquente (tous N)",
                  "Nb de N qui la donnent"]
        if cible is not None:
            entete += ["N où la cible est confirmée", "Accord maximal (modèles)",
                       "N de l'accord maximal"]
        w.writerow(entete + ["Erreur"])
        for s in synthese:
            debut = [s["colonne"], s["nb"], s["derniere"], s["reglage"], len(s["testes"]),
                     resumer_fenetres(s["testes"]), resumer_fenetres(s["ignores"])]
            if s["erreur"]:
                w.writerow(debut + [""] * (len(entete) - len(debut)) + [s["erreur"]])
                continue
            m = s["meilleure"]
            ligne = debut + [m["n"], m["prediction"], m["modele"], _nombre_fr(m["reussite"], 1),
                             _nombre_fr(m["ecart_relatif"], 1), s["frequente"], s["nb_frequente"]]
            if cible is not None:
                ligne += [resumer_fenetres(s["n_confirment"]) or "aucun", s["accord_max"],
                          resumer_fenetres(s["n_accord_max"]) or "aucun"]
            w.writerow(ligne + [""])
        w.writerow([])

        w.writerow(["DÉTAIL PAR COLONNE ET PAR N"])
        entete = ["Colonne", "N", "Meilleur N de la colonne", "Prédiction retenue",
                  "Modèle retenu", "Valeur brute", "Écart moyen", "Écart relatif (%)",
                  "Réussite (%)", "Prédiction majoritaire", "Nb de modèles d'accord"]
        if cible is not None:
            entete += ["Nb de modèles qui confirment la cible", "Modèles qui confirment",
                       "k de l'accord maximal", "k communs à tous les modèles qui confirment"]
        entete += [f"Prédiction – {nom}" for nom in noms_modeles]
        w.writerow(entete + ["Erreur"])
        for l in details:
            if l["erreur"]:
                debut = [l["colonne"], l["n"]]
                w.writerow(debut + [""] * (len(entete) - len(debut)) + [l["erreur"]])
                continue
            ligne = [l["colonne"], l["n"], "oui" if l.get("est_meilleure") else "",
                     l["prediction"], l["modele"], _nombre_fr(l["brut"]), _nombre_fr(l["ecart"]),
                     _nombre_fr(l["ecart_relatif"], 1), _nombre_fr(l["reussite"], 1),
                     l["majoritaire"], l["nb_majoritaire"]]
            if cible is not None:
                if l["nb_confirmants"] is None:
                    ligne += ["cible hors de 1 à N-1", "", "", ""]
                else:
                    ligne += [l["nb_confirmants"], ", ".join(l["confirmants"]) or "aucun",
                              resumer_fenetres(l["k_accord_max"]) or "aucun",
                              resumer_fenetres(l["k_communs"]) or "aucun"]
            ligne += [l["predictions"].get(nom, "") for nom in noms_modeles]
            w.writerow(ligne + [""])


# --------------------------------------------------------------------------- modulo glissant
# Chaque colonne est calculée pour tous les N de N min à N max (N, N+1, N+2…). Pour chaque N
# on garde la valeur calculée par chaque modèle (avant arrondi, ramenée entre 0 et N) et la
# prévision retenue. Avec une valeur future V, on cherche les N où un modèle donne V :
# exactement de préférence (écart 0), sinon à l'écart toléré près (± 0,499 par défaut,
# c'est-à-dire que l'arrondi de la valeur calculée donne V).

TOLERANCE_DEFAUT = 0.499
PRECISION_EXACTE = 0.0005   # écart affiché 0,000 : la valeur calculée vaut exactement V


def lire_tolerance(texte):
    """« 0,499 », « 0.499 » ou « ±0,499 » -> 0.499."""
    t = str(texte).strip().replace(" ", "").replace(",", ".")
    for prefixe in ("±", "+/-", "+-"):
        if t.startswith(prefixe):
            t = t[len(prefixe):]
            break
    try:
        x = float(t)
    except ValueError:
        raise ValueError(f"Écart toléré « {texte} » non compris : écrivez par exemple 0,499.") from None
    if not np.isfinite(x) or x < 0:
        raise ValueError("L'écart toléré doit être un nombre positif ou nul (par exemple 0,499).")
    return x


def lire_reglage_glissant(texte_min, texte_max, texte_future=""):
    """Lit N min et N max (dans n'importe quel ordre) et la valeur future (facultative).

    Renvoie (N min, N max, valeur future ou None)."""
    bornes = []
    for texte, quoi in ((texte_min, "N min"), (texte_max, "N max")):
        t = str(texte).strip()
        if not re.fullmatch(r"[0-9]+", t):
            raise ValueError(f"{quoi} : écrivez un nombre entier (par exemple 50).")
        n = int(t)
        if not MODULO_MIN <= n <= MODULO_MAX:
            raise ValueError(f"{quoi} = {n} : le modulo doit être compris entre "
                             f"{MODULO_MIN} et {MODULO_MAX}.")
        bornes.append(n)
    nmin, nmax = sorted(bornes)
    t = str(texte_future).strip()
    if not t:
        return nmin, nmax, None
    v = _nombre(t)
    if v is None or not np.isfinite(v) or v != int(v) or v < 1:
        raise ValueError(f"Valeur future « {t} » : écrivez un nombre entier positif (par exemple 23).")
    return nmin, nmax, int(v)


def ecart_modulo(x, cible, n):
    """Écart signé entre x et la cible sur le cycle MOD N, compris entre -N/2 et N/2."""
    return float((x - cible + n / 2) % n - n / 2)


def valeur_modulo(x, n):
    """Valeur calculée par un modèle, avant arrondi, ramenée entre 0 et N (3 décimales)."""
    v = round(float(x) % n, 3)
    return 0.0 if v >= n else v + 0.0


def _analyser_memoire(valeurs, n, memoire):
    """Même résultat que analyser(valeurs, n), mais les prédictions brutes sont gardées
    dans « memoire » et réutilisées pour le N suivant quand la suite dépliée ne change pas
    (c'est le cas de tous les N grands devant les sauts de la suite)."""
    if len(valeurs) < 3:
        raise ValueError("Il faut au moins 3 nombres pour modéliser la suite.")
    n = verifier_modulo(n)
    hors = [v for v in valeurs if not 1 <= v <= n - 1]
    if hors:
        raise ValueError(f"Avec N = {n}, les valeurs doivent être entre 1 et {n - 1}. "
                         f"Valeur(s) hors intervalle : {', '.join(map(str, sorted(set(hors))[:10]))}. "
                         f"Choisissez N ≥ {max(valeurs) + 1}.")
    y = deplier(valeurs, n)
    cle = y.tobytes()
    if memoire.get("cle") != cle:
        modeles = []
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
            # prédictions de la validation pas à pas (indépendantes de N à y égal)
            pas = [(k, _predire(fonction, y[:k])) for k in range(max(minimum, 3), len(valeurs))]
            modeles.append((nom, ajust, p, pas))
        memoire.clear()
        memoire.update(cle=cle, modeles=modeles)
    resultats = []
    for nom, ajust, p, pas in memoire["modeles"]:
        erreurs = [ecart_circulaire(reduire(q, n), valeurs[k], n) for k, q in pas if q is not None]
        nb = len(erreurs)
        resultats.append({
            "nom": nom,
            "ajustement": ajust,
            "prediction_brute": p,
            "prediction": reduire(p, n),
            "erreur": float(np.mean(erreurs)) if nb else float("nan"),
            "nb_tests": nb,
            "reussite": erreurs.count(0) / nb if nb else float("nan"),
        })
    if not resultats:
        raise ValueError("Aucun modèle n'a pu être ajusté sur ces données.")
    testes = [r for r in resultats if r["nb_tests"] > 0]
    meilleur = min(testes, key=lambda r: r["erreur"]) if testes else resultats[0]
    return {"valeurs": list(valeurs), "n": n, "deplie": y, "modeles": resultats, "meilleur": meilleur}


def _ecart_classe(d):
    """|écart| pour classer les résultats ; toutes les valeurs exactes sont à égalité."""
    return 0.0 if abs(d) < PRECISION_EXACTE else abs(d)


def calculer_modulo(nom, valeurs, n, future=None, tolerance=TOLERANCE_DEFAUT, memoire=None):
    """Une ligne du modulo glissant : la colonne calculée avec le modulo N.

    Les valeurs qui dépassent N-1 sont ramenées dans 1..N-1 par MOD N (le 0 devient 1).
    future : valeur future cherchée (ou None). Un modèle la « donne » si sa valeur calculée
    en est à moins de « tolerance » sur le cycle MOD N ; écart 0 = valeur exacte.
    """
    ligne = {"colonne": nom, "n": n, "valeurs": valeurs, "nb_modifiees": 0,
             "future": future, "cible": None, "modeles": [], "trouves": [], "nb_exacts": 0,
             "retenu_trouve": False, "exact": False, "plus_proche": None, "erreur": None}
    if valeurs and max(valeurs) >= n:
        reduites = [reduire(v, n) for v in valeurs]
        ligne["nb_modifiees"] = sum(a != b for a, b in zip(valeurs, reduites))
        ligne["valeurs"] = reduites
    try:
        a = _analyser_memoire(ligne["valeurs"], n, {} if memoire is None else memoire)
    except ValueError as e:
        ligne["erreur"] = str(e)
        return ligne
    m = a["meilleur"]
    ligne.update({
        "modele": m["nom"],
        "prediction": m["prediction"],
        "brut": m["prediction_brute"],
        "valeur": valeur_modulo(m["prediction_brute"], n),
        "reussite": _pourcent(m["reussite"]) if m["nb_tests"] else None,
        "ecart_moyen": m["erreur"] if m["nb_tests"] else None,
    })
    # une valeur future ≥ N ne peut pas sortir : avec N, les valeurs vont de 1 à N-1
    cible = future if future is not None and future < n else None
    ligne["cible"] = cible
    for r in a["modeles"]:
        x = r["prediction_brute"]
        e = {"nom": r["nom"], "brut": x, "valeur": valeur_modulo(x, n),
             "prediction": r["prediction"],
             "reussite": _pourcent(r["reussite"]) if r["nb_tests"] else None,
             "retenu": r is m, "ecart": None, "trouve": False, "exact": False, "zero_un": False}
        if cible is not None:
            d, zero_un = ecart_modulo(x, cible, n), False
            if cible == 1:  # une valeur calculée proche de 0 donne aussi 1 (le 0 devient 1)
                d0 = ecart_modulo(x, 0, n)
                if abs(d0) < abs(d):
                    d, zero_un = d0, True
            trouve = abs(d) <= tolerance + 1e-9
            e.update(ecart=d, trouve=trouve, exact=trouve and abs(d) < PRECISION_EXACTE,
                     zero_un=zero_un)
        ligne["modeles"].append(e)
    if cible is not None and ligne["modeles"]:
        ligne["trouves"] = [e for e in ligne["modeles"] if e["trouve"]]
        ligne["retenu_trouve"] = any(e["retenu"] for e in ligne["trouves"])
        ligne["nb_exacts"] = sum(e["exact"] for e in ligne["trouves"])
        ligne["exact"] = ligne["nb_exacts"] > 0
        # à égalité (valeurs exactes), le modèle retenu puis l'ordre des modèles
        ligne["plus_proche"] = min(ligne["modeles"], key=lambda e: (_ecart_classe(e["ecart"]),
                                                                    not e["retenu"]))
    return ligne


def synthetiser_glissant(nom, valeurs, reglage, lignes, ignores=()):
    """Résumé d'une colonne du modulo glissant : N calculés et N qui donnent la valeur future
    (exacts d'abord, puis par écart croissant)."""
    nmin, nmax, future = reglage
    ok = [l for l in lignes if not l["erreur"]]
    s = {"colonne": nom, "nb": len(valeurs), "derniere": valeurs[-1] if valeurs else None,
         "maxi": max(valeurs) if valeurs else None, "nmin": nmin, "nmax": nmax,
         "future": future, "lignes": ok, "calcules": [l["n"] for l in ok],
         "ignores": list(ignores), "reduits": [l["n"] for l in ok if l["nb_modifiees"]],
         "impossibles": [], "correspondances": [], "n_exacts": [], "n_trouves": [],
         "n_retenu": [], "accord_max": 0, "n_accord_max": [], "plus_proche": None, "erreur": None}
    if not ok:
        if len(valeurs) < 3:
            s["erreur"] = "Il faut au moins 3 nombres pour modéliser la suite."
        elif ignores and len(ignores) == nmax - nmin + 1:
            s["erreur"] = (f"Aucun N calculable : la valeur maximale est {max(valeurs)}, il faut "
                           f"N ≥ {max(valeurs) + 1} (ou ramener les valeurs MOD N).")
        else:
            s["erreur"] = lignes[0]["erreur"] if lignes else "Calcul interrompu."
        return s
    if future is not None:
        corresp = [(l, e) for l in ok for e in l["trouves"]]
        # exacts d'abord (en tête, les N où le plus de modèles sont exacts), puis écart croissant
        corresp.sort(key=lambda le: (not le[1]["exact"],
                                     0.0 if le[1]["exact"] else abs(le[1]["ecart"]),
                                     -le[0]["nb_exacts"], -len(le[0]["trouves"]), le[0]["n"]))
        proches = [(l, l["plus_proche"]) for l in ok if l["plus_proche"] is not None]
        accord = max((len(l["trouves"]) for l in ok), default=0)
        s.update({
            "impossibles": [l["n"] for l in ok if l["cible"] is None],
            "correspondances": corresp,
            "n_exacts": sorted({l["n"] for l, e in corresp if e["exact"]}),
            "n_trouves": sorted({l["n"] for l, _ in corresp}),
            "n_retenu": [l["n"] for l in ok if l["retenu_trouve"]],
            # N où le plus grand nombre de modèles donnent la valeur future
            "accord_max": accord,
            "n_accord_max": [l["n"] for l in ok if accord and len(l["trouves"]) == accord],
            "plus_proche": (min(proches, key=lambda le: _ecart_classe(le[1]["ecart"]))
                            if proches else None),
        })
    return s


def analyser_glissant(colonnes, reglages, tolerance=TOLERANCE_DEFAUT, reduire_donnees=True,
                      rappel=None):
    """Modulo glissant sur toutes les colonnes.

    colonnes : liste de (nom, valeurs) ; reglages : pour chaque colonne
    (N min, N max, valeur future ou None). Tous les N de N min à N max sont calculés.
    Quand des valeurs de la colonne dépassent N-1, elles sont ramenées MOD N si
    reduire_donnees est vrai ; sinon ce N est ignoré. rappel(fait, total) est appelé après
    chaque N ; s'il renvoie False le calcul s'arrête. Renvoie (synthese, details, complet).
    """
    total = sum(nmax - nmin + 1 for nmin, nmax, _ in reglages)
    fait, complet = 0, True
    synthese, details = [], []
    for (nom, valeurs), reglage in zip(colonnes, reglages):
        nmin, nmax, future = reglage
        if not complet:
            s = synthetiser_glissant(nom, valeurs, reglage, [])
            s["erreur"] = "Non calculée : calcul arrêté avant cette colonne."
            synthese.append(s)
            continue
        lignes, ignores, memoire = [], [], {}
        for n in range(nmin, nmax + 1):
            if len(valeurs) >= 3:
                if reduire_donnees or n > max(valeurs):
                    lignes.append(calculer_modulo(nom, valeurs, n, future, tolerance, memoire))
                else:
                    ignores.append(n)
            fait += 1
            if rappel is not None and rappel(fait, total) is False:
                complet = False
                break
        details.extend(lignes)
        synthese.append(synthetiser_glissant(nom, valeurs, reglage, lignes, ignores))
    return synthese, details, complet


def ecart_fr(d):
    """Écart signé à 3 décimales, « 0,000 » pour une valeur exacte."""
    if d is None:
        return ""
    if abs(d) < PRECISION_EXACTE:
        return "0,000"
    return f"{d:+.3f}".replace(".", ",")


def decrire_donnees(ligne):
    """« telles quelles » ou « ramenées MOD N (k modifiées) »."""
    k = ligne["nb_modifiees"]
    return f"ramenées MOD {ligne['n']} ({k} modifiée{'s' if k > 1 else ''})" if k else "telles quelles"


def remarque_glissant(ligne, entree=None):
    """Remarques d'une ligne (ou d'une correspondance) du modulo glissant."""
    notes = []
    zero_un = entree["zero_un"] if entree is not None else any(e["zero_un"] for e in ligne["trouves"])
    if zero_un:
        notes.append("valeur calculée proche de 0 : le 0 devient 1")
    if ligne["future"] is not None and ligne["cible"] is None and not ligne["erreur"]:
        notes.append(f"{ligne['future']} impossible avec N = {ligne['n']} "
                     f"(valeurs de 1 à {ligne['n'] - 1})")
    return " ; ".join(notes)


def exporter_glissant_csv(chemin, synthese, details, tolerance=TOLERANCE_DEFAUT,
                          reduire_donnees=True, complet=True):
    """Exporte le modulo glissant : synthèse par colonne, N qui donnent la valeur future,
    puis toutes les valeurs par N (séparateur ;, pour Excel)."""
    noms = [nom for nom, _, _ in MODELES]
    tol = _nombre_fr(tolerance, 3)
    avec_future = any(s["future"] is not None for s in synthese)
    with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Modulo glissant et valeur future – Modulo49"])
        if not complet:
            w.writerow(["Attention", "calcul interrompu : résultats partiels"])
        w.writerow(["Écart toléré", f"± {tol}"])
        w.writerow(["Valeurs supérieures à N-1", "ramenées MOD N (le 0 devient 1)"
                    if reduire_donnees else "N non calculé"])
        w.writerow(["Valeur calculée", "valeur du modèle avant arrondi, ramenée MOD N (entre 0 et N)"])
        w.writerow(["Écart", "valeur calculée moins valeur future, sur le cycle MOD N ; "
                             "0,000 = valeur exacte"])
        w.writerow([])

        w.writerow(["SYNTHÈSE PAR COLONNE"])
        entete = ["Colonne", "Nb de valeurs", "Dernière valeur", "Valeur max", "N min", "N max",
                  "Nb de N calculés", "N calculés", "N où les données sont ramenées MOD N",
                  "N ignorés", "Valeur future", "N exacts", f"N à ± {tol} (tous modèles)",
                  "N où le modèle retenu donne la valeur", "Accord maximal (modèles)",
                  "N de l'accord maximal", "Nb de correspondances",
                  "Meilleure correspondance : N", "Modèle", "Valeur calculée", "Écart",
                  "Remarque", "Erreur"]
        w.writerow(entete)
        for s in synthese:
            debut = [s["colonne"], s["nb"], s["derniere"], s["maxi"], s["nmin"], s["nmax"],
                     len(s["calcules"]), resumer_fenetres(s["calcules"]),
                     resumer_fenetres(s["reduits"]), resumer_fenetres(s["ignores"]),
                     "" if s["future"] is None else s["future"]]
            if s["erreur"]:
                w.writerow(debut + [""] * (len(entete) - len(debut) - 1) + [s["erreur"]])
                continue
            if s["future"] is None:
                w.writerow(debut + [""] * (len(entete) - len(debut)))
                continue
            ligne = debut + [resumer_fenetres(s["n_exacts"]) or "aucun",
                             resumer_fenetres(s["n_trouves"]) or "aucun",
                             resumer_fenetres(s["n_retenu"]) or "aucun",
                             f"{s['accord_max']}/{len(MODELES)}",
                             resumer_fenetres(s["n_accord_max"]) or "aucun",
                             len(s["correspondances"])]
            meilleure = s["correspondances"][0] if s["correspondances"] else s["plus_proche"]
            if meilleure:
                l, e = meilleure
                ligne += [l["n"], e["nom"], _nombre_fr(e["valeur"], 3), ecart_fr(e["ecart"]),
                          "" if s["correspondances"] else f"aucun N à ± {tol} : valeur la plus proche"]
            else:
                ligne += ["", "", "", "", f"{s['future']} impossible pour tous les N calculés"]
            w.writerow(ligne + [""])
        w.writerow([])

        if avec_future:
            w.writerow(["VALEUR FUTURE : N QUI LA DONNENT (exacts d'abord, puis écart croissant)"])
            w.writerow(["Colonne", "N", "Modèle", "Valeur calculée", "Prévision MOD N",
                        "Valeur future", "Écart", "Exacte", "Modèle retenu pour ce N",
                        "Réussite du modèle (%)", "Données", "Remarque"])
            for s in synthese:
                for l, e in s["correspondances"]:
                    w.writerow([l["colonne"], l["n"], e["nom"], _nombre_fr(e["valeur"], 3),
                                e["prediction"], l["future"], ecart_fr(e["ecart"]),
                                "oui" if e["exact"] else "non", "oui" if e["retenu"] else "non",
                                _nombre_fr(e["reussite"], 1), decrire_donnees(l),
                                remarque_glissant(l, e)])
            w.writerow([])

        w.writerow(["TOUTES LES VALEURS PAR N"])
        entete = ["Colonne", "N", "Données", "Modèle retenu", "Prévision retenue",
                  "Réussite (%)", "Écart moyen"]
        entete += [f"Valeur calculée – {nom}" for nom in noms]
        entete += [f"Prévision – {nom}" for nom in noms]
        if avec_future:
            entete += ["Valeur future", "Nb de modèles qui la donnent", "Modèles qui la donnent",
                       "Plus petit écart", "Modèle le plus proche"]
            entete += [f"Écart – {nom}" for nom in noms]
        entete += ["Remarque"]
        w.writerow(entete)
        for l in details:
            if l["erreur"]:
                debut = [l["colonne"], l["n"]]
                w.writerow(debut + [""] * (len(entete) - len(debut) - 1) + [l["erreur"]])
                continue
            par_nom = {e["nom"]: e for e in l["modeles"]}
            ligne = [l["colonne"], l["n"], decrire_donnees(l), l["modele"], l["prediction"],
                     _nombre_fr(l["reussite"], 1), _nombre_fr(l["ecart_moyen"])]
            ligne += [_nombre_fr(par_nom[nom]["valeur"], 3) if nom in par_nom else "" for nom in noms]
            ligne += [par_nom[nom]["prediction"] if nom in par_nom else "" for nom in noms]
            if avec_future:
                p = l["plus_proche"]
                ligne += ["" if l["future"] is None else l["future"],
                          len(l["trouves"]) if l["cible"] is not None else "",
                          ", ".join(e["nom"] for e in l["trouves"]),
                          ecart_fr(p["ecart"]) if p else "", p["nom"] if p else ""]
                ligne += [ecart_fr(par_nom[nom]["ecart"]) if nom in par_nom else "" for nom in noms]
            w.writerow(ligne + [remarque_glissant(l)])
