#!/usr/bin/python
"""
Creates the EC2 instances to be used with the ECS Cluster

"""

import argparse
import aws_client
import string
import arg_parser
import auto_scale
import logger


def setup_and_parse_args():
    parser = arg_parser.create_parser(desc="""
    Setup EC2 in the specified region. Environment implies both region and its use case

    Example usage:
    python ./ec2_create.py --file=<config-file.yaml>        # (region us-east-1, developer environment)
    """)
    return arg_parser.parse_config_from_args(parser)


def __main__():
    config, _ = setup_and_parse_args()
    # auto_scale.create_auto_scaling_and_launch_configuration(config)
    ec2_client = aws_client.EC2Client(config)
    instances = ec2_client.get_running_instance_ids()
    logger.logger.info('%s', instances)
    elb_client = aws_client.ElbClient(config)
    elb_client.remove_instances(instances)
    ec2_client.terminate_instances(instances)
    # response = create_ec2_instances(
    #     ec2_client, 'ami-5253c32d', 'grapes-upload-cluster-dev-us-east-1')
    # ec2_client.log.info("Created EC2 instance: %s", response)
    # ec2_client.log.info("Created EC2 instance: %s", response)


if __name__ == "__main__":
    __main__()
