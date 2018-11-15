#!/bin/python

"""
AWS boto3 client for EC2 Instances
"""
import aws_client
import boto3
import logger
import elb
import time
import copy
from botocore.exceptions import ClientError
import options

class EC2Client(aws_client.AwsClient):
    """
    Functions to create and manipulate EC2 instances.
    """

    def __init__(self, config):
        client = boto3.client('ec2', region_name=config.get_region())
        aws_client.AwsClient.__init__(self, config, client)

    def create_ec2_instances(self, ami, ec2_name, cluster_name):
        self.log.info(
            'Creating an EC2 instance for cluster %s with ami %s', cluster_name, ami)
        response = self.client.run_instances(
            # Use the official ECS image
            AdditionalInfo=ec2_name,
            KeyName=self.config.get_ssh_key(),
            ImageId=ami,
            MinCount=1,
            MaxCount=1,
            InstanceType="t2.micro",
            IamInstanceProfile={
                #     # 'Arn' : 'arn:aws:iam::144245539133:role/ecsInstanceRole'
                #     'Arn': 'arn:aws:iam::144245539133:instance-profile/ecsInstanceRole',
                "Name": self.config.get_get_ec2_iam_role(),
            },
            SecurityGroupIds=self.config.get_security_groups(),
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': ec2_name,
                        }
                    ]
                }
            ],
            UserData="#!/bin/bash \n echo ECS_CLUSTER=" + \
            cluster_name + " >> /etc/ecs/ecs.config"
        )
        self.log.debug("Created EC2 instance: %s", response)
        instances = response['Instances']
        if len(instances) > 0:
            for i in instances:
                self.log.info("Created EC2 instance: %s", i['InstanceId'])
        return response

    def get_running_instance_ids(self):
        name = self.config.get_ec2_name()
        response = self.client.describe_instances(Filters=[
            {
                # Get only the running instances
                'Name': 'instance-state-name',
                'Values': ['running', ]
            },
            {
                # Get only the instances with the right name tag
                'Name': 'tag:Name',
                'Values': [name]
            }
        ])
        # Get the instance ids of all EC2 instances.
        ids = []
        for i in response['Reservations']:
            for j in i['Instances']:
                ids.append(j['InstanceId'])

        return ids

    def get_ip_dns_info(self, id):
        public_dns = ""
        public_ip = ""
        private_dns = ""
        private_ip = ""
        response = self.client.describe_instances(InstanceIds=[id])
        for i in response['Reservations']:
            for j in i['Instances']:
                private_dns = j['PrivateDnsName']
                private_ip = j['PrivateIpAddress']
                public_dns = j['PublicDnsName']
                public_dns = j['PublicIpAddress']
                break
            break
        return public_dns, public_ip, private_dns, private_ip

    def terminate_instances(self, instances):
        self.log.info('Terminating EC2 instances %s', instances)
        self.client.terminate_instances(
            InstanceIds=instances)
