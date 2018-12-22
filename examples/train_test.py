from keras.callbacks import TensorBoard
from keras.optimizers import Adam

from segmenter.custom.callbacks import LRFinder, LRSchedulerPerStep, SingleModelCK, SGDRScheduler
from segmenter import get_or_create, save_config
from segmenter.data_loader import DataLoader

if __name__ == '__main__':
    train_file_path = "../data/2014/training"  # 训练文件目录
    valid_file_path = "../data/2014/valid"  # 验证文件目录
    config_save_path = "../data/default-config.json"  # 模型配置路径
    weights_save_path = "../models/weights.{epoch:02d}-{val_loss:.2f}.h5"  # 模型权重保存路径
    init_weights_path = "../models/weights.17-0.07.h5"  # 预训练模型权重文件路径

    src_dict_path = "../data/src_dict.json"  # 源字典路径
    tgt_dict_path = "../data/tgt_dict.json"  # 目标字典路径
    batch_size = 32
    epochs = 128
    num_gpu = 1
    max_seq_len = 256

    # import os
    #
    # os.environ["CUDA_VISIBLE_DEVICES"] = "1,2,3"

    data_loader = DataLoader(src_dict_path=src_dict_path,
                             tgt_dict_path=tgt_dict_path,
                             max_len=max_seq_len,
                             batch_size=batch_size,
                             sparse_target=False)

    # 单个数据集太大，除以epochs分为多个批次
    # steps_per_epoch = 415030 // data_loader.batch_size // epochs
    # validation_steps = 20379 // data_loader.batch_size // epochs

    steps_per_epoch = 1000
    validation_steps = 100

    config = {
        'src_vocab_size': data_loader.src_vocab_size,
        'tgt_vocab_size': data_loader.tgt_vocab_size,
        'max_seq_len': max_seq_len,
        'max_depth': 2,
        'model_dim': 320,
        'residual_dropout': 0.1,
        'attention_dropout': 0.2,
        'l2_reg_penalty': 1e-6,
        'confidence_penalty_weight': 0.1,
        'compression_window_size': None,
        'use_masking': True,
        'num_heads': 8,
        'use_crf': False,
        'label_smooth': True
    }

    # K.set_session(get_session(0.9))

    segmenter = get_or_create(config,
                              optimizer=Adam(1e-3, beta_1=0.9, beta_2=0.98, epsilon=1e-9),
                              src_dict_path=src_dict_path,
                              weights_path=init_weights_path,
                              num_gpu=num_gpu
                              )

    save_config(segmenter, config_save_path)

    segmenter.model.summary()

    ck = SingleModelCK(weights_save_path,
                       model=segmenter.model,
                       save_best_only=False,
                       save_weights_only=True,
                       monitor='val_loss',
                       verbose=0)
    log = TensorBoard(log_dir='../logs',
                      histogram_freq=0,
                      batch_size=data_loader.batch_size,
                      write_graph=True,
                      write_grads=False)

    # Use LRFinder to find effective learning rate
    lr_finder = LRFinder(1e-6, 1e-2, steps_per_epoch, epochs=1)  # => (2e-4, 3e-4)
    lr_scheduler = LRSchedulerPerStep(segmenter.model_dim)
    # lr_scheduler = SGDRScheduler(min_lr=2e-5, max_lr=2e-4, steps_per_epoch=steps_per_epoch,
    #                              cycle_length=15,
    #                              lr_decay=0.96,
    #                              mult_factor=1.3)

    segmenter.parallel_model.fit_generator(data_loader.generator(train_file_path),
                                           epochs=epochs,
                                           steps_per_epoch=steps_per_epoch,
                                           validation_data=data_loader.generator(valid_file_path),
                                           validation_steps=validation_steps,
                                           callbacks=[ck, log, lr_scheduler])

    # lr_finder.plot_lr()
    # lr_finder.plot_loss()
