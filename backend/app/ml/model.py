"""
A small, dependency-free logistic regression: standardize -> gradient
descent with L2 regularization -> sigmoid.

Why not scikit-learn: section 9 asks for "logistic regression for
interpretable probabilities" — that's a description of the model class, not
a mandate for a specific library. At the sample sizes a single user's own
logged history produces (tens to low hundreds of rows, per prediction_type),
a hand-rolled implementation trains in milliseconds and has zero build/wheel
concerns for whoever deploys this (no compiled dependency, no version
pinning against numpy/scipy ABI). If a future phase needs a genuinely
nonlinear model (section 9 also mentions random forest / gradient boosting
"for nonlinear tabular behavior"), that's the point to add scikit-learn as a
real dependency — introducing it now for a linear model this size would be
solving a problem this app doesn't have yet.

Every function here is pure and stateless: no hidden global model, nothing
cached. app/services/prediction_service.py owns persistence (ModelVersion
rows); this module only does the math.
"""
import math

Row = list[float]


def sigmoid(z: float) -> float:
    """Numerically stable logistic function."""
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def fit_standardizer(rows: list[Row]) -> tuple[list[float], list[float]]:
    """Per-feature mean/std over the training set. A zero-variance feature
    gets std=1.0 (not 0) so dividing by it doesn't blow up — it just
    contributes a constant, uninformative term, which is the correct
    behavior for a feature that never varies in this user's data yet."""
    n = len(rows)
    n_features = len(rows[0])
    means = [sum(row[i] for row in rows) / n for i in range(n_features)]
    stds: list[float] = []
    for i in range(n_features):
        variance = sum((row[i] - means[i]) ** 2 for row in rows) / n
        std = math.sqrt(variance)
        stds.append(std if std > 1e-9 else 1.0)
    return means, stds


def apply_standardizer(row: Row, means: list[float], stds: list[float]) -> Row:
    return [(x - m) / s for x, m, s in zip(row, means, stds)]


def train(
    x_rows: list[Row],
    labels: list[int],
    *,
    learning_rate: float = 0.3,
    epochs: int = 400,
    l2: float = 0.05,
) -> tuple[list[float], float]:
    """Batch gradient descent on standardized features. Returns
    (weights, bias). Caller is responsible for standardizing x_rows first
    (see fit_standardizer/apply_standardizer) and for deciding whether there
    are even enough samples to bother calling this at all — see
    prediction_service.CONFIDENCE thresholds; this function will happily
    (and uselessly) "train" on 2 rows if asked."""
    n = len(x_rows)
    n_features = len(x_rows[0])
    weights = [0.0] * n_features
    bias = 0.0

    for _ in range(epochs):
        grad_w = [0.0] * n_features
        grad_b = 0.0
        for row, label in zip(x_rows, labels):
            z = bias + sum(w * x for w, x in zip(weights, row))
            error = sigmoid(z) - label
            for j in range(n_features):
                grad_w[j] += error * row[j]
            grad_b += error
        for j in range(n_features):
            # L2 term regularizes toward 0, which matters here specifically
            # because personal datasets are small enough to overfit fast.
            grad_w[j] = grad_w[j] / n + l2 * weights[j]
            weights[j] -= learning_rate * grad_w[j]
        bias -= learning_rate * (grad_b / n)

    return weights, bias


def predict_proba(weights: list[float], bias: float, row: Row) -> float:
    z = bias + sum(w * x for w, x in zip(weights, row))
    return sigmoid(z)


def training_accuracy(weights: list[float], bias: float, x_rows: list[Row], labels: list[int]) -> float:
    """Accuracy at the 0.5 decision threshold, on the same rows the model
    was trained on. Deliberately labeled "training_accuracy" everywhere it's
    surfaced (ModelVersion.training_accuracy) — never presented as
    held-out/generalization performance, since at these sample sizes there
    usually isn't enough data left over for a meaningful test split."""
    if not labels:
        return 0.0
    correct = sum(
        1 for row, label in zip(x_rows, labels) if (predict_proba(weights, bias, row) >= 0.5) == bool(label)
    )
    return correct / len(labels)
