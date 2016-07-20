# -*- coding: utf-8 -*-
"""Entity class of site."""
import hashlib

from datetime import datetime
from pony.orm import *

db = Database()


class User(db.Entity):
    _table_ = 'users'
    username = Required(str, unique=True)
    password = Required(str)
    dt = Required(datetime, 6, default=datetime.now())
    following = Set('Following', reverse='follower')
    followers = Set('Following', reverse='followee')
    photos = Set('Photo')
    likes = Set('Like')
    comments = Set('Comment', reverse='user')
    mentioned = Set('Comment', reverse='mentioned')

    @staticmethod
    def create_password(raw):
        return hashlib.new('md5', raw.encode('utf-8')).hexdigest()

    def check_password(self, raw):
        return hashlib.new('md5', raw.encode('utf-8')).hexdigest() == self.password


class Photo(db.Entity):
    _table_ = 'photos'

    filename = Required(str)
    photo_url = Required(str)
    dt = Required(datetime, 6, default=datetime.now())
    tags = Set('Tag')
    user = Required(User)
    liked = Set('Like')
    comments = Set('Comment')

    def to_json(self, u):
        return {
            'id': self.id,
            'photo_url': self.photo_url,
            'username': self.user.username,
            'likes_count': len(self.liked),
            'liked': u in self.liked.user.username
        }


class Tag(db.Entity):
    _table_ = 'tags'
    name = Required(str, unique=True)
    name = PrimaryKey(str)
    photos = Set(Photo)


class Comment(db.Entity):
    photo = Required(Photo)
    user = Required(User, reverse='comments')
    dt = Required(datetime, 6, default=datetime.now())
    text = Required(str)
    mentioned = Set(User, reverse='mentioned')


class Like(db.Entity):
    user = Required(User)
    photo = Required(Photo)
    dt = Required(datetime, default=datetime.now())
    PrimaryKey(user, photo)


class Following(db.Entity):
    follower = Required(User, reverse='following')
    followee = Required(User, reverse='followers')
    dt = Required(datetime, default=datetime.now())
    PrimaryKey(follower, followee)
