
options = None


def create_options(args):
    global options
    options = Options(args)


def get_options():
    global options
    return options


class Options:
    def __init__(self, args):
        self._dry_run = getattr(args, 'dry_run', False)
        self._destroy = getattr(args, 'destroy', False)
        self._normalize_tasks = getattr(args, 'normalize_tasks', False)
        self._wait_for_healthy_targets = getattr(args, 'wait_for_healthy_targets', True)

    def dry_run(self):
        return self._dry_run

    def destroy(self):
        return self._destroy

    def normalize_tasks(self):
        return self._normalize_tasks

    def wait_for_healthy_targets(self):
        return self._wait_for_healthy_targets