import numpy as np


def cosine_similarity(vec1, vc2):
    vec1 = np.array(vec1)
    vec2 = np.array(vc2)

    return np.dot(vec1, vec2) / (
            np.linalg.norm(vec1) * np.linalg.norm(vec2)
    )


def top_k_similar(query_vec, vectors, texts, k=3):
    scores = []

    for i, vec in enumerate(vectors):
        score = cosine_similarity(query_vec, vec)
        scores.append((score, texts[i]))

    scores.sort(reverse=True, key=lambda x: x[0])

    return [text for _, text in scores[:k]]
