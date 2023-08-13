import os
import networkx as nx
import numpy as np
import navis
import scipy.sparse as sparse
import h5py
import tifffile as tf
from connectomics.utils.run_length import expected_run_length
from scipy import ndimage

__all__ = [
    'get_binary_jaccard',
]

from sklearn.decomposition import PCA


def adapted_rand(seg, gt, all_stats=False):
    """Compute Adapted Rand error as defined by the SNEMI3D contest [1]

    Formula is given as 1 - the maximal F-score of the Rand index 
    (excluding the zero component of the original labels). Adapted 
    from the SNEMI3D MATLAB script, hence the strange style.

    Parameters
    ----------
    seg : np.ndarray
        the segmentation to score, where each value is the label at that point
    gt : np.ndarray, same shape as seg
        the groundtruth to score against, where each value is a label
    all_stats : boolean, optional
        whether to also return precision and recall as a 3-tuple with rand_error

    Returns
    -------
    are : float
        The adapted Rand error; equal to $1 - \frac{2pr}{p + r}$,
        where $p$ and $r$ are the precision and recall described below.
    prec : float, optional
        The adapted Rand precision. (Only returned when `all_stats` is ``True``.)
    rec : float, optional
        The adapted Rand recall.  (Only returned when `all_stats` is ``True``.)

    References
    ----------
    [1]: http://brainiac2.mit.edu/SNEMI3D/evaluation
    """
    # segA is truth, segB is query
    segA = np.ravel(gt)
    segB = np.ravel(seg)
    n = segA.size

    n_labels_A = np.amax(segA) + 1
    n_labels_B = np.amax(segB) + 1

    ones_data = np.ones(n, int)

    p_ij = sparse.csr_matrix(
        (ones_data, (segA[:], segB[:])), shape=(n_labels_A, n_labels_B))

    a = p_ij[1:n_labels_A, :]
    b = p_ij[1:n_labels_A, 1:n_labels_B]
    c = p_ij[1:n_labels_A, 0].todense()
    d = b.multiply(b)

    a_i = np.array(a.sum(1))
    b_i = np.array(b.sum(0))

    sumA = np.sum(a_i * a_i)
    sumB = np.sum(b_i * b_i) + (np.sum(c) / n)
    sumAB = np.sum(d) + (np.sum(c) / n)

    precision = sumAB / sumB
    recall = sumAB / sumA

    fScore = 2.0 * precision * recall / (precision + recall)
    are = 1.0 - fScore

    if all_stats:
        return (are, precision, recall)
    else:
        return are


# Evaluation code courtesy of Juan Nunez-Iglesias, taken from
# https://github.com/janelia-flyem/gala/blob/master/gala/evaluate.py


def voi(reconstruction, groundtruth, ignore_reconstruction=[], ignore_groundtruth=[0]):
    """Return the conditional entropies of the variation of information metric. [1]

    Let X be a reconstruction, and Y a ground truth labelling. The variation of 
    information between the two is the sum of two conditional entropies:

        VI(X, Y) = H(X|Y) + H(Y|X).

    The first one, H(X|Y), is a measure of oversegmentation, the second one, 
    H(Y|X), a measure of undersegmentation. These measures are referred to as 
    the variation of information split or merge error, respectively.

    Parameters
    ----------
    seg : np.ndarray, int type, arbitrary shape
        A candidate segmentation.
    gt : np.ndarray, int type, same shape as `seg`
        The ground truth segmentation.
    ignore_seg, ignore_gt : list of int, optional
        Any points having a label in this list are ignored in the evaluation.
        By default, only the label 0 in the ground truth will be ignored.

    Returns
    -------
    (split, merge) : float
        The variation of information split and merge error, i.e., H(X|Y) and H(Y|X)

    References
    ----------
    [1] Meila, M. (2007). Comparing clusterings - an information based 
    distance. Journal of Multivariate Analysis 98, 873-895.
    """
    (hyxg, hxgy) = split_vi(reconstruction, groundtruth,
                            ignore_reconstruction, ignore_groundtruth)
    return (hxgy, hyxg)


def split_vi(x, y=None, ignore_x=[0], ignore_y=[0]):
    """Return the symmetric conditional entropies associated with the VI.

    The variation of information is defined as VI(X,Y) = H(X|Y) + H(Y|X).
    If Y is the ground-truth segmentation, then H(Y|X) can be interpreted
    as the amount of under-segmentation of Y and H(X|Y) is then the amount
    of over-segmentation.  In other words, a perfect over-segmentation
    will have H(Y|X)=0 and a perfect under-segmentation will have H(X|Y)=0.

    If y is None, x is assumed to be a contingency table.

    Parameters
    ----------
    x : np.ndarray
        Label field (int type) or contingency table (float). `x` is
        interpreted as a contingency table (summing to 1.0) if and only if `y`
        is not provided.
    y : np.ndarray of int, same shape as x, optional
        A label field to compare to `x`.
    ignore_x, ignore_y : list of int, optional
        Any points having a label in this list are ignored in the evaluation.
        Ignore 0-labeled points by default.

    Returns
    -------
    sv : np.ndarray of float, shape (2,)
        The conditional entropies of Y|X and X|Y.

    See Also
    --------
    vi
    """
    _, _, _, hxgy, hygx, _, _ = vi_tables(x, y, ignore_x, ignore_y)
    # false merges, false splits
    return np.array([hygx.sum(), hxgy.sum()])


def vi_tables(x, y=None, ignore_x=[0], ignore_y=[0]):
    """Return probability tables used for calculating VI.

    If y is None, x is assumed to be a contingency table.

    Parameters
    ----------
    x, y : np.ndarray
        Either x and y are provided as equal-shaped np.ndarray label fields
        (int type), or y is not provided and x is a contingency table
        (sparse.csc_matrix) that may or may not sum to 1.
    ignore_x, ignore_y : list of int, optional
        Rows and columns (respectively) to ignore in the contingency table.
        These are labels that are not counted when evaluating VI.

    Returns
    -------
    pxy : sparse.csc_matrix of float
        The normalized contingency table.
    px, py, hxgy, hygx, lpygx, lpxgy : np.ndarray of float
        The proportions of each label in `x` and `y` (`px`, `py`), the
        per-segment conditional entropies of `x` given `y` and vice-versa, the
        per-segment conditional probability p log p.
    """
    if y is not None:
        pxy = contingency_table(x, y, ignore_x, ignore_y)
    else:
        cont = x
        total = float(cont.sum())
        # normalize, since it is an identity op if already done
        pxy = cont / total

    # Calculate probabilities
    px = np.array(pxy.sum(axis=1)).ravel()
    py = np.array(pxy.sum(axis=0)).ravel()
    # Remove zero rows/cols
    nzx = px.nonzero()[0]
    nzy = py.nonzero()[0]
    nzpx = px[nzx]
    nzpy = py[nzy]
    nzpxy = pxy[nzx, :][:, nzy]

    # Calculate log conditional probabilities and entropies
    lpygx = np.zeros(np.shape(px))
    lpygx[nzx] = xlogx(divide_rows(nzpxy, nzpx)).sum(axis=1).ravel()
    # \sum_x{p_{y|x} \log{p_{y|x}}}
    hygx = -(px * lpygx)  # \sum_x{p_x H(Y|X=x)} = H(Y|X)

    lpxgy = np.zeros(np.shape(py))
    lpxgy[nzy] = xlogx(divide_columns(nzpxy, nzpy)).sum(axis=0).ravel()
    hxgy = -(py * lpxgy)

    return [pxy] + list(map(np.asarray, [px, py, hxgy, hygx, lpygx, lpxgy]))


def contingency_table(seg, gt, ignore_seg=[0], ignore_gt=[0], norm=True):
    """Return the contingency table for all regions in matched segmentations.

    Parameters
    ----------
    seg : np.ndarray, int type, arbitrary shape
        A candidate segmentation.
    gt : np.ndarray, int type, same shape as `seg`
        The ground truth segmentation.
    ignore_seg : list of int, optional
        Values to ignore in `seg`. Voxels in `seg` having a value in this list
        will not contribute to the contingency table. (default: [0])
    ignore_gt : list of int, optional
        Values to ignore in `gt`. Voxels in `gt` having a value in this list
        will not contribute to the contingency table. (default: [0])
    norm : bool, optional
        Whether to normalize the table so that it sums to 1.

    Returns
    -------
    cont : scipy.sparse.csc_matrix
        A contingency table. `cont[i, j]` will equal the number of voxels
        labeled `i` in `seg` and `j` in `gt`. (Or the proportion of such voxels
        if `norm=True`.)
    """
    segr = seg.ravel()
    gtr = gt.ravel()
    ignored = np.zeros(segr.shape, np.bool)
    data = np.ones(len(gtr))
    for i in ignore_seg:
        ignored[segr == i] = True
    for j in ignore_gt:
        ignored[gtr == j] = True
    data[ignored] = 0
    cont = sparse.coo_matrix((data, (segr, gtr))).tocsc()
    if norm:
        cont /= float(cont.sum())
    return cont


def divide_columns(matrix, row, in_place=False):
    """Divide each column of `matrix` by the corresponding element in `row`.

    The result is as follows: out[i, j] = matrix[i, j] / row[j]

    Parameters
    ----------
    matrix : np.ndarray, scipy.sparse.csc_matrix or csr_matrix, shape (M, N)
        The input matrix.
    column : a 1D np.ndarray, shape (N,)
        The row dividing `matrix`.
    in_place : bool (optional, default False)
        Do the computation in-place.

    Returns
    -------
    out : same type as `matrix`
        The result of the row-wise division.
    """
    if in_place:
        out = matrix
    else:
        out = matrix.copy()
    if type(out) in [sparse.csc_matrix, sparse.csr_matrix]:
        if type(out) == sparse.csc_matrix:
            convert_to_csc = True
            out = out.tocsr()
        else:
            convert_to_csc = False
        row_repeated = np.take(row, out.indices)
        nz = out.data.nonzero()
        out.data[nz] /= row_repeated[nz]
        if convert_to_csc:
            out = out.tocsc()
    else:
        out /= row[np.newaxis, :]
    return out


def divide_rows(matrix, column, in_place=False):
    """Divide each row of `matrix` by the corresponding element in `column`.

    The result is as follows: out[i, j] = matrix[i, j] / column[i]

    Parameters
    ----------
    matrix : np.ndarray, scipy.sparse.csc_matrix or csr_matrix, shape (M, N)
        The input matrix.
    column : a 1D np.ndarray, shape (M,)
        The column dividing `matrix`.
    in_place : bool (optional, default False)
        Do the computation in-place.

    Returns
    -------
    out : same type as `matrix`
        The result of the row-wise division.
    """
    if in_place:
        out = matrix
    else:
        out = matrix.copy()
    if type(out) in [sparse.csc_matrix, sparse.csr_matrix]:
        if type(out) == sparse.csr_matrix:
            convert_to_csr = True
            out = out.tocsc()
        else:
            convert_to_csr = False
        column_repeated = np.take(column, out.indices)
        nz = out.data.nonzero()
        out.data[nz] /= column_repeated[nz]
        if convert_to_csr:
            out = out.tocsr()
    else:
        out /= column[:, np.newaxis]
    return out


def xlogx(x, out=None, in_place=False):
    """Compute x * log_2(x).

    We define 0 * log_2(0) = 0

    Parameters
    ----------
    x : np.ndarray or scipy.sparse.csc_matrix or csr_matrix
        The input array.
    out : same type as x (optional)
        If provided, use this array/matrix for the result.
    in_place : bool (optional, default False)
        Operate directly on x.

    Returns
    -------
    y : same type as x
        Result of x * log_2(x).
    """
    if in_place:
        y = x
    elif out is None:
        y = x.copy()
    else:
        y = out
    if type(y) in [sparse.csc_matrix, sparse.csr_matrix]:
        z = y.data
    else:
        z = y
    nz = z.nonzero()
    z[nz] *= np.log2(z[nz])
    return y


# Functions for evaluating binary segmentation


def confusion_matrix(pred, gt, thres=0.5):
    """Calculate the confusion matrix given a probablility threshold in (0,1).
    """
    TP = np.sum((gt == 1) & (pred > thres))
    FP = np.sum((gt == 0) & (pred > thres))
    TN = np.sum((gt == 0) & (pred <= thres))
    FN = np.sum((gt == 1) & (pred <= thres))
    return (TP, FP, TN, FN)


def get_binary_jaccard(pred, gt, thres=[0.5]):
    """Evaluate the binary prediction at multiple thresholds using the Jaccard 
    Index, which is also known as Intersection over Union (IoU). If the prediction
    is already binarized, different thresholds will result the same result.

    Args:
        pred (numpy.ndarray): foreground probability of shape :math:`(Z, Y, X)`.
        gt (numpy.ndarray): binary foreground label of shape identical to the prediction.
        thres (list): a list of probablility threshold in (0,1). Default: [0.5]

    Return:
        score (numpy.ndarray): a numpy array of shape :math:`(N, 4)`, where :math:`N` is the 
        number of element(s) in the probability threshold list. The four scores in each line
        are foreground IoU, IoU, precision and recall, respectively.
    """
    score = np.zeros((len(thres), 4))
    for tid, t in enumerate(thres):
        assert 0.0 < t < 1.0, "The range of the threshold should be (0,1)."
        TP, FP, TN, FN = confusion_matrix(pred, gt, t)

        precision = float(TP) / (TP + FP)
        recall = float(TP) / (TP + FN)
        iou_fg = float(TP) / (TP + FP + FN)
        iou_bg = float(TN) / (TN + FP + FN)
        iou = (iou_fg + iou_bg) / 2.0
        score[tid] = np.array([iou_fg, iou, precision, recall])
    return score


def cremi_distance(pred, gt, resolution=(40.0, 4.0, 4.0)):
    """Compute the FP/FN statistics between predictions and ground truth as
       in the CREMI challenge (https://cremi.org/). Both inputs (pred, gt) need 
       to be of the same size.
    """

    def count_false_positives(test_clefts_mask, truth_clefts_edt, threshold=200):
        mask1 = np.invert(test_clefts_mask)
        mask2 = truth_clefts_edt > threshold
        false_positives = truth_clefts_edt[np.logical_and(mask1, mask2)]
        return false_positives.size

    def count_false_negatives(truth_clefts_mask, test_clefts_edt, threshold=200):
        mask1 = np.invert(truth_clefts_mask)
        mask2 = test_clefts_edt > threshold
        false_negatives = test_clefts_edt[np.logical_and(mask1, mask2)]
        return false_negatives.size

    def acc_false_positives(test_clefts_mask, truth_clefts_edt):
        mask = np.invert(test_clefts_mask)
        false_positives = truth_clefts_edt[mask]
        stats = {
            'mean': np.mean(false_positives),
            'std': np.std(false_positives),
            'max': np.amax(false_positives),
            'count': false_positives.size,
            'median': np.median(false_positives)}
        return stats

    def acc_false_negatives(truth_clefts_mask, test_clefts_edt):
        mask = np.invert(truth_clefts_mask)
        false_negatives = test_clefts_edt[mask]
        stats = {
            'mean': np.mean(false_negatives),
            'std': np.std(false_negatives),
            'max': np.amax(false_negatives),
            'count': false_negatives.size,
            'median': np.median(false_negatives)}
        return stats

    def convert_dtype(data):
        data = data.astype(np.uint64)
        data[data == 0] = 0xffffffffffffffff
        return data

    test_clefts = convert_dtype(pred)
    truth_clefts = convert_dtype(gt)

    truth_clefts_invalid = truth_clefts == 0xfffffffffffffffe

    test_clefts_mask = np.logical_or(
        test_clefts == 0xffffffffffffffff, truth_clefts_invalid)
    truth_clefts_mask = np.logical_or(
        truth_clefts == 0xffffffffffffffff, truth_clefts_invalid)

    print("EDT calculation in progress")
    test_clefts_edt = ndimage.distance_transform_edt(test_clefts_mask, sampling=resolution)
    truth_clefts_edt = ndimage.distance_transform_edt(truth_clefts_mask, sampling=resolution)

    false_positive_count = count_false_positives(
        test_clefts_mask, truth_clefts_edt)
    false_negative_count = count_false_negatives(
        truth_clefts_mask, test_clefts_edt)

    false_positive_stats = acc_false_positives(
        test_clefts_mask, truth_clefts_edt)
    false_negative_stats = acc_false_negatives(
        truth_clefts_mask, test_clefts_edt)

    print("Clefts Statistics")
    print("======")

    print("\tfalse positives: " + str(false_positive_count))
    print("\tfalse negatives: " + str(false_negative_count))

    print("\tdistance to ground truth: " + str(false_positive_stats))
    print("\tdistance to proposal    : " + str(false_negative_stats))

    return false_positive_stats['mean'], false_negative_stats['mean']


def confusion_matrix_visualize(pred, gt, thres=0.5):
    TP = (gt == 1) & (pred > thres)
    FP = (gt == 0) & (pred > thres)
    TN = (gt == 0) & (pred <= thres)
    FN = (gt == 1) & (pred <= thres)

    z, y, x = TP.shape
    # colored_TP   GREEN (0,255,0)
    img_rgb_tp = np.zeros((3, z, y, x))
    img_rgb_tp[0:, TP] = 0
    img_rgb_tp[1:, TP] = 255
    img_rgb_tp[2:, TP] = 0

    # colored_FP   BLUE (0,0,255)
    img_rgb_fp = np.zeros((3, z, y, x))
    img_rgb_fp[0:, FP] = 0
    img_rgb_fp[1:, FP] = 0
    img_rgb_fp[2:, FP] = 255

    # colored_FN   RED (0,0,255)
    img_rgb_fn = np.zeros((3, z, y, x))
    img_rgb_fn[0:, FN] = 255
    img_rgb_fn[1:, FN] = 0
    img_rgb_fp[2:, FN] = 0

    # img_rgb_tn = np.zeros((3,z,y,x))
    img_rgb_tn = np.zeros((3, z, y, x))

    # combine
    img_colored = img_rgb_tp + img_rgb_fp + img_rgb_fn + img_rgb_tn
    img_colored = img_colored.transpose((1, 2, 3, 0))  # # c,z,y,x - > z,y,x,c
    return img_colored


def emb2rgb_img(x_emb):
    x_emb = x_emb.squeeze(0)
    x_emb = np.array(x_emb.cpu())
    shape = x_emb.shape
    pca = PCA(n_components=3)
    x_emb = np.transpose(x_emb, [1, 2, 0])
    x_emb = x_emb.reshape(-1, 16)
    new_emb = pca.fit_transform(x_emb)
    new_emb = new_emb.reshape(shape[-2], shape[-1], 3)
    return new_emb


def emb2rgb_dim5(x_emb):
    x_emb = x_emb.squeeze(0)
    x_emb = np.array(x_emb.cpu())
    shape = x_emb.shape
    pca = PCA(n_components=3)
    x_emb = np.transpose(x_emb, [1, 2, 3, 0])
    x_emb = x_emb.reshape(-1, 16)
    new_emb = pca.fit_transform(x_emb)
    new_emb = new_emb.reshape(shape[-3], shape[-2], shape[-1], 3)
    return new_emb


def visualize(embedding, volume, index, mask=True, dir_path='/braindat/lab/liusl/flywire/block_data/v2/visualize/',
              name='show_'):
    if mask:
        show = embedding[index, 3:, :, :, :].unsqueeze(0)
        mask = np.asarray(embedding[index, 2, :, :, :].clone().detach().cpu())
        x = np.asarray(emb2rgb_dim5(show))
        y = (x - x.min()) / (x.max() - x.min()) * 240
        tf.imsave(os.path.join(dir_path, name + 'embedding.tif'), y.astype(np.uint8))
        x = np.asarray(volume[index, 0, :, :, :].clone().detach().cpu())
        x = (x - x.min()) / (x.max() - x.min()) * 240
        x = x * mask * 0.3 + x * 0.7
        tf.imsave(os.path.join(dir_path, name + 'volume.tif'), x.astype(np.uint8))
    else:
        show = embedding[index, :, :, :, :].unsqueeze(0)
        x = np.asarray(emb2rgb_dim5(show))
        y = (x - x.min()) / (x.max() - x.min()) * 240
        tf.imsave(os.path.join(dir_path, name + 'embedding.tif'), y.astype(np.uint8))
        x = np.asarray(volume[index, 0, :, :, :].clone().detach().cpu())
        x = (x - x.min()) / (x.max() - x.min()) * 240
        tf.imsave(os.path.join(dir_path, name + 'volume.tif'), x.astype(np.uint8))

def build_neuron_segment_graph():
    import cloudvolume
    import tqdm

    fafb_ffn1_20190805 = cloudvolume.CloudVolume('file:///braindat/lab/lizl/google/google_16.0x16.0x40.0', cache=True, parallel=True)
    skel_path = '/braindat/lab/liusl/flywire/fafb-public-skeletons'
    skels = []
    # import urllib
    #
    # for file in os.listdir(skel_path):
    #     if file.isdigit():
    #         skel16_url = 'https://storage.googleapis.com/fafb-ffn1/fafb-public-skeletons/' + file
    #         with urllib.request.urlopen(skel16_url) as source:
    #             skels.append(cloudvolume.Skeleton.from_precomputed(source.read(), segid=int(file)))
    # for i, skel in enumerate(skels):
    #     with open(os.path.join(skel_path, str(skel.id) + '.swc'), 'wt') as f:
    #         f.write(skel.to_swc())

    neurons = []
    for file in os.listdir(skel_path):
        if '.swc' in file:
            path = os.path.join(skel_path, file)
            with open(path, 'r') as f:
                skel = cloudvolume.Skeleton.from_swc(f.read())
                skel.segid=int(file.split('.')[0])
                skels.append(skel)
            neuron = navis.read_swc(path)
            neurons.append(neuron)

    import collections
    from concurrent import futures
    import numpy as np
    from tqdm import tqdm
    import pickle
    # import funlib.evaluate

    class PointLoader(object):
        """Build up a list of points, then load them batched by storage chunk."""

        def __init__(self, cloud_volume):
            """Initializes with zero points; see add_points to queue some."""
            self._volume = cloud_volume
            self._chunk_map = collections.defaultdict(set)

        def add_points(self, points):
            """Add more points to be loaded.

            Args:
              points: iterable of XYZ iterables, e.g. Nx3 ndarray.  Assumed to be in
                  absolute units relative to volume.scale['resolution'].
            """
            points = np.array(points)
            resolution = np.array(self._volume.scale['resolution'])
            chunk_size = np.array(self._volume.scale['chunk_sizes'])
            chunk_starts = (points // resolution).astype(int) // chunk_size * chunk_size
            for point, chunk_start in zip(points, chunk_starts):
                self._chunk_map[tuple(chunk_start)].add(tuple(point))

        def _load_chunk(self, chunk_start):
            # (No validation that this is a valid chunk_start.)
            chunk_size = np.array(self._volume.scale['chunk_sizes'])[0]
            chunk_end = chunk_start + chunk_size
            return self._volume[
                   chunk_start[0]:chunk_end[0],
                   chunk_start[1]:chunk_end[1],
                   chunk_start[2]:chunk_end[2]]

        def _load_points(self, chunk_map_key):
            chunk_start = np.array(chunk_map_key)
            points = np.array(list(self._chunk_map[chunk_map_key]))
            resolution = np.array(self._volume.scale['resolution'])
            indices = (points // resolution).astype(int) - chunk_start
            chunk = self._load_chunk(chunk_start)
            return points, chunk[indices[:, 0], indices[:, 1], indices[:, 2]]

        def load_all(self, max_workers=4):
            """Load all points in current list, batching by storage chunk.

            Args:
              max_workers: the max number of workers for parallel chunk requests.

            Returns:
              (points, data): parallel Numpy arrays of the requested points from all
                  cumulative calls to add_points, and the corresponding data loaded from
                  volume.
            """
            # progress_state = self._volume.progress
            # self._volume.progress = False
            # pbar = tqdm.notebook.tqdm(total=len(self._chunk_map), desc='loading chunks')
            # with futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            #     point_futures = [ex.submit(self._load_points, k) for k in self._chunk_map]
            #     for f in futures.as_completed(point_futures):
            #         pbar.update(1)
            # self._volume.progress = progress_state
            # pbar.close()
            #
            # results = [f.result() for f in point_futures]
            results = []
            for k in tqdm(self._chunk_map):
                results.append(self._load_points(k))
            points = np.concatenate([result[0] for result in results])
            data = np.concatenate([result[1] for result in results])
            return points, data
    graph = nx.Graph()
    for i in range(len(skels)):
        skel = skels[i]
        neuron = neurons[i]
        neuron_graph = neuron.get_graph_nx().to_undirected()
        pl = PointLoader(fafb_ffn1_20190805)
        pl.add_points(skel.vertices)
        loaded_points, loaded_data = pl.load_all(max_workers=1)
        node_segid_dict = {}
        node_pos_dict = {}
        for point, segid in zip(loaded_points, loaded_data):
            node = neuron.nodes['node_id'][(neuron.nodes['x']==point[0]) & (neuron.nodes['y']==point[1]) & (neuron.nodes['z']==point[2])]
            if len(node) != 1:
                print('debug')
            node_segid_dict[node.item()] = segid
            # node_pos_dict[node.item()] = np.array([point[2], point[1], point[0]])
            node_pos_dict[node.item()] = np.array(point)
        nx.set_node_attributes(neuron_graph, node_segid_dict, 'seg_label')
        nx.set_node_attributes(neuron_graph, node_pos_dict, 'zyx_coord')
        nx.set_node_attributes(neuron_graph, int(neuron.name), 'skeleton_id')
        # for node, attr in neuron_graph.nodes(data=True):
        #     print(attr['seg_label'], attr['zyx_coord']/np.array([4,4,40]))
        #     print(neuron_graph[node])
        # mapping the nodes to a isolated graph
        if len(graph)>0:
            mapping = dict(zip(sorted(neuron_graph), sorted(neuron_graph)+sorted(graph)[-1]+1))
            neuron_graph = nx.relabel_nodes(neuron_graph, mapping)
        graph.add_nodes_from(neuron_graph.nodes(data=True))
        graph.add_edges_from(neuron_graph.edges(data=True))
    fafb_ffn1_20190805.cache.flush()
    pickle.dump(graph, open('/braindat/lab/liusl/flywire/fafb-public-skeletons/skeleton_segment_graph.pickle', 'wb'))


def compute_ffn_erl():
    import pickle
    graph = pickle.load( open('/braindat/lab/liusl/flywire/fafb-public-skeletons/skeleton_segment_graph.pickle', 'rb'))
    mapping = {}
    graph_path = '/braindat/lab/liusl/flywire/biologicalgraphs/biologicalgraphs/neuronseg/features/biological/evaluate_fafb/result_0.980.pickle'
    proofread_subgraphs = pickle.load(open(graph_path, 'rb'))
    print(graph_path)
    for subgraph in proofread_subgraphs:
        subgraph = list(subgraph)
        mapped_id = subgraph[0]
        for id in subgraph:
            mapping[id] = mapped_id

    res = {}
    node_seg_lut = {}
    n_neurons = len(list(nx.connected_components(graph)))
    for node, attr in graph.nodes(data=True):
        if attr['seg_label'][0] in mapping.keys():
            node_seg_lut[node] = mapping[attr['seg_label'][0]]
        else:
            node_seg_lut[node] = attr['seg_label'][0]

    res["n_neurons"] = n_neurons
    res['erl'] = expected_run_length(
        skeletons=graph, skeleton_id_attribute='skeleton_id',
        node_segment_lut=node_seg_lut, skeleton_position_attributes=['zyx_coord'],
        return_merge_split_stats=False, edge_length_attribute='edge_length', merge_thres=3)

    print(f'n_neurons: {res["n_neurons"]}')
    print(f'Expected run-length: {res["erl"]}')


if __name__ == '__main__':
    # build_neuron_segment_graph()
    compute_ffn_erl()