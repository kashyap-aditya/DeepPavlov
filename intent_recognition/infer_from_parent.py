from deeppavlov.core.common.registry import _REGISTRY
from deeppavlov.core.common.params import from_params
from deeppavlov.core.models.trainable import Trainable
from deeppavlov.data.dataset import Dataset
from deeppavlov.data.dataset_readers.dataset_reader import DatasetReader
from deeppavlov.core.models.keras_model import KerasModel

from intent_recognition.intent_dataset import IntentDataset
from intent_recognition.intent_dataset_reader import IntentDatasetReader
from intent_recognition.utils import EmbeddingsDict
from intent_recognition.intent_models import KerasIntentModel
from intent_recognition.intent_model_from_parent import KerasIntentModelFromParent
from intent_recognition.intent_preprocessing import IntentPreprocessing

import os, sys
import json
import numpy as np
from sklearn.metrics import log_loss, accuracy_score
from metrics import fmeasure


def log_metrics(names, values, updates=None, mode='train'):
    sys.stdout.write("\r")  # back to previous line
    print("%s -->\t" % mode, end="")
    if updates is not None:
        print("updates: %d\t" % updates, end="")

    for id in range(len(names)):
        print("%s: %f\t" % (names[id], values[id]), end="")
    print(" ")  # , end='\r')


def main(config_name='config_infer.json'):
    with open(config_name) as f:
        config = json.load(f)

    # Reading datasets from files
    reader_config = config['dataset_reader']
    reader = _REGISTRY[reader_config['name']]
    data = reader.read(train_data_path=reader_config.get('train_data_path'),
                       valid_data_path=reader_config.get('valid_data_path'),
                       test_data_path=reader_config.get('test_data_path'))

    # Building dict of datasets
    dataset_config = config['dataset']
    dataset = from_params(_REGISTRY[dataset_config['name']],
                          dataset_config, data=data)

    # Merging train and valid dataset for further split on train/valid
    dataset.merge_data(fields_to_merge=['train', 'valid'], new_field='train')
    dataset.split_data(field_to_split='train', new_fields=['train', 'valid'], proportions=[0.9, 0.1])

    preproc = IntentPreprocessing()
    dataset = preproc.preprocess(dataset=dataset, data_type='train')
    dataset = preproc.preprocess(dataset=dataset, data_type='valid')
    dataset = preproc.preprocess(dataset=dataset, data_type='test')

    # Extracting unique classes
    intents = dataset.extract_classes()
    print("Considered intents:", intents)

    # Initializing model
    model_config = config['model']
    model = from_params(_REGISTRY[model_config['name']],
                        model_config, opt=model_config, classes=intents)

    test_batch_gen = dataset.batch_generator(batch_size=model.opt['batch_size'],
                                              data_type='test')
    test_preds = []
    test_true = []
    for test_id, test_batch in enumerate(test_batch_gen):
        test_preds.extend(model.infer(test_batch[0]))
        test_true.extend(model.labels2onehot(test_batch[1]))
        if model_config['show_examples'] and test_id == 0:
            for j in range(model.opt['batch_size']):
                print(test_batch[0][j],
                      test_batch[1][j],
                      model.proba2labels([test_preds[j]]))

    test_true = np.asarray(test_true, dtype='float64')
    test_preds = np.asarray(test_preds, dtype='float64')

    test_values = []
    test_values.append(log_loss(test_true, test_preds))
    test_values.append(accuracy_score(test_true, model.proba2onehot(test_preds)))
    test_values.append(fmeasure(test_true, model.proba2onehot(test_preds)))

    log_metrics(names=model.metrics_names,
                values=test_values,
                mode='test')



if __name__ == '__main__':
    main()
