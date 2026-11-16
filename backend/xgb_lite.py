"""
xgb_lite.py  -  run a saved XGBoost model (.json) with only numpy.

Why: if the `xgboost` / `catboost` packages are not installed on a computer, the AQI forecast
must still work.  XGBoost saves its trees as plain JSON, so we can evaluate them directly.
(Supports the regression models trained by ml/train_models.py: gbtree, reg:squarederror.)
Results are identical to xgboost's own predict().
"""

import json

import numpy as np


class XGBLite:
    def __init__(self, path):
        with open(path) as fh:
            model = json.load(fh)
        learner = model["learner"]
        if learner["objective"]["name"] != "reg:squarederror":
            raise ValueError("XGBLite only supports reg:squarederror models")
        raw = str(learner["learner_model_param"]["base_score"]).strip("[] ")
        self.base_score = float(raw)
        self.n_features = int(learner["learner_model_param"]["num_feature"])
        self.trees = []
        for t in learner["gradient_booster"]["model"]["trees"]:
            self.trees.append((
                np.asarray(t["left_children"], dtype=np.int32),
                np.asarray(t["right_children"], dtype=np.int32),
                np.asarray(t["split_indices"], dtype=np.int32),
                np.asarray(t["split_conditions"], dtype=np.float32),   # leaf value for leaf nodes
                np.asarray(t["default_left"], dtype=bool),
            ))

    def predict(self, X):
        X = np.asarray(X, dtype=np.float32)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        n = X.shape[0]
        rows = np.arange(n)
        total = np.full(n, self.base_score, dtype=np.float64)
        for left, right, feat, cond, dleft in self.trees:
            node = np.zeros(n, dtype=np.int32)
            while True:
                lc = left[node]
                active = lc != -1
                if not active.any():
                    break
                x = X[rows, feat[node]]
                go_left = np.where(np.isnan(x), dleft[node], x < cond[node])
                nxt = np.where(go_left, lc, right[node])
                node = np.where(active, nxt, node)
            total += cond[node]
        return total
