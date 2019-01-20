import uuid
import base64

import utils


TABLE_RATINGS = 'ratings'
TABLE_CARDBOXES = 'cardboxs'

DEFAULT_INFO = 'No Description feature added yet. No content display feature added yet.'


class CardBox:

    def __init__(self, _id: str, name: str, owner: str,
                 rating: int, tags: list, content: list, info=DEFAULT_INFO):

        self._id = _id
        self.name = name
        self.owner = owner
        self.rating = rating
        self.tags = tags
        self.content = content
        self.info = info

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
    def delete(db, card_box_id: str):
        db.hdel(TABLE_CARDBOXES, card_box_id)
        return True

    @staticmethod
    def fetch(db, card_box_id: str):
        json_string = db.hget(TABLE_CARDBOXES, card_box_id)

        if not json_string:
            return None

        _dict = utils.unjsonify(json_string)
        return CardBox(**_dict)

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

    def __init__(self, _id: str, name: str, question: str,
                 answers: list, correct_answer: int, explanation: str):

        self._id = _id
        self.name = name
        self.question = question
        self.answers = answers
        self.correct_answer = correct_answer
        self.explanation = explanation
