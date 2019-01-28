import uuid
import base64
import json

import redis

import utils
from model import CardBox, Card


DUEL_SUFFIX = '_duels'
CHALLENGE_SUFFIX = '_challenges'
ARCHIVE_SUFFIX = '_archive'
TABLE_VS = 'vs-info'

DRAW = 'd'

"""
Design of challenge-dict:
'challenger': user-id of challenging user
'challenged': user-id of challenged user
'box_id': box-id of CardBox used for challenge
'box_name': box name of CardBox used for challenge
'box_content': content of CardBox used for challenge at time of challenge issue
'started': Bool, True if challenge is accepted; running or finished
'winner': user-id of winner if finished, else emptystring
"""


def gen_duel_id():
    return base64.urlsafe_b64encode(uuid.uuid4().bytes).decode('utf-8')


def challenge(db, challenger_id, challenged_id, box_id):
    new_duel_id = gen_duel_id()

    box = CardBox.fetch(db, box_id)
    content = Card.fetch_content(db, box_id)

    vs_dict = dict(duel_id=new_duel_id,
                   challenger=challenger_id,
                   challenged=challenged_id,
                   box_id=box_id,
                   box_name=box.name,
                   box_content=content,
                   started=False,
                   finish_time=None,
                   winner='')

    db.hset(TABLE_VS, new_duel_id, json.dumps(vs_dict))
    db.rpush(challenger_id + CHALLENGE_SUFFIX, new_duel_id)
    db.rpush(challenged_id + CHALLENGE_SUFFIX, new_duel_id)

    return new_duel_id


def fetch_duel(db, duel_id: str):
    if not duel_id:
        return None

    json_string = db.hget(TABLE_VS, duel_id)

    if not json_string:
        return None

    return utils.unjsonify(json_string)


def fetch_multiple_duels(db, duel_ids: list):
    if not duel_ids:
        return []

    json_strings = db.hmget(TABLE_VS, *duel_ids)

    if not json_strings:
        return []

    return [utils.unjsonify(json_string)
            for json_string in json_strings]


def remove_challenge(db, duel_id):
    duel = fetch_duel(db, duel_id)

    if not duel:
        return

    db.lrem(duel['challenger'] + CHALLENGE_SUFFIX, 0, duel_id)
    db.lrem(duel['challenged'] + CHALLENGE_SUFFIX, 0, duel_id)

    return True


def fetch_challenges_of(db, user_id) -> list:
    all_ids = _list_items_of_key(db, user_id + CHALLENGE_SUFFIX)
    all_duels = fetch_multiple_duels(db, all_ids)
    return [duel for duel in all_duels
            if duel['challenger'] == user_id]


def fetch_challenges_to(db, user_id) -> list:
    all_ids = _list_items_of_key(db, user_id + CHALLENGE_SUFFIX)
    all_duels = fetch_multiple_duels(db, all_ids)
    return [duel for duel in all_duels
            if duel['challenged'] == user_id]


def start_duel(db, duel_id):
    duel = fetch_duel(db, duel_id)

    if duel['started']:
        return

    remove_challenge(db, duel_id)

    duel['started'] = True
    _store_duel(db, duel_id, duel)

    db.rpush(duel['challenger'] + DUEL_SUFFIX, duel_id)
    db.rpush(duel['challenged'] + DUEL_SUFFIX, duel_id)

    return True


def fetch_duels_of(db, user_id) -> list:
    all_ids = _list_items_of_key(db, user_id + DUEL_SUFFIX)
    return fetch_multiple_duels(db, all_ids)


def fetch_archived_duels(db, user_id) -> list:
    all_ids = _list_items_of_key(db, user_id + ARCHIVE_SUFFIX, reverse=True)
    return fetch_multiple_duels(db, all_ids)


def archive_duel(db, duel_id):
    duel = fetch_duel(db, duel_id)

    if not duel:
        return

    db.lrem(duel['challenger'] + DUEL_SUFFIX, 0, duel_id)
    db.lrem(duel['challenged'] + DUEL_SUFFIX, 0, duel_id)

    db.rpush(duel['challenger'] + ARCHIVE_SUFFIX, duel_id)
    db.rpush(duel['challenged'] + ARCHIVE_SUFFIX, duel_id)

    return True


def get_card_from_duel(duel: dict, index: int) -> dict:
    cards = duel['box_content']

    if not cards:
        return None

    # do the magick
    card = dict(question=cards['questions'][index],
                answers=cards['answers'][index],
                correct_answer=cards['correct_answers'][index],
                explanation=cards['explanations'][index])

    return card


def answers_of(db, user_id: str, duel_id: str) -> list:
    answers = db.lrange(duel_id + '_' + user_id, 0, -1)

    return [int(x.decode('utf-8'))
            for x in answers]


def put_answer(db, user_id: str, duel_id: str, answer: int):
    """ 'answer' should be in [0, 1, 2]."""
    db.rpush(duel_id + '_' + user_id, answer)


def finish_duel(db, duel_id: str) -> str:
    duel = fetch_duel(db, duel_id)

    if not duel:
        return

    challenger_id = duel['challenger']
    challenged_id = duel['challenged']

    answers_challenger = answers_of(db, challenger_id, duel_id)
    answers_challenged = answers_of(db, challenged_id, duel_id)

    list_truth = duel['box_content']['correct_answers']

    score_challenger = num_correct_answers(list_truth, answers_challenger)
    score_challenged = num_correct_answers(list_truth, answers_challenged)

    if score_challenger == score_challenged:
        winner = DRAW
    else:
        winner = (challenger_id if score_challenger > score_challenged
                  else challenged_id)

    duel['winner'] = winner
    duel['finish_time'] = utils.unix_time_in_seconds()

    _store_duel(db, duel_id, duel)

    archive_duel(db, duel_id)

    return winner


def get_opponent(duel: dict, user_id: str) -> str:
    d = duel
    return d['challenger'] if user_id == d['challenged'] else d['challenged']


def num_answers_of(db, user_id: str, duel_id: str) -> int:
    return db.llen(duel_id + '_' + user_id)


def duel_length(duel: dict) -> int:
    return len(duel['box_content']['questions'])


def num_correct_answers(list_truth: list, list_answers: list):
    if not len(list_truth) == len(list_answers):
        raise ValueError()

    return sum([x_t == x_a for x_t, x_a in zip(list_truth, list_answers)])


def check_answer_list(list_truth: list, list_answers: list):
    len_dif = len(list_truth) - len(list_answers)

    if len_dif < 0:
        raise ValueError()

    list_truth_check = list_truth[:len(list_answers)]

    bool_list = [xt == xa for xt, xa in zip(list_truth_check, list_answers)]

    tail = [False] * len_dif
    bool_list.extend(tail)

    return bool_list


def num_incoming_challenges(db, user_id: str) -> int:
    # TODO: redis counter, maybe?
    return len(fetch_challenges_to(db, user_id))


def num_outgoing_challenges(db, user_id: str) -> int:
    # TODO: redis counter, maybe?
    return len(fetch_challenges_of(db, user_id))


def num_duels(db, user_id: str) -> int:
    return db.llen(user_id + DUEL_SUFFIX)


def _store_duel(db, duel_id: str, duel: dict):
    if not duel:
        return

    db.hset(TABLE_VS, duel_id, json.dumps(duel))


def _list_items_of_key(db, key: str, reverse=False) -> list:
    result = [x.decode('utf-8')
              for x in db.lrange(key, 0, -1)]

    if reverse:
        result.reverse()

    return result
