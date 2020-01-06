import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from DQN.Models.DuelingMLPPolicy import DuelingMLPPolicy
from Utils.replay_memory import Memory


class DuelingDQN:
    def __init__(self,
                 num_states,
                 num_actions,
                 learning_rate=0.01,
                 gamma=0.90,
                 batch_size=128,
                 epsilon=0.90,
                 memory_size=20000,
                 update_target_gap=50,
                 enable_gpu=False):
        if enable_gpu:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device("cpu")

        self.gamma = gamma
        self.batch_size = batch_size
        self.update_target_gap = update_target_gap
        self.epsilon = epsilon

        self.num_learn_step = 0

        self.memory = Memory(memory_size)
        self.eval_net, self.target_net = DuelingMLPPolicy(num_states, num_actions).to(self.device), DuelingMLPPolicy(
            num_states,
            num_actions).to(
            self.device)
        self.optimizer = optim.Adam(self.eval_net.parameters(), lr=learning_rate)
        self.loss_func = nn.MSELoss()

    # greedy 策略动作选择
    def choose_action(self, state, num_actions):
        state = torch.unsqueeze(torch.tensor(state), 0).to(self.device)
        if np.random.uniform() <= self.epsilon:  # greedy policy
            action_val = self.eval_net(state.float())
            action = action_val.max(1)[1].cpu().numpy()
            return action[0]
        else:
            action = np.random.randint(0, num_actions)
            return action

    def learn(self):
        # 更新目标网络 target_net
        if self.num_learn_step % self.update_target_gap == 0:
            self.target_net.load_state_dict(self.eval_net.state_dict())
        self.num_learn_step += 1

        # 从Memory中采batch
        batch = self.memory.sample(self.batch_size)
        batch_state = torch.cat(batch.state).to(self.device)
        batch_action = torch.stack(batch.action, 0).to(self.device)
        batch_reward = torch.stack(batch.reward, 0).to(self.device)
        batch_next_state = torch.cat(batch.next_state).to(self.device)

        # 训练eval_net
        q_eval = self.eval_net(batch_state.float()).gather(1, batch_action)
        # 不更新 target_net参数
        q_next = self.target_net(batch_next_state.float()).detach()
        q_target = batch_reward + self.gamma * q_next.max(1)[0].view(self.batch_size, 1)

        # 计算误差
        loss = self.loss_func(q_eval, q_target)

        # 更新梯度
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
