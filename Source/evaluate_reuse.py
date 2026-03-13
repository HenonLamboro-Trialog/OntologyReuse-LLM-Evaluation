import rdflib
import pandas as pd
from owlready2 import *
from pathlib import Path

# -----------------------------
# Utility Functions
# -----------------------------

def load_graph(file_path):
    g = rdflib.Graph()
    g.parse(file_path)
    return g

def normalize(uri):
    return str(uri).split("/")[-1].split("#")[-1].lower()


# -----------------------------
# Extraction Functions
# -----------------------------

def extract_terms(g):
    """T : class and property labels"""
    terms = set()

    for s, p, o in g:
        if "label" in str(p):
            terms.add(str(o).lower())

    return terms


def extract_hierarchy(g):
    """H : subclass pairs"""
    H = set()
    for s, p, o in g.triples((None, rdflib.RDFS.subClassOf, None)):
        H.add((normalize(s), normalize(o)))
    return H


def extract_property_patterns(g):
    """P : (property, domain, range) triples"""
    P = set()

    for prop in g.subjects(rdflib.RDF.type, rdflib.OWL.ObjectProperty):

        domain = None
        range_ = None

        for _, _, d in g.triples((prop, rdflib.RDFS.domain, None)):
            domain = normalize(d)

        for _, _, r in g.triples((prop, rdflib.RDFS.range, None)):
            range_ = normalize(r)

        if domain and range_:
            P.add((normalize(prop), domain, range_))

    return P


def extract_subsumption(g):
    """S : subclass relations"""
    S = set()

    for s, p, o in g.triples((None, rdflib.RDFS.subClassOf, None)):
        S.add((normalize(s), normalize(o)))

    return S


def extract_constraints(g):
    """C : OWL restrictions"""
    C = set()

    for s, p, o in g.triples((None, rdflib.RDF.type, rdflib.OWL.Restriction)):
        C.add(normalize(s))

    return C


# -----------------------------
# Reuse Calculation
# -----------------------------

def reuse_score(ref_set, gen_set):
    if len(ref_set) == 0:
        return 0
    return len(ref_set.intersection(gen_set)) / len(ref_set)


# -----------------------------
# Logical Validity
# -----------------------------

def check_logical_validity(ontology_path):
    try:
        onto = get_ontology(str(ontology_path)).load()
        sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)
        return 1
    except:
        return 0


# -----------------------------
# Evaluation Function
# -----------------------------

def evaluate(reference_file, generated_file,
             alpha=0.5,
             gamma=(0.2,0.3,0.3,0.2)):

    g_ref = load_graph(reference_file)
    g_gen = load_graph(generated_file)

    # Extract components
    T_r, T_g = extract_terms(g_ref), extract_terms(g_gen)
    H_r, H_g = extract_hierarchy(g_ref), extract_hierarchy(g_gen)
    P_r, P_g = extract_property_patterns(g_ref), extract_property_patterns(g_gen)
    S_r, S_g = extract_subsumption(g_ref), extract_subsumption(g_gen)
    C_r, C_g = extract_constraints(g_ref), extract_constraints(g_gen)

    # Metrics
    LR = reuse_score(T_r, T_g)

    SR = alpha * reuse_score(H_r, H_g) + (1-alpha) * reuse_score(P_r, P_g)

    SA = reuse_score(S_r, S_g)

    LC = reuse_score(C_r, C_g) * check_logical_validity(generated_file)

    g1,g2,g3,g4 = gamma

    RD = g1*LR + g2*SR + g3*SA + g4*LC

    return {
        "LR":LR,
        "SR":SR,
        "SA":SA,
        "LC":LC,
        "RD":RD
    }


# -----------------------------
# Batch Evaluation
# -----------------------------

def run_batch(reference, generated_folder):

    import os
    os.makedirs("results", exist_ok=True)

    rows = []

    for file in Path(generated_folder).glob("*.ttl"):

        scores = evaluate(reference, file)

        scores["ontology"] = file.name

        rows.append(scores)

    df = pd.DataFrame(rows)

    df.to_csv("results/reuse_scores.csv", index=False)

    print(df)


if __name__ == "__main__":

    run_batch(
        "data/reference/fiesta.owl",
        "data/generated2/"
    )