import numpy as np
from typing import Dict, List, Tuple
from sklearn.preprocessing import OneHotEncoder
import copy
from common.loss_funcions import cross_entropy_error, squared_error
from common.forward_functions import forward_middle, forward_last_classification

class SGDNeuralNet:
    def __init__(self, X: np.ndarray, T: np.ndarray, 
                 hidden_size: int, n_layers: int,
                 batch_size: int, n_iter: int,
                 loss_type: str, activation_function: str,
                 learning_rate: float,
                 weight_init_std=0.01):
        """
        ハイパーパラメータの読込＆パラメータの初期化

        Parameters
        ----------
        X : numpy.ndarray 2D
            入力データ (データの次元数確認のみに使用)
        T : numpy.ndarray 1D or 2D
            正解データ (データの次元数確認のみに使用)
        hidden_size : int
            隠れ層の1層あたりニューロン
        n_layers : int
            層数 (隠れ層の数 - 1)
        batch_size : int
            ミニバッチのデータ数
        n_iter : int
            学習 (SGD)の繰り返し数
        loss_type : {'cross_entropy', 'squared_error'}
            損失関数の種類 ('cross_entropy': 交差エントロピー誤差, 'squared_error': 2乗和誤差)
        activation_function : {'sigmoid', 'relu'}
            中間層活性化関数の種類 ('sigmoid': シグモイド関数, 'relu': ReLU関数)
        learning_rate : float
            学習率
        weight_init_std : float
            重み初期値生成時の標準偏差
        """
        # 各種メンバ変数 (ハイパーパラメータ等)の入力
        self.input_size = X.shape[1]  # 説明変数の次元数(1層目の入力数)
        self.output_size = T.shape[1] if T.ndim == 2 else np.unique(T).size  # クラス数 (出力層のニューロン数)
        self.hidden_size = hidden_size  # 隠れ層の1層あたりニューロン
        self.n_layers = n_layers  # 層数
        self.learning_rate = learning_rate  # 学習率
        self.batch_size = batch_size  # ミニバッチのデータ数
        self.n_iter = n_iter  # 学習のイテレーション(繰り返し)数
        self.loss_type = loss_type  # 損失関数の種類
        self.activation_function = activation_function  # 中間層活性化関数の種類
        self.weight_init_std = weight_init_std  # 重み初期値生成時の標準偏差
        # 損失関数と活性化関数が正しく入力されているか判定
        if loss_type not in ['cross_entropy', 'squared_error']:
            raise Exception('the `loss_type` argument should be "cross_entropy" or "squared_error"')
        if activation_function not in ['sigmoid', 'relu']:
            raise Exception('the `activation_function` argument should be "sigmoid" or "relu"')
        # パラメータを初期化
        self._initialize_parameters()
        
    def _initialize_parameters(self):
        """
        パラメータを初期化
        """
        # パラメータ格納用に空の辞書のリストを準備
        self.params = [{} for l in range(self.n_layers)]
        # 重みパラメータ
        self.params[0]['W'] = self.weight_init_std \
                            * np.random.randn(self.input_size, self.hidden_size)  # 1層目の重みパラメータ
        for l in range(1, self.n_layers-1):
            self.params[l]['W'] = self.weight_init_std \
                            * np.random.randn(self.hidden_size, self.hidden_size) # 中間層の重みパラメータ
        self.params[self.n_layers-1]['W'] = self.weight_init_std \
                            * np.random.randn(self.hidden_size, self.output_size) # 出力層の重みパラメータ
        # バイアスパラメータ
        for l in range(self.n_layers-1):
            self.params[l]['b'] = np.zeros(self.hidden_size)  # 中間層のバイアスパラメータ
        self.params[self.n_layers-1]['b'] = np.zeros(self.output_size)  # 最終層のバイアスパラメータ

    def _one_hot_encoding(self, T):
        """
        One-hot encodingを実行する
        """
        # Tが1次元ベクトルなら2次元に変換してOne-hot encodingする
        if T.ndim == 1:
            T_onehot = T.reshape([T.size, 1])
            self.one_hot_encoder_ = OneHotEncoder().fit(T_onehot)  # エンコーダをメンバ変数として保持
            T_onehot = self.one_hot_encoder_.transform(T_onehot).toarray()
        # Tが2次元ベクトルなら既にOne-hot encodingされているとみなしてそのまま返す
        else:
            T_onehot = T
        return T_onehot

    def _one_hot_encoding_reverse(self, T):
        """
        One-hot encodingから元のカテゴリ変数に戻す
        """
        # One-hotをクラスのインデックスに変換
        T_label = np.argmax(T, axis=1)
        # メンバ変数として保持したエンコーダを参照にカテゴリ変数に戻す
        T_cat = np.vectorize(lambda x: self.one_hot_encoder_.categories_[0][x])(T_label)
        return T_cat
    
    def _predict_onehot(self, X):
        """
        順伝播を全て計算(One-hot encodingで出力)
        """
        Z_current = X  # 入力値を保持
        # 中間層(1〜n_layers-1層目)の順伝播
        for l in range(self.n_layers-1):
            W = self.params[l]['W']  # 重みパラメータ
            b = self.params[l]['b']  # バイアスパラメータ
            Z_current = forward_middle(Z_current, W, b, 
                activation_function=self.activation_function)  # 中間層の計算
        # 出力層の順伝播
        W_final = self.params[self.n_layers-1]['W']
        b_final = self.params[self.n_layers-1]['b']
        Z_result = forward_last_classification(Z_current, W_final, b_final)
        return Z_result
    
    def predict(self, X) -> np.ndarray:
        """
        順伝播を全て計算(クラス名で出力)

        Parameters
        ----------
        X : np.ndarray
            入力データとなる2D numpy配列（形状:(n_samples, n_features)）
        
        Returns
        -------
        np.ndarray
            予測されたクラスラベルの1D numpy配列
        """
        Y = self._predict_onehot(X)
        Y = self._one_hot_encoding_reverse(Y)
        return Y

    def select_minibatch(self, X: np.ndarray, T: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        ステップ1: ミニバッチの取得

        Parameters
        ----------
        X : np.ndarray
            入力データとなる2D numpy配列（形状:(n_samples, n_features)）
        T : np.ndarray
            ターゲットラベルとなる2D numpy配列（形状:(n_samples, n_classes)）

        Returns
        -------
        X_batch : np.ndarray
            ランダムに選択されたミニバッチの入力データ（形状：(batch_size, n_features)）
        T_batch : np.ndarray
            ランダムに選択されたミニバッチの教師データ（形状：(batch_size, n_classes)）
        """
        train_size = X.shape[0]  # サンプリング前のデータ数
        batch_mask = np.random.choice(train_size, self.batch_size)  # ランダムサンプリング
        X_batch = X[batch_mask]
        T_batch = T[batch_mask]
        return X_batch, T_batch

    def _loss(self, X, T):
        """
        損失関数の計算
        """
        Y = self._predict_onehot(X)
        if self.loss_type == 'cross_entropy':
            return cross_entropy_error(Y, T)
        elif self.loss_type == 'squared_error':
            return squared_error(Y, T)
        else:
            raise Exception('The `loss_type` argument should be "cross_entropy" or "squared_error"')
    
    def _numerical_gradient(self, X, T, param_name, l):
        """
        層ごとの勾配を計算

        Parameters
        ----------
        X : numpy.ndarray 2D
            入力データ (ランダムサンプリング後)
        T : numpy.ndarray 2D
            正解データ (ランダムサンプリング後)
        param_name : {'W', 'b'}
            パラメータの種類 ('W': 重みパラメータ, 'b': バイアス)
        l : int
            何層目のパラメータか
        """
        # 勾配計算対象のパラメータを抽出 (self.params更新時に一緒に更新されないようDeepCopyする)
        P = copy.deepcopy(self.params[l][param_name])

        h = 1e-4  # 原書に記載された適切な微小変化量hの値として1e-4を採用
        P_ravel = np.ravel(P)  # Pが行列(重みパラメータ)の時、一旦ベクトルとして展開
        grad = np.zeros_like(P_ravel)  # Pと同じ形状のベクトルor行列を生成

        # パラメータごとに偏微分を計算
        for idx in range(P_ravel.size):
            # 微小変化量に相当するベクトル(該当パラメータに相当する成分のみh、他成分は全て0)
            h_vector = np.eye(P_ravel.size)[idx] * h
            # f(x+h)の計算
            P1 = (P_ravel + h_vector).reshape(P.shape)  # 微小変換させたP
            self.params[l][param_name] = P1  # 微小変化させたPをパラメータに反映
            fxh1 = self._loss(X, T)  # 微小変化後の損失関数を計算
            # f(x-h)の計算
            P2 = (P_ravel - h_vector).reshape(P.shape)  # 微小変換させたP
            self.params[l][param_name] = P2  # 微小変化させたPをパラメータに反映
            fxh2 = self._loss(X, T)  # 微小変化後の損失関数を計算
            # 偏微分の計算
            grad[idx] = (fxh1 - fxh2) / (2*h)
            # 微小変化させたPを元に戻す
            self.params[l][param_name] = P
        
        return grad.reshape(P.shape)

    def numerical_gradient_all(self, X: np.ndarray, T: np.ndarray) -> List[Dict[str, np.ndarray]]:
        """
        ステップ2: 全パラメータの勾配を計算

        Parameters
        ----------
        X : np.ndarray
            入力データとなる2D numpy配列（形状:(n_samples, n_features)）
        T : np.ndarray
            ターゲットラベルとなる2D numpy配列（形状:(n_samples, n_classes)）

        Returns
        -------
        grads : List[Dict[str, np.ndarray]]
            計算された各層の勾配をリストとして保持 (パラメータ名をキーとした辞書のリスト)
        """
        # 勾配格納用 (空の辞書のリスト)
        grads = [{} for l in range(self.n_layers)]
        # 層ごとに計算
        for l in range(self.n_layers):
            grads[l]['W'] = self._numerical_gradient(X, T, 'W', l)
            grads[l]['b'] = self._numerical_gradient(X, T, 'b', l)
        return grads

    def update_parameters(self, grads: List[Dict[str, np.ndarray]]):
        """
        ステップ3: パラメータの更新

        Parameters
        ----------
        grads : List[Dict[str, np.ndarray]]
            各層の勾配を保持したリスト (パラメータ名をキーとした辞書のリスト)
        """
        # パラメータの更新
        for l in range(self.n_layers):
            self.params[l]['W'] -= self.learning_rate * grads[l]['W']
            self.params[l]['b'] -= self.learning_rate * grads[l]['b']
    
    def fit(self, X: np.ndarray, T: np.ndarray):
        """
        ステップ4: ステップ1-3を繰り返す

        Parameters
        ----------
        X : np.ndarray
            入力データとなる2D numpy配列（形状:(n_samples, n_features)）
        T : np.ndarray
            ターゲットラベルとなる1D or 2D numpy配列（1次元ベクトルの場合One-hot encodingで自動変換される）
        """
        # パラメータを初期化
        self._initialize_parameters()
        # Tが1次元ベクトルなら2次元に変換してOne-hot encodingする
        T = self._one_hot_encoding(T)
        # n_iter繰り返す
        self.train_loss_list = []
        for i_iter in range(self.n_iter):
            # ステップ1: ミニバッチの取得
            X_batch, T_batch = self.select_minibatch(X, T)
            # ステップ2: 勾配の計算
            grads = self.numerical_gradient_all(X_batch, T_batch)
            # ステップ3: パラメータの更新
            self.update_parameters(grads)
            # 学習経過の記録
            loss = self._loss(X_batch, T_batch)
            self.train_loss_list.append(loss)
        
    def accuracy(self, X_test, T_test) -> float:
        """
        正解率Accuracyを計算

        Parameters
        ----------
        X_test : np.ndarray
            入力データとなる2D numpy配列（形状:(n_samples, n_features)）
        T_test : np.ndarray
            ターゲットラベルとなる1D or 2D numpy配列（1次元ベクトルの場合One-hot encodingで自動変換される）

        Returns
        -------
        float
            正解率 (Accuracy)
        """
        # Tが1次元ベクトルなら2次元に変換してOne-hot encodingする
        T_test = self._one_hot_encoding(T_test)
        # 順伝播を計算
        Y_test = self._predict_onehot(X_test)
        Y_test_label = np.argmax(Y_test, axis=1)  # 予測クラス (One-hotをクラスのインデックスに変換)
        T_test_label = np.argmax(T_test, axis=1)  # 正解クラス (One-hotをクラスのインデックスに変換)
        accuracy = np.sum(Y_test_label == T_test_label) / float(X_test.shape[0])
        return accuracy