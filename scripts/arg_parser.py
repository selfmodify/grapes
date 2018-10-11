#!/usr/bin/python
"""
Creates the standard argument parser for use by the AWS CLI scripts

"""

import argparse
import sys
import service_env
import tempfile
import logger
import string
import os.path

logger = logger.getLogger()


def create_parser(desc):
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=desc)
    # Add the standard --env argument
    parser.add_argument('--file',
                        required=True, help='The cluster config file')
    return parser


def parse(parser):
    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()
    return args


def preprocess_yaml_file(filename):
    # Form a file suffix.
    outfile_suffix = '-{}'.format(os.path.split(filename)[1])
    with open(filename, 'r') as input_file:
        with tempfile.NamedTemporaryFile(mode='w', suffix=outfile_suffix, delete=False) as out_file:
            for line in input_file:
                if line.startswith('import_file:'):
                    # Bring in the imported file.
                    parts = line.split()
                    included_file = parts[1]
                    with open(included_file, 'r') as imported_file:
                        out_file.write('\n')
                        out_file.write('#################### Begin file {}'.format(included_file))
                        out_file.write('\n')
                        for imported_file_line in imported_file:
                            out_file.write(imported_file_line)
                        out_file.write('\n')
                        out_file.write('#################### End file {}'.format(included_file))
                        out_file.write('\n')
                else:
                    out_file.write(line)
            logger.info('Generated preprocessed file %s from %s',
                        out_file.name, filename)
            return out_file.name


def parse_config_from(filename, custom_fn_map=None):
    """
    Return the parsed cluster config file.
    """
    preprocessed_file = preprocess_yaml_file(filename)
    return service_env.load_env_with_extension(preprocessed_file, custom_fn_map)


def parse_config_from_args(parser, custom_fn_map=None):
    """
    Return the parsed cluster config file and the command line arguments. Also do some basic checks.
    """
    args = parse(parser)
    preprocessed_file = preprocess_yaml_file(args.file)
    env = service_env.load_env_with_extension(preprocessed_file, custom_fn_map)
    # Check basic things in the config file
    return env, args
