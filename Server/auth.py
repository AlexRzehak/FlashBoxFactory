from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, Length
from werkzeug.security import generate_password_hash, check_password_hash

import utils


TABLE_USER = 'users'


class User:

    def __init__(self, _id: str, password_hash=None, cardboxs=[], rated=[],
                 offline_score=0, score=0, following=[],
                 is_active=None, is_authenticated=None, is_anonymous=None):

        self._id = _id
        self.password_hash = password_hash
        self.cardboxs = cardboxs
        self.rated = rated
        self.offline_score = offline_score
        self.score = score
        self.following = following

        self.is_active = True
        self.is_authenticated = True
        self.is_anonymous = False

    def get_id(self) -> str:
        return self._id

    def set_password(self, password_plain: str):
        self.password_hash = generate_password_hash(password_plain)

    def check_password(self, password_plain: str) -> bool:
        return check_password_hash(self.password_hash, password_plain)

    def store(self, db):
        db.hset(TABLE_USER, self._id, utils.jsonify(self))

    def update_score(self) -> int:
        # TODO implement function
        pass

    def toggle_follow(self, _id):
        if (_id in self.following):
            self.following.remove(_id)
        else:
            self.following.append(_id)

    def is_following(self, _id):
            return (_id in self.following)

    @staticmethod
    def fetch(db, user_id: str):
        json_string = db.hget(TABLE_USER, user_id)

        if not json_string:
            return None

        _dict = utils.unjsonify(json_string)
        return User(**_dict)

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
    submit = SubmitField('Change')
