# -*- coding: utf-8 -*-
'''
Готовим датасет для обучения модели, определяющей релевантность
вопроса и предпосылки для проекта чатбота (https://github.com/Koziev/chatbot)

Используется несколько входных датасетов.
paraphrases.txt - отсюда получаем релевантные и нерелевантные перефразировки
qa.txt и premise_question_answer5.txt - отсюда получаем релевантные вопросы и предпосылки
questions.txt - список вопросов для негативного сэмплинга
и т.д.

Создаваемый датасет в формате CSV представляет из себя четыре колонки.
Первые две - текст сравниваемых фраз.
Третья содержит целое число:
0 - не релевантны
1 - есть полная семантическая релевантность
2 - есть релевантность вопроса и предпосылки
Четвертая - вес сэмпла, 1 для автоматически сгенерированных, >1 для сэмплов
из вручную сформированных файлов.

(c) by Koziev Ilya inkoziev@gmail.com
'''

from __future__ import division  # for python2 compatability
from __future__ import print_function

import codecs
import collections
import itertools
import os
import random

from utils.tokenizer import Tokenizer

HANDCRAFTED_WEIGHT = 10 # вес для сэмплов, которые в явном виде созданы вручную
AUTOGEN_WEIGHT = 1 # вес для синтетических сэмплов, сгенерированных автоматически

tmp_folder = '../tmp'
data_folder = '../data'
paraphrases_path = '../data/paraphrases.txt'
qa_paths = [('qa.txt', HANDCRAFTED_WEIGHT),
            ('current_time_pqa.txt', AUTOGEN_WEIGHT),
            ('premise_question_answer6.txt', AUTOGEN_WEIGHT),
            ('premise_question_answer5.txt', AUTOGEN_WEIGHT),
            ('premise_question_answer4.txt', AUTOGEN_WEIGHT),
            ('premise_question_answer4_1s.txt', AUTOGEN_WEIGHT),
            ('premise_question_answer4_2s.txt', AUTOGEN_WEIGHT),
            ('premise_question_answer5_1s.txt', AUTOGEN_WEIGHT),
            ('premise_question_answer5_2s.txt', AUTOGEN_WEIGHT),
            ]
questions_path = '../data/questions.txt'

include_repeats = True
n_negative_per_positive = 5

# Добавлять ли сэмплы, в которых задается релевантность предпосылки и вопроса,
# например:
# premise=Кошка ловит мышей
# question=Кто ловит мышей?
INCLUDE_PREMISE_QUESTION = True

stop_words = { u'и', u'или', u'ли', u'что' }

# ---------------------------------------------------------------

def normalize_qline( line ):
    line = line.replace(u'(+)', u'')
    line = line.replace(u'(-)', u'')
    line = line.replace(u'T:', u'')
    line = line.replace(u'Q:', u'')
    line = line.replace(u'A:', u'')
    line = line.replace(u'\t', u' ')
    line = line.replace( '.', ' ' ).replace( ',', ' ' ).replace( '?', ' ' ).replace( '!', ' ' ).replace( '-', ' ' )
    line = line.replace( '  ', ' ' ).strip().lower()
    return line


# ---------------------------------------------------------------

tokenizer = Tokenizer()

# ------------------------------------------------------------------------

random_questions = []
random_facts = set()

# прочитаем список случайных вопросов из заранее сформированного файла
print('Loading random questions from {}'.format(questions_path))
with codecs.open(questions_path, 'r', 'utf-8') as rdr:
    for line in rdr:
        if len(line)<40:
            question = line.strip()
            question = question.replace(u'- ', u'')
            random_questions.append(question)

# ------------------------------------------------------------------------

# Прочитаем список случаных фактов, чтобы потом генерировать отрицательные паттерны
print('Loading random questions and facts...')
for facts_path in ['facts4.txt', 'facts5.txt', 'facts6.txt']:
    with codecs.open(os.path.join(data_folder, facts_path), 'r', 'utf-8') as rdr:
        n=0
        for line in rdr:
            if n>100000:
                s = line.strip()
                if s[-1]==u'?':
                    random_questions.append(s)
                else:
                    random_facts.add(s)
            n += 1
            if n>2000000:
                break

random_facts = list(random_facts)

print('Prepare random facts index...')
word2random_facts = dict()
for ifact,fact in enumerate(random_facts):
    words = tokenizer.tokenize(fact)

    for word in words:
        if word not in stop_words:
            if word not in word2random_facts:
                word2random_facts[word] = [ifact]
            else:
                word2random_facts[word].append(ifact)


print('{} random facts in set'.format(len(random_facts)))
print('{} random questions in set'.format(len(random_questions)))
# ------------------------------------------------------------------------

class ResultantDataset(object):
    def __init__(self):
        self.str_pairs = [] # предпосылки и вопросы
        self.relevancy = [] # релевантность вопросов и предпосылок в парах
        self.weights   = [] # вес сэмпла, 1 для автоматически созданных сэмплов
        self.added_pairs_set = set() # для предотвращения повторов

    def add_pair( self, x1, x2, rel, weight ):
        s1 = x1.replace(u'\t', u'').strip()
        s2 = x2.replace(u'\t', u'').strip()
        s12 = s1+'|'+s2
        if s12 not in self.added_pairs_set:
            self.added_pairs_set.add(s12)
            self.str_pairs.append((s1, s2))
            self.relevancy.append(rel)
            self.weights.append(weight)

    def positive_count(self):
        return sum(self.relevancy)

    def save_csv(self, filepath):
        # сохраним получившийся датасет в CSV
        with codecs.open(filepath, 'w', 'utf-8') as wrt:
            wrt.write(u'premise\tquestion\trelevance\tweight\n')
            for (s1, s2), r, w in itertools.izip(self.str_pairs, self.relevancy, self.weights):
                wrt.write(u'{}\t{}\t{}\t{}\n'.format(s1, s2, r, w))

    def print_stat(self):
        print('Total number of samples={}'.format(len(self.str_pairs)))

        for y in range(3):
            print('rel={} number of samples={}'.format(y, len(filter(lambda z: z == y, self.relevancy))))

        weight2count = collections.Counter()
        for w in self.weights:
            weight2count[w] += 1

        print('number of handcrafted samples={}'.format(weight2count[HANDCRAFTED_WEIGHT]))

        print('premise  max len={}'.format(max(map(lambda z: len(z[0]), self.str_pairs))))
        print('question max len={}'.format(max(map(lambda z: len(z[1]), self.str_pairs))))


# ------------------------------------------------------------------------

res_dataset = ResultantDataset()


print('Parsing {}'.format(paraphrases_path))
lines = []
posit_pairs_count = 0
negat_pairs_count = 0
with codecs.open(paraphrases_path, "r", "utf-8") as inf:
    for line in inf:
        line = line.strip()
        if len(line) == 0:
            if len(lines) > 1:
                posit_lines = []
                negat_lines = []
                for line in lines:
                    if line.startswith(u'(+)') or not line.startswith(u'(-)'):
                        posit_lines.append(normalize_qline(line))
                    else:
                        negat_lines.append(normalize_qline(line))

                for i1 in range(len(posit_lines)):
                    for i2 in range(len(posit_lines)):
                        if i1 == i2 and not include_repeats:
                            continue
                        res_dataset.add_pair( posit_lines[i1], posit_lines[i2], 1, HANDCRAFTED_WEIGHT )
                        posit_pairs_count += 1

                    for negat in negat_lines:
                        res_dataset.add_pair( posit_lines[i1], negat, 0, HANDCRAFTED_WEIGHT )
                        negat_pairs_count += 1

                    # добавим пары со случайными фактами в качестве негативных сэмплов
                    for _ in range(n_negative_per_positive):
                        res_dataset.add_pair( posit_lines[i1], random.choice(random_facts), 0, AUTOGEN_WEIGHT )
                        negat_pairs_count += 1

                    # добавим пары со случайными фактами, отобранными по критерию наличия общих слов.
                    words = tokenizer.tokenize(posit_lines[i1])
                    selected_random_facts = None
                    for word in words:
                        if word not in stop_words:
                            if word in word2random_facts:
                                if selected_random_facts is None:
                                    selected_random_facts = set(word2random_facts[word])
                                else:
                                    selected_random_facts |= set(word2random_facts[word])

                    if selected_random_facts is not None and len(selected_random_facts)>0:
                        words = set(words)
                        for _ in range(n_negative_per_positive):
                            ifact = random.choice(list(selected_random_facts))
                            neg_fact = random_facts[ifact]
                            neg_words = set(tokenizer.tokenize(neg_fact))
                            found_in_posit = False
                            for p in posit_lines:
                                posit_words = set(tokenizer.tokenize(p))
                                if posit_words == neg_words:
                                    found_in_posit = True
                                    break

                            if not found_in_posit:
                                res_dataset.add_pair(posit_lines[i1], neg_fact, 0, AUTOGEN_WEIGHT)
                                negat_pairs_count += 1

            lines = []
        else:
            lines.append(line)


print('done, posit_pairs_count={} negat_pairs_count={}'.format(posit_pairs_count, negat_pairs_count))
# ------------------------------------------------------------------------

if INCLUDE_PREMISE_QUESTION:

    for qa_path, qa_weight in qa_paths:
        print('Parsing {}'.format(qa_path))
        premise_questions = []
        posit_pairs_count = 0
        negat_pairs_count = 0
        with codecs.open( os.path.join(data_folder, qa_path), "r", "utf-8") as inf:
            loading_state = 'T'

            text = []
            questions = []

            for line in inf:
                line = line.strip()

                if line.startswith(u'T:'):
                    if loading_state=='T':
                        text.append(normalize_qline(line))
                    else:
                        # закончился парсинг предыдущего блока из текста (предпосылки),
                        # вопросов и ответов.
                        # Из загруженных записей добавим пары в обучающий датасет
                        if len(text)==1:

                            premise_questions.append( (text[0], questions) )

                            for premise in text:
                                for question in questions:
                                    res_dataset.add_pair( premise, question, 1, qa_weight )
                                    posit_pairs_count += 1

                                # Добавим несколько нерелевантных вопросов
                                for _ in range(len(questions)*n_negative_per_positive):
                                    random_question = random.choice(random_questions)
                                    res_dataset.add_pair( premise, random_question, 0, AUTOGEN_WEIGHT)
                                    negat_pairs_count += 1

                        loading_state = 'T'
                        questions = []
                        text = [normalize_qline(line)]

                elif line.startswith(u'Q:'):
                    loading_state = 'Q'
                    questions.append(normalize_qline(line))

        # Добавляем случайные вопросы из qa датасета в качестве негативных сэмплов.
        for i, (premise, questions) in enumerate(premise_questions):
            rnd_pool = [j for j in range(len(premise_questions)) if j!=i]

            n_added_random = 0
            while n_added_random<n_negative_per_positive:
                rnd_index = random.choice(rnd_pool)
                for random_question in premise_questions[rnd_index][1]:
                    if random_question not in questions:
                        res_dataset.add_pair(premise, random_question, 0, AUTOGEN_WEIGHT)
                        negat_pairs_count += 1
                        n_added_random += 1

        print('done, posit_pairs_count={} negat_pairs_count={}'.format(posit_pairs_count, negat_pairs_count))
# ---------------------------------------------------------------------------------------

# Добавим негативные пары из случайных источников.

N_NEGATIVE = res_dataset.positive_count()*n_negative_per_positive
# кол-во добавляемых рандомных негативных будет равно числу
# имеющихся позитивных с заданным коэффициентом.

srclines = []
group_counter = 0
with codecs.open( paraphrases_path, "r", "utf-8") as inf:
    for line in inf:
        line = line.strip()
        if len(line)==0:
            group_counter += 1
        else:
            if not line.startswith(u'(-)'):
                srclines.append((normalize_qline(line),group_counter))

negative_pairs = 0
while negative_pairs < N_NEGATIVE:
    line1 = random.choice(srclines)
    line2 = random.choice(srclines)
    # выбираем строки из разных групп
    if( line1[1]!=line2[1] ):
        res_dataset.add_pair( line1[0], line2[0], 0, AUTOGEN_WEIGHT)
        negative_pairs += 1

print( 'random negatives count=', negative_pairs )

# ---------------------------------------------------------------------------


# Добавляем перестановочные перефразировки.
# Подготовка датасетов с перестановочными перефразировками выполняется
# C# кодом, находящимся здесь: https://github.com/Koziev/NLP_Datasets/tree/master/ParaphraseDetection

srcpaths = ['SENT4.duplicates.txt', 'SENT5.duplicates.txt', 'SENT6.duplicates.txt']

nb_permut = res_dataset.positive_count()/len(srcpaths) # кол-во перестановочных перефразировок одной длины,
                                         # чтобы в итоге кол-во перестановочных пар не превысило число
                                         # явно заданных положительных пар.
print('nb_permut={}'.format(nb_permut))
total_permutations = 0
include_repeats = False # включать ли нулевые перефразировки - когда левая и правая части идентичны
emitted_perm = set()

for srcpath in srcpaths:
    print( 'source=', srcpath )
    lines = []
    with codecs.open( os.path.join(data_folder, srcpath), "r", "utf-8") as inf:
        nperm=0
        for line in inf:
            line = line.strip()
            if len(line)==0:
                if len(lines)>1:

                    for i1 in range( len(lines) ):
                        for i2 in range( len(lines) ):
                            if i1==i2 and include_repeats==False:
                                continue
                            k1 = lines[i1].strip() + u'|' + lines[i2].strip()
                            k2 = lines[i2].strip() + u'|' + lines[i1].strip()
                            if k1 not in emitted_perm and k2 not in emitted_perm:
                                emitted_perm.add(k1)
                                emitted_perm.add(k2)

                                res_dataset.add_pair(lines[i1], lines[i2], 1, AUTOGEN_WEIGHT)
                                total_permutations += 1
                                nperm += 1
                                if nperm>nb_permut:
                                    break

                lines = []
            else:
                lines.append( normalize_qline(line) )

print( 'total_permutations={}'.format(total_permutations) )

# ---------------------------------------------------------------------------

res_dataset.print_stat()

# сохраним получившийся датасет в CSV
res_dataset.save_csv( os.path.join(data_folder,'premise_question_relevancy.csv') )