#!/usr/bin/python
"""
Creates the EC2 instances behind a LB

"""
import aws_client
import arg_parser


def setup_and_parse_args():
    parser = arg_parser.create_parser(desc="""
    Setup ELB in the specified environment/region. Environment implies both region and its use case

    Example usage:
    python ./elb_create.py --file=<config-file.yaml>        # (region us-east-1, developer environment)
    """)
    return arg_parser.parse_config_from_args(parser)


def __main__():
    config, _ = setup_and_parse_args()
    elb_client = aws_client.ElbClient(config)
    elb_client.create_lb_and_friends()


if __name__ == "__main__":
    __main__()
