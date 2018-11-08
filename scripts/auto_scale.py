#!/usr/bin/python
"""
Creates the auto scale group

"""

import aws_client_auto_scaling
import aws_client_app_auto_scaling
import string
import arg_parser


def setup_and_parse_args():
    parser = arg_parser.create_parser(desc="""
    Setup Auto scale group.

    Example usage:
    python ./auto_scale_create.py --file=<config-file.yaml>        # (region us-east-1, developer environment)
    """)
    return arg_parser.parse_config_from_args(parser)


def create_auto_scaling_and_launch_configuration(config):
    as_client = aws_client_auto_scaling.AutoScalingClient(config)
    as_client.get_or_create_launch_configuration()
    as_client.get_or_create_auto_scaling_group()
    as_client.update_auto_scale_policy()
    app_as_client = aws_client_app_auto_scaling.AppAutoScalingClient(config)
    app_as_client.create_ecs_autoscaling()


def delete_auto_scaling_and_launch_configuration(config):
    app_as_client = aws_client_app_auto_scaling.AppAutoScalingClient(config)
    app_as_client.destroy_ecs_autoscaling()
    as_client = aws_client_auto_scaling.AutoScalingClient(config)
    as_client.delete_auto_scaling_group()
    as_client.delete_launch_configuration()


def __main__():
    config, _ = setup_and_parse_args()
    create_auto_scaling_and_launch_configuration(config)


if __name__ == "__main__":
    __main__()
