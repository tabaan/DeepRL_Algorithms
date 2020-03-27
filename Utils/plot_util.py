import math
import traceback

import click
import seaborn as sns
import pandas as pd
import matplotlib.pyplot as plt
import os
import numpy as np
import tensorflow as tf
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

"""
plot the performance of core from TensorBoard Log History
"""
DEFAULT_SIZE_GUIDANCE = {
    "scalars": 0,
    "tensors": 0,
}

# palette=sns.color_palette("hls", 8)
# themes = ['deep', 'muted', 'pastel', 'bright', 'dark', 'colorblind']
flatui = ["#9b59b6", "#3498db", "#95a5a6", "#e74c3c", "#34495e", "#2ecc71"]

sns.set(style="white", font_scale=1.2, rc={"lines.linewidth": 1.5}, palette=sns.color_palette(flatui))


# plt.style.use('bmh')

def plot_data(data, x_axis='num steps', y_axis="average reward", hue="algorithm", smooth=1, ax=None, **kwargs):
    if smooth > 1:
        """
        smooth data with moving window average.
        that is,
            smoothed_y[t] = average(y[t-k], y[t-k+1], ..., y[t+k-1], y[t+k])
        where the "smooth" param is width of that window (2k+1)
        """
        y = np.ones(smooth)
        for datum in data:
            x = np.asarray(datum[y_axis])
            z = np.ones(len(x))
            smoothed_x = np.convolve(x, y, 'same') / np.convolve(z, y, 'same')
            datum[y_axis] = smoothed_x

    if isinstance(data, list):
        data = pd.concat(data, ignore_index=True, sort=True)

    sns.lineplot(data=data, x=x_axis, y=y_axis, hue=hue, ci='sd', ax=ax, **kwargs)
    # ax.legend(loc='best').set_draggable(True)
    """Spining up style"""
    ax.legend(loc='upper center', ncol=6, handlelength=1, frameon=False,
              mode="expand", borderaxespad=0.02, prop={'size': 13})

    xscale = np.max(np.asarray(data[x_axis])) > 5e3
    if xscale:
        # Just some formatting niceness: x-axis scale in scientific notation if max x is large
        ax.ticklabel_format(style='sci', axis='x', scilimits=(0, 0))
    plt.tight_layout(pad=1.2)


def load_event_scalars(log_path):
    feature = log_path.split(os.sep)[-1]
    print(f"Processing logfile: {os.path.abspath(log_path)}")
    if feature.find("_") != -1:
        feature = feature.split("_")[-1]
    df = pd.DataFrame()
    try:
        event_acc = EventAccumulator(log_path, DEFAULT_SIZE_GUIDANCE)
        event_acc.Reload()
        tags = event_acc.Tags()["scalars"]
        env_list = event_acc.Scalars
        use_tensorflow = False
        if not tags:
            tags = event_acc.Tags()["tensors"]
            env_list = event_acc.tensors.Items
            use_tensorflow = True
        for tag in tags:
            event_list =env_list(tag)
            if use_tensorflow:
                values = list(map(lambda x: float(tf.make_ndarray(x.tensor_proto)), event_list))
                step = list(map(lambda x: x.step, event_list))
                df[tag] = values
            else:
                values = list(map(lambda x: x.value, event_list))
                step = list(map(lambda x: x.step, event_list))
                df = pd.DataFrame({feature: values}, index=step)
    # Dirty catch of DataLossError
    except:
        print("Event file possibly corrupt: {}".format(os.path.abspath(log_path)))
        traceback.print_exc()
    return df


def get_env_alg_log(log_path):
    """
    拆分Env
    :param log_path:
    :return:
    """
    alg = log_path.split(os.sep)[-1]
    if alg.find("_") != -1:
        alg = alg.rsplit("_", maxsplit=1)[0]
    env_alg_fulldir = lambda x: os.path.join(log_path, x)
    alg_features = [env_alg_fulldir(fea) for fea in os.listdir(log_path) if os.path.isdir(env_alg_fulldir(fea))]
    if alg_features:
        df = pd.concat([load_event_scalars(feature) for feature in alg_features], axis=1)
    else:
        df = load_event_scalars(log_path)
    if "num steps" in df:
        df["num steps"] = df["num steps"].cumsum()
    else:
        df["num steps"] = (np.ones((1, df.shape[0])) * 4000).cumsum()
        df = df[df["num steps"] <= 3500000]
    df["algorithm"] = [alg] * df.shape[0]
    return df


def plot_all_logs(log_dir=None, x_axis=None, y_axis=None, hue=None, smooth=1, env_filter_func=None,
                  alg_filter_func=None):
    if y_axis is None:
        y_axis = ['min reward', 'average reward', 'max reward', 'total reward']

    basedir = os.path.dirname(log_dir)  # ../log/
    fulldir = lambda x: os.path.join(basedir, x)  # ../log/Ant-v3/
    envs_logdirs = sorted(
        [fulldir(x) for x in os.listdir(basedir) if os.path.isdir(fulldir(x))])  # [../log/Ant-v3/, ../log/Hopper-v3/]
    if env_filter_func:
        envs_logdirs = sorted(filter(env_filter_func, envs_logdirs))
    print("All envs are: ", list(map(os.path.abspath, envs_logdirs)))

    num_envs = len(envs_logdirs)
    sub_plot_height = round(math.sqrt(num_envs))
    sub_plot_width = math.ceil(num_envs / sub_plot_height)

    envs_fulldir = lambda env_dir, alg_dir: os.path.join(env_dir, alg_dir)
    for y_ax in y_axis:
        k = 0
        fig, axes = plt.subplots(sub_plot_height, sub_plot_width, figsize=(6 * sub_plot_width, 4 * sub_plot_height))
        for env_dir in envs_logdirs:
            if sub_plot_height == 1:
                if sub_plot_width == 1:
                    ax = axes
                else:
                    ax = axes[k]
            else:
                ax = axes[k // sub_plot_width][k % sub_plot_width]

            env_id = env_dir.split(os.sep)[-1]
            env_alg_dirs = sorted(
                filter(os.path.isdir, [envs_fulldir(env_dir, alg_dir) for alg_dir in os.listdir(env_dir)]))
            if alg_filter_func:
                env_alg_dirs = sorted(filter(alg_filter_func, env_alg_dirs))
            print(f"Env id: {env_id}, logs: {list(map(os.path.abspath, env_alg_dirs))}")

            env_log_df = [get_env_alg_log(env_alg_dir) for env_alg_dir in env_alg_dirs]
            make_plot(data=env_log_df, x_axis=x_axis, y_axis=y_ax, smooth=smooth, title=env_id, hue=hue, ax=ax)
            k += 1
    plt.show()


def make_plot(data, x_axis=None, y_axis=None, title=None, hue=None, smooth=1, estimator='mean', ax=None):
    estimator = getattr(np, estimator)
    plot_data(data, x_axis=x_axis, y_axis=y_axis, hue=hue, smooth=smooth, ax=ax, estimator=estimator)
    if title:
        ax.set_title(title)


# @click.command()
# @click.option("--log_dir", type=str, default="../log/", help="Directory to load tensorboard logs")
# @click.option("--x_axis", type=str, default="num steps", help="X axis data")
# @click.option("--y_axis", type=list, default=["average reward"], help="Y axis data(can be multiple)")
# @click.option("--hue", type=str, default="algorithm", help="Hue for legend")
def main(log_dir='../Algorithms/pytorch/log/', x_axis='num steps', y_axis=['average reward'], hue='algorithm',
         env_filter_func=None, alg_filter_func=None):
    """
    1.遍历所有环境, 对每个环境下所有算法的log信息进行绘图
    2.对每个环境下的所有算法数据载入一个 data frame
    :return:
    """
    plot_all_logs(log_dir=log_dir, x_axis=x_axis, y_axis=y_axis, hue=hue,
                  smooth=11,
                  env_filter_func=env_filter_func,
                  alg_filter_func=alg_filter_func)

if __name__ == "__main__":
    env_filter_func_dqn = lambda x: x.split(os.sep)[-1] in ["CartPole-v1", "MountainCar-v0", "Acrobot-v1",
                                                            "LunarLander-v2"]
    env_filter_func = lambda x: x.split(os.sep)[-1] in ["MountainCar-v0"]
    env_filter_func_pg = lambda x: x.split(os.sep)[-1] in ["HalfCheetah-v3", "Hopper-v3", "Walker2d-v3", "Swimmer-v3",
                                                           "Ant-v3", "BipedalWalker-v3"]
    alg_filter_func = lambda x: x.split(os.sep)[-1].rsplit("_")[0] in []
    main(env_filter_func=env_filter_func_dqn, alg_filter_func=None)
    sns.despine()
