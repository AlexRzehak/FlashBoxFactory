import os

import redis
from flask import Flask, request, redirect, url_for, flash, render_template, send_from_directory, abort, jsonify
from flask_login import LoginManager, current_user, login_user, login_required, logout_user
from flask_table import Table, Col, ButtonCol, LinkCol
from flask_bootstrap import Bootstrap
from werkzeug.urls import url_parse

import utils
from model import CardBox
from user import User, Showcase, RegistrationForm, LoginForm, ChangePasswordForm
from display import CardBoxTable, UserTable, ScoreTable, FilterForm, CommunityForm, ShowcaseForm, PictureForm


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


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico')


@app.route('/challenge/<_id>')
@login_required
def challenge(_id):
    return render_template('challenge.html', partner=_id)


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


@app.route('/user/<_id>')
@login_required
def show_user(_id):
    if not User.exists(db, _id):
        flash('Invalid User Name.'
              'Be the first User to have this name! :D', 'error')
        return redirect(url_for('index'))

    User.update_score(db, _id)

    user = User.fetch(db, _id)
    picture_filepath = utils.profile_img_path(app, user._id)

    if user._id == current_user._id:
        return render_template('show_user_myself.html',
                               user=user,
                               picture_filepath=picture_filepath,
                               active='profile')

    return render_template('show_user.html', user=user,
                           picture_filepath=picture_filepath,
                           following=current_user.is_following(_id))


@app.route('/user/settings', methods=['POST', 'GET'])
@login_required
def user_settings():

    # <-- Change profile picture -->
    picture_form = PictureForm()

    if picture_form.validate_on_submit():
        filename = utils.sha1_of(current_user._id) + '.jpg'
        filepath = os.path.join(app.static_folder, 'img', filename)

        utils.save_file_field_img(picture_form.picture, filepath)

        flash('Successfully changed profile picture!')

        return(redirect(url_for('user_settings')))

    elif picture_form.is_submitted():
        for message in picture_form.picture.errors:
            flash(message, category='error')

        return(redirect(url_for('user_settings')))

    picture_filepath = utils.profile_img_path(app, current_user._id)

    # # <-- Change Showcase -->
    # boxes = [CardBox.fetch(db, box_id) for box_id in current_user.cardboxs]

    # showcase_form = ShowcaseForm()
    # showcase_form.cardbox_input.choices = [(b._id, b.name) for b in boxes]

    # if showcase_form.validate_on_submit():
    #     new_showcase = Showcase({'info': showcase_form.check_info.data,
    #                              'cardbox': showcase_form.check_cardbox.data,
    #                              'rank': showcase_form.check_rank.data},
    #                             showcase_form.info_input.data,
    #                             showcase_form.cardbox_input.data)

    #     current_user.showcase = new_showcase
    #     current_user.store(db)

    #     flash('Showcase adjusted!')

    #     return redirect(url_for('user_settings'))

    # u_showcase = current_user.showcase
    # if not u_showcase.show:
    #     u_showcase.show = {'info': False, 'cardbox': False, 'rank': False}
    # showcase_form.check_info.data = u_showcase.show['info']
    # showcase_form.info_input.data = u_showcase.info
    # showcase_form.check_cardbox.data = u_showcase.show['cardbox']
    # # showcase_form.info_input.data = u_showcase.info
    # showcase_form.check_rank.data = u_showcase.show['rank']

    # <-- Change Password -->
    password_form = ChangePasswordForm()

    if password_form.validate_on_submit():

        if not current_user.check_password(password_form.old_password.data):
            flash('Old passwort not correct.', 'error')
            return redirect(url_for('user_settings'))

        current_user.set_password(password_form.new_password.data)
        current_user.store(db)

        flash('Successfully changed password!')

        return redirect(url_for('user_settings'))

    return render_template('profile_settings.html', user=current_user,
                           picture_form=picture_form,
                           password_form=password_form,
                           picture_filepath=picture_filepath)
    # showcase_form=showcase_form)


@app.route('/community/<_id>/toggle-follow')
@login_required
def toggle_follow(_id):

    user = User.fetch(db, _id)

    if not user:
        flash('Invalid User Name.', 'error')
        return redirect(url_for('index'))

    current_user.toggle_follow(_id)
    current_user.store(db)
    User.update_score(db, current_user._id)

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
                                   active='community', no_table=True)

        users = User.fetch(db, *current_user.following)
    else:
        users = User.fetch_all(db)

    # <-- filter process -->
    if filter_term:
        users = [user for user in users
                 if filter_term.lower() in getattr(user, '_id').lower()]

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

    def follow_label_producer(item):
        return 'Unfollow' if current_user.is_following(item._id) else 'Follow'

    wrapper = utils.LabelTableItemWrapper(dict(follows=follow_label_producer))

    table = UserTable(wrapper(pagination.items),
                      sort_reverse=sort_direction_bool,
                      sort_by=sort_key)

    return render_template('community.html',
                           table=table,
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

    users = User.fetch_all(db)

    if users:
        users.sort(key=lambda u: u.score, reverse=True)

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

    big_table = ScoreTable(pagination.items)

    # TODO Show score not retarded
    you = [User.fetch(db, current_user._id)]
    small_table = ScoreTable(you)

    return render_template('scoreboard.html',
                           table=big_table,
                           you=small_table,
                           pagination_kwargs=pag_kwargs,
                           active='community')


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

    # filter_option: filter only applied if non-empty string given (None case)
    # TODO: filter_option validation analogous to tags/user input sanitization

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
    if filter_option == 'name' or filter_option == 'owner':
        cardboxes = [box for box in cardboxes
                     if filter_term.lower()
                     in getattr(box, filter_option).lower()]
    elif filter_term:
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


@app.route('/cardboxes/<_id>/delete')
@login_required
def delete_cardbox(_id):
    box = CardBox.fetch(db, _id)

    if not box:
        flash('Invalid Cardbox ID.', 'error')
        return redirect(url_for('index'))

    if box._id not in current_user.cardboxs:
        flash('You can only delete cardboxes that you own.', 'error')
        return redirect(url_for('show_box', _id=_id))

    CardBox.delete(db, _id)

    current_user.cardboxs.remove(box._id)

    current_user.store(db)
    User.update_score(db, current_user._id)

    flash("Successfully removed CardBox")
    return redirect(url_for('huge_list',
                            foption='owner', fterm=current_user._id))


# TODO filter malevolent input
# TODO fix error responses
@app.route('/add_cardbox', methods=['POST'])
def add_cardbox():
    if not request.is_json:
        abort(404)

    # already returns dictionary
    payload = request.get_json()

    req = ('username', 'password', 'tags', 'content', 'name', 'info')
    if not payload or not all(r in payload for r in req):
        abort(404)

    if User.exists(db, payload['username']):
        user = User.fetch(db, payload['username'])
        if not user.check_password(payload['password']):
            abort(404)

        cardbox_id = CardBox.gen_card_id()

        # 'Update'-Function
        # TODO contemplate for better solution
        boxes = CardBox.fetch(db, *user.cardboxes)

        for box in boxes:
            if box.name == payload['name']:
                cardbox_id = box._id
                break
        else:
            user.cardboxs.append(cardbox_id)

        new_box = CardBox(cardbox_id, name=payload['name'],
                          owner=user._id, rating=0, info=payload['info'],
                          tags=payload['tags'], content=payload['content'])

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

    return jsonify(vars(box))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegistrationForm(db)

    if form.validate_on_submit():
        user = User(form.username.data)
        user.set_password(form.password.data)

        user.store(db)

        flash("Accont creation successful."
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


@login_manager.user_loader
def load_user(user_id: str):
    return User.fetch(db, user_id)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
