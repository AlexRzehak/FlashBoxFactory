import json
import random
import string
import requests

import redis

from server import SCORE_SYNC_SECRET

# A test client to check out multiple functionalities
# of the server and get data to the server

TAGS = ['maths', 'physics', 'chemistry', 'music', 'history', 'silent_movies',
        'food', 'gaming', 'star_wars', 'death_star', 'traitor', 'hello_there',
        'donald_trump', 'buddha', 'the_purge', 'veganism', 'john_cena',
        'elon_musk', 'cybervalley', 'exodia', 'cheese', 'more_cheese', '1984',
        'Mr.Robot', 'owo', ':D', 'insert_tag_here', 'Hääyöaieuutinen']

# USER = 'Obi_wan_Kenobi'
# PASSWORD = 'highground'
USER = 'DER MARKUS'
PASSWORD = 'wurstbrot'
# USER = 'deppo'
# PASSWORD = 'doofkopp'
# USER = 'Ainz'
# PASSWORD = 'skurleton'

SAMPLE_CONTENT = [{"correct_answer": 1, "answers": ["b", "a", "why not?"],
                   "explanation": "Deal with it!", "question": "Why?"},
                  {"correct_answer": 2, "answers": ["a lie", "a", "tasty!"],
                   "explanation": "WHY YOU TAKE MY CAKE?!", "question":
                   "Cake is..."}]


def create_many_boxes(username, password, number=100):
    for _ in range(number):
        upper = random.randint(4, 12)

        name = ''.join(random.choice(string.ascii_lowercase)
                       for _ in range(upper))
        tags = random.sample(TAGS, 2)
        info = 'A box that makes sense!'
        create_sample_box(username, password, name, tags, 'PLACEHOLDER', info)


def create_sample_box(username, password, name, tags, content, info):
    payload = dict(username=username,
                   password=password,
                   name=name,
                   tags=tags,
                   info=info,
                   content=SAMPLE_CONTENT)
    r = requests.post('http://localhost:5000/add_cardbox', json=payload)


def sample_user_score(username, password, score, secret):
    payload = dict(username=username,
                   password=password,
                   score=score,
                   secret=secret)
    r = requests.post('http://localhost:5000/sync_user_score', json=payload)


def test_download():
    r = requests.get(
        'http://localhost:5000/cardboxes/iqPLZZxkQKeAYEIWBVyDgA==/download')
    print(r.content)


def print_boxes():
    db = redis.StrictRedis(host='localhost', port=6379, db=0)
    print(db.hgetall('cardboxs'))


def print_users():
    db = redis.StrictRedis(host='localhost', port=6379, db=0)
    print(db.hgetall('users'))


def main():
    # print_boxes()
    create_many_boxes(USER, PASSWORD, 1)
    # sample_user_score(USER, PASSWORD, 400, SCORE_SYNC_SECRET)
    # test_download()


if __name__ == "__main__":
    main()
