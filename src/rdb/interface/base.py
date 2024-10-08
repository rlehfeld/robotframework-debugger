import logging


class BaseDebugInterface:
    def __init__(self, debugger):
        self.robotDebugger = debugger
        self.debugCtx = debugger.debugCtx
        self.logger = logging.getLogger("rbt.int")
        self.bp_id = 0

    def start(self, settings):
        """start debug interface."""
        pass

    def close(self):
        pass

    def go_steps(self, count):
        self.debugCtx.go_steps(int(count))

    def go_into(self):
        self.debugCtx.go_into()

    def go_over(self):
        self.debugCtx.go_over()

    def go_on(self):
        self.debugCtx.go_on()

    def go_return(self):
        self.debugCtx.go_return()

    def go_pause(self):
        return self.debugCtx.go_pause()

    def add_breakpoint(self, bp):
        self.robotDebugger.add_breakpoint(bp)

    def watch_variable(self, name):
        return self.robotDebugger.watch_variable(name)

    def remove_variable(self, name):
        return self.robotDebugger.remove_variable(name)

    def run_keyword(self, name, *args):
        return self.robotDebugger.run_keyword(name, *args)

    def update_variable(self, name, value):
        from robot.running import NAMESPACES
        if NAMESPACES.current is not None:
            NAMESPACES.current.variables[name] = value

    def variable_value(self, var_list):
        from robot.running import NAMESPACES
        if NAMESPACES.current is None:
            return [(e, None) for e in var_list]

        robot_vars = NAMESPACES.current.variables
        val_list = []
        for e in var_list:
            try:
                v = robot_vars.replace_scalar(e)
            except Exception as et:
                if "Non-existing" in str(et):
                    v = None
                else:
                    raise
            val_list.append((e, v))
        return val_list

    @property
    def watching_variable(self):
        return self.robotDebugger.watching_variable

    @property
    def callstack(self):
        """Return a runtime list"""
        return list(self.debugCtx.call_stack)

    @property
    def breakpoints(self):
        """Return list of breakpoint"""
        return list(self.debugCtx.break_points)

    @property
    def active_breakpoint(self):
        return self.debugCtx.active_break_point

    def disable_breakpoint(self, name, match_kw=False):
        bp = self._get_breakpoint(name, match_kw)
        if bp:
            bp.active = False

    def enable_breakpoint(self, name, match_kw=False):
        bp = self._get_breakpoint(name, match_kw)
        if bp:
            bp.active = True

    def update_breakpoint(self, name, match_kw=False):
        bp = self._get_breakpoint(name, match_kw)
        if bp:
            bp.active = not bp.active

    def _get_breakpoint(self, name, match_kw):
        for e in self.debugCtx.break_points:
            if match_kw and hasattr(e, 'kw_name') and e.kw_name == name:
                return e
            if not match_kw and e.name == name:
                return e
        return None

    def add_telnet_monitor(self, monitor):
        """this is IPAMml special feature."""
        self.robotDebugger.add_telnet_monitor(monitor)

    def add_debug_listener(self, listener):
        self.debugCtx.add_listener(listener)

    def remove_debug_listener(self, listener):
        self.debugCtx.remove_listener(listener)


class Listener:
    def __init__(self):
        pass

    def pause(self, breakpoint):  # pylint: disable=W0622
        pass

    def go_on(self):
        pass

    def start_keyword(self, keyword):
        pass

    def end_keyword(self, keyword):
        pass
