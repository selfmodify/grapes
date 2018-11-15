#!/bin/python

"""
AWS boto3 client for EC2/ELB Auto Scaling
"""
import aws_client
import aws_client_elb 
import aws_client_ecs
import boto3
import logger
import elb
import time
import copy
from botocore.exceptions import ClientError
import options

class AutoScalingClient(aws_client.AwsClient):
    """
    Client for doing AutoScaling
    """

    def __init__(self, config):
        client = boto3.client('autoscaling', region_name=config.get_region())
        aws_client.AwsClient.__init__(self, config, client)
        self.as_group_name = self.config.get_as_name()
        self.launch_configuration_name = self.config.get_launch_config_name()

    def update_tag(self):
        # Update tags
        response2 = self.client.create_or_update_tags(
            Tags=[
                {
                    'ResourceId': self.as_group_name,
                    'ResourceType': 'auto-scaling-group',
                    'Key': 'Name',
                    'Value': self.config.get_ecs_cluster_name(),
                    'PropagateAtLaunch': True,
                }
            ]
        )
        self.log.info('Updated auto scale group with tag: %s', response2)

    def delete_auto_scaling_group(self):
        try:
            self.log.info('Deleting auto scaling group %s', self.as_group_name)
            self.client.delete_auto_scaling_group(
                AutoScalingGroupName=self.as_group_name,
                ForceDelete=True,
            )
            # Wait for auto scaling group to completely go away
            while True:
                response = self.client.describe_auto_scaling_groups(
                    AutoScalingGroupNames=[self.as_group_name]
                )
                self.log.debug(
                    'Response from describe_auto_scaling_groups %s', response)
                as_group = response['AutoScalingGroups']
                if len(as_group) > 0:
                    self.log.info('Status for AutoScalingGroup: %s "%s"',
                                  self.as_group_name, as_group[0]['Status'])
                else:
                    break
                time.sleep(10)
        except Exception as ex:
            self.log.warn(
                "Could not delete auto scaling group %s. Exception: %s", self.as_group_name, ex)

    def get_or_create_auto_scaling_group(self):
        elb_client = aws_client_elb.ElbClient(self.config)
        tg = elb_client.create_or_update_target_group()
        # Check for existing auto scaling group
        response = self.client.describe_auto_scaling_groups(
            AutoScalingGroupNames=[
                self.as_group_name,
            ],
        )
        if len(response['AutoScalingGroups']) > 0:
            # Update existing auto scaling group configuration
            response = self.update_capacity()
            self.update_tag()
            return response
        # Create a new auto-scaling group
        min_value, max_value, desired, availability_zones, vpc_zone_identifier, default_cooldown = self.config.get_auto_scale_params()
        response = self.client.create_auto_scaling_group(
            AutoScalingGroupName=self.as_group_name,
            LaunchConfigurationName=self.launch_configuration_name,
            MinSize=min_value,
            MaxSize=max_value,
            DesiredCapacity=desired,
            VPCZoneIdentifier=vpc_zone_identifier,
            AvailabilityZones=availability_zones,
            DefaultCooldown=default_cooldown,
            TargetGroupARNs=[
                tg['TargetGroupArn']
            ]
        )
        self.update_tag()
        return response

    def delete_launch_configuration(self):
        try:
            self.client.delete_launch_configuration(
                LaunchConfigurationName=self.launch_configuration_name
            )
        except Exception as ex:
            self.log.warn(
                'Could not delete launch configuration %s. Error: %s', self.launch_configuration_name, ex)

    def get_or_create_launch_configuration(self):
        response = self.client.describe_launch_configurations(
            LaunchConfigurationNames=[
                self.launch_configuration_name,
            ],
        )
        if len(response['LaunchConfigurations']) > 0:
            self.log.info(
                'Returning existing launch configuration: %s', response)
            return response
        # Create a new one
        response = self.client.create_launch_configuration(
            LaunchConfigurationName=self.launch_configuration_name,
            ImageId=self.config.get_ami(),
            KeyName=self.config.get_ssh_key(),
            SecurityGroups=self.config.get_security_groups(),
            IamInstanceProfile=self.config.get_ec2_iam_role(),
            InstanceType=self.config.get_instance_type(),
            AssociatePublicIpAddress=self.config.get_launch_ec2_with_public_ip(),
            UserData="#!/bin/bash \n echo ECS_CLUSTER=" +
            self.config.get_ecs_cluster_name() + " >> /etc/ecs/ecs.config"
        )
        self.log.info("Response: %s", response)
        return response

    def update_service_auto_scale_count(self, desired):
        # Update the service
        ecs_client = aws_client_ecs.EcsCluster(self.config)
        service_name = self.config.get_ecs_service_name()
        cluster_name = self.config.get_ecs_cluster_name()

        ecs_client.client.update_service(
            cluster=cluster_name,
            service=service_name,
            desiredCount=desired
        )

    def update_auto_scale_policy(self):
        """
        Update the auto scale policy to create new instances when CPU hits the target cpu_threshold
        """
        response = self.client.put_scaling_policy(
            AutoScalingGroupName=self.as_group_name,
            PolicyName=self.as_group_name,
            PolicyType='TargetTrackingScaling',
            AdjustmentType='PercentChangeInCapacity',
            TargetTrackingConfiguration={
                'PredefinedMetricSpecification': {
                    'PredefinedMetricType': 'ASGAverageCPUUtilization'},
                'TargetValue': self.config.get_auto_scale_cpu_threshold(),
            },
            Cooldown=200,
            EstimatedInstanceWarmup=10
        )
        self.log.info('Setting AutoScale policy for group:%s.',
                      self.as_group_name)
        self.log.debug("Response: %s", response)

    def assign_load_balancer(self, lb_arn):
        """
        Set the 'Target Group' LoadBalancer so that new instances spun up get added to the right load balancer
        """
        response = self.client.attach_load_balancer_target_groups(
            AutoScalingGroupName=self.as_group_name,
            TargetGroupARNs=[lb_arn]
        )
        self.log.info(
            'Associating AutoScalingGroup: %s to LoadBalancer ARN: %s', self.as_group_name, lb_arn)
        self.log.debug('Response: %s', response)

    def update_capacity_and_task_definition(self, min_value, max_value, desired, termination_policy):
        _, _, _, availability_zones, vpc_zone_identifier, _ = self.config.get_auto_scale_params()
        tdname = self.config.get_task_definition_name()
        self.log.info(
            'Updating auto scaling group and task definition. capacity min:%d max:%d desired:%d availability_zones:%s vpc_zone_identifier:%s taskdef:%s',
            min_value, max_value, desired, availability_zones, vpc_zone_identifier, tdname)
        ecs_client = aws_client_ecs.EcsCluster(self.config)
        service_name = self.config.get_ecs_service_name()
        cluster_name = self.config.get_ecs_cluster_name()
        ecs_client.client.update_service(
            taskDefinition=tdname,
            forceNewDeployment=True,
            desiredCount=desired,
            cluster=cluster_name,
            service=service_name,
            deploymentConfiguration={
                'maximumPercent': 200,
                'minimumHealthyPercent': 100,
            },
        )
        if termination_policy == "":
            termination_policy = "Default"
        response = self.client.update_auto_scaling_group(
            AutoScalingGroupName=self.as_group_name,
            LaunchConfigurationName=self.launch_configuration_name,
            MinSize=min_value,
            MaxSize=max_value,
            DesiredCapacity=desired,
            VPCZoneIdentifier=vpc_zone_identifier,
            AvailabilityZones=availability_zones,
            TerminationPolicies=[termination_policy],
        )
        self.log.debug("Response: %s", response)
        return response

    def update_capacity_to(self, min_value, max_value, desired, termination_policy):
        self.log.info('Updated desired capacity to %s', desired)
        self.update_service_auto_scale_count(desired)
        _, _, _, availability_zones, vpc_zone_identifier, cooldown = self.config.get_auto_scale_params()
        if termination_policy == "":
            termination_policy = "Default"
        self.log.info('Updating auto scaling group capacity min:%d max:%d desired:%d availability_zones:%s vpc_zone_identifier: %s termination_policy: %s',
                      min_value, max_value, desired, availability_zones, vpc_zone_identifier, termination_policy)
        response = self.client.update_auto_scaling_group(
            AutoScalingGroupName=self.as_group_name,
            LaunchConfigurationName=self.launch_configuration_name,
            MinSize=min_value,
            MaxSize=max_value,
            DesiredCapacity=desired,
            DefaultCooldown=cooldown,
            VPCZoneIdentifier=vpc_zone_identifier,
            AvailabilityZones=availability_zones,
            TerminationPolicies=[termination_policy],
        )
        self.log.debug("Response: %s", response)
        return response

    def set_capacity_to_zero(self):
        return self.update_capacity_to(min_value=0,
                                       max_value=0,
                                       desired=0,
                                       termination_policy="")

    def update_capacity(self):
        """
        Update Min/Max/Desired count for auto scaling group.
        """
        min_value, max_value, desired_value, _, _, _ = self.config.get_auto_scale_params()
        return self.update_capacity_to(min_value, max_value, desired_value, "")

