from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

_embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


def embed_texts(texts):
    return _embedding_model.encode(texts, normalize_embeddings=True)


def cluster_by_similarity(texts, threshold=0.8):
    """
    Groups texts by semantic similarity.
    Returns list of clusters (each cluster is list of indices).
    """
    embeddings = embed_texts(texts)
    sim_matrix = cosine_similarity(embeddings)

    clusters = []
    used = set()

    for i in range(len(texts)):
        if i in used:
            continue

        cluster = [i]
        used.add(i)

        for j in range(i + 1, len(texts)):
            if j not in used and sim_matrix[i][j] >= threshold:
                cluster.append(j)
                used.add(j)

        clusters.append(cluster)

    return clusters