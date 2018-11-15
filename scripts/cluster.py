#!/usr/bin/python
"""
Creates the ECS Cluster

"""

import argparse
import aws_client_ec2
import aws_client_ecs
import string
import ec2
import auto_scale
import sqs
import logger

logger = logger.getLogger()


def create_or_update_cluster(config):
    """
    Create the cluster.
    """
    config.log_component_names()
    # Create the SQS queue
    sqs.maybe_create_sqs(config)
    # Create the ECS Cluster, task definition and the service.
    ecs_cluster = aws_client_ecs.EcsCluster(config)
    ecs_cluster.create_cluster()
    ecs_cluster.create_taskd()
    ecs_cluster.create_service()
    # Create the auto scaling group
    auto_scale.create_auto_scaling_and_launch_configuration(config)

def upgrade_cluster(config):
    """
    Do a rolling upgrade of the instances in the cluster.
    """
    config.log_component_names()
    logger.info('Doing a rolling upgrade')
    ecs_cluster = aws_client_ecs.EcsCluster(config)
    # Create the new task definition before doing the upgrade
    ecs_cluster.create_taskd()
    # Use the new task definition in the service
    ecs_cluster.create_service()
    ecs_cluster.rolling_upgrade_service()
    logger.info('Finished doing rolling upgrade')


def destroy_cluster(config, destroy_sqs):
    """
    Delete the cluster and shutdown all instances
    """
    config.log_component_names()
    ecs_cluster = aws_client_ecs.EcsCluster(config)
    # Delete service, task definition and then the cluster
    ecs_cluster.stop_tasks()
    ecs_cluster.deregister_container_instance()
    ecs_cluster.delete_service()
    ecs_cluster.deregister_task_definition()
    ecs_cluster.delete_cluster()
    # Delete Auto scaling group and launch configuration
    auto_scale.delete_auto_scaling_and_launch_configuration(config)
    if destroy_sqs:
        sqs.delete_sqs(config)
    else:
        logger.info('Not deleting SQS use --delete_sqs to force this')
