class BaseRuntime:
    START = 'start'
    RUNNING = 'running'
    END = 'end'
    DONE = 'done'

    def __init__(self, object, type, attrs):  # pylint: disable=W0622
        self.object = object
        self.result = None
        self.state = self.START
        self.rt_type = type
        self.attrs = attrs

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError('Internal Attribute %s.' % name)
        return self.attrs.get(name, "")


class KeywordRuntime(BaseRuntime):
    def __init__(self, object, attrs):  # pylint: disable=W0622
        super().__init__(object, 'kw', attrs)
        self.name = object
        self.keyword = object

    def __str__(self):
        return "kw:%s" % self.name


class TestSuiteRuntime(BaseRuntime):
    def __init__(self, object, attrs):  # pylint: disable=W0622
        super().__init__(object, 'suite', attrs)
        self.name = object

    def __str__(self):
        return "suite:%s" % self.name


class TestCaseRuntime(BaseRuntime):
    def __init__(self, object, attrs):  # pylint: disable=W0622
        super().__init__(object, 'case', attrs)
        self.name = object

    def __str__(self):
        return "test:%s" % self.name
