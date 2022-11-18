import random

from ruchatbot.utils.constant_replacer import replace_constant


class ActorBase(object):
    def __init__(self, actor_keyword):
        self.actor_keyword = actor_keyword

    @staticmethod
    def load_from_yaml(yaml_node, constants, text_utils):
        actor_keyword = list(yaml_node.keys())[0] if isinstance(yaml_node, dict) else yaml_node
        if actor_keyword in ('say', 'rewrite'):
            return ActorSay.load_from_yaml(yaml_node, constants, text_utils)
        else:
            raise NotImplementedError(actor_keyword)

    def do_action(self, matching, session, text_utils):
        raise NotImplementedError()


class ActorResult(object):
    def __init__(self, actor):
        self.actor = actor

    def get_response_text(self):
        """Вернет текст сгенерированной реплики для <say>"""
        return None


class ActorSay(ActorBase):
    """Оператор генерации ответной реплики"""
    def __init__(self, actor_keyword):
        super(ActorSay, self).__init__(actor_keyword)
        self.phrases = []  # шаблоны генерации реплик, в самом простом случае - просто варианты текста выдываемой реплики
        self.exhausted_phrases = []
        self.known_answer_policy = 'utter'
        self.np_sources = dict()
        self.on_repeat = []
        self.on_repeat_again = []

    @staticmethod
    def load_from_yaml(yaml_root, constants, text_utils):
        actor = ActorSay(list(yaml_root.keys())[0])

        # Надо понять, тут расширенная форма описания актора или просто список реплик, возможно
        # из одного элемента.
        yaml_node = yaml_root[actor.actor_keyword]
        if isinstance(yaml_node, dict):
            # Расширенный формат.
            for inner_keyword in yaml_node.keys():
                if 'phrases' == inner_keyword:
                    for utterance in yaml_node['phrases']:
                        s = replace_constant(utterance, constants, text_utils)
                        actor.phrases.append(s)
                elif 'exhausted' == inner_keyword:
                    for utterance in yaml_node['exhausted']:
                        s = replace_constant(utterance, constants, text_utils)
                        actor.exhausted_phrases.append(s)
                elif 'on_repeat' == inner_keyword:
                    for utterance in yaml_node['on_repeat']:
                        s = replace_constant(utterance, constants, text_utils)
                        actor.on_repeat.append(s)
                elif 'on_repeat_again' == inner_keyword:
                    for utterance in yaml_node['on_repeat_again']:
                        s = replace_constant(utterance, constants, text_utils)
                        actor.on_repeat_again.append(s)
                elif 'known_answer' == inner_keyword:
                    actor.known_answer_policy = yaml_node[inner_keyword]
                    # TODO - проверить значение флага: 'skip' | 'utter'
                else:
                    raise NotImplementedError()

        elif isinstance(yaml_node, list):
            for utterance in yaml_node:
                if isinstance(utterance, str):
                    s = replace_constant(utterance, constants, text_utils)
                    actor.phrases.append(s)
                else:
                    raise SyntaxError()
        elif isinstance(yaml_node, str):
            s = replace_constant(yaml_node, constants, text_utils)
            actor.phrases.append(s)
        else:
            raise NotImplementedError()

        return actor

    def __str__(self):
        return 'say "{}"'.format(' | '.join(self.phrases))

    def prepare4saying(self, phrase, matching, text_utils):
        # TODO подстановка слотов из результатов сопоставления
        # ...
        return phrase

    def do_action(self, matching, session, text_utils):
        session.actor_say_hit(id(self))
        if session.get_actor_say_hits(id(self)) > 1:
            # Выдадим реплику из отдельного списка, так как в текущей сессии это повторный вопрос
            new_utterances = []
            if self.on_repeat_again and session.get_actor_say_hits(id(self)) > 2:
                for utterance0 in self.on_repeat_again:
                    utterance = self.prepare4saying(utterance0, matching, text_utils)
                    new_utterances.append(utterance)

            if len(new_utterances) == 0 and self.on_repeat:
                new_utterances = []
                for utterance0 in self.on_repeat:
                    utterance = self.prepare4saying(utterance0, matching, text_utils)
                    new_utterances.append(utterance)

            if new_utterances:
                result_text = random.choice(new_utterances)
                return [ActorSayResult(self, result_text)]

        # Сначала попробуем убрать из списка те реплики, которые мы уже произносили.
        new_utterances = []
        for utterance0 in self.phrases:
            utterance = self.prepare4saying(utterance0, matching, text_utils)

            if '$' in utterance:
                # Не удалось подставить значение в один из $-слотов, значит
                # надо исключить фразу.
                continue

            if session.count_bot_phrase(utterance) == 0:
                #if self.known_answer_policy == 'skip' and utterance[-1] == '?':
                #    # Проверим, что бот еще не знает ответ на этот вопрос:
                #    if bot.does_bot_know_answer(utterance, session, interlocutor):
                #        continue
                new_utterances.append(utterance)

        if len(new_utterances) > 0:
            # Выбираем одну из оставшихся фраз.
            if len(new_utterances) == 1:
                result_text = new_utterances[0]
            else:
                result_text = random.choice(new_utterances)

            return [ActorSayResult(self, result_text)]

        else:
            # Все фразы бот уже произнес
            # Если задан список фраз на случай исчерпания (типа "не знаю больше ничего про кошек"),
            # то выдадим одну из них.

            new_utterances = []
            for utterance0 in self.exhausted_phrases:
                utterance = self.prepare4saying(utterance0, matching, text_utils)

                if '$' in utterance:
                    # Не удалось подставить значение в один из $-слотов, значит
                    # надо исключить фразу.
                    continue

                if session.count_bot_phrase(utterance) == 0:
                    #if self.known_answer_policy == 'skip' and utterance[-1] == '?':
                    #    # Проверим, что бот еще не знает ответ на этот вопрос:
                    #    if bot.does_bot_know_answer(utterance, session, interlocutor):
                    #        continue
                    new_utterances.append(utterance)

            if new_utterances:
                result_text = random.choice(new_utterances)
                return [ActorSayResult(self, result_text)]
            else:
                if self.known_answer_policy == 'skip':
                    raise NotImplementedError()
                else:
                    # Начиная с этого момента данное правило будет повторно выдавать
                    # одну из фраз.
                    #for src_phrase in sorted(self.phrases, key=lambda z: random.random()):
                    #    random_phrase = self.prepare4saying(src_phrase, condition_matching_results, text_utils)
                    #    if '$' not in random_phrase:
                    #        bot.say(session, random_phrase)
                    #        uttered = True
                    #        break
                    return None

        return None


class ActorSayResult(ActorResult):
    def __init__(self, actor, result_phrase_text):
        super(ActorSayResult, self).__init__(actor)
        self.result_phrase_text = result_phrase_text

    def __repr__(self):
        return "say 《" + self.result_phrase_text + "》"

    def get_response_text(self):
        return self.result_phrase_text
