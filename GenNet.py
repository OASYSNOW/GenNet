import sys
import os
import warnings

warnings.filterwarnings('ignore')
import argparse

sys.path.insert(1, os.path.dirname(os.getcwd()) + "/GenNet_utils/")
from GenNet_utils.Create_plots import plot
from GenNet_utils.Train_network import train_classification, train_regression
from GenNet_utils.Convert import convert


def main(args):
    if args.mode == 'train':
        if args.problem_type == "classification":
            train_classification(args)
        elif args.problem_type == "regression":
            train_regression(args)
        else:
            print('something went wrong invalid problem type', args.problem_type)
    elif args.mode == "plot":
        plot(args)
    if args.mode == 'convert':
        convert(args)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="GenNet: Interpretable neural networks for phenotype prediction.",
                                     epilog="Check the wiki on github.com/arnovanhilten/gennet/ for more info")
    subparsers = parser.add_subparsers(help="GenNet main options", dest="mode")

    parser_convert = subparsers.add_parser("convert", help="Convert genotype data to hdf5")
    parser_convert.add_argument("-g", "--genotype", nargs='+', type=str, help="path/paths to genotype data folder")
    parser_convert.add_argument('-study_name', type=str, required=True, nargs='+',
                                help=' Name for saved genotype data, without ext')
    parser_convert.add_argument('-variants', type=str,
                                help="Path to file with row numbers of variants to include, if none is "
                                     "given all variants will be used", default=None)
    parser_convert.add_argument("-o", "--out", type=str, required=True, help="path to save result folder")
    parser_convert.add_argument('-ID', action='store_true', default=False,
                                help='Flag to convert minimac data to genotype per subject files first (default False)')

    parser_convert.add_argument('-vcf', action='store_true', default=False, help='Flag for VCF data to convert')
    parser_convert.add_argument('-tcm', type=int, default=500000000, help='Modifier for chunk size during TRANSPOSING'
                                                                          ' make it lower if you run out of memory during transposing')

    parser_train = subparsers.add_parser("train", help="Trains the network")
    parser_train.add_argument(
        "path",
        type=str,
        help="path to the data"
    )
    parser_train.add_argument(
        "ID",
        type=int,
        help="ID of the experiment"
    )
    parser_train.add_argument(
        "-problem_type",
        default='classification', type=str,
        choices=['classification', 'regression'],
        help="Type of problem, choices are: classification or regression"
    )
    parser_train.add_argument(
        "-wpc",
        type=float,
        metavar="weight positive class",
        default=1,
        help="Hyperparameter:weight of the positive class"
    )
    parser_train.add_argument(
        "-lr", '--learning_rate',
        type=float,
        metavar="learning rate",
        default=0.001,
        help="Hyperparameter: learning rate of the optimizer"
    )
    parser_train.add_argument(
        "-bs", '--batch_size',
        type=int,
        metavar="batch size",
        default=32,
        help='Hyperparameter: batch size'
    )
    parser_train.add_argument(
        "-epochs",
        type=int,
        metavar="number of epochs",
        default=100,
        help='Hyperparameter: batch size'
    )
    parser_train.add_argument(
        "-L1",
        metavar="",
        type=float,
        default=0.01,
        help='Hyperparameter: value for the L1 regularization pentalty similar as in lasso, enforces sparsity'
    )

    parser_plot = subparsers.add_parser("plot", help="Generate plots from a trained network")
    parser_plot.add_argument(
        "ID",
        type=int,
        help="ID of the experiment"
    )
    parser_plot.add_argument(
        "-type",
        type=str,
        choices=['layer_weight', 'circos', 'raw_importance'],
    )
    parser_plot.add_argument(
        "-layer_n",
        type=int,
        help="Only for layer weight: Number of the to be plotted layer",
        metavar="Layer_number:",
        default=0
    )

    args = parser.parse_args()

    main(args)
