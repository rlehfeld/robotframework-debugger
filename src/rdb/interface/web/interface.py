import logging
import sys
import re
import random
import socket
import os
import subprocess
import importlib
from time import time
from datetime import datetime
from urllib.parse import urlparse, unquote
from urllib.request import urlopen
from http.server import BaseHTTPRequestHandler, HTTPServer
from robot.serializing import Template, Namespace
from rdb.interface import BaseDebugInterface
from rdb.debugger.breakpoints import KeywordBreakPoint
from .views import BreakPointView, CallStackView
from . import templates
from . import standalone


class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self, ):  # noqa, N802
        self.logger = logger = logging.getLogger("rdb.web")
        try:
            output = self.process()

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Expires", self.date_time_string(time()))
            self.send_header("Last-Modified", self.date_time_string(time()))
            self.send_header("Content-Length", len(output))
            self.end_headers()

            self.wfile.write(output)
        except BaseException as e:
            logger.exception(e)
            return "Error:%s" % e

    def process(self):
        logger = self.logger
        self.rbt_debugger = self.server.robot_debugger

        # output = "xx:%s,\n%s" % (self.server.debug_interface, self.path)
        url = urlparse(self.path)
        command_name = command = url.path.split("/")[1]
        params = self.params = self.__parse_param(url.query)
        if self.check_session(params):
            logger.debug("command:%s,%s" % (command, str(params)))
            if command and hasattr(self.rbt_debugger, command):
                command = getattr(self.rbt_debugger, command)
            elif command and hasattr(self, command):
                command = getattr(self, command)
            if callable(command):
                status, msg = self.execute(command, params)
            else:
                status, msg = ('ERR', "Not found command '%s'" % command)
        else:
            status = 'ERR'
            msg = 'debug session error'

        output = self.response_views(command_name, status, msg)
        return output

    def refresh(self):
        return "status at %s" % datetime.now()

    def check_session(self, params):
        session = params.get("sid", "").strip()
        result = session and self.server.sid and session == self.server.sid
        self.server.sid = str(random.random())
        return result

    def log_message(self, format, *args):  # pylint: disable=W0622
        self.logger.debug(format % args)

    def response_views(self, command, status, msg):
        importlib.reload(templates)

        debugger_template = templates.DEBUGGER_TEMPLATE

        rdb = self.rbt_debugger

        break_points = [
            BreakPointView(e) for e in rdb.breakpoints
            if isinstance(e, KeywordBreakPoint)
        ]
        for e in break_points:
            if e.obj == rdb.active_breakpoint:
                e.css_class = 'active'

        call_stack = [
            CallStackView(e) for e in rdb.callstack
        ]
        if rdb.active_breakpoint:
            call_stack[-1].css_class = 'active'
        call_stack.reverse()

        # listener attrs
        if len(call_stack) > 0:
            listener_attrs = call_stack[0].attrs
        else:
            listener_attrs = {}
        keys = listener_attrs.keys()
        attr_order = ['doc', 'longname', 'starttime', 'endtime', 'elapsetime',
                      'tags', 'status', 'message', 'statistics']

        def index_attr(z):
            try:
                return attr_order.index(z)
            except ValueError:
                return 999

        def cmp(a, b):
            return (a > b) - (a < b)

        keys.sort(lambda x, y: cmp(index_attr(x), index_attr(y)))
        cur_attrs = []
        for e in keys:
            def a():
                return 0
            a.name = e
            a.value = listener_attrs[e]
            cur_attrs.append(a)
            del a

        variables = listener_attrs.get('args', [])
        cur_variables = []
        args_variables = [e for e in variables if e[0] in ['$', '@']]
        args_variables += rdb.watching_variable
        for name, value in rdb.variable_value(args_variables):
            def v():
                return 0
            v.name = name
            if value is None:
                v.value = "<STRIKE>Non-existing variable</STRIKE>"
            else:
                value = str(value)
                v.value = re.sub(
                    r"([^ <>]{50})",
                    lambda r: "<span>%s</span> " % r.group(0),
                    value
                )
            cur_variables.append(v)
            del v

        def robot_status():
            return 0

        if rdb.active_breakpoint is not None:
            if hasattr(rdb.active_breakpoint, 'kw_name'):
                robot_status.name = "Paused at keyword breakpoint '%s'" % \
                    rdb.active_breakpoint.kw_name
            else:
                robot_status.name = "Paused by step debug."
            robot_status.css_class = "paused"
        else:
            robot_status.name = "Running....."
            robot_status.css_class = "running"

        refresh_interval = "120" if rdb.active_breakpoint else "1"

        namespace = Namespace(
            call_stack=call_stack,
            break_points=break_points,
            active_bp=rdb.active_breakpoint,
            command=command,
            command_result=status,
            msg=msg,
            title="Robot framework web debugger",
            robot_status=robot_status,
            cur_attrs=cur_attrs,
            cur_variables=cur_variables,
            refresh_interval=refresh_interval,
            session=self.server.sid,
            kw=self.params.get("kw", '')
        )

        return Template(template=debugger_template).generate(namespace)

    def execute(self, command, params):
        if command.func_defaults:
            reqiured_args_count = (
                command.func_code.co_argcount - len(command.func_defaults)
            )
        else:
            reqiured_args_count = command.func_code.co_argcount

        var_names = command.func_code.co_varnames
        reqiured_args, options_args = (
            var_names[:reqiured_args_count],
            var_names[reqiured_args_count:]
        )

        try:
            args, kw_args = (
                self.__parse_args(params, reqiured_args, options_args)
            )
            result = command(*args, **kw_args)
        except BaseException as e:
            self.logger.exception(e)
            return ('ERR', str(e))

        return ('OK', result and str(result) or '')

    def __parse_param(self, param):
        p = {}
        for e in param.split("&"):
            if "=" not in e:
                continue
            k, v = e.split("=", 1)
            p[k] = unquote(v)
        return p

    def __parse_args(self, args, reqiured_args, options_args):
        param = []
        for name in reqiured_args:
            if 'self' == name:
                continue
            if not args.has_key(name):
                raise RuntimeError("Not found required parameter '%s'" % name)
            param.append(args[name])
        kw_param = {}
        for name in options_args:
            if args.has_key(name):
                kw_param[str(name)] = args[name]
        return (param, kw_param)


class TelnetMonitor:
    def __init__(self, size=16 * 1024):
        self.html_output = ''
        self.buffer_size = size

    def write(self, c):
        for e in str(c):
            if ord(e) > 128:
                continue
            self.html_output += {
                '\n': '<br/>',
                ' ': '&nbsp;',
                '>': '&gt;',
                '<': '&lt;',
            }.get(e, e)

        self.html_output = self.html_output[-self.buffer_size:]

    @property
    def buffer(self):
        return self.html_output


class WebDebugger(BaseDebugInterface):
    def start(self, cfg):
        self.cfg = cfg
        if cfg.WEB_PROXY == 'Y':
            server_address = (cfg.WEB_BIND, 0)
            self.proxy_address = ("127.0.0.1", cfg.WEB_PORT)
            self.start_rdb_proxy()
        else:
            server_address = (cfg.WEB_BIND, int(cfg.WEB_PORT))

        httpd = HTTPServer(server_address, WebHandler)
        httpd.robot_debugger = self
        httpd.sid = ""
        self.telnetMonitor = TelnetMonitor()
        self.add_telnet_monitor(self.telnetMonitor)

        self.local_address = (httpd.server_name, httpd.server_port)
        self.logger.info(
            "starting web interface, binding address=%s:%s..." % (
                self.local_address
            )
        )

        if cfg.WEB_PROXY == 'Y':
            self.register_rdb_proxy()

        if cfg.WEB_PORT == '0':
            sys.__stderr__.write("=" * 80 + "\n")
            sys.__stderr__.write(
                "Open 'http://%s:%s' in browser to monitor robot status.\n" % (
                    self.local_address
                )
            )
            sys.__stderr__.write("=" * 80 + "\n")

        httpd.serve_forever()

    def close(self):
        """the proxy can tell user the robot is stopped friendly.
        Otherwise the user will get a 404 error."""
        if self.cfg.WEB_PROXY == 'Y':
            self.unregister_rdb_proxy()

    def run_keyword(self, kw):
        return super().run_keyword(
            *kw.replace('+', ' ').split(',')
        )

    def __str__(self):
        return "Web interface %s:%s" % (self.cfg.WEB_BIND,
                                        self.cfg.WEB_PORT,)

    def start_rdb_proxy(self):
        self.proxy_alived = True
        if self.alived_proxy():
            return
        script = re.sub(".pyc$", ".py", standalone.__file__)
        work_root = os.getcwd()
        validate_script = "python %s %s" % (script, self.cfg.source_file)
        output = open("proxy_output.log", "a")
        subprocess.Popen(validate_script, shell=True,
                         stdout=output, stderr=output,
                         cwd=work_root)
        self.logger.info(
            "starting RDB proxy, binding address=%s:%s..." % (
                self.proxy_address
            )
        )
        for _ in range(3):
            if self.alived_proxy():
                self.logger.info("start RDB proxy ok!")
                return
        self.logger.error("failed to start RDB proxy!")
        self.proxy_alived = False

    def register_rdb_proxy(self,):
        proxy_url = "http://%s:%s/manage/start_rdb?host=%s&port=%s" % (
            self.proxy_address + self.local_address
        )
        if not self.proxy_alived:
            return
        try:
            with urlopen(proxy_url) as response:
                data = response.read()
                if data == 'OK':
                    self.logger.info("register proxy ok")
                    return
                self.logger.error("%s->%s" % (proxy_url, data))
        except BaseException as e:
            self.proxy_alived = False
            self.logger.exception(e)

    def unregister_rdb_proxy(self):
        proxy_url = "http://%s:%s/manage/done_rdb?host=%s&port=%s" % (
            self.proxy_address + self.local_address
        )
        if not self.proxy_alived:
            return
        try:
            with urlopen(proxy_url) as response:
                data = response.read()
                if data == 'OK':
                    self.logger.info("unregister proxy ok")
                    return
                self.logger.error("%s->%s" % (proxy_url, data))
        except BaseException as e:
            self.proxy_alived = False
            self.logger.exception(e)

    def alived_proxy(self):
        proxy_url = "http://%s:%s/alive" % self.proxy_address
        try:
            socket.setdefaulttimeout(3)
            with urlopen(proxy_url) as response:
                data = response.read()
                if data.strip() == 'OK':
                    return True
        except BaseException:
            pass
        return False


if "__main__" == __name__:
    def x():
        return 0

    x.WEB_PORT = 8000
    print("start server...")
    WebDebugger().start(x)
