import pandas as pd
import scipy.stats as stats
from numba import jit
import numpy as np


# Function to quantile normalize a pandas DataFrame
# Code taken from: https://github.com/ShawnLYU/Quantile_Normalize/blob/master/quantile_norm.py
# Using implementation described on Wikipedia: https://en.wikipedia.org/wiki/Quantile_normalization
# data: Pandas DataFrame (propagated genotypes) where rows are samples (samples), and columns are features (genes)
# Returns df_out: Quantile normalized Pandas DataFrame with same orientation as data df
def qnorm(data):
    df = data.T
    df_out = df.copy(deep=True)
    dic = {}

    # Sort each patient by gene propagation value
    for col in df:
        dic.update({col:sorted(df[col])})
    sorted_df = pd.DataFrame(dic)

    # Rank averages for each gene across samples
    ranked_avgs = sorted_df.mean(axis = 1).tolist()

    # Construct quantile normalized Pandas DataFrame by assigning ranked averages to ranks of each gene for each sample
    for col in df_out:
        t = stats.rankdata(df[col]).astype(int)
        df_out[col] = [ranked_avgs[i-1] for i in t]
    return df_out.T

# Network-regularized non-negative matrix factorization
# Cai et al 2008. Proceedings - 8th IEEE International Conference on Data Mining, ICDM 2008
# http://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=4781101
# X = np.float64 numpy array of patients-by-genes data
# A = np.float64 numpy array of binary graph adjacency matrix (for regularization)
# D = np.float64 numpy array of rol/col sums of A on diagonal (for regularization)
# k = number of clusters in factorization
# gamma = regularization constant
# tol = minimum error tolerance needed to break NMF update loop
# max_iter = maximum number of NMF update iterations to run
@jit(nopython=True)
def netNMF(X, A, D, k, gamma=1, tol=1e-8, max_iter=10):
    # Get dimensions
    n_samples = X.shape[0]
    n_features = X.shape[1]
    # Initialize W, H 
    U = np.random.normal(0, 1, (n_samples, k))**2   # Equivalent to W in most represenatations of NMF
    V = np.random.normal(0, 1, (n_features, k))**2  # Equivalent to H.T in most represenatations of NMF
    # Initialize reconstruction error
    reconstruction_err = np.linalg.norm(X-np.dot(U, V.T))
    # Iterative multiplicative update
    for n_iter in np.arange(max_iter):
        # Update U
        u1 = np.dot(X, V)
        u2 = np.dot(U, np.dot(V.T, V))
        U = U*(u1/u2)
        # Update V
        v1 = np.dot(X.T, U)+gamma*np.dot(A,V)
        v2 = np.dot(V, np.dot(U.T, U))+gamma*np.dot(D,V)
        V = V*((v1)/(v2))    
        # Update reconstruction error
        reconstruction_err = np.linalg.norm(X - np.dot(U, V.T))
        if reconstruction_err < tol:
            break
        if n_iter == max_iter-1:
            break
    return U, V, n_iter+1, reconstruction_err


# Perform network regularized NMF for clustering
# Code adapated from github GHFC/stratipy
# data = numpy array of patients-by-genes
# graph_laplacian = numpy array of D-A, A: adjacency matrix, D: Sum of row degree (of A) on diagonal
# k = number of clusters in factorization
# gamma = regularization constant
@jit(nopython=True)
def netNMF_stratipy(data, graph_laplacian, k, gamma=2, tol=1e-8, max_iter=100, verbose=False):
    n_samples = data.shape[0]
    n_features = data.shape[1]
    # Initialize W, H 
    W = np.random.normal(0, 1, (n_samples, k))**2
    H = np.random.normal(0, 1, (k, n_features))**2
    # Initialize reconstruction error
    reconstruction_err_ = np.linalg.norm(data-np.dot(W, H))
    # Default Matlab epsilon
    eps = 2**(-52)
    # Internal Laplacian transformations
    Lp = (np.absolute(graph_laplacian)+graph_laplacian) / 2
    Lm = (np.absolute(graph_laplacian)-graph_laplacian) / 2

    # Iterative multiplicative update
    for n_iter in np.arange(1, max_iter + 1):
        # Update H
        h1 = gamma*np.dot(H,Lm)+np.dot(W.T,(data)/(np.dot(W,H)))
        h2 = gamma*np.dot(H,Lp)+np.dot(W.T,np.ones(data.shape).astype(np.float64))
        H = H*((h1)/(h2))
        # Protect against divide by 0 in updating H
        for i in np.arange(H.shape[0]):
            for j in np.arange(H.shape[1]):
                if H[i,j]<=0:
                    H[i,j]=eps
                if np.isnan(H[i,j]):
                    H[i,j]=eps
        # Update W
        w1 = np.dot((data)/(np.dot(W,H)),H.T)
        w2 = np.dot(np.ones(data.shape).astype(np.float64),H.T)
        W = W*((w1)/(w2))
        # Protect against divide by 0 in updating W
        for i in np.arange(W.shape[0]):
            for j in np.arange(W.shape[1]):
                if W[i,j]<=0:
                    W[i,j]=eps
                if np.isnan(W[i,j]):
                    W[i,j]=eps			

        # Update reconstruction error
        reconstruction_err_ = np.linalg.norm(data - np.dot(W, H))		
        if reconstruction_err_ < tol:
            break
        if n_iter == max_iter:
            break
    return W, H, n_iter, reconstruction_err_