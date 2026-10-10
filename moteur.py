"""Moteur de modélisation et de prédiction pour les suites de nombres de 1 à 49.

Principe
--------
1. La suite brute u(0..n-1) est "dépliée" : chaque saut u(i) - u(i-1) est ramené
   modulo 50 dans l'intervalle [-24, 25], puis cumulé. On obtient ainsi une courbe
   continue qui représente la fonction d'évolution sans les retours à 1.
2. Plusieurs modèles sont ajustés sur cette courbe dépliée.
3. Chaque modèle est évalué par validation glissante (on le refait sur le début de la
   suite et on compare sa prédiction à la valeur réellement observée ensuite).
4. La prédiction est ramenée dans l'intervalle par MOD 50. Le résultat 0 n'étant pas
   admis, un 0 est remplacé par 1 (on passe à la valeur suivante du cycle).
"""

import csv
import io

import numpy as np

MODULO = 50
VAL_MIN, VAL_MAX = 1, 49


def mod50(x):
    """Ramène un nombre réel dans 1..49 avec la règle MOD 50 (0 interdit -> 1)."""
    r = int(round(x)) % MODULO
    return 1 if r == 0 else r


def ecart_circulaire(a, b):
    """Distance entre deux valeurs sur le cycle MOD 50 (0 à 25)."""
    d = abs(int(a) - int(b)) % MODULO
    return min(d, MODULO - d)


def deplier(valeurs):
    """Transforme la suite brute en courbe continue (sauts ramenés dans [-24, 25])."""
    out = [float(valeurs[0])]
    for prec, cour in zip(valeurs, valeurs[1:]):
        saut = (cour - prec) % MODULO
        if saut > MODULO // 2:
            saut -= MODULO
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


MODELES = [
    ("Régression linéaire", modele_lineaire, 2),
    ("Régression quadratique", modele_quadratique, 3),
    ("Saut moyen", modele_saut_moyen, 2),
    ("Dernier saut répété", modele_dernier_saut, 2),
    ("Récurrence u(n+1)=a·u(n)+b", modele_recurrence, 3),
]


def evaluer(fonction, valeurs, minimum):
    """Erreur moyenne (sur le cycle) des prédictions faites pas à pas sur l'historique."""
    erreurs = []
    debut = max(minimum, 3)
    for k in range(debut, len(valeurs)):
        y = deplier(valeurs[:k])
        try:
            _, p = fonction(y)
        except (np.linalg.LinAlgError, ValueError):
            continue
        if np.isfinite(p):
            erreurs.append(ecart_circulaire(mod50(p), valeurs[k]))
    return (float(np.mean(erreurs)), len(erreurs)) if erreurs else (float("nan"), 0)


def analyser(valeurs):
    """Analyse complète. Renvoie un dict avec la courbe dépliée, les modèles et le meilleur."""
    if len(valeurs) < 3:
        raise ValueError("Il faut au moins 3 nombres pour modéliser la suite.")
    y = deplier(valeurs)
    resultats = []
    for nom, fonction, minimum in MODELES:
        if len(valeurs) < minimum:
            continue
        try:
            ajust, p = fonction(y)
        except (np.linalg.LinAlgError, ValueError):
            continue
        if not np.isfinite(p):
            continue
        erreur, nb = evaluer(fonction, valeurs, minimum)
        resultats.append({
            "nom": nom,
            "ajustement": ajust,
            "prediction_brute": p,
            "prediction": mod50(p),
            "erreur": erreur,
            "nb_tests": nb,
        })
    if not resultats:
        raise ValueError("Aucun modèle n'a pu être ajusté sur ces données.")
    testes = [r for r in resultats if r["nb_tests"] > 0]
    meilleur = min(testes, key=lambda r: r["erreur"]) if testes else resultats[0]
    return {"valeurs": list(valeurs), "deplie": y, "modeles": resultats, "meilleur": meilleur}


# --------------------------------------------------------------------------- CSV
def lire_csv(chemin):
    """Lit la colonne A d'un fichier CSV. Renvoie (valeurs, avertissements)."""
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
        if v != int(v) or not VAL_MIN <= v <= VAL_MAX:
            avertissements.append(f"Ligne {num} ignorée : {ligne[0]} n'est pas un entier entre 1 et 49.")
            continue
        valeurs.append(int(v))
    return valeurs, avertissements
