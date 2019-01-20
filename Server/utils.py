import json
import math


def unjsonify(json_string: str):
    return json.loads(json_string.decode('utf-8'))


def jsonify(obj: object):
    return json.dumps(vars(obj))


def clean_boxes(db):
    db.hdel('cardboxs', *db.hgetall('cardboxs').keys())
    db.hdel('ratings', *db.hgetall('ratings').keys())


def clean_users(db):
    db.hdel('users', *db.hgetall('users').keys())


def page_range(total_count: int, per_page: int):
    return range(1, int(math.ceil(total_count / per_page))+1)


class Pagination:

    def __init__(self, parent: object,
                 page: int, per_page: int,
                 total_count: int):

        self.parent = parent

        self.page = page
        self.per_page = per_page
        self.total_count = total_count

        self.items = None
        self._init_items()

        # just to fit the signature; should stay 'None'!
        self.query = None

    def _init_items(self):
        _from = (self.page-1) * self.per_page
        to = _from + self.per_page

        self.items = self.parent[_from:to]

    @property
    def pages(self):
        return int(math.ceil(self.total_count / self.per_page))

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    @property
    def prev_num(self):
        return self.page - 1

    @property
    def next_num(self):
        return self.page + 1

    def next(self, error_out=False):
        return Pagination(self.parent, self.next_num, self.per_page,
                          self.total_count)

    def prev(self, error_out=False):
        return Pagination(self.parent, self.prev_num, self.per_page,
                          self.total_count)

    def iter_pages(self, left_edge=2, left_current=2,
                   right_current=5, right_edge=2):
        last = 0
        page = self.page
        pages = self.pages

        for num in range(1, pages + 1):
            if (num <= left_edge or
                    (num > page - left_current - 1
                     and num < page + right_current) or
                    num > pages - right_edge):

                if last + 1 != num:
                    yield None

                yield num
                last = num


class _LabelTableItemContainer:

    def __init__(self, obj: object):

        for attr, val in vars(obj).items():
            setattr(self, attr, val)


class LabelTableItemWrapper:

    def __init__(self, producer_dict: dict):
        self.producer_dict = producer_dict

    def __call__(self, items):
        result = []

        for item in items:
            wrapped_item = _LabelTableItemContainer(item)

            for attr, producer in self.producer_dict.items():
                setattr(wrapped_item, attr + '_label', producer(wrapped_item))

            result.append(wrapped_item)

        return result
