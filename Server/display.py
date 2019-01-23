from flask import url_for, request
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from flask_table import Table, Col, LinkCol
from wtforms import RadioField, SubmitField, StringField, BooleanField, SelectField, TextAreaField, IntegerField

import utils


class CardBoxTable(Table):

    classes = ['table', 'table-hover', 'table-bordered']

    name = LinkCol('Name', endpoint='show_box',
                   url_kwargs=dict(_id='_id'), attr_list='name')
    tags = Col('Tags', allow_sort=False)
    owner = LinkCol('Owner', endpoint='show_user',
                    url_kwargs=dict(_id='owner'), attr_list='owner')
    rating = Col('Rating')

    allow_sort = True

    def sort_url(self, col_key, reverse=False):
        direction = 'desc' if reverse else 'asc'

        kwargs = {key: value for key, value in request.args.items()}
        kwargs.update(direction=direction, sort=col_key)

        return url_for('huge_list', **kwargs)


class UserTable(Table):

    classes = ['table', 'table-hover', 'table-bordered']
    no_items = ("There are no users matching your criteria! "
                "Please check your search terms.")

    username = LinkCol('Username', endpoint='show_user',
                       url_kwargs=dict(_id='_id'), attr_list='_id')
    score = Col('Score')
    following = LinkCol('Following', endpoint='toggle_follow',
                        url_kwargs=dict(_id='_id'), attr_list='follows_label',
                        allow_sort=False)
    challenge = LinkCol('Challenge', endpoint='challenge',
                        text_fallback='Challenge!', url_kwargs=dict(_id='_id'),
                        allow_sort=False)

    allow_sort = True

    def sort_url(self, col_key, reverse=False):
        direction = 'desc' if reverse else 'asc'

        kwargs = {key: value for key, value in request.args.items()}
        kwargs.update(direction=direction, sort=col_key)

        return url_for('user_list', **kwargs)


# TODO implement score table correctly
class ScoreTable(Table):

    classes = ['table', 'table-hover', 'table-bordered']

    score = Col('Score')
    username = LinkCol('Username', endpoint='show_user',
                       url_kwargs=dict(_id='_id'), attr_list='_id')


class FilterForm(FlaskForm):

    option = RadioField(
        '', choices=[('tags', 'Tags'), ('name', 'Cardbox Name'),
                     ('owner', 'Username')],
        default='tags')
    term = StringField('Filter Term')
    submit = SubmitField('Filter!')


class CommunityForm(FlaskForm):

    term = StringField('Look for a user!')
    submit = SubmitField('Go!')


class ShowcaseForm(FlaskForm):

    check_info = BooleanField('Display your Info?')
    info_input = TextAreaField('What you want to tell this world:')
    check_cardbox = BooleanField('Display your favourite CardBox?')
    cardbox_input = SelectField('Your best CardBox:')
    check_rank = BooleanField('Display your current Rank?')
    rank_token = IntegerField('You are currently rank',
                              render_kw={'readonly': True})
    submit_showcase = SubmitField('Change')


class PictureForm(FlaskForm):

    picture = FileField('Profile picture',
                        validators=[FileRequired(),
                                    FileAllowed(['jpg', 'png'],
                                                'JPG, PNG images only!'),
                                    utils.FixedImageSize([(256, 256)],
                                                         '256x256px only!')])
    submit = SubmitField('Change')


class ConfirmationForm(FlaskForm):

    submit = SubmitField('Yes')
