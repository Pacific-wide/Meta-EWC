import tensorflow as tf
import numpy as np
import argparse
import importlib
from optimizer import metric
from result import logger

from model import grouplearner
from optimizer import optimizer as op
from optimizer import spec


def main(argv):
    parser = argparse.ArgumentParser(description='Homeostatic Synapse')

    # model parameters
    parser.add_argument('--model', type=str, default='Single', help='main learner')
    parser.add_argument('--meta_model_dir', type=str, default='HMTrain', help='checkpoint for pre-trained HM')
    parser.add_argument('--alpha', type=float, default=1.0, help='Intensity of Regularization')

    # data parameters
    parser.add_argument('--data', type=str, default='MNISTPERM', help='Type of Dataset')

    # optimizer parameters
    parser.add_argument('--n_epoch', type=int, default=1, help='Number of epochs per task')
    parser.add_argument('--batch_size', type=int, default=100, help='batch size')
    parser.add_argument('--lr', type=float, default=5e-2, help='SGD learning rate for main network')
    parser.add_argument('--meta_lr', type=float, default=5e-2, help='SGD learning rate for HM')

    # experiment parameters
    parser.add_argument('--n_task', type=int, default=10, help='Number of tasks')
    parser.add_argument('--n_block', type=int, default=7, help='Number of blocks in BPERM')
    parser.add_argument('--seed', type=int, default=0, help='random seed')
    parser.add_argument('--save_path', type=str, default='results/', help='save models')

    args = parser.parse_args()

    seed = args.seed
    alpha = args.alpha
    learning_rate = args.lr
    n_epoch = args.n_epoch
    n_batch = args.batch_size
    n_task = args.n_task
    n_block = args.n_block
    np.random.seed(seed)

    model_dir = args.model
    meta_model_dir = args.meta_model_dir

    # generate sequence dataset
    DataClass = getattr(importlib.import_module('dataset.set_of_dataset'), 'SetOfRand' + args.data)
    # generate sequence dataset
    if args.data[-5:] == 'BPERM':
        set_of_datasets = DataClass(n_task, n_block)  # For Block-wise Permutation
    else:
        set_of_datasets = DataClass(n_task)

    d_in = set_of_datasets.list[0].d_in
    n_train = set_of_datasets.list[0].n_train

    learning_rates = learning_rate * np.ones(n_task)
    learning_specs = []

    # config
    run_config = tf.estimator.RunConfig(model_dir=model_dir, save_checkpoints_steps=int(n_train / n_batch))
    ws0 = tf.estimator.WarmStartSettings(ckpt_to_initialize_from=meta_model_dir, vars_to_warm_start="meta")
    ws1 = tf.estimator.WarmStartSettings(ckpt_to_initialize_from=model_dir, vars_to_warm_start=".*")

    # learning specs
    for i in range(n_task):
        opt = op.SGDOptimizer(learning_rates[i]).build()
        opt_spec = spec.OptimizerSpec(opt, d_in)
        learning_specs.append(spec.LearningSpec(n_epoch, n_batch, n_train, n_task, model_dir, opt_spec, alpha))

    my_grouplearner = grouplearner.GroupHMTestLearner(set_of_datasets, learning_specs, n_task, run_config, ws0, ws1)

    accuracy_matrix = my_grouplearner.train_and_evaluate()

    avg_acc = metric.AverageAccuracy(accuracy_matrix).compute()
    tot_acc = metric.TotalAccuracy(accuracy_matrix).compute()
    avg_forget = metric.AverageForgetting(accuracy_matrix).compute()
    tot_forget = metric.TotalForgetting(accuracy_matrix).compute()

    metric_list = [avg_acc, tot_acc, avg_forget, tot_forget]

    filepath = "meta_cifar.txt"
    logger.save(filepath, model_dir, accuracy_matrix, metric_list, seed, learning_specs, 0, n_block)


if __name__ == '__main__':
    tf.logging.set_verbosity(tf.logging.INFO)
    tf.app.run()
