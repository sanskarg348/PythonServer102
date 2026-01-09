import numpy as np
from scipy.stats import zscore
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans


def generate_recommendations(df):
    recs = []

    for _, row in df.iterrows():
        if abs(row.qty_z) > 2.5:
            recs.append({
                "operation_id": row.operation_id,
                "type": "PLANNED_QTY_MISMATCH",
                "confidence": "HIGH",
                "reason": "Actual material usage deviates significantly"
            })

        if row.high_failure:
            recs.append({
                "operation_id": row.operation_id,
                "type": "HIGH_FAILURE_RATE",
                "confidence": "MEDIUM",
                "reason": "Operation fails frequently relative to executions"
            })

    return recs


def run_numeric_analysis(df):
    df["qty_delta"] = df["material_qty"] - df["planned_qty"]
    df["duration_delta"] = df["actual_duration"] - df["planned_duration"]

    df["qty_z"] = zscore(df["qty_delta"].fillna(0))
    df["duration_z"] = zscore(df["duration_delta"].fillna(0))

    return df


def run_frequency_analysis(df):
    df["failure_rate"] = df["failure_count"] / df["frequency"].replace(0, 1)

    df["high_failure"] = df["failure_rate"] > df["failure_rate"].quantile(0.75)

    return df


def run_text_analysis(df):
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(df["operation_desc"].tolist())

    kmeans = KMeans(n_clusters=5, random_state=42)
    df["text_cluster"] = kmeans.fit_predict(embeddings)

    return df


