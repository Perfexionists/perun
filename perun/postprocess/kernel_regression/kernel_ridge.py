import numpy as np

from sklearn.metrics.pairwise import pairwise_kernels
from sklearn.base import BaseEstimator, RegressorMixin


class KernelRidge(BaseEstimator, RegressorMixin):
    def __init__(self, kernel="rbf", gamma=None):
        self.x_pts = []
        self.y_pts = []
        self.kernel = kernel
        self.gamma = gamma

    def fit(self, x_pts, y_pts):
        self.x_pts = x_pts
        self.y_pts = y_pts

        if hasattr(self.gamma, "__iter__"):
            self.gamma = self._optimize_gamma(self.gamma)

        return self

    def predict(self, x_pts):
        kernel = pairwise_kernels(self.x_pts, x_pts, metric=self.kernel, gamma=self.gamma)
        return (kernel * self.y_pts[:, None]).sum(axis=0) / kernel.sum(axis=0)

    def _optimize_gamma(self, gamma_values):
        mse = np.empty_like(gamma_values, dtype=np.float)
        for i, gamma in enumerate(gamma_values):
            kernel = pairwise_kernels(self.x_pts, self.x_pts, metric=self.kernel, gamma=gamma)
            np.fill_diagonal(kernel, 0)
            kernel_y = kernel * self.y_pts[:, np.newaxis]
            y_pred = kernel_y.sum(axis=0) / kernel.sum(axis=0)
            mse[i] = ((y_pred - self.y_pts) ** 2).mean()

        return gamma_values[np.nanargmin(mse)]
