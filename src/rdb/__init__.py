import logging
from .RobotDebugger import RobotDebugger
from .debugger.runtime import KeywordRuntime, TestCaseRuntime, TestSuiteRuntime


class Listener:
    ROBOT_LISTENER_API_VERSION = 2

    def __init__(self, *bps, cfg='debug.rdb'):
        self.debugger = RobotDebugger(cfg)
        self.debugger.run()
        self.call_stack = []
        self.debugCtx = self.debugger.debugCtx
        self.logger = logging.getLogger("rbt.lis")
        for e in bps:
            self.debugger.add_breakpoint(e)

    def start_suite(self, name, attrs):
        self.logger.debug("start_suite:%s, attr:%s" % (name, attrs))
        self.call_stack.append(TestSuiteRuntime(name, attrs))
        self.debugCtx.start_function(self.call_stack[-1])

    def end_suite(self, name, attrs):
        self.logger.debug("end_suite:%s, attr:%s" % (name, attrs))
        self.call_stack[-1].attrs = attrs
        self.debugCtx.end_function(self.call_stack[-1])
        self.call_stack.pop()

    def start_test(self, name, attrs):
        self.logger.debug("start_test:%s, attr:%s" % (name, attrs))
        self.call_stack.append(TestCaseRuntime(name, attrs))
        self.debugCtx.start_function(self.call_stack[-1])

    def end_test(self, name, attrs):
        self.logger.debug("end_test:%s, attr:%s" % (name, attrs))
        self.call_stack[-1].attrs = attrs
        self.debugCtx.end_function(self.call_stack[-1])
        self.call_stack.pop()

    def start_keyword(self, name, attrs):
        self.logger.debug("start_keyword:%s, attr:%s" % (name, attrs))
        if name.startswith("RDB."):
            return
        if "." in name:
            _, name = name.split(".", 1)
        self.call_stack.append(KeywordRuntime(name, attrs))
        self.debugCtx.start_function(self.call_stack[-1])

    def end_keyword(self, name, attrs):
        self.logger.debug("end_keyword:%s, attr:%s" % (name, attrs))
        if name.startswith("RDB."):
            return
        self.call_stack[-1].attrs = attrs
        self.debugCtx.end_function(self.call_stack[-1])
        self.call_stack.pop()

    def close(self):
        self.logger.debug("close..................")
        self.debugger.close()
