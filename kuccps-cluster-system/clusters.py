import math

# -------------------------------
# GRADE POINTS
# -------------------------------
GRADE_POINTS = {
    "A":12, "A-":11, "B+":10, "B":9, "B-":8,
    "C+":7, "C":6, "C-":5,
    "D+":4, "D":3, "D-":2, "E":1
}

# -------------------------------
# SUBJECT GROUPS (CODES)
# -------------------------------
G1 = ["ENG","KIS","MAT"]
G2 = ["BIO","CHE","PHY","GSC"]
G3 = ["HAG","GEO","CRE","IRE","HRE"]
G4 = ["CMP","AGR","ARD","HSC"]
G5 = ["BST","FRE","GER","MUS","ARB"]

ALL = G1 + G2 + G3 + G4 + G5

# -------------------------------
# HELPERS
# -------------------------------

def best(scores, subjects):
    return max([scores.get(s,0) for s in subjects], default=0)

def nth_best(scores, subjects, n):
    vals = sorted([scores[s] for s in subjects if s in scores], reverse=True)
    return vals[n-1] if len(vals) >= n else 0

def top7_total(scores):
    vals = sorted(scores.values(), reverse=True)
    return sum(vals[:7]) if len(vals) >= 7 else 0

def cluster_formula(r, t):
    return round(math.sqrt((r/48)*(t/84))*48*0.94, 3)

# -------------------------------
# MAIN ENGINE
# -------------------------------

def compute_cluster(cluster, raw_grades):

    # convert grades → points
    scores = {}
    for s,g in raw_grades.items():
        if g in GRADE_POINTS:
            scores[s] = GRADE_POINTS[g]

    if len(scores) < 7:
        return 0.0

    T = top7_total(scores)

    def fail(): return 0.0

    # ---------------- CLUSTERS ----------------

    if cluster == 1:
        if not ("ENG" in scores or "KIS" in scores): return fail()
        r = best(scores,["ENG","KIS"]) \
          + max(scores.get("MAT",0), best(scores,G2)) \
          + best(scores,G3) \
          + max(best(scores,G2), nth_best(scores,G3,2), best(scores,G4), best(scores,G5))

    elif cluster == 2:
        if not ("ENG" in scores or "KIS" in scores): return fail()
        r = best(scores,["ENG","KIS"]) \
          + scores.get("MAT",0) \
          + max(best(scores,G2), best(scores,G3)) \
          + max(best(scores,G2), best(scores,G3), best(scores,G4), best(scores,G5))

    elif cluster == 3:
        if not ("ENG" in scores or "KIS" in scores): return fail()
        r = best(scores,["ENG","KIS"]) \
          + max(scores.get("MAT",0), best(scores,G2)) \
          + best(scores,G3) \
          + max(best(scores,G2), nth_best(scores,G3,2), best(scores,G4), best(scores,G5))

    elif cluster == 4:
        if not ("MAT" in scores and "PHY" in scores): return fail()
        r = scores["MAT"] + scores["PHY"] \
          + max(scores.get("BIO",0), scores.get("CHE",0), scores.get("GEO",0)) \
          + max(best(scores,G2), best(scores,G3), best(scores,G4), best(scores,G5))

    elif cluster == 5:
        if not ("MAT" in scores and "PHY" in scores and "CHE" in scores): return fail()
        r = scores["MAT"] + scores["PHY"] + scores["CHE"] \
          + max(scores.get("BIO",0), best(scores,G3), best(scores,G4), best(scores,G5))

    elif cluster == 6:
        if not ("MAT" in scores and "PHY" in scores): return fail()
        r = scores["MAT"] + scores["PHY"] \
          + best(scores,G3) \
          + max(nth_best(scores,G2,2), nth_best(scores,G3,2), best(scores,G4), best(scores,G5))

    elif cluster == 7:
        if not ("MAT" in scores and "PHY" in scores): return fail()
        r = scores["MAT"] + scores["PHY"] \
          + max(nth_best(scores,G2,2), best(scores,G3)) \
          + max(best(scores,G2), best(scores,G3), best(scores,G4), best(scores,G5))

    elif cluster == 8:
        if not ("MAT" in scores and "BIO" in scores): return fail()
        r = scores["MAT"] + scores["BIO"] \
          + max(scores.get("PHY",0), scores.get("CHE",0)) \
          + max(nth_best(scores,G2,3), best(scores,G3), best(scores,G4), best(scores,G5))

    elif cluster == 9:
        if not "MAT" in scores: return fail()
        r = scores["MAT"] \
          + best(scores,G2) \
          + nth_best(scores,G2,2) \
          + max(nth_best(scores,G2,3), best(scores,G3), best(scores,G4), best(scores,G5))

    elif cluster == 10:
        if not "MAT" in scores: return fail()
        r = scores["MAT"] \
          + best(scores,G2) \
          + best(scores,G3) \
          + max(nth_best(scores,G2,2), nth_best(scores,G3,2), best(scores,G4), best(scores,G5))

    elif cluster == 11:
        r = max(
            scores.get("CHE",0) + max(scores.get("MAT",0),scores.get("PHY",0)) +
            max(scores.get("BIO",0),scores.get("HSC",0)) +
            max(best(scores,["ENG","KIS"]),best(scores,G3),best(scores,G4),best(scores,G5)),

            max(scores.get("BIO",0),scores.get("GSC",0)) + scores.get("MAT",0) +
            max(best(scores,G2),best(scores,G3)) +
            max(best(scores,["ENG","KIS"]),best(scores,G2),best(scores,G3),best(scores,G4),best(scores,G5))
        )

    elif cluster in [12,13]:
        if not ("BIO" in scores and "CHE" in scores): return fail()
        r = scores["BIO"] + scores["CHE"] \
          + max(scores.get("MAT",0), scores.get("PHY",0)) \
          + max(best(scores,["ENG","KIS"]), nth_best(scores,G2,3), best(scores,G3), best(scores,G4), best(scores,G5))

    elif cluster == 14:
        if not "CHE" in scores: return fail()
        r = max(scores.get("BIO",0),scores.get("AGR",0),scores.get("HSC",0)) \
          + scores["CHE"] \
          + max(scores.get("MAT",0),scores.get("PHY",0),scores.get("GEO",0)) \
          + max(best(scores,["ENG","KIS"]), best(scores,G3), best(scores,G4), best(scores,G5))

    elif cluster == 15:
        if not ("BIO" in scores and "CHE" in scores): return fail()
        r = scores["BIO"] + scores["CHE"] \
          + max(scores.get("MAT",0),scores.get("PHY",0),scores.get("AGR",0)) \
          + max(best(scores,["ENG","KIS"]), best(scores,G3), best(scores,G4), best(scores,G5))

    elif cluster == 16:
        if not "GEO" in scores: return fail()
        r = scores["GEO"] \
          + scores.get("MAT",0) \
          + best(scores,G2) \
          + max(nth_best(scores,G2,2), nth_best(scores,G3,2), best(scores,G4), best(scores,G5))

    elif cluster == 17:
        if not ("FRE" in scores or "GER" in scores): return fail()
        r = best(scores,["FRE","GER"]) \
          + best(scores,["ENG","KIS"]) \
          + max(scores.get("MAT",0),best(scores,G2),best(scores,G3)) \
          + max(best(scores,G2),best(scores,G3),best(scores,G4),nth_best(scores,G5,2))

    elif cluster == 18:
        if not "MUS" in scores: return fail()
        r = scores["MUS"] \
          + best(scores,["ENG","KIS"]) \
          + max(scores.get("MAT",0),best(scores,G2),best(scores,G3)) \
          + max(best(scores,G2),best(scores,G3),best(scores,G4),nth_best(scores,G5,2))

    elif cluster == 19:
        r = best(scores,ALL) \
          + nth_best(scores,ALL,2) \
          + nth_best(scores,ALL,3) \
          + nth_best(scores,ALL,4)

    elif cluster == 20:
        if not (scores.get("CRE") or scores.get("IRE") or scores.get("HRE")):
            return fail()
        r = best(scores,["CRE","IRE","HRE"]) \
          + best(scores,["ENG","KIS"]) \
          + nth_best(scores,G3,2) \
          + max(best(scores,G2),best(scores,G4),best(scores,G5))

    else:
        return fail()

    return cluster_formula(r,T)

# -------------------------------
# MEDICINE ELIGIBILITY
# -------------------------------

def medicine_eligibility(grades):
    needed = ["BIO","CHE","MAT","PHY"]
    return all(s in grades and grades[s] in GRADE_POINTS for s in needed)
