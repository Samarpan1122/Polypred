"""Traditional ML wrappers - from sabya1 & BL_rd_kit_test notebooks.

Covers: Decision Tree, Random Forest, Gradient Boosting, XGBoost,
        Extra Trees, AdaBoost, Ridge, Lasso, ElasticNet, KNN, SVM,
        Linear Regression, RF Classifier.

All models are stored as joblib files and loaded at runtime.
"""

from __future__ import annotations
import joblib
import numpy as np
from pathlib import Path
from typing import Any

from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import (
    RandomForestRegressor,
    GradientBoostingRegressor,
    ExtraTreesRegressor,
    AdaBoostRegressor,
    RandomForestClassifier,
)
from sklearn.linear_model import LinearRegression, Ridge, Lasso, ElasticNet
from sklearn.neighbors import KNeighborsRegressor
from sklearn.svm import SVR

try:
    from xgboost import XGBRegressor
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

# Registry of sklearn model constructors
SKLEARN_MODELS: dict[str, type] = {
    "decision_tree": DecisionTreeRegressor,
    "random_forest": RandomForestRegressor,
    "gradient_boosting": GradientBoostingRegressor,
    "extra_trees": ExtraTreesRegressor,
    "adaboost": AdaBoostRegressor,
    "linear_regression": LinearRegression,
    "ridge": Ridge,
    "lasso": Lasso,
    "elasticnet": ElasticNet,
    "knn": KNeighborsRegressor,
    "svm": SVR,
    "rf_classifier": RandomForestClassifier,
}
if HAS_XGB:
    SKLEARN_MODELS["xgboost"] = XGBRegressor


class TraditionalModelWrapper:
    """Unified interface for all sklearn / xgboost models.

    Each traditional model is actually a *pair* of models:
      model_r1 predicts r₁
      model_r2 predicts r₂
    stored as {name}_r1.joblib and {name}_r2.joblib
    """

    def __init__(self, model_r1: Any, model_r2: Any, name: str = ""):
        self.model_r1 = model_r1
        self.model_r2 = model_r2
        self.name = name

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Return shape (n, 2) - [r₁, r₂] predictions."""
        r1 = np.asarray(self.model_r1.predict(X)).reshape(-1, 1)
        r2 = np.asarray(self.model_r2.predict(X)).reshape(-1, 1)
        return np.hstack([r1, r2])

    @classmethod
    def load(cls, path_r1: str | Path, path_r2: str | Path, name: str = "") -> "TraditionalModelWrapper":
        m1 = joblib.load(path_r1)
        m2 = joblib.load(path_r2)
        return cls(m1, m2, name=name)


def build_default_model(name: str, **kwargs) -> Any:
    """Create a fresh sklearn model instance with good defaults from notebooks."""
    defaults: dict[str, dict] = {
        "decision_tree": {"max_depth": 10, "min_samples_split": 5},
        "random_forest": {"n_estimators": 200, "max_depth": 15, "n_jobs": -1},
        "gradient_boosting": {"n_estimators": 200, "max_depth": 5, "learning_rate": 0.1},
        "extra_trees": {"n_estimators": 200, "max_depth": 15, "n_jobs": -1},
        "adaboost": {"n_estimators": 100, "learning_rate": 0.1},
        "linear_regression": {},
        "ridge": {"alpha": 1.0},
        "lasso": {"alpha": 0.01},
        "elasticnet": {"alpha": 0.01, "l1_ratio": 0.5},
        "knn": {"n_neighbors": 5},
        "svm": {"kernel": "rbf", "C": 10.0, "gamma": "scale"},
        "rf_classifier": {"n_estimators": 200, "max_depth": 15, "n_jobs": -1},
    }
    if HAS_XGB:
        defaults["xgboost"] = {"n_estimators": 200, "max_depth": 5, "learning_rate": 0.1}

    params = {**defaults.get(name, {}), **kwargs}
    return SKLEARN_MODELS[name](**params)
