from abc import ABCMeta, abstractmethod
from sklearn.base import BaseEstimator, ClassifierMixin
from ml_edm.utils import *
from warnings import warn


class BaseTimeClassifier(ClassifierMixin, BaseEstimator, metaclass=ABCMeta):

    def __init__(self, 
                 timestamps=None,
                 sampling_ratio=None, 
                 min_length=None):
        
        self.end2end = False
        
        self.timestamps = timestamps
        self.sampling_ratio = sampling_ratio

        self.min_length = min_length
        self.max_length = None

        self.classes_ = None
        self.class_prior = None

    def fit(self, X, y, cost_matrices=None):

        # check input integrity
        X, y = check_X_y(X, y)

        # CHECKING COST MATRICES INTEGRITY
        # ....

        self.max_length = X.shape[1]
        if self.min_length is None:
            warn("No min_length procided, using a minimum length of 1 by default")
            self.min_length = 1

        # Getting prior probabilities
        self.classes_ = np.unique(y)
        self.class_prior = np.array([np.sum(y == class_) / len(y) for class_ in self.classes_])

        # check timestamps parameters validity as well as sampling ratio
        if self.timestamps is not None:
            if isinstance(self.timestamps, list):
                self.timestamps = np.array(self.timestamps)
            elif not isinstance(self.timestamps, np.ndarray):
                raise TypeError("Argument 'timestamps' should be a list or array of positive int.")
            if len(self.timestamps) == 0:
                raise ValueError("List argument 'timestamps' is empty.")
            for t in self.timestamps:
                if not (isinstance(t, np.int32) or isinstance(t, np.int64)):
                    raise TypeError("Argument 'timestamps' should be a list or array of positive int.")
                if t < 0:
                    raise ValueError("Argument 'timestamps' should be a list or array of positive int.")
                
            if len(np.unique(self.timestamps)) != len(self.timestamps):
                self.timestamps = np.unique(self.timestamps)
                warn("Removed duplicates in argument 'timestamps'.")
            
            if self.sampling_ratio is not None:
                warn("Both 'timestamps' and 'sampling_ratio' are defined, in that case" 
                     "argument 'sampling_ratio' is ignored")
                self.sampling_ratio = None

        elif self.sampling_ratio is not None:
            if not isinstance(self.sampling_ratio, float) \
                    and not isinstance(self.sampling_ratio, int):
                raise TypeError(
                    "Argument 'sampling_ratio' should be a strictly positive float between 0 and 1.")
            if self.sampling_ratio <= 0 or self.sampling_ratio > 1:
                raise ValueError(
                    "Argument 'sampling_ratio' should be a strictly positive float between 0 and 1.")
            
            self.nb_classifiers = np.minimum(int(1/self.sampling_ratio), self.max_length - self.min_length + 1)
            
        else:
            warn("No 'sampling_ratio' or pre-defined list of 'timestamps' "
                 "provided, using default 5'%' sampling, i.e. 20 classifiers")
            self.nb_classifiers = 20
            
        if self.timestamps is None:
            self.timestamps = np.array(list(set(
                [int((self.max_length - self.min_length) * i / self.nb_classifiers) + self.min_length
                 for i in range(1, self.nb_classifiers+1)]
            )))
            # update nb_classifiers if the previously setted value
            # was too large for example
            self.nb_classifiers = len(self.timestamps)

        # sort to avoid mismatch 
        self.timestamps = np.sort(self.timestamps)
            
        self._fit(X, y, cost_matrices)

        return self
    
    def predict_proba(self, X, cost_matrices=None):

        # check input integrity, not all ts have to be same length
        X, _ = check_X_y(X, None, equal_length=False)
        # Group X by batch of same length
        grouped_X = self._grouped_by_length(X)

        return self._predict_proba(grouped_X, cost_matrices)
    
    def predict_past_proba(self, X, cost_matrices=None):
        
        # check input integrity, not all ts have to be same length
        X, _ = check_X_y(X, None, equal_length=False)
        # Group X by batch of same length
        grouped_X = self._grouped_by_length(X)

        return self._predict_past_proba(grouped_X, cost_matrices)
    
    def predict(self, X, cost_matrices=None):
        """
        Predict a dataset of time series of various lengths using the right classifier in the ChronologicalClassifiers
        object. If a time series has a different number of measurements than the values in 'models_input_lengths', the
        time series is truncated to the closest compatible length. If its length is shorter than the first length in
        'models_input_lengths', the prior probabilities are used. Returns the most probable class of each series.
        Parameters:
            X: np.ndarray
            Dataset of time series of various sizes to predict. An array of size (N*max_T) where N is the number of
            time series, max_T the max number of measurements in a time series and where empty values are filled with
            nan. Can also be a pandas DataFrame or a list of lists.
        Returns:
            np.ndarray containing the classifier predicted class for each time series in the dataset.
        """
        return self.predict_proba(X, cost_matrices).argmax(axis=-1)
    
    def _grouped_by_length(self, X):

        truncated = False
        grouped_X = {}
        for serie in X:
            length = len(serie)
            if length not in self.timestamps and \
                length > self.timestamps[0]:
                # truncate to nearest valid timestamp
                filtered = filter(lambda x: x <= length, self.timestamps)
                length = min(filtered, key=lambda x: length-x, default=None)
                if length:
                    serie = serie[:length]
                    truncated = True

            if length in grouped_X.keys():
                grouped_X[length].append(serie)
            else:
                grouped_X[length] = [serie]
        
        if truncated:
            warn("Some time series were truncated during prediction since no classifier was fitted for their lengths.")
        
        return grouped_X
    
    @abstractmethod
    def _fit(self, X, y, cost_matrices):
        """Fit the classifier(s) to 
        target y
        """
    
    @abstractmethod
    def _predict_proba(self, grouped_X, cost_matrices):
        """Predict probabilities for each 
        class to be true label
        """
    
    @abstractmethod
    def _predict_past_proba(self, grouped_X, cost_matrices):
        """Predict probabilities for each 
        class to be true label, for each 
        past timestamps 
        """