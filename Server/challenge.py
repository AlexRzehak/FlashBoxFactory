import uuid
import base64
import json

import redis

import utils


DUEL_SUFFIX = '_duels'
CHALLENGE_SUFFIX = '_challenges'
TABLE_VS = 'vs-info'

"""
Design of challenge-dict:
'challenger': user-id of challenging user
'challenged': user-id of challenged user
'box': box-id of cCardBox used for challenge
'started': Bool, True if challenge is accepted; running or finished
'winner': user-id of winner if finished, else emptystring
"""


def gen_duel_id():
    return base64.urlsafe_b64encode(uuid.uuid4().bytes).decode('utf-8')


def challenge(db, challenger_id, challenged_id, box_id):
    new_duel_id = gen_duel_id()
    vs_dict = dict(challenger=challenger_id,
                   challenged=challenged_id,
                   box=box_id,
                   started=False,
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

    db.hdel(db, TABLE_VS, duel_id)

    return True


def fetch_challenges_of(db, user_id):
    all_ids = _list_items_of_key(db, user_id + CHALLENGE_SUFFIX)
    all_duels = fetch_multiple_duels(db, all_ids)
    return [duel for duel in all_duels
            if duel['challenger'] == user_id]


def fetch_challenges_to(db, user_id):
    all_ids = _list_items_of_key(db, user_id + CHALLENGE_SUFFIX)
    all_duels = fetch_multiple_duels(db, all_ids)
    return [duel for duel in all_duels
            if duel['challenged'] == user_id]


def start_duel(db, duel_id):
    duel = fetch_duel(db, duel_id)

    if duel['started']:
        return

    # order is important!
    remove_challenge(db, duel_id)

    duel['started'] = True
    _store_duel(db, duel_id, duel)

    db.rpush(duel['challenger'] + DUEL_SUFFIX, duel_id)
    db.rpush(duel['challenged'] + DUEL_SUFFIX, duel_id)

    return True


def _store_duel(db, duel_id, duel):
    if not duel:
        return

    db.hset(TABLE_VS, duel_id, json.dumps(duel))


def _list_items_of_key(db, key):
    return [x.decode('utf-8')
            for x in db.lrange(key, 0, -1)]
