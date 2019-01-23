from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, Length
from werkzeug.security import generate_password_hash, check_password_hash

import utils
from model import CardBox


TABLE_USER = 'users'
TABLE_SCORE = 'score'


class User:

    def __init__(self, _id: str, password_hash=None, cardboxs=[], rated=[],
                 offline_score=0, score=0, following=[], showcase_info=None,
                 is_active=None, is_authenticated=None, is_anonymous=None):

        self._id = _id
        self.password_hash = password_hash
        self.cardboxs = cardboxs
        self.rated = rated
        self.offline_score = offline_score
        self.following = following
        self.showcase_info = showcase_info or dict(info='', cardbox='',
                                                   show_info=False,
                                                   show_cardbox=False,
                                                   show_rank=False)
        # self.showcase = showcase or Showcase({}, '', '')

        # TODO: clean DB if removed
        self.score = score

        self.is_active = True
        self.is_authenticated = True
        self.is_anonymous = False

    def get_score(self, db):
        return db.zscore(TABLE_SCORE, self._id)

    def get_rank(self, db):
        return db.zrevrank(TABLE_SCORE, self._id) + 1

    def get_id(self) -> str:
        return self._id

    def set_password(self, password_plain: str):
        self.password_hash = generate_password_hash(password_plain)

    def check_password(self, password_plain: str) -> bool:
        return check_password_hash(self.password_hash, password_plain)

    def store(self, db):
        db.hset(TABLE_USER, self._id, utils.jsonify(self))

    def toggle_follow(self, _id):
        if (_id in self.following):
            self.following.remove(_id)
        else:
            self.following.append(_id)

    def is_following(self, _id):
        return (_id in self.following)

    # TODO: look at me, I'm new!
    @staticmethod
    def top_users(db, _from=0, to=-1, reverse=True):
        top_ids = [(uid.decode('utf-8'), score)
                   for uid, score in db.zrange('score', _from, to,
                                               desc=reverse,
                                               withscores=True)]

        return top_ids

    @staticmethod
    def update_score(db, _id) -> int:
        user = User.fetch(db, _id)

        score_likes = 0

        boxes = CardBox.fetch_multiple(db, user.cardboxs)
        for box in boxes:
            score_likes = score_likes + box.rating

        score_followers = 0

        users = User.fetch_all(db)
        for u in users:
            if u.is_following(user._id):
                score_followers += 1

        score_boxes = len(user.cardboxs)

        score = (user.offline_score + score_likes * 100 +
                 score_followers * 200 + score_boxes * 100)

        db.zadd(TABLE_SCORE, {_id: score})

        # TODO delete while reforming database
        # user.score = score
        # user.store(db)

        return score

    @staticmethod
    def fetch(db, user_id: str):
        if not user_id:
            return None

        json_string = db.hget(TABLE_USER, user_id)

        if not json_string:
            return None

        return User(**utils.unjsonify(json_string))

    @staticmethod
    def fetch_multiple(db, user_ids: list):
        if not user_ids:
            return []

        json_strings = db.hmget(TABLE_USER, *user_ids)

        if not json_strings:
            return []

        return [User(**utils.unjsonify(json_string))
                for json_string in json_strings]

    # TODO Add implementation that does not crash with too much data
    @staticmethod
    def fetch_all(db):
        dict_json_users = db.hgetall(TABLE_USER)

        if not dict_json_users:
            return []

        users = [User(**utils.unjsonify(d))
                 for d in dict_json_users.values()]

        return users

    @staticmethod
    def exists(db, user_id: str) -> bool:
        return db.hexists(TABLE_USER, user_id)


class Showcase:
    def __init__(self, show: dict, info: str, cardbox: str):

        self.show = show
        self.info = info
        self.cardbox = cardbox


class RegistrationForm(FlaskForm):

    def __init__(self, db, **kwargs):
        super().__init__(**kwargs)
        self.db = db

    username = StringField('Username',
                           validators=[DataRequired(),
                                       Length(min=3, max=16)])
    password = PasswordField('Password',
                             validators=[DataRequired(),
                                         Length(min=6, max=32)])
    password2 = PasswordField('Repeat Password',
                              validators=[DataRequired(),
                                          EqualTo('password')])
    submit = SubmitField('Register')

    # auto-invoked by WTForms
    def validate_username(self, username):

        user = User.exists(self.db, username.data)

        if user:
            raise ValidationError('Username is already taken.')


class LoginForm(FlaskForm):

    def __init__(self, db, **kwargs):
        super().__init__(**kwargs)
        self.db = db

    username = StringField('Username',
                           validators=[DataRequired(),
                                       Length(min=3, max=16)])
    password = PasswordField('Password',
                             validators=[DataRequired(),
                                         Length(min=6, max=32)])
    submit = SubmitField('Go!')

    # auto-invoked by WTForms
    def validate_username(self, username):

        user = User.exists(self.db, username.data)

        if not user:
            raise ValidationError('User does NOT exist. Mostly.')


class ChangePasswordForm(FlaskForm):

    old_password = PasswordField('Old Password',
                                 validators=[DataRequired(),
                                             Length(min=6, max=32)])
    new_password = PasswordField('New Password',
                                 validators=[DataRequired(),
                                             Length(min=6, max=32)])
    new_password2 = PasswordField('Confirm new Password',
                                  validators=[DataRequired(),
                                              EqualTo('new_password')])
    submit_password = SubmitField('Change')
