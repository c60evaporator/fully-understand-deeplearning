import numpy as np
from typing import Dict, List, Tuple
from sklearn.preprocessing import OneHotEncoder
from common.loss_funcions import cross_entropy_error, squared_error
from common.forward_functions import forward_middle, forward_last_classification
from common.backward_functions import softmax_loss_backward, affine_backward_bias, affine_backward_weight, affine_backward_zprev, relu_backward, sigmoid_backward

class BackpropNeuralNet:
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
    
    def _predict_onehot(self, X, train_flg=False):
        """
        順伝播を全て計算(One-hot encodingで出力)
        """
        Z_current = X  # 入力値を保持
        Z_intermediate = []  # 中間層出力の保持用 (5章の誤差逆伝播法で使用)
        A_intermediate = []  # 中間層の途中結果Aの保持用 (5章の誤差逆伝播法で使用)
        # 中間層(1〜n_layers-1層目)の順伝播
        for l in range(self.n_layers-1):
            W = self.params[l]['W']  # 重みパラメータ
            b = self.params[l]['b']  # バイアスパラメータ
            Z_current, A_current = forward_middle(Z_current, W, b, 
                activation_function=self.activation_function, output_A=True)  # 中間層の計算
            Z_intermediate.append(Z_current)  # 中間層出力を保持 (5章の誤差逆伝播法で使用)
            A_intermediate.append(A_current)  # 中間層の途中結果Aを保持 (5章の誤差逆伝播法で使用)
        # 出力層の順伝播
        W_final = self.params[self.n_layers-1]['W']
        b_final = self.params[self.n_layers-1]['b']
        Z_result = forward_last_classification(Z_current, W_final, b_final)
        # 中間層出力も出力する場合 (5章の誤差逆伝播法で使用)
        if train_flg:
            return Z_result, Z_intermediate, A_intermediate
        # 中間層出力を出力しない場合
        else:
            return Z_result
    
    def predict(self, X: np.ndarray) -> np.ndarray:
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

    def gradient_backpropagation(self, X: np.ndarray, T: np.ndarray) -> List[Dict[str, np.ndarray]]:
        """
        ステップ2: 誤差逆伝播法で全パラメータの勾配を計算

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
        # 順伝播 (中間層出力Zおよび中間層の中間結果Aも保持する)
        Y, Z_intermediate, A_intermediate = self._predict_onehot(X, train_flg=True)
        # 逆伝播結果格納用 (空の辞書のリスト)
        grads = [{} for l in range(self.n_layers)]
        ###### 出力層の逆伝播 ######
        # Softmax-with-Lossレイヤ
        dA = softmax_loss_backward(Y, T)
        # Affineレイヤ
        db = affine_backward_bias(dA)  # バイアスパラメータbの偏微分
        dW = affine_backward_weight(dA, Z_intermediate[self.n_layers-2])  # 重みパラメータWの偏微分 (前層出力Z_prevを入力)
        dZ_prev = affine_backward_zprev(dA, self.params[self.n_layers-1]['W'])  # 前層出力Z_prevの偏微分 (重みパラメータWを入力)
        # 計算した偏微分(勾配)を保持
        grads[self.n_layers-1]['b'] = db
        grads[self.n_layers-1]['W'] = dW
        ###### 中間層の逆伝播 (下流から順番にループ) ######
        for l in range(self.n_layers-2, -1, -1):
            # 当該層の出力偏微分dZを更新
            dZ = dZ_prev.copy()
            # Reluレイヤ
            if self.activation_function == 'relu':
                dA = relu_backward(dZ, A_intermediate[l])  # (中間結果Aを入力)
            # Sigmoidレイヤ
            if self.activation_function == 'sigmoid':
                dA = sigmoid_backward(dZ, Z_intermediate[l])  # (中間層出力Zを入力)
            # Affineレイヤ
            db = affine_backward_bias(dA)  # バイアスパラメータbの偏微分
            # 初層以外の場合
            if l > 0:
                dW = affine_backward_weight(dA, Z_intermediate[l-1])  # 重みパラメータWの偏微分 (前層出力Z_prevを入力)
                dZ_prev = affine_backward_zprev(dA, self.params[l]['W'])  # 前層出力Z_prevの偏微分 (重みパラメータWを入力)
            # 初層の場合
            else:
                dW = affine_backward_weight(dA, X)  # 重みパラメータZ (入力データXを入力)
            # 計算した偏微分(勾配)を保持
            grads[l]['b'] = db
            grads[l]['W'] = dW

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
            grads = self.gradient_backpropagation(X_batch, T_batch)
            # ステップ3: パラメータの更新
            self.update_parameters(grads)
            # 学習経過の記録
            loss = self._loss(X_batch, T_batch)
            self.train_loss_list.append(loss)
        
    def accuracy(self, X_test: np.ndarray, T_test: np.ndarray) -> float:
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