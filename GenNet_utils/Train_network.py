import os
import sys
import warnings
import shutil
import matplotlib
import datetime
warnings.filterwarnings('ignore')
matplotlib.use('agg')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tensorflow as tf
import tensorflow.keras as K

tf.keras.backend.set_epsilon(0.0000001)
from GenNet_utils.Dataloader import *
from GenNet_utils.Utility_functions import *
from GenNet_utils.Create_network import *
from GenNet_utils.Create_plots import *


def weighted_binary_crossentropy(y_true, y_pred):
    y_true = K.backend.clip(tf.cast(y_true, dtype=tf.float32), 0.0001, 1)
    y_pred = K.backend.clip(tf.cast(y_pred, dtype=tf.float32), 0.0001, 1)

    return K.backend.mean(
        -y_true * K.backend.log(y_pred + 0.0001) * weight_positive_class - (1 - y_true) * K.backend.log(
            1 - y_pred + 0.0001) * weight_negative_class)



def train_classification(args):
    SlURM_JOB_ID = get_SLURM_id()
    model = None
    masks = None
    datapath = args.path
    jobid = args.ID
    wpc = args.wpc
    lr_opt = args.learning_rate
    batch_size = args.batch_size
    epochs = args.epochs
    problem_type = args.problem_type
    patience = args.patience

    if args.genotype_path == "undefined":
        genotype_path = datapath
    else:
        genotype_path = args.genotype_path

    args.genotype_path = genotype_path

    if args.mixed_precision == True:
        use_mixed_precision()
        
    if args.workers > 1:
        multiprocessing = True
    else:
        multiprocessing = False
        
    check_data(datapath=datapath, genotype_path=genotype_path, mode=problem_type)

    global weight_positive_class, weight_negative_class

    weight_positive_class = wpc
    weight_negative_class = 1

    args.optimizer_model = tf.keras.optimizers.Adam(lr=lr_opt)
    

    train_size = sum(pd.read_csv(datapath + "subjects.csv")["set"] == 1)
    val_size = sum(pd.read_csv(datapath + "subjects.csv")["set"] == 2)
    test_size = sum(pd.read_csv(datapath + "subjects.csv")["set"] == 3)
    args.num_covariates = pd.read_csv(datapath + "subjects.csv").filter(like='cov_').shape[1]
    val_size_train = val_size

    if args.epoch_size is None:
        args.epoch_size = train_size
    else:
        val_size_train = min(args.epoch_size // 2, val_size)
        print("Using each epoch", args.epoch_size,"randomly selected training examples")
        print("Validation set size used during training is also set to half the epoch_size")

    inputsize = get_inputsize(genotype_path)

    folder, resultpath = get_paths(args)

    print("weight_possitive_class", weight_positive_class)
    print("weight_possitive_class", weight_negative_class)
    print("jobid =  " + str(jobid))
    print("folder = " + str(folder))
    print("batchsize = " + str(batch_size))
    print("lr = " + str(lr_opt))

    model, masks  = get_classification_network(args)

    csv_logger = K.callbacks.CSVLogger(resultpath + 'train_log.csv', append=True)
    
    early_stop = K.callbacks.EarlyStopping(monitor='val_loss', min_delta=0.0001, patience=patience, verbose=1, mode='auto',
                                           restore_best_weights=True)
    save_best_model = K.callbacks.ModelCheckpoint(resultpath + "bestweights_job.h5", monitor='val_loss',
                                                  verbose=1, save_best_only=True, mode='auto')
    
    reduce_lr = K.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.2,
                              patience=5, min_lr=0.001)
    
    if os.path.exists(resultpath + '/bestweights_job.h5') and not(args.resume):
        print('Model already Trained')
    elif os.path.exists(resultpath + '/bestweights_job.h5') and args.resume:
        print("load and save weights before resuming")
        shutil.copyfile(resultpath + '/bestweights_job.h5', resultpath + '/weights_before_resuming_' 
                        + datetime.datetime.now().strftime("%Y_%m_%d-%I_%M_%p")+'.h5') # save old weights
        log_file = pd.read_csv(resultpath + "/train_log.csv")
        save_best_model = K.callbacks.ModelCheckpoint(resultpath + "bestweights_job.h5", monitor='val_loss',
                                                  verbose=1, save_best_only=True, mode='auto', 
                                                      initial_value_threshold=log_file.val_loss.min())
            
        print("Resuming training")
        model.load_weights(resultpath + '/bestweights_job.h5')
        train_generator = TrainDataGenerator(datapath=datapath,
                                             genotype_path=genotype_path,
                                             batch_size=batch_size,
                                             trainsize=int(train_size),
                                             inputsize=inputsize,
                                             epoch_size=args.epoch_size)
        history = model.fit_generator(
            generator=train_generator,
            shuffle=True,
            epochs=epochs,
            verbose=1,
            callbacks=[early_stop, save_best_model, csv_logger, reduce_lr],
            workers=args.workers,
            use_multiprocessing=multiprocessing,
            validation_data=EvalGenerator(datapath=datapath, genotype_path=genotype_path, batch_size=batch_size,
                                          setsize=val_size_train,
                                          inputsize=inputsize, evalset="validation")

        )
    else:
        print("Start training from scratch")
        train_generator = TrainDataGenerator(datapath=datapath,
                                             genotype_path=genotype_path,
                                             batch_size=batch_size,
                                             trainsize=int(train_size),
                                             inputsize=inputsize,
                                             epoch_size=args.epoch_size)
        history = model.fit_generator(
            generator=train_generator,
            shuffle=True,
            epochs=epochs,
            verbose=1,
            callbacks=[early_stop, save_best_model, csv_logger, reduce_lr],
            workers=args.workers,
            use_multiprocessing=multiprocessing,
            validation_data=EvalGenerator(datapath=datapath, genotype_path=genotype_path, batch_size=batch_size,
                                          setsize=val_size_train,
                                          inputsize=inputsize, evalset="validation")

        )

    plot_loss_function(resultpath)
    model.load_weights(resultpath + '/bestweights_job.h5')
    print("Finished")
    print("Analysis over the validation set")
    pval = model.predict_generator(
        EvalGenerator(datapath=datapath, genotype_path=genotype_path, batch_size=batch_size, setsize=val_size,
                      inputsize=inputsize,
                      evalset="validation"))
    yval = get_labels(datapath, set_number=2)
    auc_val, confusionmatrix_val = evaluate_performance(yval, pval)
    np.save(resultpath + "/pval.npy", pval)

    print("Analysis over the test set")
    ptest = model.predict_generator(
        EvalGenerator(datapath=datapath, genotype_path=genotype_path, batch_size=batch_size, setsize=test_size,
                      inputsize=inputsize, evalset="test"))
    ytest = get_labels(datapath, set_number=3)
    auc_test, confusionmatrix_test = evaluate_performance(ytest, ptest)
    np.save(resultpath + "/ptest.npy", ptest)

    data = {'Jobid': args.ID,
            'Datapath': str(args.path),
            'genotype_path': str(genotype_path),
            'Batchsize': args.batch_size,
            'Learning rate': args.learning_rate,
            'L1 value': args.L1,
            'L1 act': args.L1_act,
            'patience': args.patience,
            'epoch size': args.epoch_size,
            'epochs': args.epochs,
            'Weight positive class': args.wpc,
            'AUC validation': auc_val,
            'AUC test': auc_test,
            'SlURM_JOB_ID': SlURM_JOB_ID}
    
    pd_summary_row = pd.Series(data)
    pd_summary_row.to_csv(resultpath + "/pd_summary_results.csv")
    
    data['confusionmatrix_val'] = confusionmatrix_val
    data['confusionmatrix_test'] = confusionmatrix_test
    
    with open(resultpath + "results_summary.txt", 'w') as f: 
        for key, value in data.items(): 
            f.write('%s:%s\n' % (key, value))

    if os.path.exists(datapath + "/topology.csv"):
        importance_csv = create_importance_csv(datapath, model, masks)
        importance_csv.to_csv(resultpath + "connection_weights.csv")


def train_regression(args):
    SlURM_JOB_ID = get_SLURM_id()
    model = None
    masks = None
    datapath = args.path
    jobid = args.ID
    lr_opt = args.learning_rate
    batch_size = args.batch_size
    epochs = args.epochs
    problem_type = args.problem_type
    patience = args.patience

    if args.genotype_path == "undefined":
        genotype_path = datapath
    else:
        genotype_path = args.genotype_path
    
    args.genotype_path = genotype_path

    if args.mixed_precision == True:
        use_mixed_precision()
        
    if args.workers > 1:
        multiprocessing = True
    else:
        multiprocessing = False
    
    check_data(datapath=datapath, genotype_path=args.genotype_path, mode=problem_type)

    args.optimizer_model = tf.keras.optimizers.Adam(lr=lr_opt)

    train_size = sum(pd.read_csv(datapath + "subjects.csv")["set"] == 1)
    val_size = sum(pd.read_csv(datapath + "subjects.csv")["set"] == 2)
    test_size = sum(pd.read_csv(datapath + "subjects.csv")["set"] == 3)
    args.num_covariates = pd.read_csv(datapath + "subjects.csv").filter(like='cov_').shape[1]
    inputsize = get_inputsize(args.genotype_path)
    args.inputsuze = inputsize
    val_size_train = val_size

    if args.epoch_size is None:
        args.epoch_size = train_size
    else:
        val_size_train = min(args.epoch_size // 2, val_size)
        print("Using each epoch", args.epoch_size,"randomly selected training examples")
        print("Validation set size used during training is also set to half the epoch_size")


    folder, resultpath = get_paths(args)

    print("jobid =  " + str(jobid))
    print("folder = " + str(folder))
    print("batchsize = " + str(batch_size))
    print("lr = " + str(lr_opt))

    model, masks = get_regression_network(args)
        
    csv_logger = K.callbacks.CSVLogger(resultpath + 'train_log.csv', append=True)
    early_stop = K.callbacks.EarlyStopping(monitor='val_loss', min_delta=0.0001, patience=patience, verbose=1, mode='auto',
                                           restore_best_weights=True)
    save_best_model = K.callbacks.ModelCheckpoint(resultpath + "bestweights_job.h5", monitor='val_loss',
                                                  verbose=1, save_best_only=True, mode='auto')
    reduce_lr = K.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.2,
                              patience=5, min_lr=0.001)
    

    if os.path.exists(resultpath + '/bestweights_job.h5') and not(args.resume):
        print('Model already trained')
    elif os.path.exists(resultpath + '/bestweights_job.h5') and args.resume:
        print("load and save weights before resuming")
        shutil.copyfile(resultpath + '/bestweights_job.h5', resultpath + '/weights_before_resuming_' 
                        + datetime.datetime.now().strftime("%Y_%m_%d-%I_%M_%p")+'.h5') # save old weights
        
        log_file = pd.read_csv(resultpath + "/train_log.csv")
        save_best_model = K.callbacks.ModelCheckpoint(resultpath + "bestweights_job.h5", monitor='val_loss',
                                                  verbose=1, save_best_only=True, mode='auto', 
                                                      initial_value_threshold=log_file.val_loss.min())
        print("Resuming training")
        model.load_weights(resultpath + '/bestweights_job.h5')
                
        history = model.fit_generator(
            generator=TrainDataGenerator(datapath=datapath,
                                         genotype_path=genotype_path,
                                         batch_size=batch_size,
                                         trainsize=int(train_size),
                                         inputsize=inputsize,
                                         epoch_size=args.epoch_size),
            shuffle=True,
            epochs=epochs,
            verbose=1,
            callbacks=[early_stop, save_best_model, csv_logger, reduce_lr],
            workers=args.workers,
            use_multiprocessing=multiprocessing,
            validation_data=EvalGenerator(datapath=datapath, genotype_path=genotype_path, batch_size=batch_size,
                                          setsize=val_size_train, inputsize=inputsize, evalset="validation")
        )
     
    else:
        print("Start training from scratch")
        history = model.fit_generator(
            generator=TrainDataGenerator(datapath=datapath,
                                         genotype_path=genotype_path,
                                         batch_size=batch_size,
                                         trainsize=int(train_size),
                                         inputsize=inputsize,
                                         epoch_size=args.epoch_size),
            shuffle=True,
            epochs=epochs,
            verbose=1,
            callbacks=[early_stop, save_best_model, csv_logger, reduce_lr],
            workers=args.workers,
            use_multiprocessing=multiprocessing,
            validation_data=EvalGenerator(datapath=datapath, genotype_path=genotype_path, batch_size=batch_size,
                                          setsize=val_size_train, inputsize=inputsize, evalset="validation")
        )

    plot_loss_function(resultpath)
    model.load_weights(resultpath + '/bestweights_job.h5')
    print("Finished")
    print("Analysis over the validation set")
    pval = model.predict_generator(
        EvalGenerator(datapath=datapath, genotype_path=genotype_path, batch_size=batch_size, setsize=val_size,
                      evalset="validation", inputsize=inputsize))
    yval = get_labels(datapath, set_number=2)
    fig, mse_val, explained_variance_val, r2_val = evaluate_performance_regression(yval, pval)
    np.save(resultpath + "/pval.npy", pval)
    fig.savefig(resultpath + "/validation_predictions.png", bbox_inches='tight', pad_inches=0)

    print("Analysis over the test set")
    ptest = model.predict_generator(
        EvalGenerator(datapath=datapath, genotype_path=genotype_path, batch_size=batch_size, setsize=test_size,
                      inputsize=inputsize, evalset="test"))
    ytest = get_labels(datapath, set_number=3)
    fig, mse_test, explained_variance_test, r2_test = evaluate_performance_regression(ytest, ptest)
    np.save(resultpath + "/ptest.npy", ptest)
    fig.savefig(resultpath + "/test_predictions.png", bbox_inches='tight', pad_inches=0)

    data = {'Jobid': args.ID,
            'Datapath': str(args.path),
            'genotype_path': str(genotype_path),
            'Batchsize': args.batch_size,
            'Learning rate': args.learning_rate,
            'L1 value': args.L1,
            'L1 act': args.L1_act,
            'patience': args.patience,
            'epoch size': args.epoch_size,
            'epochs': args.epochs,
            'MSE validation': mse_val,
            'MSE test': mse_test,
            'Explained variance val': explained_variance_val,
            'Explained variance test': explained_variance_test,
            'R2_validation': r2_val,
            'R2_test': r2_test,           
            'SlURM_JOB_ID': SlURM_JOB_ID}
    
    pd_summary_row = pd.Series(data)
    pd_summary_row.to_csv(resultpath + "/pd_summary_results.csv")
    
    with open(resultpath + "results_summary.txt", 'w') as f: 
        for key, value in data.items(): 
            f.write('%s:%s\n' % (key, value))

    if os.path.exists(datapath + "/topology.csv"):
        importance_csv = create_importance_csv(datapath, model, masks)
        importance_csv.to_csv(resultpath + "connection_weights.csv")



def get_network(args):
    regression = args.regression if hasattr(args, 'regression') else False

    if args.network_name == "lasso":
        print("lasso network")
        model, masks = lasso(inputsize=args.inputsize, l1_value=args.l1_value, L1_act=args.L1_act if hasattr(args, 'L1_act') else None)

    elif args.network_name == "sparse_directed_gene_l1" and not regression:
        print("sparse_directed_gene_l1 network")
        model, masks = sparse_directed_gene_l1(inputsize=args.inputsize, l1_value=args.l1_value)

    elif args.network_name == "gene_network_multiple_filters":
        print("gene_network_multiple_filters network")
        model, masks = gene_network_multiple_filters(datapath=args.datapath, inputsize=args.inputsize, genotype_path=args.genotype_path,
                                                     l1_value=args.l1_value, L1_act=args.L1_act, 
                                                     regression=regression, num_covariates=args.num_covariates,
                                                     filters=args.filters)

    elif args.network_name == "gene_network_snp_gene_filters":
        print("gene_network_snp_gene_filters network")
        model, masks = gene_network_snp_gene_filters(datapath=args.datapath, inputsize=args.inputsize, genotype_path=args.genotype_path,
                                                     l1_value=args.l1_value, L1_act=args.L1_act, 
                                                     regression=regression, num_covariates=args.num_covariates,
                                                     filters=args.filters)

    elif args.network_name == "regression_height" and regression:
        print("regression_height network")
        model, masks = regression_height(inputsize=args.inputsize, l1_value=args.l1_value)

    else:
        if os.path.exists(args.datapath + "/topology.csv"):
            model, masks = create_network_from_csv(datapath=args.datapath, inputsize=args.inputsize, genotype_path=args.genotype_path,
                                                   l1_value=args.l1_value, L1_act=args.L1_act, regression=regression,
                                                   num_covariates=args.num_covariates)
        elif len(glob.glob(args.datapath + "/*.npz")) > 0:
            model, masks = create_network_from_npz(datapath=args.datapath, inputsize=args.inputsize, genotype_path=args.genotype_path,
                                                   l1_value=args.l1_value, L1_act=args.L1_act, regression=regression,
                                                   num_covariates=args.num_covariates, 
                                                   mask_order=args.mask_order if hasattr(args, 'mask_order') else None)

    if regression:
        model.compile(loss="mse", optimizer=args.optimizer_model, metrics=["mse"])
    else:
        model.compile(loss=weighted_binary_crossentropy, optimizer=args.optimizer_model,
                      metrics=["accuracy", sensitivity, specificity])

    with open(args.resultpath + '/model_architecture.txt', 'w') as fh:
        model.summary(print_fn=lambda x: fh.write(x + '\n'))

    return model, masks



def get_classification_network(args):
    """needs the following inputs
    args.inputsize
    args.l1_value
    args.L1_act
    args.datapath
    args.genotype_path
    args.num_covariates
    args.filter
    """
    
    if args.network_name == "lasso":
        print("lasso network")
        model, masks = lasso(inputsize=args.inputsize, l1_value=args.l1_value, L1_act=args.L1_act)
        
    elif args.network_name == "sparse_directed_gene_l1":
        print("sparse_directed_gene_l1 network")
        model, masks = sparse_directed_gene_l1(inputsize=args.inputsize, l1_value=args.l1_value)
    elif args.network_name == "gene_network_multiple_filters":
        print("gene_network_multiple_filters network")
        model, masks = gene_network_multiple_filters(datapath=args.datapath, inputsize=args.inputsize, genotype_path=args.genotype_path,
                                                   l1_value=args.l1_value, L1_act=args.L1_act, 
                                                   regression=False,num_covariates=args.num_covariates,
                                                   filters=args.filters)
    elif args.network_name == "gene_network_snp_gene_filters":
        print("gene_network_snp_gene_filters network")
        model, masks = gene_network_snp_gene_filters(datapath=args.datapath, inputsize=args.inputsize, genotype_path=args.genotype_path,
                                                   l1_value=args.l1_value, L1_act =args.L1_act,
                                                   regression=False, num_covariates=args.num_covariates,
                                                   filters=args.filters)
    else:
        if os.path.exists(args.datapath + "/topology.csv"):
            model, masks = create_network_from_csv(datapath=args.datapath, inputsize=args.inputsize, genotype_path=args.genotype_path,
                                                   l1_value=args.l1_value, L1_act =args.L1_act, num_covariates=args.num_covariates)
        elif len(glob.glob(args.datapath + "/*.npz")) > 0:
            model, masks = create_network_from_npz(datapath=args.datapath, inputsize=args.inputsize, genotype_path=args.genotype_path,
                                                   l1_value=args.l1_value, L1_act =args.L1_act, num_covariates=args.num_covariates, 
                                                   mask_order=args.mask_order)

    model.compile(loss=weighted_binary_crossentropy, optimizer=args.optimizer_model,
                  metrics=["accuracy", sensitivity, specificity])

    with open(args.resultpath + '/model_architecture.txt', 'w') as fh:
        model.summary(print_fn=lambda x: fh.write(x + '\n'))

    return model, masks


def get_regression_network(args):
    if args.network_name == "lasso":
        print("lasso network")
        model, masks = lasso(inputsize=args.inputsize, l1_value=args.l1_value)
    elif args.network_name == "regression_height":
        print("regression_height network")
        model, masks = regression_height(inputsize=args.inputsize, l1_value=args.l1_value)
    elif args.network_name == "gene_network_multiple_filters":
        print("gene_network_multiple_filters network")
        model, masks = gene_network_multiple_filters(datapath=args.datapath, inputsize=args.inputsize, genotype_path=args.genotype_path,
                                                   l1_value=args.l1_value, L1_act =args.L1_act, regression=True, 
                                                     num_covariates=args.num_covariates,  filters=args.filters)
    elif args.network_name == "gene_network_snp_gene_filters":
        print("gene_network_snp_gene_filters network")
        model, masks = gene_network_snp_gene_filters(datapath=args.datapath, inputsize=args.inputsize, genotype_path=args.genotype_path,
                                                   l1_value=args.l1_value, L1_act=args.L1_act, regression=True, 
                                                     num_covariates=args.num_covariates, filters=args.filters)       
        
        
    else:
        if os.path.exists(args.datapath + "/topology.csv"):
            model, masks = create_network_from_csv(datapath=args.datapath, inputsize=args.inputsize, genotype_path=args.genotype_path,
                                                   l1_value=args.l1_value, L1_act=args.L1_act, regression=True, 
                                                   num_covariates=args.num_covariates)
        elif len(glob.glob(args.datapath + "/*.npz")) > 0:
            model, masks = create_network_from_npz(datapath=args.datapath, inputsize=args.inputsize, genotype_path=args.genotype_path,
                                                   l1_value=args.l1_value, L1_act=args.L1_act, regression=True, 
                                                   num_covariates=args.num_covariates)

    model.compile(loss="mse", optimizer=args.optimizer_model,
                  metrics=["mse"])

    with open(args.resultpath + '/model_architecture.txt', 'w') as fh:
        model.summary(print_fn=lambda x: fh.write(x + '\n'))
    
    return model, masks