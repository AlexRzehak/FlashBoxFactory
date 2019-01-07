from flask import url_for, request
from flask_wtf import FlaskForm
from wtforms import RadioField, SubmitField, StringField
from flask_table import Table, Col, LinkCol


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

    username = LinkCol('Username', endpoint='show_user',
                       url_kwargs=dict(_id='_id'), attr_list='_id')
    score = Col('Score')
    # following = LinkCol('Username', endpoint='show_user',
    # url_kwargs=dict(_id='_id'), attr_list='_id', allow_sort=False)
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
