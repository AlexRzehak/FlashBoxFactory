import os

import redis
from flask import (Flask, request, redirect, url_for, flash, render_template,
                   send_from_directory, abort, jsonify, session)
from flask_login import (LoginManager, current_user, login_user,
                         login_required, logout_user)
from flask_table import Table, Col, ButtonCol, LinkCol
from flask_bootstrap import Bootstrap
from werkzeug.urls import url_parse

import utils
import challenge
from model import CardBox, Card
from user import User, RegistrationForm, LoginForm, ChangePasswordForm
from display import (CardBoxTable, UserTable, ScoreTable, ChooseBoxTable,
                     FilterForm, CommunityForm, ShowcaseForm, PictureForm,
                     ConfirmationForm, ChallengeFilterForm,
                     ChallgengeIncomingTable, ChallgengeSentTable, DuelTable,
                     DuelArchiveTable)


SCORE_SYNC_SECRET = ('25b7aa166063e863cb63d2d4'
                     'ebfcdfe412e93f8c5d38e455')

app = Flask(__name__)
app.secret_key = ('34c059badbbd38455b4eb44865c25303'
                  '582a6056565be9eee146f46b7079ff95')

db = redis.StrictRedis(host='localhost', port=6379, db=0)

# configure Login Manager:
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'You must be logged in to access this page.'

Bootstrap(app)


# TODO: improve error code responses


@app.route('/')
@app.route('/index')
def index():
    if current_user.is_authenticated:
        return render_template('welcome.html', active='start')
    return render_template('index.html')


@app.route('/impressum')
def impressum():
    return render_template('impressum.html')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico')


"""
<=====================[Routing: /cardboxes]==========================>
<====================================================================>
"""


@app.route('/cardboxes/<_id>')
@login_required
def show_box(_id):
    box = CardBox.fetch(db, _id)

    if not box:
        flash('Invalid Cardbox ID.', 'error')
        return redirect(url_for('huge_list'))

    owned = box.owner == current_user._id

    return render_template('show_box.html', box=box, owned=owned)


@app.route('/cardboxes/<_id>/peek')
@login_required
def preview_box(_id):
    box = CardBox.fetch(db, _id)

    if not box:
        flash('Invalid Cardbox ID.', 'error')
        return redirect(url_for('huge_list'))

    return render_template('preview_box.html', box=box)


@app.route('/cardboxes/<_id>/rate')
@login_required
def rate_cardbox(_id):
    box = CardBox.fetch(db, _id)

    if not box:
        flash('Invalid Cardbox ID.', 'error')
        return redirect(url_for('index'))

    if box.increment_rating(db, current_user):
        User.update_score(db, box.owner)
        flash('Successfully rated. Thank you for your appreciation! :3')
        return redirect(url_for('show_box', _id=_id))

    flash("Already rated. Don't try to fool us!", 'error')
    return redirect(url_for('show_box', _id=_id))


@app.route('/cardboxes/<_id>/delete', methods=['POST', 'GET'])
@login_required
def delete_cardbox(_id):
    box = CardBox.fetch(db, _id)

    if not box:
        flash('Invalid Cardbox ID.', 'error')
        return redirect(url_for('index'))

    if box._id not in current_user.cardboxs:
        flash('You can only delete cardboxes that you own.', 'error')
        return redirect(url_for('show_box', _id=_id))

    form = ConfirmationForm()
    form.submit.label.text = 'Delete'
    message = 'Are you sure you want to delete CardBox ' + box.name + '?'

    if form.is_submitted():

        CardBox.delete(db, _id)

        current_user.cardboxs.remove(box._id)

        current_user.store(db)
        User.update_score(db, current_user._id)

        flash("Successfully removed CardBox")
        return redirect(url_for('huge_list',
                                foption='owner', fterm=current_user._id))

    return render_template('_confirm.html', message=message,
                           address='show_box', add_kwargs={'_id': _id},
                           form=form)


@app.route('/cardboxes', methods=['POST', 'GET'])
@login_required
def huge_list():

    args = request.args

    # <-- receive parameters -->
    sort_key = args.get('sort')
    sort_direction = args.get('direction')
    page = args.get('page')
    filter_option = args.get('foption')
    filter_term = args.get('fterm')

    # <-- validate parameters and set fallback values -->
    sort_key_possible = ('name', 'owner', 'rating')
    sort_key = sort_key if sort_key in sort_key_possible else 'rating'

    sort_direction_possible = ('desc', 'asc')
    sort_direction = (sort_direction
                      if sort_direction in sort_direction_possible
                      else 'desc')
    sort_direction_bool = sort_direction == 'desc'

    filter_option_possible = ('name', 'owner', 'tags')
    filter_option = (filter_option if filter_option in filter_option_possible
                     else 'tags')

    # filter_term: filter only applied if non-empty string given (None case)
    # TODO: filter_term validation analogous to tags/user input sanitization

    page = page or 1  # equals 1 if None; else: stays the same
    try:
        page = int(page)
    except ValueError:
        page = 1

    # <-- filter form -->
    form = FilterForm()
    if form.validate_on_submit():
        filter_option = form.option.data
        filter_term = form.term.data

        kwargs = {key: value for key, value in args.items()}
        kwargs.update(sort=sort_key, direction=sort_direction,
                      foption=filter_option, fterm=filter_term, page=1)

        return redirect(url_for('huge_list', **kwargs))

    form.term.data = filter_term
    form.option.data = filter_option

    cardboxes = CardBox.fetch_all(db)

    # <-- filter process -->
    # checks for filter_option = 'tags' if term exists in tag list
    # checks for filter_option = 'name', 'owner' if term is part of string
    if filter_term:
        if filter_option == 'name' or filter_option == 'owner':
            cardboxes = [box for box in cardboxes
                         if filter_term.lower()
                         in getattr(box, filter_option).lower()]
        else:
            cardboxes = [box for box in cardboxes
                         if filter_term in getattr(box, filter_option)]

    # <-- sort process -->
    def _sort_key_of(box):
        if sort_key == 'name':
            return box.name.lower()
        if sort_key == 'owner':
            return box.owner.lower()

        return getattr(box, sort_key)

    if cardboxes:
        cardboxes.sort(key=_sort_key_of, reverse=sort_direction_bool)

    # <-- pagination -->
    per_page = 50
    cardbox_count = len(cardboxes)
    page_range = utils.page_range(total_count=cardbox_count, per_page=per_page)
    page = (page if page in page_range else 1)

    pagination = utils.Pagination(parent=cardboxes,
                                  page=page,
                                  per_page=per_page,
                                  total_count=cardbox_count)

    # <-- standard values-->
    kwargs = {key: value for key, value in args.items()}
    kwargs.update(sort=sort_key, direction=sort_direction,
                  foption=filter_option, fterm=filter_term, page=page)

    # <-- creation of dynamic content -->
    pag_kwargs = dict(pagination=pagination, endpoint='huge_list',
                      prev='<', next='>', ellipses='...', size='lg',
                      args=kwargs)

    table = CardBoxTable(pagination.items,
                         sort_reverse=sort_direction_bool,
                         sort_by=sort_key)

    return render_template('huge_list.html',
                           table=table,
                           filter_form=form,
                           pagination_kwargs=pag_kwargs,
                           active='explore')


"""
<=================[Routing: /user, /community]=======================>
<====================================================================>
"""


@app.route('/user/<_id>')
@login_required
def show_user(_id):
    if not User.exists(db, _id):
        flash('Invalid User Name.'
              'Be the first User to have this name! :D', 'error')
        return redirect(url_for('index'))

    score = User.update_score(db, _id)

    user = User.fetch(db, _id)
    picture_filepath = utils.profile_img_path(app, user._id)

    # <-- Showcase -->
    showcase = dict(info=False, cardbox=False, rank=False)

    infocase = user.showcase
    if infocase['show_info']:
        showcase['info'] = infocase['info']
    if infocase['show_cardbox']:
        box = CardBox.fetch(db, infocase['cardbox'])
        if box:
            showcase['cardbox'] = box
        else:
            showcase['cardbox'] = 'string'
    if infocase['show_rank']:
        showcase['rank'] = user.get_rank(db)

    # <-- my own profile? -->
    if user._id == current_user._id:
        return render_template('show_user_myself.html',
                               user=user, showcase=showcase,
                               picture_filepath=picture_filepath,
                               score=score,
                               active='profile')

    return render_template('show_user.html', user=user, active='community',
                           picture_filepath=picture_filepath,
                           showcase=showcase, score=score,
                           following=current_user.is_following(_id))


@app.route('/user/settings', methods=['POST', 'GET'])
@login_required
def user_settings():

    # <-- Change profile picture -->
    picture_form = PictureForm()

    if picture_form.submit.data and picture_form.validate_on_submit():
        filename = utils.sha1_of(current_user._id) + '.jpg'
        filepath = os.path.join(app.static_folder, 'img', filename)

        utils.save_file_field_img(picture_form.picture, filepath)

        flash('Successfully changed profile picture!')

        return(redirect(url_for('user_settings')))

    elif picture_form.submit.data and picture_form.is_submitted():
        for message in picture_form.picture.errors:
            flash(message, category='error')

        return(redirect(url_for('user_settings')))

    picture_filepath = utils.profile_img_path(app, current_user._id)

    # <-- Change Showcase -->
    boxes = CardBox.fetch_multiple(db, current_user.cardboxs)

    showcase_form = ShowcaseForm()
    choices = [(b._id, b.name) for b in boxes]
    choices = [('', '---')] + choices
    showcase_form.cardbox_input.choices = choices

    if (showcase_form.submit_showcase.data and
            showcase_form.validate_on_submit()):
        new_showcase = dict(info=showcase_form.info_input.data,
                            cardbox=showcase_form.cardbox_input.data,
                            show_info=showcase_form.check_info.data,
                            show_cardbox=showcase_form.check_cardbox.data,
                            show_rank=showcase_form.check_rank.data)

        current_user.showcase = new_showcase
        current_user.store(db)

        flash('Showcase adjusted!')

        return redirect(url_for('user_settings'))

    showcase_form.check_info.data = current_user.showcase['show_info']
    showcase_form.info_input.data = current_user.showcase['info']
    showcase_form.check_cardbox.data = current_user.showcase['show_cardbox']
    showcase_form.cardbox_input.data = current_user.showcase['cardbox']
    showcase_form.check_rank.data = current_user.showcase['show_rank']
    showcase_form.rank_token.data = current_user.get_rank(db)

    # <-- Change Password -->
    password_form = ChangePasswordForm()

    if (password_form.submit_password.data and
            password_form.validate_on_submit()):

        if not current_user.check_password(password_form.old_password.data):
            flash('Old passwort not correct.', 'error')
            return redirect(url_for('user_settings'))

        current_user.set_password(password_form.new_password.data)
        current_user.store(db)

        flash('Successfully changed password!')

        return redirect(url_for('user_settings'))

    return render_template('profile_settings.html', user=current_user,
                           picture_form=picture_form,
                           showcase_form=showcase_form,
                           password_form=password_form,
                           picture_filepath=picture_filepath)


@app.route('/user/settings/remove-avatar', methods=['POST', 'GET'])
@login_required
def delete_profile_picture():

    form = ConfirmationForm()
    form.submit.label.text = 'Delete'
    message = 'Are you sure you want to delete your current profile picture?'

    if form.is_submitted():

        if utils.delete_profile_img(app, current_user._id):
            flash("Successfully removed profile picture.")
        else:
            flash("There was no picture to delete.")

        return redirect(url_for('user_settings'))

    return render_template('_confirm.html', message=message,
                           address='user_settings', add_kwargs={},
                           form=form)


@app.route('/community/<_id>/toggle-follow')
@login_required
def toggle_follow(_id):

    user = User.fetch(db, _id)

    if not user:
        flash('Invalid User Name.', 'error')
        return redirect(url_for('index'))

    current_user.toggle_follow(_id)
    current_user.store(db)
    User.update_score(db, _id)

    return_address = request.referrer or url_for('show_user', _id=_id)

    if current_user.is_following(_id):
        flash(f'Now following {_id}')

        return redirect(return_address)

    flash(f'Unfollowed {_id}')

    return redirect(return_address)


@app.route('/community', methods=['POST', 'GET'])
@login_required
def user_list():

    args = request.args

    # <-- receive parameters -->
    sort_key = args.get('sort')
    sort_direction = args.get('direction')
    page = args.get('page')
    filter_term = args.get('fterm')
    following = args.get('show')

    # <-- validate parameters and set fallback values -->
    sort_key_possible = ('username', 'score')
    sort_key = sort_key if sort_key in sort_key_possible else 'score'

    sort_direction_possible = ('desc', 'asc')
    sort_direction = (sort_direction
                      if sort_direction in sort_direction_possible
                      else 'desc')
    sort_direction_bool = sort_direction == 'desc'

    # filter_term: filter only applied if non-empty string given (None case)
    # TODO: filter_term validation analogous to tags/user input sanitization

    following_possible = ('following', 'all')
    following = following if following in following_possible else 'following'
    following_bool = following == 'following'

    page = page or 1  # equals 1 if None; else: stays the same
    try:
        page = int(page)
    except ValueError:
        page = 1

    # <-- search form -->
    form = CommunityForm()
    if form.validate_on_submit():
        filter_term = form.term.data

        kwargs = {key: value for key, value in args.items()}
        kwargs.update(sort=sort_key, direction=sort_direction,
                      fterm=filter_term, show='all', page=1)

        return redirect(url_for('user_list', **kwargs))

    form.term.data = filter_term

    # <-- distinction: followed users - all users -->
    if following_bool:
        if not current_user.following:
            return render_template('community.html', search_form=form,
                                   following_bool=following_bool,
                                   active='community', no_table=True)

        users = User.fetch_multiple(db, current_user.following)
    else:
        users = User.fetch_all(db)

    # <-- filter process -->
    if filter_term:
        users = [user for user in users
                 if filter_term.lower() in getattr(user, '_id').lower()]

    # <-- create wrapper objects -->
    def follow_label_producer(item):
        return 'Unfollow' if current_user.is_following(item._id) else 'Follow'

    def score_value_producer(item):
        return item.raw.get_score(db)

    wrapper = utils.TableItemWrapper(dict(follow_label=follow_label_producer,
                                          score=score_value_producer))

    users = wrapper(users)

    # <-- sort process -->
    def _sort_key_of(user):
        if sort_key == 'username':
            return user._id.lower()

        return getattr(user, sort_key)

    if users:
        users.sort(key=_sort_key_of, reverse=sort_direction_bool)

    # <-- pagination -->
    per_page = 50
    user_count = len(users)
    page_range = utils.page_range(total_count=user_count, per_page=per_page)
    page = (page if page in page_range else 1)

    pagination = utils.Pagination(parent=users,
                                  page=page,
                                  per_page=per_page,
                                  total_count=user_count)

    # <-- standard values-->
    kwargs = {key: value for key, value in args.items()}
    kwargs.update(sort=sort_key, direction=sort_direction,
                  fterm=filter_term, show=following, page=page)

    # <-- creation of dynamic content -->
    pag_kwargs = dict(pagination=pagination, endpoint='user_list',
                      prev='<', next='>', ellipses='...', size='lg',
                      args=kwargs)

    table = UserTable(pagination.items,
                      sort_reverse=sort_direction_bool,
                      sort_by=sort_key)

    return render_template('community.html',
                           table=table, following_bool=following_bool,
                           search_form=form,
                           pagination_kwargs=pag_kwargs,
                           active='community')


@app.route('/scoreboard')
@login_required
def score_list():

    args = request.args

    # <-- receive parameters -->
    page = args.get('page')

    # <-- validate parameters and set fallback values -->
    page = page or 1  # equals 1 if None; else: stays the same
    try:
        page = int(page)
    except ValueError:
        page = 1

    users = User.top_user_dicts(db)

    # <-- pagination -->
    per_page = 50
    user_count = len(users)
    page_range = utils.page_range(total_count=user_count, per_page=per_page)
    page = (page if page in page_range else 1)

    pagination = utils.Pagination(parent=users,
                                  page=page,
                                  per_page=per_page,
                                  total_count=user_count)

    # <-- standard values-->
    kwargs = {key: value for key, value in args.items()}
    kwargs.update(page=page)

    # <-- creation of dynamic content -->
    pag_kwargs = dict(pagination=pagination, endpoint='score_list',
                      prev='<', next='>', ellipses='...', size='lg',
                      args=kwargs)

    table = ScoreTable(pagination.items)

    your_score = dict(score=current_user.get_score(db),
                      rank=current_user.get_rank(db))

    return render_template('scoreboard.html',
                           table=table,
                           your_score=your_score,
                           pagination_kwargs=pag_kwargs,
                           active='community')


"""
<=====================[Routing: /challenge]==========================>
<====================================================================>
"""


@app.route('/challenge/<_id>', methods=['POST', 'GET'])
@login_required
def challenge_user(_id):
    if _id == current_user._id:
        flash('You can not even challenge yourself. Nice try.', 'error')
        return redirect(url_for('user_list'))

    args = request.args

    # <-- receive parameters -->
    sort_key = args.get('sort')
    sort_direction = args.get('direction')
    page = args.get('page')
    filter_option = args.get('foption')
    filter_term = args.get('fterm')

    # <-- validate parameters and set fallback values -->
    sort_key_possible = ('name', 'owner', 'rating')
    sort_key = sort_key if sort_key in sort_key_possible else 'rating'

    sort_direction_possible = ('desc', 'asc')
    sort_direction = (sort_direction
                      if sort_direction in sort_direction_possible
                      else 'desc')
    sort_direction_bool = sort_direction == 'desc'

    filter_option_possible = ('name', 'owner')
    filter_option = (filter_option if filter_option in filter_option_possible
                     else 'name')

    # filter_term: filter only applied if non-empty string given (None case)
    # TODO: filter_term validation analogous to tags/user input sanitization

    page = page or 1  # equals 1 if None; else: stays the same
    try:
        page = int(page)
    except ValueError:
        page = 1

    # <-- filter form -->
    form = ChallengeFilterForm()
    if form.validate_on_submit():
        filter_option = form.option.data
        filter_term = form.term.data

        kwargs = {key: value for key, value in args.items()}
        kwargs.update(sort=sort_key, direction=sort_direction,
                      foption=filter_option, fterm=filter_term, page=1)

        return redirect(url_for('challenge_user', _id=_id, **kwargs))

    form.term.data = filter_term
    form.option.data = filter_option

    cardboxes = CardBox.fetch_all(db)

    # <-- filter process -->
    # checks for filter_option = 'name', 'owner' if term is part of string
    if filter_term:
        if filter_option == 'name' or filter_option == 'owner':
            cardboxes = [box for box in cardboxes
                         if filter_term.lower()
                         in getattr(box, filter_option).lower()]
        else:
            cardboxes = [box for box in cardboxes
                         if filter_term in getattr(box, filter_option)]

    # <-- sort process -->
    def _sort_key_of(box):
        if sort_key == 'name':
            return box.name.lower()
        if sort_key == 'owner':
            return box.owner.lower()

        return getattr(box, sort_key)

    if cardboxes:
        cardboxes.sort(key=_sort_key_of, reverse=sort_direction_bool)

    # <-- pagination -->
    per_page = 50
    cardbox_count = len(cardboxes)
    page_range = utils.page_range(total_count=cardbox_count, per_page=per_page)
    page = (page if page in page_range else 1)

    pagination = utils.Pagination(parent=cardboxes,
                                  page=page,
                                  per_page=per_page,
                                  total_count=cardbox_count)

    # <-- standard values-->
    kwargs = {key: value for key, value in args.items()}
    kwargs.update(sort=sort_key, direction=sort_direction,
                  foption=filter_option, fterm=filter_term, page=page, _id=_id)

    # <-- creation of dynamic content -->
    pag_kwargs = dict(pagination=pagination, endpoint='challenge_user',
                      prev='<', next='>', ellipses='...', size='lg',
                      args=kwargs)

    def partner_id_producer(item):
        return _id

    wrapper = utils.TableItemWrapper(dict(partner_id=partner_id_producer))

    table = ChooseBoxTable(wrapper(pagination.items), _id,
                           sort_reverse=sort_direction_bool,
                           sort_by=sort_key)

    return render_template('challenge.html', _id=_id,
                           table=table,
                           filter_form=form,
                           pagination_kwargs=pag_kwargs,
                           active='versus')


@app.route('/challenge/<user_id>/<box_id>', methods=['POST', 'GET'])
@login_required
def confirm_challenge(user_id, box_id):
    box = CardBox.fetch(db, box_id)

    if not box:
        flash('Invalid Cardbox ID.', 'error')
        return redirect(url_for('challenge_user', _id=user_id))

    if user_id == current_user._id:
        flash('You can not even challenge yourself. Nice try.', 'error')
        return redirect(url_for('user_list'))

    user = User.fetch(db, user_id)

    if not user:
        flash('Invalid User ID.', 'error')
        return redirect(url_for('user_list'))

    form = ConfirmationForm()
    form.submit.label.text = 'Challenge'
    message = 'Challenge ' + user_id + ' to duel ' + box.name + '?'

    if form.is_submitted():
        challenge.challenge(db, current_user._id, user._id, box._id)
        flash('Challenge request sent!')
        return redirect(url_for('challenge_list', requests='sent'))

    return render_template('_confirm.html', message=message,
                           address='challenge_user',
                           add_kwargs={'_id': user_id},
                           form=form)


@app.route('/challenge')
@login_required
def challenge_list():

    args = request.args

    # <-- receive parameters -->
    chrequests = args.get('requests')

    # <-- validate parameters and set fallback values -->
    chrequests_poss = ('sent', 'incoming')
    chrequests = chrequests if chrequests in chrequests_poss else 'incoming'
    # chrequests_bool = chrequests == 'incoming'

    if chrequests == 'incoming':
        requests = challenge.fetch_challenges_to(db, current_user._id)
        table = ChallgengeIncomingTable(requests)

    else:
        requests = challenge.fetch_challenges_of(db, current_user._id)
        table = ChallgengeSentTable(requests)

    return render_template('challenge_list.html', active='versus',
                           table=table, chrequests=chrequests)


@app.route('/challenge/<_id>/rm')
@login_required
def delete_challenge(_id):
    vs_dict = challenge.fetch_duel(db, _id)

    if not vs_dict:
        flash('A challenge with this ID does not exist', 'error')
        return redirect(url_for('challenge_list'))

    if vs_dict['started']:
        flash('This duel has already started.', 'error')
        return redirect(url_for('challenge_list'))

    if vs_dict['challenger'] == current_user._id:
        challenge.delete_challenge(db, _id)
        flash('Successfully canceled challenge request.')
        return redirect(url_for('challenge_list', requests='sent'))

    if vs_dict['challenged'] == current_user._id:
        challenge.delete_challenge(db, _id)
        flash('Successfully declined challenge request.')
        return redirect(url_for('challenge_list'))

    flash('You have no rights to alter this challenge!', 'error')
    return redirect(url_for('challenge_list'))


@app.route('/challenge/<_id>/start')
@login_required
def start_duel(_id):
    vs_dict = challenge.fetch_duel(db, _id)

    if not vs_dict:
        flash('A challenge with this ID does not exist.', 'error')
        return redirect(url_for('challenge_list'))

    if vs_dict['started']:
        flash('This duel has already started.', 'error')
        return redirect(url_for('challenge_list'))

    if vs_dict['challenged'] == current_user._id:
        challenge.start_duel(db, _id)
        return redirect(url_for('duel', _id=_id))

    flash('You have no rights to alter this challenge!', 'error')
    return redirect(url_for('challenge_list'))


@app.route('/duel/<_id>/r')
@login_required
def duel_r(_id):
    vs_dict = challenge.fetch_duel(db, _id)
    cuser_id = current_user._id

    if not vs_dict or not vs_dict['started']:
        flash('A duel with this ID does not exist.', 'error')
        return redirect(url_for('duel_list'))

    # if vs_dict['winner']:
    #     return redirect(url_for('duel_result', _id=_id))

    if cuser_id not in (vs_dict['challenger'], vs_dict['challenged']):
        flash('You have no rights to access this duel!', 'error')
        return redirect(url_for('duel_list'))

    num_answers = challenge.num_answers_of(db, cuser_id, _id)

    if num_answers == 0:
        return redirect(url_for('duel', _id=_id))

    # pointer to last answer card
    index = num_answers - 1

    card = challenge.get_card_from_duel(vs_dict, index)
    answers = challenge.answers_of(db, cuser_id, _id)
    last_choice = answers[index]
    last_choice_letter = 'abc'[last_choice]
    cardbox_size = challenge.duel_length(vs_dict)
    cardbox_name = vs_dict['box_name']

    correct = vs_dict['box_content']['correct_answers'][:num_answers]
    num_correct_answers = challenge.num_correct_answers(correct, answers)

    opponent = (vs_dict['challenger'] if cuser_id == vs_dict['challenged']
                else vs_dict['challenged'])

    return render_template('duel_card_result.html',
                           answer_list=answers,
                           opponent=opponent,
                           cardbox_name=cardbox_name,
                           card_number=num_answers,
                           cardbox_size=cardbox_size,
                           num_correct_answers=num_correct_answers,
                           last_choice=last_choice,
                           last_choice_letter=last_choice_letter,
                           card=card,
                           cardbox_id=_id,
                           active='versus')


@app.route('/duel/<_id>', methods=['GET', 'POST'])
@login_required
def duel(_id):
    vs_dict = challenge.fetch_duel(db, _id)

    cuser_id = current_user._id
    opponent = challenge.get_opponent(vs_dict, cuser_id)
    duel_len = challenge.duel_length(vs_dict)

    if not vs_dict or not vs_dict['started']:
        flash('A duel with this ID does not exist.', 'error')
        return redirect(url_for('duel_list'))

    if vs_dict['winner']:
        return redirect(url_for('duel_result', _id=_id))

    if cuser_id not in (vs_dict['challenger'], vs_dict['challenged']):
        flash('You have no rights to access this duel!', 'error')
        return redirect(url_for('duel_list'))

    if (request.method == 'POST' and
            request.form and 'choice' in request.form.keys()):
        # the second and third 'and' is only necessary to prevent
        # malformed/malicious POST requests form crashing the site

        choice = request.form['choice']

        # try casting choice to int and perform range check before
        # actually using it for anything serious!
        try:
            choice = int(choice)

            if choice not in range(0, 3):
                raise ValueError()
        except:
            flash('Hacking much? Not appreciated. Thx.', 'error')
            return redirect(url_for('duel', _id=_id))

        challenge.put_answer(db, cuser_id, _id, choice)

        we_finished = challenge.num_answers_of(db, cuser_id, _id) == duel_len
        opp_finished = challenge.num_answers_of(db, opponent, _id) == duel_len

        if we_finished and opp_finished:
            challenge.finish_duel(db, _id)

        return redirect(url_for('duel_r', _id=_id))

    we_finished = challenge.num_answers_of(db, cuser_id, _id) == duel_len

    cardbox_name = vs_dict['box_name']

    if we_finished:
        return render_template('wait.html',
                               opponent=opponent,
                               cardbox_name=cardbox_name,
                               duel_id=_id,
                               active='versus')

    num_answers = challenge.num_answers_of(db, cuser_id, _id)
    cardbox_size = challenge.duel_length(vs_dict)
    card = challenge.get_card_from_duel(vs_dict, num_answers)

    answers = challenge.answers_of(db, cuser_id, _id)
    correct = vs_dict['box_content']['correct_answers'][:num_answers]
    num_correct_answers = challenge.num_correct_answers(correct, answers)

    return render_template('duel.html',
                           opponent=opponent,
                           cardbox_name=cardbox_name,
                           card_number=num_answers + 1,
                           cardbox_size=cardbox_size,
                           num_correct_answers=num_correct_answers,
                           number_answers=num_answers,
                           card=card,
                           #    cardbox_id=_id, #  TODO: for FORFEIT
                           active='versus')


@app.route('/duel/<_id>/result')
@login_required
def duel_result(_id):
    vs_dict = challenge.fetch_duel(db, _id)

    if not vs_dict or not vs_dict['winner']:
        return redirect(url_for('duel_list'))

    challenger = vs_dict['challenger']
    challenged = vs_dict['challenged']

    cardbox_size = challenge.duel_length(vs_dict)

    correct = vs_dict['box_content']['correct_answers']
    answers_challenger = challenge.answers_of(db, challenger, _id)
    answers_challenged = challenge.answers_of(db, challenged, _id)

    num_correct_challenger = challenge.num_correct_answers(correct,
                                                           answers_challenger)
    num_correct_challenged = challenge.num_correct_answers(correct,
                                                           answers_challenged)

    bool_challenger = challenge.check_answer_list(correct, answers_challenger)
    bool_challenged = challenge.check_answer_list(correct, answers_challenged)

    time_stamp = utils.unix_time_to_iso(vs_dict['finish_time'])

    return render_template('duel_result.html',
                           challenger=challenger,
                           challenged=challenged,
                           box_name=vs_dict['box_name'],
                           box_id=vs_dict['box_id'],
                           cardbox_size=cardbox_size,
                           num_correct_challenger=num_correct_challenger,
                           num_correct_challenged=num_correct_challenged,
                           bool_challenger=bool_challenger,
                           bool_challenged=bool_challenged,
                           correct_answers=correct,
                           answers_challenger=answers_challenger,
                           answers_challenged=answers_challenged,
                           winner=vs_dict['winner'],
                           time_stamp=time_stamp,
                           active='versus')


@app.route('/duel')
@login_required
def duel_list():

    args = request.args

    # <-- receive parameters -->
    location = args.get('location')

    # <-- validate parameters and set fallback values -->
    location_possible = ('current', 'archive')
    location = location if location in location_possible else 'current'

    def opponent_id_producer(item):
        if current_user._id == item.challenger:
            return item.challenged
        return item.challenger

    if location == 'archive':

        duels = challenge.fetch_archived_duels(db, current_user._id)

        def time_stamp_producer(item):
            return utils.unix_time_to_iso(item.finish_time)

        wrapper = utils.TableItemWrapper(dict(partner_id=opponent_id_producer,
                                              time=time_stamp_producer))
        table = DuelArchiveTable(wrapper(duels))

    else:
        duels = challenge.fetch_duels_of(db, current_user._id)
        wrapper = utils.TableItemWrapper(dict(partner_id=opponent_id_producer))
        table = DuelTable(wrapper(duels))

    return render_template('duel_list.html', table=table,
                           location=location, active='versus')


"""
<=====================[Public API endpoints:]========================>
<====================================================================>
"""


# TODO fix error responses
@app.route('/add_cardbox', methods=['POST'])
def add_cardbox():
    if not request.is_json:
        print('not json')
        abort(404)

    # already returns dictionary
    payload = request.get_json()

    # <-- validate payload -->
    req = ('username', 'password', 'tags', 'content', 'name', 'info')
    if not payload or not all(r in payload for r in req):
        print('missing key in payload')
        abort(404)

    # None check
    if any(payload[key] is None for key in req):
        print('key is None')
        abort(404)

    # type check
    if not all([isinstance(payload['tags'], list),
                isinstance(payload['name'], str),
                isinstance(payload['info'], str)]):
        print('key wrong type')
        abort(404)

    if any(' ' in tag for tag in payload['tags']):
        print('whitespace in tag')
        abort(404)

    # <-- validate content -->
    if not isinstance(payload['content'], list):
        print('content not list')
        abort(404)

    attrs = ('question', 'answers', 'correct_answer', 'explanation')
    if not all(a in _dict for a in attrs for _dict in payload['content']):
        print('missing key in card')
        abort(404)

    number_of_answers = 3

    for card in payload['content']:

        q, a, ca, e = (card['question'], card['answers'],
                       card['correct_answer'], card['explanation'])

        if not isinstance(q, str) or not isinstance(e, str):
            abort(404)

        if not (isinstance(a, list) and len(a) == number_of_answers):
            abort(404)

        if not (isinstance(ca, int) and ca in range(number_of_answers)):
            abort(404)

    # check authorization
    if User.exists(db, payload['username']):
        user = User.fetch(db, payload['username'])
        if not user.check_password(payload['password']):
            print('unauthorized')
            abort(404)

        cardbox_id = CardBox.gen_card_id()

        # 'Update'-Function
        boxes = CardBox.fetch_multiple(db, user.cardboxs)

        for box in boxes:
            if box.name == payload['name']:
                cardbox_id = box._id
                break
        else:
            user.cardboxs.append(cardbox_id)

        # store content in separate redis table
        Card.save_content(db, cardbox_id, payload['content'])

        # create CardBox object for metadata
        new_box = CardBox(cardbox_id, name=payload['name'],
                          owner=user._id, rating=0, info=payload['info'],
                          tags=payload['tags'])

        new_box.store(db)
        user.store(db)
        User.update_score(db, user._id)

    return 'OK'


# TODO filter malevolent input
# TODO fix error responses
@app.route('/sync_user_score', methods=['POST'])
def sync_score():
    if not request.is_json:
        abort(404)

    # already returns dictionary
    payload = request.get_json()

    req = ('username', 'password', 'secret', 'score')
    if not payload or not all(r in payload for r in req):
        abort(404)

    if not payload['secret'] == SCORE_SYNC_SECRET:
        abort(404)

    if User.exists(db, payload['username']):
        user = User.fetch(db, payload['username'])
        if not user.check_password(payload['password']):
            abort(404)

        user.offline_score = payload['score']
        user.store(db)

        User.update_score(db, user._id)

    return 'OK'


@app.route('/cardboxes/<_id>/prepare-download')
def prepare_download(_id: str):
    return render_template('prepare_download.html', box_id=_id)


@app.route('/cardboxes/<_id>/download', methods=['GET'])
def download_cardbox(_id: str):
    box = CardBox.fetch(db, _id)

    if not box:
        abort(404)

    content = Card.fetch_content_to_list(db, _id)
    vars_box = vars(box)
    vars_box['content'] = content

    # use flask jsonify to create valid json response
    return jsonify(vars_box)


"""
<======================[Authentification:]===========================>
<====================================================================>
"""


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegistrationForm(db)

    if form.validate_on_submit():
        user = User(form.username.data)
        user.set_password(form.password.data)

        user.init_user_score(db)
        user.store(db)

        flash("Account creation successful. "
              "Welcome to our happy lil' community!")
        return redirect(url_for('login'))

    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm(db)

    if form.validate_on_submit():

        user = User.fetch(db, form.username.data)
        if not user.check_password(form.password.data):
            flash('You shall not password.', 'error')
            return redirect(url_for('login'))

        login_user(user)

        flash('Login successful!')

        # flask_login.LoginManager sets 'next' url Argument by default.
        next_page = request.args.get('next')

        # Additional check if address is relative (no netloc component).
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('index')

        return redirect(next_page)

    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout successful. See you soon!')
    return redirect(url_for('index'))


def update_notifications(user):
    if not user:
        return

    user_id = user._id

    session['counter_ch_in'] = challenge.num_incoming_challenges(db, user_id)
    session['counter_ch_out'] = challenge.num_outgoing_challenges(db, user_id)
    session['counter_duels'] = challenge.num_duels(db, user_id)


@login_manager.user_loader
def load_user(user_id: str):
    user = User.fetch(db, user_id)

    update_notifications(user)

    return user


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
