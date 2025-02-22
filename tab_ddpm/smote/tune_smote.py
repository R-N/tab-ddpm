import optuna
from tab_ddpm import lib
from copy import deepcopy
import argparse
from tab_ddpm.util import try_argparse
import tempfile
from pathlib import Path
import os
from tab_ddpm.scripts.eval_catboost import train_catboost
from tab_ddpm.scripts.eval_seeds import main as eval_seeds
from .sample_smote import sample_smote
#import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('data_path', type=str)
parser.add_argument('eval_type', type=str)

args = try_argparse(parser)
real_data_path = args.data_path
eval_type = args.eval_type

def objective(trial):
    
    k_neighbours = trial.suggest_int("k_neighbours", 5, 20)
    frac_samples = 2 ** trial.suggest_int('frac_samples', -2, 3)

    # z = \lam*x + (1 - \lam)*y, \lam ~ U[frac_lam_del/2, 1-frac_lam_del/2]
    frac_lam_del = trial.suggest_float("frac_lam_del", 0.0, 0.95, step=0.05)

    score = 0.0
    with tempfile.TemporaryDirectory() as dir_:
        dir_ = Path(dir_)
        for seed in range(5): 
            sample_smote(
                parent_dir=dir_,
                real_data_path=real_data_path, 
                eval_type=eval_type,
                frac_samples=frac_samples,
                frac_lam_del=frac_lam_del,
                k_neighbours=k_neighbours,
                change_val=True,
                seed=seed
            )
            T_dict = {
                "seed": 0,
                "normalization": None,
                "num_nan_policy": None,
                "cat_nan_policy": None,
                "cat_min_frequency": None,
                "cat_encoding": None,
                "y_policy": "default"
            }
            metrics = train_catboost(
                parent_dir=dir_,
                real_data_path=real_data_path, 
                eval_type=eval_type,
                T_dict=T_dict,
                change_val=True,
                seed = 0
            )

            score += metrics.get_val_score()

    return score / 5

study = optuna.create_study(
    direction='maximize',
    sampler=optuna.samplers.TPESampler(seed=0),
)

study.optimize(objective, n_trials=5, show_progress_bar=True)

os.makedirs(f"exp/{Path(real_data_path).name}/smote/", exist_ok=True)
config = {
    "parent_dir": f"exp/{Path(real_data_path).name}/smote/",
    "real_data_path": real_data_path,
    "seed": 0,
    "smote_params": {},
    "sample": {"seed": 0},
    "eval": {
        "type": {"eval_model": "catboost", "eval_type": eval_type},
        "T": {
            "seed": 0,
            "normalization": None,
            "num_nan_policy": None,
            "cat_nan_policy": None,
            "cat_min_frequency": None,
            "cat_encoding": None,
            "y_policy": "default"
        },
    }
}

config["smote_params"] = study.best_params
config["smote_params"]["frac_samples"] = 2 ** config["smote_params"]["frac_samples"]

lib.dump_config(config, config["parent_dir"]+"config.toml")

#subprocess.run(['python', "scripts/eval_seeds.py", '--config', f'{config["parent_dir"]+"config.toml"}', '10', "smote", eval_type, "catboost", "5"], check=True)
eval_seeds(
    config=f'{config["parent_dir"]+"config.toml"}',
    n_seeds=10,
    sampling_method="smote",
    eval_type=eval_type,
    model_type="catboost",
    n_datasets=5
)
