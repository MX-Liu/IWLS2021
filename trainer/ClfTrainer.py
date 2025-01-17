import os
import numpy as np
from scipy.special import comb
from itertools import combinations as combs
from joblib import Parallel, delayed
from .BinClfEns import BinVoter_write

class Trainer():
    # different training/testing modes for n-class classification:
    # - 'dir': directly predict the labels (non-binary output)
    # - 'oaa': one-against-all, one-hot encoding with n outputs (balanced class weight in dtree is preferred)
    # - 'gag': group-against-group, vote by [C(n, n/2) / ((n+1) % 2 + 1)] binary classifiers (not yet tested if n is odd)
    # - 'oao': one-against-one, vote by C(n, 2) binary classifers
    # - 'col': removed
    def __init__(self, clf, nClass=10, mode='dir', verbose=True, clfParams=dict()):
        self.nClass = nClass
        self.mode = mode
        self.verbose = verbose
        self.__initClf__(clf, clfParams)

    # initialize the classifier
    def __initClf__(self, clf, clfParams):
        if self.mode == 'dir':
            n = 1
        elif self.mode == 'oaa':
            n = self.nClass
        elif self.mode == 'gag':
            #n = comb(self.nClass, self.nClass//2, exact=1)
            n = comb(self.nClass, self.nClass//2, exact=1)
            if self.nClass % 2 == 0:
                n //= 2
        elif self.mode == 'oao':
            n = comb(self.nClass, 2, exact=1)
        #elif self.mode == 'col':
        #    n = 3
        else:
            print(self.mode, 'mode not supported.')
            assert False
        self.clfs = [clf(i, self.verbose, clfParams) for i in range(n)]
    
    # train the classifier with the given data and labels
    def train(self, data, labels, valData=None, valLabels=None, nJob=1):
        # convert labels according to training mode
        traLabs = self.__traLabPrep__(labels)

        #for dt, lab in zip(self.dtrees, traLabs):
        #    dt.train(flatDat, lab)

        #def _trainCol_(clf, data, lab):
        #    data_ = np.zeros(data.shape, dtype=np.uint8)
        #    data_[:, clf.idx] = data[:, clf.idx]
        #    clf.train(data_, lab)
        #    return clf

        #if self.mode == 'col':
        #    self.clfs = Parallel(n_jobs=nJob, backend='threading')(delayed(_trainCol_)(clf, data, traLabs[0]) for clf in self.clfs)
        #else:
        
        # parallel training
        Parallel(n_jobs=nJob, backend='threading')(delayed(clf.train)(data, lab) for clf, lab in zip(self.clfs, traLabs))
        #def f(dt, dat, lab):
        #    dt.train(dat, lab)
        #    return dt
        #self.dtrees = Parallel(n_jobs=self.nJob)(delayed(f)(dt, flatDat, lab) for dt, lab in zip(self.dtrees, traLabs))

        _, traAcc = self.test(data, labels)
        _, valAcc = self.test(valData, valLabels)
        if self.verbose:
            print('Clf training acc={}'.format(str(traAcc)))
            print('Clf validation acc={}'.format(str(valAcc)))
        
        return traAcc, valAcc
    
    # training labels preprocessing
    def __traLabPrep__(self, labels):
        # 'dir': same labels as given
        if (self.mode == 'dir'):# or (self.mode == 'col'):
            return [labels]
        # 'oaa': one-hot encoding of labels
        elif self.mode == 'oaa':
            return np.eye(self.nClass, dtype=np.int8)[labels].T
        # 'gag': divide all classes into 2 groups, each annotated with 0 and 1 labels
        elif self.mode == 'gag':
            ret = []
            for i, s in enumerate(combs(range(self.nClass), self.nClass//2)):
                if i >= len(self.clfs): break
                s = set(s)
                ret.append([lab in s for lab in labels])
            return np.array(ret, dtype=np.int8)
        # 'oao': select 2 classes for comparison, annotate the first class with 0, second with 1, and the rest with -1
        elif self.mode == 'oao':
            ret = []
            for s in combs(range(self.nClass), 2):
                x = []
                for lab in labels:
                    if lab == s[0]: x.append(0)
                    elif lab == s[1]: x.append(1)
                    else: x.append(-1)
                ret.append(x)
            return np.array(ret, dtype=np.int8)
        else:
            print(self.mode, 'mode not supported.')
            assert False

    # return the predicted labels of the input data by the classifier
    def predict(self, data, nJob=1):
        #flatDat = data.reshape((data.shape[0], -1))
        #preds = [dt.predict(flatDat) for dt in self.dtrees]
        preds = Parallel(n_jobs=nJob)(delayed(clf.predict)(data) for clf in self.clfs)

        return self.__predLabPrep__(np.array(preds))

    # predicted labels postprocessing
    # preds.shape = (nClf, nData)
    def __predLabPrep__(self, preds):
        if self.mode == 'dir':
            return preds[0]
        elif self.mode == 'oaa':
            return np.argmax(preds, axis=0)
        elif self.mode == 'gag':
            ret = np.zeros((self.nClass, preds.shape[1]))
            for i, s in enumerate(combs(range(self.nClass), self.nClass//2)):
                if i >= len(self.clfs): break
                s0, s1 = (set(range(self.nClass)) - set(s)), set(s)
                for j in range(preds.shape[1]):
                    assert preds[i, j] in {0, 1}
                    ss = s1 if (preds[i, j] == 1) else s0
                    # accumulate the vote
                    for k in ss: ret[k, j] += 1
            return np.argmax(ret, axis=0)
        elif self.mode == 'oao':
            ret = np.zeros((self.nClass, preds.shape[1]))
            for i, s in enumerate(combs(range(self.nClass), 2)):
                for j in range(preds.shape[1]):
                    k = s[0] if (preds[i, j] == 0) else s[1]
                    ret[k, j] += 1
            return np.argmax(ret, axis=0)
            
            # testing: remove tied votes
            #rret = []
            #for x in ret.T:
            #    if len(np.argwhere(x == x.max())) > 1:
            #        rret.append(-1)
            #    else:
            #        rret.append(x.argmax())
            #return np.array(rret)
        #elif self.mode == 'col':
        #    ret = np.zeros((self.nClass, preds.shape[1]))
        #    for i in range(preds.shape[0]):
        #        for j in range(preds.shape[1]):
        #            ret[preds[i, j], j] += 1
        #    return np.argmax(ret, axis=0)
        else:
            print(self.mode, 'mode not supported.')
            assert False

    # return the predictions and accuracy of the classifier on the input data
    def test(self, data, labels, nJob=1):
        if (data is None) or (labels is None):
            return None, None
        preds = self.predict(data, nJob)
        acc = np.sum(np.array(preds)==np.array(labels)) / len(labels)
        return preds, acc

    # path: folder to dump the circuit files
    def dump(self, path, nBit, pre=''):
        nOut = self.nClass if (self.mode == 'dir') else 1
        
        clfList = [pre+'clf_{}'.format(str(i)) for i in range(len(self.clfs))]
        for name, clf in zip(clfList, self.clfs):
            name = os.path.join(path, name + '.v')
            clf.dump(name, nBit, nOut)

        BinVoter_write(os.path.join(path, pre+'predictor.v'), self.mode, self.nClass, clfList)