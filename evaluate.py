import hydra
from omegaconf import DictConfig
import tensorflow as tf

import data_generator
from utils.general_utils import join_paths, set_gpus
from models.model import prepare_model
from losses.loss import dice_coef
from losses.unet_loss import unet3p_hybrid_loss


def evaluate(cfg: DictConfig):
    if cfg.USE_MULTI_GPUS.VALUE:
        set_gpus(cfg.USE_MULTI_GPUS.GPU_IDS)

    val_generator = data_generator.DataGenerator(cfg, mode="VAL")

    optimizer = tf.keras.optimizers.Adam(lr=cfg.HYPER_PARAMETERS.LEARNING_RATE)
    if cfg.USE_MULTI_GPUS.VALUE:
        strategy = tf.distribute.MirroredStrategy(
            cross_device_ops=tf.distribute.HierarchicalCopyAllReduce()
        )
        print('Number of visible gpu devices: {}'.format(strategy.num_replicas_in_sync))
        with strategy.scope():
            model = prepare_model(cfg)
    else:
        model = prepare_model(cfg)

    model.compile(
        optimizer=optimizer,
        loss=unet3p_hybrid_loss,
        metrics=[dice_coef],
    )

    checkpoint_path = join_paths(
        cfg.WORK_DIR,
        cfg.CALLBACKS.MODEL_CHECKPOINT.PATH,
        f"{cfg.MODEL.WEIGHTS_FILE_NAME}.hdf5"
    )
    # TODO: verify without augment it produces same results
    model.load_weights(checkpoint_path, by_name=True, skip_mismatch=True)
    model.summary()

    evaluation_metric = "dice_coef"
    if len(model.outputs) > 1:
        evaluation_metric = f"{model.output_names[0]}_dice_coef"

    result = model.evaluate(
        x=val_generator,
        batch_size=cfg.HYPER_PARAMETERS.BATCH_SIZE,
        workers=cfg.DATALOADER_WORKERS,
        return_dict=True,
    )

    return result, evaluation_metric


@hydra.main(version_base=None, config_path="configs", config_name="config")
def main(cfg: DictConfig):
    result, evaluation_metric = evaluate(cfg)
    print(result)
    print(f"Validation dice coefficient: {result[evaluation_metric]}")


if __name__ == "__main__":
    main()