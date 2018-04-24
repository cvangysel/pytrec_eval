#!/bin/env python

import argparse
import collections
import json
import logging
import numpy as np
import gym
import gym.spaces
import gym.spaces.discrete as discrete
import sklearn.model_selection
import sys
import time

import pytrec_eval

import pyndri
import pyndri.utils


class NullAgent(object):

    @property
    def name(self):
        return 'null'

    def act(self, observation, reward, done, deterministic=True):
        return None

    def can_learn(self):
        return False

    def learn(self, env, *args, **kwargs):
        return None


class RandomAgent(object):

    def __init__(self, action_space):
        self.action_space = action_space

    @property
    def name(self):
        return 'random'

    def act(self, observation, reward, done, deterministic=True):
        return self.action_space.sample()

    def can_learn(self):
        return False

    def learn(self, env, *args, **kwargs):
        return None


class TabularQAgent(object):

    def __init__(self, observation_space, action_space, **userconfig):
        if not isinstance(observation_space, discrete.Discrete):
            raise RuntimeError()

        if not isinstance(action_space, discrete.Discrete):
            raise RuntimeError()

        self.observation_space = observation_space
        self.action_space = action_space
        self.action_n = action_space.n

        self.config = {
            'init_mean': 0.0,      # Initialize Q values with this mean
            'init_std': 0.0,       # Initialize Q values with this std dev
            'learning_rate': 0.1,
            'eps': 0.05,           # Epsilon in epsilon greedy policies
            'discount': 0.95,
            'n_iter': 1000,        # Number of iterations
        }

        self.config.update(userconfig)
        self.q = collections.defaultdict(
            lambda:
                self.config["init_std"] *
                np.random.randn(self.action_n) +
                self.config["init_mean"])

    @property
    def name(self):
        return 'tabular'

    def act(self, observation, reward, done, eps=None, deterministic=False):
        if not deterministic and eps is None:
            eps = self.config["eps"]
        elif deterministic:
            eps = -1.0

        if isinstance(observation, np.ndarray):
            observation = tuple(observation.tolist())
        elif isinstance(observation, tuple):
            pass
        else:
            raise RuntimeError()

        # epsilon greedy.
        action = np.argmax(self.q[observation]) \
            if np.random.random() > eps else self.action_space.sample()
        return action

    def can_learn(self):
        return True

    def learn(self, env, *args, **kwargs):
        total_reward = 0.0

        reward = 0.0
        done = False

        obs = env._reset(*args, **kwargs)
        obs = tuple(obs.tolist())

        q = self.q

        for t in range(self.config["n_iter"]):
            action = self.act(obs, reward, done)
            obs2, reward, done, _ = env.step(action)
            obs2 = tuple(obs2.tolist())

            if not done:
                future = np.max(q[obs2])
            else:
                future = 0.0

            q[obs][action] = \
                (1.0 - self.config['learning_rate']) * q[obs][action] + \
                self.config['learning_rate'] * (
                    reward + self.config['discount'] * future)

            obs = obs2

            total_reward += reward

            if t > 0 and t % 1000 == 0:
                logging.info('Step=%d, total reward=%.4f, average reward=%.4f',
                             t, total_reward, total_reward / t)

            if done:
                break

        return total_reward


class RetrievalEnv(gym.Env):

    def __init__(self, index,
                 measure='ndcg',
                 max_num_expanded_query_terms=None):
        vocabulary = pyndri.extract_dictionary(index)

        self.vocabulary = vocabulary

        self.action_space = gym.spaces.Discrete(len(self.vocabulary))
        self.observation_space = gym.spaces.Discrete(len(self.vocabulary))

        self.index = index
        self.measure = measure
        self.max_num_expanded_query_terms = max_num_expanded_query_terms

        assert self.max_num_expanded_query_terms is None or \
            self.max_num_expanded_query_terms > 0

        self.state = None  # Taken care of in reset().

    def _compute_utility(self, manyhot_query):
        query = sorted(np.nonzero(manyhot_query)[0])

        if len(query) >= 1:
            query_str = '#weight({})'.format(
                ' '.join(
                    '{:.2f} {}'.format(
                        manyhot_query[token_id],
                        self.vocabulary.id2token[token_id])
                    for token_id in query
                    if token_id > 0))
        else:
            query_str = None

        if not query_str:
            self.state['cache'][query_str] = {'0': {}}
        elif query_str not in self.state['cache']:
            document_scores = {
                self.index.ext_document_id(internal_doc_id): score
                for internal_doc_id, score in
                self.index.query(query_str, results_requested=10)}

            self.state['cache'][query_str] = {'0': document_scores}

        run = self.state['cache'][query_str]

        evaluation = self.state['evaluator'].evaluate(run)
        utility = evaluation['0'][self.measure]

        return utility

    def _step(self, action):
        if action > 0:
            next_manyhot_query = self.state['manyhot_query'].copy()
            next_manyhot_query[action] += 1

            prev_utility = self.state['utility']

            self.state['manyhot_query'] = next_manyhot_query
            self.state['utility'] = self._compute_utility(next_manyhot_query)

            reward = self.state['utility'] - prev_utility

            done = self.state['utility'] == 1.0
        else:
            next_manyhot_query = self.state['manyhot_query'].copy()
            reward = 0
            done = False

        self.state['num_steps'] += 1

        if self.max_num_expanded_query_terms and \
                self.state['num_steps'] >= \
                self.max_num_expanded_query_terms:
            done = True

        return next_manyhot_query > 0.0, reward, done, {}

    def _query_to_many_hot(self, query_token_ids):
        many_hot = np.zeros(len(self.vocabulary) + 1, dtype=np.int32)
        for token_idx in query_token_ids:
            many_hot[token_idx] = 1
        return many_hot

    def _reset(self, query_str, relevance):
        query_token_ids = [
            self.vocabulary.token2id[token]
            for token in self.index.tokenize(query_str)
            if token in self.vocabulary.token2id]
        manyhot_query = self._query_to_many_hot(query_token_ids)

        self.state = {
            'manyhot_query': manyhot_query,
            'evaluator': pytrec_eval.RelevanceEvaluator(
                {'0': relevance}, {self.measure}),
            'num_steps': 0,
            'cache': {},
        }

        self.original_utility = self._compute_utility(manyhot_query)
        self.state['utility'] = self.original_utility

        return self.state['manyhot_query'].copy()

    def _render(self, mode='human', close=False):
        return

    def _seed(self, seed=None):
        return []


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('--index', type=pyndri.utils.existing_directory_path,
                        required=True)

    parser.add_argument('--limit_queries_for_debug',
                        type=pyndri.utils.positive_int,
                        default=None)

    parser.add_argument('--test_set_size', type=float, default=None)

    parser.add_argument('--num_epochs',
                        type=pyndri.utils.positive_int,
                        default=500)

    parser.add_argument('--queries', type=pyndri.utils.existing_file_path,
                        required=True)
    parser.add_argument('--query_relevance',
                        type=pyndri.utils.existing_file_path,
                        required=True)

    parser.add_argument('--trace_output',
                        type=pyndri.utils.nonexisting_file_path,
                        required=True)

    args = parser.parse_args()

    args.index = pyndri.Index(args.index)

    try:
        pyndri.utils.configure_logging(args)
    except IOError:
        return -1

    qrel = {}

    env = RetrievalEnv(args.index, max_num_expanded_query_terms=5)

    with open(args.queries, 'r') as f_queries:
        queries = list(pyndri.utils.read_queries(f_queries).items())

    with open(args.query_relevance, 'r') as f_qrel:
        qrel = pytrec_eval.parse_qrel(f_qrel)

    queries_idx = np.array(list(range(len(queries))))
    np.random.shuffle(queries_idx)

    if args.limit_queries_for_debug:
        queries_idx = queries_idx[:args.limit_queries_for_debug]

    if args.test_set_size and args.test_set_size > 0:
        train_queries_idx, test_queries_idx = \
            sklearn.model_selection.train_test_split(
                queries_idx, test_size=args.test_set_size)

        logging.info('Split query set into train=%s and test=%s.',
                     train_queries_idx.size, test_queries_idx.size)

        def evaluate(agent):
            episode_count = 1
            max_steps = 10

            logging.info('Evaluating %s using %d queries.',
                         agent, len(test_queries_idx))

            ndcgs = []

            for idx, query_idx in enumerate(test_queries_idx):
                reward = 0
                done = False

                for i in range(episode_count):
                    query_id, query_str = queries[query_idx]
                    ob = env._reset(query_str, qrel[query_id])

                    for _ in range(max_steps):
                        action = agent.act(ob, reward, done,
                                           deterministic=True)

                        if action is not None:
                            ob, reward, done, _ = env.step(action)

                        if done:
                            break

                    logging.debug('Query %s: %.4f -> %.4f',
                                  query_id,
                                  env.original_utility, env.state['utility'])

                    ndcgs.append(env.state['utility'])

                if idx > 0 and (idx + 1) % 10 == 0:
                    logging.info('Finished %d out of %d queries.',
                                 idx + 1, len(test_queries_idx))

            return ndcgs
    else:
        train_queries_idx = queries_idx

        def evaluate(agent):
            return np.nan,

    if args.trace_output:
        f_trace_out = open(args.trace_output, 'w')
    else:
        f_trace_out = None

    agents = [
        NullAgent(),
        RandomAgent(env.action_space),
        TabularQAgent(env.observation_space, env.action_space)]

    ndcg_per_agent = {}

    for agent in agents:
        if agent.can_learn():
            logging.info('Training %s using %d queries.',
                         agent, len(train_queries_idx))

            avg_rewards = []
            test_set_ndcgs = []

            start_time = time.time()

            for epoch_idx in range(args.num_epochs):
                logging.info('Epoch %d.', epoch_idx + 1)

                np.random.shuffle(train_queries_idx)

                avg_reward = 0.0

                for idx, query_idx in enumerate(train_queries_idx):
                    query_id, query_str = queries[query_idx]
                    relevance = qrel[query_id]

                    logging.debug('Learning from %s.', query_id)

                    total_reward = agent.learn(env, query_str, relevance)

                    if total_reward is not None:
                        avg_reward += total_reward

                    if idx > 0 and (idx + 1) % 500 == 0:
                        logging.info('Finished %d out of %d queries.',
                                     idx + 1, len(train_queries_idx))

                avg_reward /= len(train_queries_idx)
                avg_rewards.append(avg_reward)

                epoch_finish_time = time.time()

                epoch_data = {
                    'agent': agent.name,
                    'epoch_idx': epoch_idx,
                    'train_avg_reward': avg_reward,
                    'seconds_since_start': epoch_finish_time - start_time,
                }

                logging.info('Average rewards: %s', avg_rewards)

                if (epoch_idx + 1) % 10 == 0:
                    test_set_ndcg = np.mean(evaluate(agent))
                    test_set_ndcgs.append(test_set_ndcg)

                    logging.info('Test set NDCGs: %s', test_set_ndcgs)

                    epoch_data['test_set_ndcg'] = test_set_ndcg

                if f_trace_out:
                    f_trace_out.write(json.dumps(epoch_data))
                    f_trace_out.write('\n')

                    f_trace_out.flush()

        ndcgs = evaluate(agent)
        logging.info('NDCG: %.4f', np.mean(ndcgs))

        ndcg_per_agent[agent] = np.mean(ndcgs)

    logging.info('%s', ndcg_per_agent)

    if f_trace_out:
        f_trace_out.close()

if __name__ == '__main__':
    sys.exit(main())
