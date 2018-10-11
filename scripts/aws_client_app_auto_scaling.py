#!/bin/python

"""
AWS boto3 client for Application Auto Scaling
https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/application-autoscaling.html
"""
import aws_client
import aws_client_elb 
import boto3
import logger
import elb
import time
import copy
from botocore.exceptions import ClientError
import options

class AppAutoScalingClient(aws_client.AwsClient):
    """
    Client for doing application AutoScaling
    """

    def __init__(self, config):
        client = boto3.client('application-autoscaling', region_name=config.get_region())
        aws_client.AwsClient.__init__(self, config, client)

    def _build_resource_id(self):
        return "service/"+self.config.get_ecs_cluster_name()+"/"+self.config.get_ecs_service_name()

    def _set_ecs_scaling_parameters(self, min, max):
        resourceID = self._build_resource_id()
        try:
            self.log.info('Registering %s as a scalable target for application autio scaling, min=%d, max=%d', resourceID, min, max)
            response = self.client.register_scalable_target(
                ServiceNamespace="ecs",
                ResourceId=resourceID,
                ScalableDimension="ecs:service:DesiredCount",
                MinCapacity=min,
                MaxCapacity=max
            )
            self.log.debug('Registered. Response:%s', response)
        except Exception as e:
            self.log.warn(
                'Error registering ECS service %s as a scalable target. Error: %s', resourceID, e)

    def _register_ecs_target(self):
        min, max, desired, availability_zones, vpc_zone_identifier, default_cooldown = self.config.get_auto_scale_params()
        self._set_ecs_scaling_parameters(min, max)

    def _deregister_ecs_target(self):
        resourceID = self._build_resource_id()
        try:
            self.log.info('De-registering %s as a scalable target for application autio scaling', resourceID)
            response = self.client.deregister_scalable_target(
                ServiceNamespace="ecs",
                ResourceId=resourceID,
                ScalableDimension="ecs:service:DesiredCount"
            )
            self.log.debug('Deregistered. Response:%s', response)
        except Exception as e:
            self.log.warn(
                'Error deregistering ECS service %s as a scalable target. Error: %s', resourceID, e)

    def _put_ecs_scaling_policy(self):
        resourceID = self._build_resource_id()
        try:
            self.log.info('Applying application auto scaling policy to ECS service %s', resourceID)
            response = self.client.put_scaling_policy(
                PolicyName=self.config.get_as_name(),
                PolicyType='TargetTrackingScaling',
                ResourceId=resourceID,
                ScalableDimension="ecs:service:DesiredCount",
                ServiceNamespace="ecs",
                TargetTrackingScalingPolicyConfiguration={
                    'PredefinedMetricSpecification': {
                        'PredefinedMetricType': 'ECSServiceAverageCPUUtilization'},
                    'TargetValue': self.config.get_auto_scale_cpu_threshold(),
                    'ScaleOutCooldown': 200
                }
            )
            self.log.info('Applied. Response:%s', response)
        except Exception as e:
            self.log.warn(
                'Error applying policy to ECS service %s. Error: %s', resourceID, e)

    def _delete_ecs_scaling_policy(self):
        resourceID = self._build_resource_id()
        try:
            self.log.info('Removing application auto scaling policy from %s', resourceID)
            response = self.client.delete_scaling_policy(
                PolicyName=self.config.get_as_name(),
                ServiceNamespace="ecs",
                ResourceId=resourceID,
                ScalableDimension="ecs:service:DesiredCount"
            )
            self.log.info('Removed. Response:%s', response)
        except Exception as e:
            self.log.warn(
                'Error removing policy from ECS service %s. Error: %s', resourceID, e)

    def create_ecs_autoscaling(self):
        self._register_ecs_target()
        self._put_ecs_scaling_policy()

    def update_ecs_autoscaling_parameters(self, min, max):
        self._set_ecs_scaling_parameters(min, max)
        self._put_ecs_scaling_policy()

    def destroy_ecs_autoscaling(self):
        self._delete_ecs_scaling_policy()
        self._deregister_ecs_target()

