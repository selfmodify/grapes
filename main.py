#!/usr/bin/python
"""
Put all parts of cluster together.

"""
import scripts
import aws_custom_functions
import tempfile

logger = scripts.logger.getLogger()


def setup_and_parse_args():
    parser = scripts.arg_parser.create_parser(desc="""
    Create, Update, Delete or do a rolling upgrade of ECS in the specified region. Environment implies both region and its use case

    Example usage:
    python ./main.py --file=<config-file.yaml> --create 
    python ./main.py --file=<config-file.yaml> --destroy
    python ./main.py --file=<config-file.yaml> --upgrade # Do a rolling upgrade
    """)
    parser.add_argument(
        '--upgrade',
        default=False,
        action="store_true",
        help='If true then do a rolling upgrade of instances.')
    parser.add_argument(
        '--create',
        default=False,
        action="store_true",
        help='Create/update cluster')
    parser.add_argument(
        '--destroy',
        default=False,
        action="store_true",
        help='If true then the cluster along with its service, taskdef etc are destroyed')
    parser.add_argument(
        '--destroy_sqs',
        default=False,
        action="store_true",
        help='If true then the SQS queue is also deleted when --destroy is used')
    parser.add_argument(
        '--dry_run',
        '-d',
        default=False,
        action="store_true",
        help='If true then simply tests the config loading and does nothing')
    parser.add_argument(
        '--wait_for_healthy_targets',
        default=True,
        action="store_true",
        help='If false then --upgrade won\'t wait for taargets to become healthy before downscaling')
    return parser


def load_env(args):
    scripts.options.create_options(args)
    # Create the custom function instance and pass it to build the config file
    aws_functions = aws_custom_functions.AwsCustomFunctions()
    env = scripts.arg_parser.parse_config_from(
        args.file, aws_functions.get_custom_functions_map())
    aws_functions.set_env(env)
    # Write out a temporary YAML to a file which is fully resolved
    with tempfile.NamedTemporaryFile(suffix='-out.yaml', delete=False) as out:
        logger.info('Writing fully resolved YAML file to %s', out.name)
        env.dump(out)
    env = scripts.arg_parser.parse_config_from(out.name, None)
    return env

def _input(display):
    input_func = None
    try:
        input_func = raw_input
    except NameError:
        input_func = input
    ret = input_func(display)
    return ret

def __main__():
    parser = setup_and_parse_args()
    # parse command line args and set options
    args = scripts.arg_parser.parse(parser)
    logger.info(
        '------------------------------------------------------------------------------------')
    logger.info('Running AWS Graaaaaaaaaaaaaaaaapes script with args: %s', args)
    config = load_env(args)
    verb = ""
    if args.destroy:
        verb = "Destroying "
    elif args.create:
        verb = "Creating   "
    elif args.upgrade:
        verb = "Upgrading  "
    elif args.dry_run:
        verb = "Testing    "
    else:
        logger.info('Nothing to do')
        return 1
    print('------------------------------------------------------------------------------------')
    print('AWS Deploy Script')
    print('{0} {1}, {2}'.format(verb, config.get_raw_service_name(), config.get_service_version()))
    print('Environment {0}{1}'.format(config.get_prefix_str(), config.get_region()))
    if args.dry_run:
        print('(Dry run only, no changes will be made)')
    print('------------------------------------------------------------------------------------')
    confirm = _input("Type 'yes' to continue...")
    if confirm != "yes":
        logger.warn('Aborting')
        return 0 
    checkprod = config.get_prefix_str()
    logger.debug(checkprod)
    if checkprod.startswith("prod"):
        confirm = _input("This is a PRODUCTION environment, type 'yes' to continue...")
        if confirm != "yes":
            logger.warn('Aborting')
            return 0 

    if args.destroy:
        scripts.cluster.destroy_cluster(config, args.destroy_sqs)
    elif args.create:
        scripts.cluster.create_or_update_cluster(config)
    elif args.upgrade:
        scripts.cluster.upgrade_cluster(config)
    elif args.dry_run:
        logger.info('Dry run only, dumping config:\n%s', config.dump())
    else:
        logger.info('Nothing to do')


if __name__ == "__main__":
    __main__()
