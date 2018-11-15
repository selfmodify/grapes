#!/bin/python

"""
AWS boto3 client for ECS Services and Tasks
"""
import aws_client
import aws_client_elb
import aws_client_auto_scaling
import aws_client_app_auto_scaling
import boto3
import logger
import elb
import time
import copy
from botocore.exceptions import ClientError
import options

def get_first_matching_active_service(ecs_client, cluster_name, service_name):
    response = ecs_client.client.describe_services(
        cluster=cluster_name,
        services=[service_name],
    )
    services = response['services']
    if len(services) > 0 and services[0]['status'] == 'ACTIVE':
        return services[0]
    return None

class EcsCluster(aws_client.AwsClient):
    """
    ECS Cluster client.
    """

    def __init__(self, config):
        client = boto3.client('ecs', region_name=config.get_region())
        aws_client.AwsClient.__init__(self, config, client)

    def create_cluster(self):
        name = self.config.get_ecs_cluster_name()
        response = self.client.create_cluster(clusterName=name)
        self.log.debug("Created ECS Cluster: %s", response)
        # Create the Cluster wrapper from the response
        self.cluster = response['cluster']
        self.log.info("Created/Updated ECS ClusterName: %s Status: %s",
                      name, self.status())
        return self.cluster

    def _stop_tasks(self):
        """
        Stop the tasks and return immediately.
        """
        cluster_name = self.config.get_ecs_cluster_name()
        service_name = self.config.get_ecs_service_name()
        self.log.info(
            'Stopping all tasks in cluster %s for service %s', cluster_name, service_name)
        # List all tasks and stop the tasks
        nextToken = ''
        while nextToken is not None:
            # Loop through all the tasks and stop them.
            response = self.client.list_tasks(
                cluster=cluster_name,
                serviceName=service_name,
                nextToken=nextToken,
                desiredStatus='RUNNING')
            for i in response['taskArns']:
                self.log.info(
                    'Stopping task %s in cluster:%s service:%s', i, cluster_name, service_name)
                self.client.stop_task(
                    cluster=cluster_name,
                    task=i
                )
            if 'nextToken' in response:
                nextToken = response['nextToken']
            else:
                nextToken = None

    def stop_tasks(self):
        self._stop_tasks()

    def deregister_task_definition(self):
        tdname = self.config.get_task_definition_name()
        response = self.client.list_task_definitions(
            familyPrefix=tdname,
            status='ACTIVE',
            sort='DESC',
        )
        if len(response['taskDefinitionArns']) > 0:
            for t in response['taskDefinitionArns']:
                self.log.info('Deregistering task definition %s', t)
                # TODO: Don't crash if task def is not there.
                self.client.deregister_task_definition(taskDefinition=t)
        else:
            self.log.debug('No task definition found')

    def deregister_container_instance(self):
        name = self.config.get_ecs_cluster_name()
        self.log.info('Deregistering container instances from %s', name)
        # Remove container instances
        try:
            while True:
                response = self.client.list_container_instances(
                    cluster=name,
                )
                for inst in response['containerInstanceArns']:
                    self.client.deregister_container_instance(
                        cluster=name,
                        containerInstance=inst
                    )
                if not 'nextToken' in response:
                    break
        except Exception as e:
            self.log.warn(
                'Error deregistering container instances from cluster %s. Error: %s', name, e)

    def delete_cluster(self):
        name = self.config.get_ecs_cluster_name()
        # Remove container instances
        try:
            # Delete cluster
            response = self.client.delete_cluster(cluster=name)
            self.log.debug('Deleted cluster. Response:%s', response)
            self.log.info('Deleted cluster: %s', name)
        except Exception as e:
            self.log.warn('Error when deleting cluster %s. Error: %s', name, e)

    def status(self):
        return self.cluster['status']

    def get_instances_for_target_group(self, tg_arn):
        """
        Get all the instances associated with the target group.
        """
        response = self.client.describe_target_health(
            TargetGroupArn=tg_arn,  # targetGroup["TargetGroupArn"],
        )
        return response

    def _get_task_count(self):
        response = self.client.describe_services(
            cluster=self.config.get_ecs_cluster_name(),
            services=[
                self.config.get_ecs_service_name()
            ]
        )
        running = response['services'][0]['runningCount']
        desired = response['services'][0]['desiredCount']
        return running, desired

    def _terminate_instance(self, elb_client, tg_arn, ec2_client, waiter, ec2_instance_id):
        """
        Deregister the instance from the target group and then terminate the instance.
        """
        self.log.info(
            'Terminating old instance %s', ec2_instance_id)
        ec2_client.client.terminate_instances(
            InstanceIds=[ec2_instance_id]
        )

    def _get_running_targets(self, elb_client, tg_arn):
        """
        Get the running targets attached to this LB
        """
        response = elb_client.client.describe_target_health(
            TargetGroupArn=tg_arn,
        )
        instanceIds = []
        instanceIdMap = {}
        for i in response['TargetHealthDescriptions']:
            id = i['Target']['Id']
            instanceIds.append(id)
            instanceIdMap[id] = i
        return instanceIds, instanceIdMap

    def _get_inactive_task_definitions(self):
        response = self.client.list_task_definitions(
            familyPrefix=self.config.get_task_definition_name(),
            status='INACTIVE'
        )
        try:
        	return response['taskDefinitionArns']
        except:
        	return []

    def _get_inactive_running_tasks(self):
        task_arns = []
        inactive_task_definitions = self._get_inactive_task_definitions()
        self.log.info('Found %d inactive task definitions', len(inactive_task_definitions))
        self.log.info(inactive_task_definitions)
        if len(inactive_task_definitions) == 0:
            return task_arns
        task_response = self.client.list_tasks(
            cluster=self.config.get_ecs_cluster_name(),
            desiredStatus='RUNNING'
        )
        if task_response['taskArns'] is None:
            return task_arns
        response = self.client.describe_tasks(
            cluster=self.config.get_ecs_cluster_name(),
            tasks=task_response['taskArns']
        )
        if response['tasks'] is None:
            return task_arns
        for task in response['tasks']:
            if task['taskDefinitionArn'] in inactive_task_definitions:
                task_arns.append(task['taskArn'])
        return task_arns

    def rolling_upgrade_service(self):
        # Get instances attached to this target group which will be terminated
        # once rolling upgrade is done.
        elb = aws_client_elb.ElbClient(self.config)
        _, tg_arn = elb.get_lb_and_tg()
        instanceIds, _ = self._get_running_targets(elb, tg_arn)
        self.log.info(
            'Found %s instances in target group to be upgraded.', instanceIds)
        # Use AutoScaling group to increase the number of instances.
        # New instances will be launched with the updated task definition
        as_client = aws_client_auto_scaling.AutoScalingClient(self.config)
        app_as_client = aws_client_app_auto_scaling.AppAutoScalingClient(self.config)
        original_min, original_max, original_desired, _, _, _ = self.config.get_auto_scale_params()

        # Step 1. Delete all but the latest task definition
        self.delete_all_but_latest_taskd()

        # Step 2(optional). Ensure the number of tasks is set to the original capacity before starting the rolling upgrade.
        # This can happen if a rolling upgrade was aborted in between and min,max,desired was not set back to its original value
        if options.get_options().normalize_tasks():
            self.log.info(
                'Ensuring # of tasks are set to the original desired capacity')
            as_client.update_capacity_to(
                original_min, original_max, original_desired, "OldestInstance")
            running, desired = self._get_task_count()
            while True:
                if running == desired:
                    self.log.info(
                        'Running count:%d reached desired count:%d', running, desired)
                    break
                # Wait for running count of number of tasks to catch up to the desired count
                running, desired = self._get_task_count()
                self.log.info(
                    'Waiting for runningCount:%d to catch upto desiredCount:%d. TargetGroup:%s', running, desired, self.config.get_tg_name())
                time.sleep(30)
        else:
            self.log.info(
                'Not normalizing task count before doing rolling upgrade')

        # Step 3. Increase the capacity to 2x the original with the new task definition
        new_desired = max(original_desired * 2, 3)
        new_min = new_desired
        new_max = new_desired
        self.log.info('Starging rolling upgrade with newmin=%d newmax=%d newdesired=%d',
                      new_min, new_max, new_desired)
        app_as_client.update_ecs_autoscaling_parameters(new_min, new_max)
        as_client.update_capacity_and_task_definition(
            new_min, new_max, new_desired, "")
        running, desired = self._get_task_count()
        while True:
            if running >= desired:
                self.log.info(
                    'Running count:%d reached desired count:%d', running, desired)
                break
            # Wait for running count of number of tasks to catch up to the desired count
            running, desired = self._get_task_count()
            self.log.info(
                'Waiting for runningCount:%d to catch upto desiredCount:%d. TargetGroup:%s', running, desired, self.config.get_tg_name())
            time.sleep(30)
        # Step 4. Wait for the targets to be marked healthy by the LB before decreasing the number of tasks
        # Remove/Terminate any old instances.
        if not options.get_options().wait_for_healthy_targets():
            self.log.info(
                'Not waiting for targets to become healthy before scaling down')
        else:
            while True:
                healthy_targets = 0
                _, instanceIdMap = self._get_running_targets(elb, tg_arn)
                for k, v in instanceIdMap.items():
                    health = v['TargetHealth']['State']
                    if health == 'healthy':
                        healthy_targets += 1
                if healthy_targets >= new_desired:
                    self.log.info(
                        'healthyTargetCount:%d has reached desiredCount:%d.', healthy_targets, new_desired)
                    break
                self.log.info(
                    'Waiting for healthyTargetCount:%d to catch up to upscaled desiredCount:%d.', healthy_targets, new_desired)
                time.sleep(30)

        inactive_tasks = self._get_inactive_running_tasks()
        self.log.info('Found %d tasks listed as inactive and running', len(inactive_tasks))
        for task in inactive_tasks:
            self.log.info('Task \'%s\' is listed as inactive', task)

        as_client.update_capacity_to(
            original_min, original_max, original_desired, "OldestInstance")

        # Step 5: Wait for the targets to disappear from the LB before decreasing the number of tasks
        while True:
            _, instanceIdMap = self._get_running_targets(elb, tg_arn)
            num_targets = len(instanceIdMap)
            if num_targets == original_desired:
                self.log.info(
                    'targetCount:%d has reached desiredCount:%d.', num_targets, original_desired)
                break
            if num_targets < original_desired:
                self.log.warn(
                    'targetCount:%d IS BELOW desiredCount:%d.', num_targets, original_desired)
                break
            self.log.info(
                'Waiting for targetCount:%d to catch up to original desiredCount:%d.', num_targets, original_desired)
            time.sleep(30)

        # Step 6: Drop the number of tasks, restore termination policy to default
        app_as_client.update_ecs_autoscaling_parameters(original_min, original_max)
        as_client.update_capacity_to(original_min, original_max, original_desired, "")

    def create_taskd(self):
        """ ECS Create Task Definition """
        container_definition = copy.deepcopy(
            self.config.get_container_definition())
        tdname = self.config.get_task_definition_name()
        # Read the task definition from the config and update the name
        container_definition.update(
            {
                'name': self.config.create_name_with_separator(container_definition['name']),
                'image': self.config.create_name(container_definition['image']),
            }
        )
        response = self.client.register_task_definition(
            family=tdname,
            networkMode=self.config.get_task_def_network_mode(),
            # taskRoleArn='arn:aws:iam::144245539133:role/ecsInstanceRole',
            # executionRoleArn='arn:aws:iam::144245539133:role/ecsInstanceRole',
            containerDefinitions=[container_definition],
        )
        # log some information
        self.log.debug("Created TaskDefinition: %s",
                       self.config.pretty_print_json(response))
        self.task_def = response['taskDefinition']
        self.log.info("Created/Updated TaskDefinition: TaskDefinitionArn:%s",
                      self.task_def['taskDefinitionArn'])
        return self.task_def

    def delete_all_but_latest_taskd(self):
        """ ECS Create Task Definition """
        tdname = self.config.get_task_definition_name()
        response = self.client.list_task_definitions(
            familyPrefix=tdname,
            status='ACTIVE',
            sort='DESC',
        )
        if len(response['taskDefinitionArns']) > 0:
            task_definitions = response['taskDefinitionArns'][1:]
            for t in task_definitions:
                self.log.info('Deregistering task definition %s', t)
                # TODO: Don't crash if task def is not there.
                self.client.deregister_task_definition(taskDefinition=t)
        else:
            self.log.debug('No task definition found')

    def get_or_create_lb(self):
        lb_name = self.config.get_lb_name()
        self.log.info(
            'Load balancer name is: %s', lb_name)
        elb_client = aws_client_elb.ElbClient(self.config)
        elb_client.create_lb_and_friends()
        grape_lb_arn, _dns_name = elb_client.get_lb_details()
        grape_tg = elb_client.get_first_matching_target_group(
            grape_lb_arn)
        container_definition = self.task_def['containerDefinitions'][0]
        # Create LB to be passed to create_service
        lb_info = {
            'targetGroupArn': grape_tg['TargetGroupArn'],
            # 'loadBalancerName': 'grapes-upload',
            'containerName': container_definition['name'],
            'containerPort': container_definition['portMappings'][0]['containerPort'],
        }
        return lb_info

    def is_service_inactive(self):
        service_name = self.config.get_ecs_service_name()
        cluster_name = self.config.get_ecs_cluster_name()
        response = self.client.describe_services(
            cluster=cluster_name,
            services=[
                service_name,
            ]
        )
        for s in response['services']:
            if s['status'] == 'INACTIVE':
                return True
        return False

    def _delete_service(self, blocking):
        """
        Delete the service and related LB and Target group.
        """
        elb_client = aws_client_elb.ElbClient(self.config)
        elb_client.delete_lb_and_friends()
        service_name = self.config.get_ecs_service_name()
        cluster_name = self.config.get_ecs_cluster_name()
        self.log.info('Deleting service %s in cluster %s',
                      service_name, cluster_name)
        as_client = aws_client_auto_scaling.AutoScalingClient(self.config)
        try:
            as_client.update_capacity_to(
                0,  # min
                0,  # max
                0,  # desired
                "", # termination_policy
            )
            self.client.delete_service(
                cluster=cluster_name,
                service=service_name,
            )
            if blocking:
                while self.is_service_inactive() == False:
                    self.log.info(
                        'Waiting for service %s to become INACTIVE', service_name)
                    time.sleep(10)
        except Exception as ex:
            self.log.info('Error deleting service %s. Error: %s',
                          service_name, ex)

    def delete_service_nonblocking(self):
        """
        Delete the service and related LB and Target group.
        Does not wait for service to become inactive before deleting LB and Target Group.
        """
        self._delete_service(blocking=False)

    def delete_service(self):
        """
        Delete the service and related LB and Target group.
        Waits for service to becoming inactive before deleting LB and Target Group.
        """
        self._delete_service(blocking=True)

    def create_service(self):
        """ Create or Update an ECS Service for the given task"""
        service_name = self.config.get_ecs_service_name()
        cluster_name = self.config.get_ecs_cluster_name()
        lb_info = self.get_or_create_lb()

        # # Check to see if the service already exists
        service = get_first_matching_active_service(
            self, cluster_name, service_name)
        if service == None:
            # Create the service
            response = self.client.create_service(
                cluster=cluster_name,
                serviceName=service_name,
                desiredCount=self.config.get_auto_scale_desired_count(),
                taskDefinition=self.task_def['taskDefinitionArn'],
                role=self.config.get_ecs_role(),
                loadBalancers=[lb_info],
            )
            # log some information
            service = response['service']
            self.log.info("Created ECS Service: Name:%s ServiceArn:%s",
                          service['serviceName'], service['serviceArn'])
        else:
            # log some information
            response = self.client.update_service(
                cluster=cluster_name,
                service=service_name,
                taskDefinition=self.task_def['taskDefinitionArn'],
            )
            service = response['service']
            self.log.info("Updated ECS Service: Name:%s ServiceArn:%s",
                          service['serviceName'], service['serviceArn'])
        return service
