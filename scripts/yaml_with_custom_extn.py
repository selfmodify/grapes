# Custom YAML tag parser

import yaml
import logger

# Extend yaml with custom extension tags. e.g.
# <test.yaml>
#   environment:
#    - name: CMDLINEPARAM
#      value : !AwsCustomFunction get_jamz_cmdline_params()
#   Define a function called get_jamz_cmdline_argument() and pass it as a function map
#   to load_config_with_custom_extension function (defined below).


class AwsCustomFunction():
    yaml_loader = yaml.SafeLoader
    yaml_dumper = yaml.SafeDumper
    YAML_TAG = '!AwsCustomFunction'
    AWS_FN_MAP = {}
    YAML_CONFIG = None

    def __init__(self, line):
        self.line = line
        self.fn_name = None
        self.fn_params = []
        self.log = logger.getLogger()
        if type(line) == list and len(line) > 0:
            self.fn_name = line[0].value
            for i in line[1:]:
                self.fn_params.append(i.value)
        self.log.debug('Function: %s Params:%s',
                       self.fn_name, self.fn_params)

    def __repr__(self):
        if self.fn_name in AwsCustomFunction.AWS_FN_MAP:
            fn = AwsCustomFunction.AWS_FN_MAP[self.fn_name]
            self.value = fn(*self.fn_params)
            self.log.debug('Function:%s returned:%s', self.fn_name, self.value)
            return '%s(line=%r)' % (self.__class__.__name__, self.line)
        self.log.warning('No function mapping for Name:%s Map:%s ',
                         self.fn_name, AwsCustomFunction.AWS_FN_MAP)
        raise Exception('No function mapping found for ' + self.fn_name)

    @classmethod
    def register_mapping(cls, yaml_config, aws_fn_map):
        cls.YAML_CONFIG = yaml_config
        if aws_fn_map is not None:
            cls.AWS_FN_MAP = aws_fn_map


def from_yaml(loader, node):
    return AwsCustomFunction(node.value)


def to_yaml(dumper, data):
    _ = str(data)    # Force running the 'repr' to convert the object.
    # Convert custom tag to string representation
    v = dumper.represent_scalar('tag:yaml.org,2002:str', '%s' % data.value)
    return v


def load_config_with_custom_extension(filename, aws_fn_map):
    """
    Load YAML file with custom tag
    """
    with open(filename, 'r') as stream:
        # Register custom tag loader and dumper
        yaml.SafeLoader.add_constructor(AwsCustomFunction.YAML_TAG, from_yaml)
        yaml.SafeDumper.add_representer(AwsCustomFunction, to_yaml)
        # load the config and return it
        config = yaml.safe_load(stream)
        # Register custom function map with the YAML config
        AwsCustomFunction.register_mapping(config, aws_fn_map)
        return config
