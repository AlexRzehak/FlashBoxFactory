import json
import uuid
import base64


import utils


TABLE_RATINGS = 'ratings'
TABLE_CARDBOXES = 'cardboxs'
TABLE_CONTENT = 'cards'

DEFAULT_INFO = 'No Description feature added yet. No content display feature added yet.'


class CardBox:

    def __init__(self, _id: str, name: str, owner: str,
                 rating: int, tags: list, content: list, info=DEFAULT_INFO):

        self._id = _id
        self.name = name
        self.owner = owner
        self.rating = rating
        self.tags = tags
        self.info = info

        # TODO to be deleted
        self.content = content

    @staticmethod
    def gen_card_id() -> str:
        return base64.urlsafe_b64encode(uuid.uuid4().bytes).decode('utf-8')

    def store(self, db):
        db.hset(TABLE_CARDBOXES, self._id, utils.jsonify(self))

    def increment_rating(self, db, user):
        if self._id in user.rated:
            # already incremented
            return False

        try:
            db.hincrby(TABLE_RATINGS, self._id, amount=1)
        except:
            # TODO: check exception circumstance and re-raise accordingly
            return False

        user.rated.append(self._id)
        user.store(db)

        try:
            self.rating = int(db.hget(TABLE_RATINGS, self._id).decode('utf-8'))
        except:
            # TODO: check exception circumstance and re-raise accordingly
            return False

        self.store(db)

        # success
        return True

    @staticmethod
    def delete(db, cardbox_id: str):
        db.hdel(TABLE_CARDBOXES, cardbox_id)
        Card.remove_content(db, cardbox_id)
        return True

    @staticmethod
    def fetch(db, cardbox_id: str):
        if not cardbox_id:
            return None

        json_string = db.hget(TABLE_CARDBOXES, cardbox_id)

        if not json_string:
            return None

        return CardBox(**utils.unjsonify(json_string))

    @staticmethod
    def fetch_multiple(db, cardbox_ids: list):
        if not cardbox_ids:
            return []

        json_strings = db.hmget(TABLE_CARDBOXES, *cardbox_ids)

        if not json_strings:
            return []

        return [CardBox(**utils.unjsonify(json_string))
                for json_string in json_strings]

    # TODO Add implementation that does not crash with too much data

    @staticmethod
    def fetch_all(db):
        dict_json_boxes = db.hgetall(TABLE_CARDBOXES)

        if not dict_json_boxes:
            return []

        boxes = [CardBox(**utils.unjsonify(d))
                 for d in dict_json_boxes.values()]

        return boxes


class Card:
    # def __init__(self, _id: str, name: str, question: str,
    #              answers: list, correct_answer: int, explanation: str):

    #     self.question = question
    #     self.answers = answers
    #     self.correct_answer = correct_answer
    #     self.explanation = explanation
    @staticmethod
    def save_content(db, box_id: str, content_list: list):
        questions = []
        answers = []
        correct_answers = []
        explanations = []

        for card in content_list:
            questions.append(card['question'])
            answers.append(card['answers'])
            correct_answers.append(card['correct_answer'])
            explanations.append(card['explanation'])

        content = dict(questions=questions, answers=answers,
                       correct_answers=correct_answers,
                       explanations=explanations)

        db.hset(TABLE_CONTENT, box_id, json.dumps(content))

    @staticmethod
    def fetch_content_to_list(db, box_id: str):

        cards = Card.fetch_content(db, box_id)

        if not cards:
            return []

        # do the magick
        l = [dict(question=q, answers=a, correct_answer=ca, explanation=e)
             for q, a, ca, e in zip(cards['questions'], cards['answers'],
                                    cards['correct_answers'],
                                    cards['explanations'])]
        return l

    @staticmethod
    def get_card_by_index(db, box_id: str, index: int):

        cards = Card.fetch_content(db, box_id)

        if not cards:
            return None

        # do the magick
        card = dict(question=cards['questions'][index],
                    answers=cards['answers'][index],
                    correct_answer=cards['correct_answers'][index],
                    explanation=cards['explanations'][index])

        return card

    @staticmethod
    def fetch_content(db, box_id: str):
        cards = db.hget(TABLE_CONTENT, box_id)

        if not cards:
            return None

        return json.loads(cards.decode('utf-8'))

    @staticmethod
    def remove_content(db, box_id: str):
        db.hdel(TABLE_CONTENT, box_id)
        return True

    @staticmethod
    def get_content_size(db, box_id: str):
        cards = Card.fetch_content(db, box_id)

        if not cards:
            return 0

        return len(cards['questions'])
