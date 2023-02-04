import numpy as np
from sklearn.preprocessing import OneHotEncoder
from common.loss_funcions import cross_entropy_error, squared_error
from common.optimizers import SGD, Momentum, AdaGrad, RMSprop, Adam

class ConvolutionNet:
    def __init__(self, layers, 
                 batch_size, n_iter,
                 loss_type,
                 learning_rate, 
                 solver='sgd', momentum=0.9,
                 beta_1=0.9, beta_2=0.999, epsilon=1e-8):
        """
        ハイパーパラメータの読込＆パラメータの初期化

        Parameters
        ----------
        layers : list
            ネットワーク構造 (各層のクラスをリスト化したもの)
        batch_size : int
            ミニバッチのデータ数
        n_iter : int
            学習 (SGD)の繰り返し数
        loss_type : {'cross_entropy', 'squared_error'}
            損失関数の種類 ('cross_entropy': 交差エントロピー誤差, 'squared_error': 2乗和誤差)
        learning_rate : float
            学習率
        solver : {'sgd', 'momentum', 'adagrad', 'rmsprop', 'adam'}
            最適化アルゴリズムの種類 ('sgd': SGD, 'momentum': モーメンタム, 'adagrad': AdaGrad, 'rmsprop': 'RMSProp', 'adam': Adam)
        momentum : float
            勾配移動平均の減衰率ハイパーパラメータ (solver = 'momentum'の時のみ有効)
        beta_1 : float
            勾配移動平均の減衰率ハイパーパラメータ (solver = 'adam'の時のみ有効)
        beta_2 : float
            過去の勾配2乗和の減衰率ハイパーパラメータ (solver = 'rmsprop' or 'adam'の時のみ有効)
        epsilon : float
            ゼロ除算によるエラーを防ぐハイパーパラメータ (solver = 'adagrad', 'rmsprop', or 'adam'の時のみ有効)
        """
        # 各種メンバ変数 (ハイパーパラメータ等)の入力
        self.layers = layers  # ネットワーク構造 (各層のクラスをリスト化したもの)
        self.learning_rate = learning_rate  # 学習率
        self.batch_size = batch_size  # ミニバッチのデータ数
        self.n_iter = n_iter  # 学習のイテレーション(繰り返し)数
        self.loss_type = loss_type  # 損失関数の種類
        self.solver = solver  # 最適化アルゴリズムの種類
        self.momentum = momentum  # 勾配移動平均の減衰率ハイパーパラメータ (モーメンタムで使用)
        self.beta_1 = beta_1  # 勾配移動平均の減衰率ハイパーパラメータ (Adamで使用)
        self.beta_2 = beta_2  # 過去の勾配2乗和の減衰率ハイパーパラメータ (RMSProp, Adamで使用)
        self.epsilon = epsilon  # ゼロ除算によるエラーを防ぐためのハイパーパラメータ (AdaGrad, RMSProp, Adamで使用)
        # 損失関数が正しく入力されているか判定
        if loss_type not in ['cross_entropy', 'squared_error']:
            raise Exception('the `loss_type` argument should be "cross_entropy" or "squared_error"')
        # パラメータを初期化
        self._initialize_parameters()
        # 層数を計算
        self.n_layers = len(self.layers)

    def _initialize_parameters(self):
        """
        パラメータを初期化
        """
        # 層ごとにパラメータ初期化
        for l, layer in enumerate(self.layers):
            # 初層のとき、自身のinput_shapeを入力サイズとして使用
            if l == 0:
                layer.initialize_parameters(input_shape=layer.input_shape)
            # 初層以外のとき、前層の出力サイズを入力サイズとして使用
            else:
                layer.initialize_parameters(input_shape=self.layers[l-1].output_shape)
        # 最適化用クラスも初期化
        self._initialize_optimizers()

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
    
    def _predict_onehot(self, X, output_intermediate=False):
        """
        順伝播を全て計算(One-hot encodingで出力)
        """
        Z_current = X  # 入力値を保持
        # 順伝播
        for l, layer in enumerate(self.layers):
            Z_current = layer.forward(Z_current)
        #　結果を出力
        return Z_current
    
    def predict(self, X):
        """
        順伝播を全て計算(クラス名で出力)
        """
        Y = self._predict_onehot(X)
        Y = self._one_hot_encoding_reverse(Y)
        return Y

    def select_minibatch(self, X, T):
        """
        ステップ1: ミニバッチの取得
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

    def gradient_backpropagation(self, X, T):
        """
        ステップ2: 誤差逆伝播法で全パラメータの勾配を計算
        """
        # 順伝播 (中間層出力Zおよび中間層の中間結果Aも保持する)
        Y = self._predict_onehot(X, output_intermediate=True)
        ###### 出力層の逆伝播 ######
        dZ = self.layers[self.n_layers-1].backward(Y, T)  # 逆伝播を計算
        ###### 中間層の逆伝播 (下流から順番にループ) ######
        for l in range(self.n_layers-2, -1, -1):
            dZ = self.layers[l].backward(dZ)  # 逆伝播を計算
    
    def _initialize_optimizers(self):
        """最適化で利用するクラスの初期化"""
        self.optimizers=[]  # 相互ごとの最適化用インスタンス保持用のリスト
        for l, layer in enumerate(self.layers):  # 層ごとに初期化
            # 最適化アルゴリズムがSGDの時
            if self.solver == 'sgd':
                self.optimizers.append(SGD(self.learning_rate))
            # 最適化アルゴリズムがモーメンタムの時
            elif self.solver == 'momentum':
                self.optimizers.append(Momentum(self.learning_rate, self.momentum))
            # 最適化アルゴリズムがAdaGradの時
            elif self.solver == 'adagrad':
                self.optimizers.append(AdaGrad(self.learning_rate, self.epsilon))
            # 最適化アルゴリズムがRMSpropの時
            elif self.solver == 'rmsprop':
                self.optimizers.append(RMSprop(self.learning_rate, self.beta_2, self.epsilon))
            # 最適化アルゴリズムがAdamの時
            elif self.solver == 'adam':
                self.optimizers.append(Adam(self.learning_rate, self.beta_1, self.beta_2, self.epsilon))
            
            # 最適化で使用する変数の初期化
            self.optimizers[l].initialize_opt_params(layer.params)

    def update_parameters(self):
        """
        ステップ3: パラメータの更新
        """
        # 層ごとに最適化アルゴリズムによるパラメータ更新を実施
        for l, layer in enumerate(self.layers):
            self.optimizers[l].update(layer.params, layer.grads)

    def fit(self, X, T):
        """
        ステップ4: ステップ1-3を繰り返す

        Parameters
        ----------
        X : numpy.ndarray 2D
            入力データ
        T : numpy.ndarray 1D or 2D
            正解データ
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
            self.gradient_backpropagation(X_batch, T_batch)
            # ステップ3: パラメータの更新
            self.update_parameters()
            # 学習経過の記録
            loss = self._loss(X_batch, T_batch)
            self.train_loss_list.append(loss)
            # 学習経過をプロット
            if i_iter%10 == 0:
                print(f'Iteration{i_iter}/{self.n_iter}')
        
    def accuracy(self, X_test, T_test):
        """
        正解率Accuracyを計算
        """
        # Tが1次元ベクトルなら2次元に変換してOne-hot encodingする
        T_test = self._one_hot_encoding(T_test)
        # 順伝播を計算
        Y_test = self._predict_onehot(X_test)
        Y_test_label = np.argmax(Y_test, axis=1)  # 予測クラス (One-hotをクラスのインデックスに変換)
        T_test_label = np.argmax(T_test, axis=1)  # 正解クラス (One-hotをクラスのインデックスに変換)
        accuracy = np.sum(Y_test_label == T_test_label) / float(X_test.shape[0])
        return accuracy