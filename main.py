# -*- coding: utf-8 -*-
""""""
import os
import json
import logging

from hashlib import md5
from tornado import web, gen, ioloop
from jinja2 import Environment, FileSystemLoader
from sockjs.tornado import SockJSRouter, SockJSConnection
from pony.orm import sql_debug

from entities import *

logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger('photo')

sql_debug(True)

template_env = Environment(loader=FileSystemLoader(searchpath="templates"))
db.generate_mapping(create_tables=True)

TORNADO_PORT = 8080

ws_router = None
connections = set()


class BaseHandler(web.RequestHandler):
    """"""
    def get_current_user(self):
        return self.get_secure_cookie('username')

    def render(self, file_name, **kwargs):
        template = template_env.get_template(file_name)
        kwargs.update({
            'TORNADO_PORT': TORNADO_PORT,
            'current_user': self.current_user
        })
        self.write(template.render(**kwargs))

    def broadcast(self, msg):
        ws_router.broadcast(connections, msg)


class MainHandler(BaseHandler):
    @gen.coroutine
    @db_session
    def get(self):
        photos = select(p for p in Photo)
        self.render('photos.html', photos=photos)


class LoginHandler(BaseHandler):
    @gen.coroutine
    def get(self):
        self.render('login.html')

    @gen.coroutine
    @db_session
    def post(self):
        username = self.get_argument('username', '')
        password = self.get_argument('password', '')
        user = User.get(username=username, password=User.check_password(password))
        if user:
            self.set_secure_cookie('username', username)
            self.redirect('/user/%s' % username)
            return
        self.render('login.html', error='username or password not error.')


class SignupHandler(BaseHandler):
    @gen.coroutine
    def get(self):
        self.render('signup.html')

    @gen.coroutine
    def post(self):
        username = self.get_argument('username', '')
        password = self.get_argument('password', '')
        if username and password:
            if User.exists(username=username):
                self.render('signup.html', error='username is already exisits.')
                return
            User(username=username, password=User.create_password(password))
            self.set_secure_cookie('username', username)
            self.redirect('/user/%s' % username)
            return
        self.render('signup.html', error='Please specify username and password')


class LogoutHandler(BaseHandler):
    @gen.coroutine
    def get(self):
        self.clear_all_cookies()
        self.redirect('/')


class UserHomeHandler(BaseHandler):
    @gen.coroutine
    @db_session
    def get(self, username):
        user = User.get(username=username)
        if not user:
            raise web.HTTPError(404, 'No such user.')
        photos = select(p for p in Photo if p.user.username == username)
        self.render('photos.html', page_owner=username, photos=photos)


class UploadHandler(BaseHandler):
    @gen.coroutine
    @web.authenticated
    @gen.coroutine
    def get(self):
        self.render('upload.html')

    # -----------

    @web.authenticated
    @db_session
    def post(self):
        if 'photo_file' not in self.request.files:
            self.render('upload.html')
            return
        photo_file = self.request.files['photo_file'][0]
        content = photo_file['body']
        extension = os.path.splitext(photo_file['filename'])[1]
        filename = "photos/%s%s" % (md5(content).hexdigest(), extension)
        if not os.path.exists(filename):
            with open(filename, 'wb') as f:
                f.write(content)
        photo_url = '/%s' % filename
        user = User.get(username=self.current_user)
        photo = Photo(user=user, filename=filename, photo_url=photo_url)
        commit()
        self.broadcast({'event': 'new_photo',
                        'data': {'id': photo.id, 'photo_url': photo_url, 'username': self.current_user,
                                 'likes_count': 0, 'liked': False}})
        self.redirect('/')


class LikeHandler(BaseHandler):
    @db_session
    def post(self):
        if not self.current_user:
            return
        user = User.get(username=self.current_user)
        photo_id = self.get_argument('photo_id')
        username = self.get_argument('username')
        photo = Photo[photo_id]
        like = Like.get(user=user, photo=photo)
        if like is None:
            Like(user=user, photo=photo)
            self.broadcast({'event': 'like', 'data': {'photo_id': photo_id, 'username': username}})
        else:
            like.delete()
            self.broadcast({'event': 'unlike', 'data': {'photo_id': photo_id, 'username': username}})


class WSConnection(SockJSConnection):
    def on_open(self, request):
        print('on open')
        connections.add(self)

    def on_message(self, message):
        print('on message')
        print(message)
        data = json.loads(message)
        message_name = data.get('message_name')
        data = data.get('data')
        func = getattr(self, 'on_' + message_name)
        func(data)

    def on_close(self):
        print('on close')
        connections.discard(self)

    @db_session
    def on_get_last_photos(self, data):
        print('on_get_last_photos')
        current_user = data.get('current_user', None)
        page_owner = data.get('page_owner', None)
        query = select(p for p in Photo)
        if page_owner:
            query = query.filter(lambda p: p.user.username == page_owner)
        photos = query.order_by(desc(Photo.id))[:10]
        data = [p.to_json(current_user) for p in photos]
        self.send({'event': 'photo_list', 'data': data})

if __name__ == "__main__":
    ws_router = SockJSRouter(WSConnection, '/ws')
    app = web.Application(
        [
            (r"/", MainHandler),
            (r"/login", LoginHandler),
            (r"/signup", SignupHandler),
            (r"/logout", LogoutHandler),
            (r"/user/(\w+)", UserHomeHandler),
            (r"/upload", UploadHandler),
            (r"/photos/(.*)", web.StaticFileHandler, {'path': 'photos/'}),
            (r"/fonts/(.*)", web.StaticFileHandler, {'path': 'static/fonts'}),
            (r"/like", LikeHandler)
        ] + ws_router.urls,
        cookie_secret='Secret Cookie',
        login_url="/login",
        static_path=os.path.join(os.path.dirname(__file__), "static"),
        debug=True
    )
    app.listen(TORNADO_PORT)
    logger.info("application started, go to http://localhost:{port}".format(**{'port': TORNADO_PORT}))
    ioloop.IOLoop.instance().start()